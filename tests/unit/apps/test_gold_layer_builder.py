import unittest
from unittest.mock import patch, MagicMock, call, ANY
import pandas as pd
import pandas_ta as ta # 用於對比計算結果
import datetime
import numpy as np
import sys # <--- 手動路徑校正
import os # <--- 手動路徑校正

# --- 手動路徑校正 ---
current_script_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_script_path))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from apps.gold_layer_builder.builder import GoldLayerBuilder
from core.schemas.gold_schemas import GoldMarketOHLCVDaily, GoldMarketFeaturesDaily
# 如果 GoldLayerBuilder.read_silver_ohlcv_1m 需要返回或處理銀層 schema 對象，則可能需要導入銀層 schema
# from core.schemas.silver_schemas import MarketOHLCV1M # 暫時註釋，根據需要取消
from apps.gold_layer_builder import run as gold_layer_run


# 用於比較 DataFrame 的輔助函數 (可考慮移至共享的測試工具模組)
def assert_df_equals(df1, df2, check_dtype=True, rtol=1e-5, atol=1e-8, sort_by_cols=None, reset_index=True):
    d1, d2 = df1.copy(), df2.copy()
    if sort_by_cols:
        d1 = d1.sort_values(by=sort_by_cols)
        d2 = d2.sort_values(by=sort_by_cols)
    if reset_index:
        d1 = d1.reset_index(drop=True)
        d2 = d2.reset_index(drop=True)
    pd.testing.assert_frame_equal(d1, d2, check_dtype=check_dtype, rtol=rtol, atol=atol)


class TestGoldLayerBuilder(unittest.TestCase):
    """
    測試 GoldLayerBuilder 類的核心邏輯。
    """
    def setUp(self):
        self.db_path = "dummy_test_gold_builder.db"
        self.builder = GoldLayerBuilder(db_path=self.db_path)

        # 準備銀層分鐘數據樣本 (用於多個測試)
        self.silver_start_time = datetime.datetime(2023, 1, 1, 9, 0, 0)
        self.silver_data = []
        self.num_days_for_features = 25 # 足夠計算 MA20 和 RSI14
        self.instruments = ["FXA_USD", "FXB_EUR"]

        for inst in self.instruments:
            for day_idx in range(self.num_days_for_features):
                day_base_time = self.silver_start_time + datetime.timedelta(days=day_idx)
                # 每天模擬幾條分鐘線 (簡化，每天只用一條代表日線聚合前的數據)
                # 實際測試日線聚合時，會用更細緻的分鐘數據
                # 這裡的數據主要用於測試特徵計算鏈條
                price_base = 100 + day_idx + (10 if inst == "FXB_EUR" else 0)
                self.silver_data.append({
                    'timestamp': day_base_time.replace(hour=10, minute=0), # 開盤
                    'instrument': inst, 'open': price_base - 0.5, 'high': price_base + 1,
                    'low': price_base - 1, 'close': price_base, 'volume': 1000 + day_idx * 10
                })
                self.silver_data.append({ # 收盤前
                    'timestamp': day_base_time.replace(hour=15, minute=45),
                    'instrument': inst, 'open': price_base, 'high': price_base + 0.8,
                    'low': price_base - 0.2, 'close': price_base + 0.3, 'volume': 800
                })
        self.sample_silver_df = pd.DataFrame(self.silver_data)
        self.sample_silver_df['timestamp'] = pd.to_datetime(self.sample_silver_df['timestamp'])

    @patch('apps.gold_layer_builder.builder.DatabaseManager') # <--- 已修改 Patch
    def test_read_silver_ohlcv_1m(self, MockDatabaseManager):
        mock_db_manager_instance = MockDatabaseManager.return_value
        mock_db_conn = mock_db_manager_instance._connect.return_value

        current_builder = GoldLayerBuilder(db_path=self.db_path) # 使用 mock 的 DB Manager

        expected_df_data = [{'timestamp': self.silver_start_time, 'instrument': 'FXA_USD', 'open': 100, 'high': 101, 'low': 99, 'close': 100.5, 'volume': 1000}]
        mock_returned_df = pd.DataFrame(expected_df_data)
        mock_returned_df['timestamp'] = pd.to_datetime(mock_returned_df['timestamp'])
        mock_db_conn.execute.return_value.fetchdf.return_value = mock_returned_df

        result_df = current_builder.read_silver_ohlcv_1m("silver_test_table")

        MockDatabaseManager.assert_called_once_with(db_path=self.db_path)
        current_builder.db_manager._connect.assert_called_once()
        mock_db_conn.execute.assert_called_once()
        args, _ = mock_db_conn.execute.call_args
        self.assertIn("SELECT timestamp, instrument, open, high, low, close, volume", args[0])
        self.assertIn("FROM silver_test_table", args[0])
        assert_df_equals(result_df, mock_returned_df)

    def test_aggregate_to_daily_ohlcv(self):
        # 創建更細緻的分鐘數據來測試日線聚合
        daily_agg_test_data = []
        test_date = datetime.date(2023, 1, 10)
        test_dt_base = datetime.datetime.combine(test_date, datetime.time(9,0,0))

        # Instrument 1
        daily_agg_test_data.extend([
            {'timestamp': test_dt_base, 'instrument': 'TEST01', 'open': 10.0, 'high': 10.2, 'low': 9.8, 'close': 10.1, 'volume': 100}, # First
            {'timestamp': test_dt_base + datetime.timedelta(minutes=30), 'instrument': 'TEST01', 'open': 10.1, 'high': 10.5, 'low': 10.0, 'close': 10.3, 'volume': 150}, # Max high
            {'timestamp': test_dt_base + datetime.timedelta(hours=1), 'instrument': 'TEST01', 'open': 10.3, 'high': 10.4, 'low': 9.5, 'close': 9.6, 'volume': 120},    # Min low
            {'timestamp': test_dt_base + datetime.timedelta(hours=2), 'instrument': 'TEST01', 'open': 9.6, 'high': 9.9, 'low': 9.5, 'close': 9.8, 'volume': 130},      # Last
        ])
        # Instrument 2 (single entry for the day)
        daily_agg_test_data.append({'timestamp': test_dt_base + datetime.timedelta(hours=1), 'instrument': 'TEST02', 'open': 50.0, 'high': 50.0, 'low': 50.0, 'close': 50.0, 'volume': 50})

        minutely_df = pd.DataFrame(daily_agg_test_data)
        minutely_df['timestamp'] = pd.to_datetime(minutely_df['timestamp'])

        result_daily_df = self.builder.aggregate_to_daily_ohlcv(minutely_df)

        expected_daily_data = [
            {'date': test_date, 'instrument': 'TEST01', 'open': 10.0, 'high': 10.5, 'low': 9.5, 'close': 9.8, 'volume': 100+150+120+130},
            {'date': test_date, 'instrument': 'TEST02', 'open': 50.0, 'high': 50.0, 'low': 50.0, 'close': 50.0, 'volume': 50},
        ]
        expected_daily_df = pd.DataFrame(expected_daily_data)
        expected_daily_df['date'] = pd.to_datetime(expected_daily_df['date']).dt.date

        assert_df_equals(result_daily_df, expected_daily_df, sort_by_cols=['instrument'])

    def test_calculate_features_correctness(self):
        # 使用 setUp 中準備的 self.sample_silver_df，先聚合成日線
        daily_ohlcv_df = self.builder.aggregate_to_daily_ohlcv(self.sample_silver_df.copy())

        # 確保有足夠數據 (self.num_days_for_features = 25)
        self.assertTrue(len(daily_ohlcv_df[daily_ohlcv_df['instrument'] == 'FXA_USD']) >= 20)

        result_features_df = self.builder.calculate_features(daily_ohlcv_df.copy())

        # 驗證 FXA_USD 的特徵 (可以選最後一條記錄或特定記錄)
        for inst in self.instruments:
            inst_daily_df = daily_ohlcv_df[daily_ohlcv_df['instrument'] == inst].copy()
            inst_features_df = result_features_df[result_features_df['instrument'] == inst].copy()

            # 使用 pandas-ta 直接計算以供比較
            expected_ma5 = ta.sma(inst_daily_df['close'], length=5)
            expected_ma20 = ta.sma(inst_daily_df['close'], length=20)
            expected_rsi14 = ta.rsi(inst_daily_df['close'], length=14)

            # 比較 ma5 (跳過開頭的 NaN)
            pd.testing.assert_series_equal(
                inst_features_df['ma5'].dropna().reset_index(drop=True), # 小寫 'ma5'
                expected_ma5.dropna().reset_index(drop=True),
                check_dtype=False, rtol=1e-5, check_names=False
            )
            # 比較 ma20
            pd.testing.assert_series_equal(
                inst_features_df['ma20'].dropna().reset_index(drop=True), # 小寫 'ma20'
                expected_ma20.dropna().reset_index(drop=True),
                check_dtype=False, rtol=1e-5, check_names=False
            )
            # 比較 rsi14
            pd.testing.assert_series_equal(
                inst_features_df['rsi14'].dropna().reset_index(drop=True), # 小寫 'rsi14'
                expected_rsi14.dropna().reset_index(drop=True),
                check_dtype=False, rtol=1e-5, check_names=False # RSI 比較敏感，可能需要調整 rtol
            )

            # 確保合併後的 DataFrame 包含原始 OHLCV 數據
            self.assertIn('open', inst_features_df.columns)
            self.assertIn('volume', inst_features_df.columns)
            self.assertEqual(len(inst_features_df), len(inst_daily_df))


    @patch('apps.gold_layer_builder.builder.DatabaseManager') # <--- 已修改 Patch
    def test_write_gold_tables(self, MockDatabaseManager):
        mock_db_manager_instance = MockDatabaseManager.return_value
        current_builder = GoldLayerBuilder(db_path=self.db_path) # 使用 mock 的 DB Manager

        # 準備一個包含 OHLCV 和特徵的 DataFrame 樣本
        final_df_data = [{
            'date': datetime.date(2023,1,20), 'instrument': 'FXA_USD',
            'open': 119, 'high': 120, 'low': 118, 'close': 119.5, 'volume': 1500,
            'ma5': 118.0, 'ma20': 110.0, 'rsi14': 65.0  # 使用小寫鍵名
        }]
        final_df = pd.DataFrame(final_df_data)
        final_df['date'] = pd.to_datetime(final_df['date']).dt.date # 確保是 date object

        current_builder.write_gold_tables(final_df, "gold_ohlcv_test", "gold_features_test")

        # 驗證 create_table_if_not_exists 的調用
        expected_create_calls = [
            call("gold_ohlcv_test", GoldMarketOHLCVDaily),
            call("gold_features_test", GoldMarketFeaturesDaily)
        ]
        current_builder.db_manager.create_table_if_not_exists.assert_has_calls(expected_create_calls, any_order=True)

        # 驗證 insert_data 的調用
        # 準備預期的 Pydantic 模型列表
        ohlcv_cols = [field for field in GoldMarketOHLCVDaily.model_fields.keys() if field in final_df.columns]
        ohlcv_gold_df = final_df[ohlcv_cols].replace({np.nan: None})
        if 'date' in ohlcv_gold_df.columns:
             ohlcv_gold_df['date'] = ohlcv_gold_df['date'].apply(lambda x: None if pd.isna(x) else x)
        expected_ohlcv_records = [GoldMarketOHLCVDaily(**row) for row in ohlcv_gold_df.to_dict(orient='records')]

        feature_cols = [field for field in GoldMarketFeaturesDaily.model_fields.keys() if field in final_df.columns]
        features_gold_df = final_df[feature_cols].replace({np.nan: None})
        if 'date' in features_gold_df.columns:
            features_gold_df['date'] = features_gold_df['date'].apply(lambda x: None if pd.isna(x) else x)
        expected_feature_records = [GoldMarketFeaturesDaily(**row) for row in features_gold_df.to_dict(orient='records')]

        expected_insert_calls = [
            call("gold_ohlcv_test", expected_ohlcv_records),
            call("gold_features_test", expected_feature_records)
        ]
        current_builder.db_manager.insert_data.assert_has_calls(expected_insert_calls, any_order=True)


class TestGoldLayerRunScript(unittest.TestCase):
    """
    測試 apps.gold_layer_builder.run.py 主執行腳本的流程。
    """
    @patch('apps.gold_layer_builder.run.GoldLayerBuilder')
    @patch('apps.gold_layer_builder.run.os.remove')
    @patch('apps.gold_layer_builder.run.os.path.exists')
    def test_run_main_flow_full_execution(self, mock_path_exists, mock_os_remove, MockGoldLayerBuilder):
        mock_path_exists.return_value = False # 避免清理邏輯
        mock_builder_instance = MockGoldLayerBuilder.return_value.__enter__.return_value

        # 模擬 builder 方法的返回值
        mock_daily_ohlcv_df = pd.DataFrame({'date': [datetime.date(2023,1,1)], 'instrument': ['TEST'], 'close': [100]})
        mock_features_df = mock_daily_ohlcv_df.copy()
        mock_features_df['MA5'] = 99.0

        mock_builder_instance.aggregate_to_daily_ohlcv.return_value = mock_daily_ohlcv_df
        mock_builder_instance.calculate_features.return_value = mock_features_df

        gold_layer_run.main()

        MockGoldLayerBuilder.assert_called_once_with(db_path="market_data.duckdb")
        mock_builder_instance.aggregate_to_daily_ohlcv.assert_called_once_with(ANY) # 輸入是模擬生成的DF

        # 驗證 calculate_features 的調用和參數
        mock_builder_instance.calculate_features.assert_called_once()
        call_args_calc_features, _ = mock_builder_instance.calculate_features.call_args
        # 比較傳遞給 calculate_features 的 DataFrame 是否與 mock_daily_ohlcv_df 相等
        # 注意：這裡的 mock_daily_ohlcv_df 是 aggregate_to_daily_ohlcv 的模擬返回值
        # 而 call_args_calc_features[0] 是實際傳入 calculate_features 的參數
        # 它們應該是同一個對象或內容相同
        assert_df_equals(call_args_calc_features[0], mock_daily_ohlcv_df, sort_by_cols=['instrument', 'date'])


        mock_builder_instance.write_gold_tables.assert_called_once_with(
            mock_features_df, # 這裡 mock_features_df 是 calculate_features 的模擬返回值
            ohlcv_table_name="gold_market_ohlcv_daily",
            features_table_name="gold_market_features_daily"
        )

    @patch('apps.gold_layer_builder.run.GoldLayerBuilder')
    @patch('apps.gold_layer_builder.run.os.remove')
    @patch('apps.gold_layer_builder.run.os.path.exists')
    def test_run_main_skips_if_daily_aggregation_empty(self, mock_path_exists, mock_os_remove, MockGoldLayerBuilder):
        mock_path_exists.return_value = False
        mock_builder_instance = MockGoldLayerBuilder.return_value.__enter__.return_value

        mock_builder_instance.aggregate_to_daily_ohlcv.return_value = pd.DataFrame() # 空聚合結果

        gold_layer_run.main()

        mock_builder_instance.aggregate_to_daily_ohlcv.assert_called_once()
        mock_builder_instance.calculate_features.assert_not_called()
        mock_builder_instance.write_gold_tables.assert_not_called()

if __name__ == '__main__':
    unittest.main()
