import unittest
from unittest.mock import patch, MagicMock, call, ANY
import pandas as pd
import datetime
import numpy as np # 用於 NaN 比較
# import sys # <--- 移除
# import os # <--- 移除

# --- 手動路徑校正 (移除) ---
# current_script_path = os.path.abspath(__file__)
# project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_script_path))))
# if project_root not in sys.path:
#     sys.path.insert(0, project_root)

# 導入重構後的模組
from apps.time_aggregator.aggregator import TimeAggregator
from core.schemas.silver_schemas import MarketOHLCV1M
from apps.time_aggregator import run as time_aggregator_run # 用於測試 run.py 的主流程

# 用於比較 DataFrame 的輔助函數
def assert_df_equals(df1, df2, check_dtype=True, rtol=1e-5, atol=1e-8):
    """
    比較兩個 Pandas DataFrame 是否相等，處理浮點數和 NaN。
    """
    pd.testing.assert_frame_equal(df1, df2, check_dtype=check_dtype, rtol=rtol, atol=atol)


class TestTimeAggregator(unittest.TestCase):
    """
    測試 TimeAggregator 類的核心邏輯。
    """

    def setUp(self):
        """
        每個測試方法執行前設置。
        """
        self.db_path = "dummy_test_aggregator.db" # 模擬路徑，實際不寫入
        self.aggregator = TimeAggregator(db_path=self.db_path)

        # 準備一個標準的 Tick DataFrame 輸入，用於多個測試
        self.sample_start_time = datetime.datetime(2023, 1, 1, 10, 0, 0)
        self.sample_ticks_data = [
            # Instrument A: 2 分鐘的數據
            {'timestamp': self.sample_start_time + datetime.timedelta(seconds=10), 'price': 100.0, 'volume': 10, 'instrument': 'INST_A'}, # O=100
            {'timestamp': self.sample_start_time + datetime.timedelta(seconds=20), 'price': 102.0, 'volume': 5,  'instrument': 'INST_A'}, # H=102
            {'timestamp': self.sample_start_time + datetime.timedelta(seconds=30), 'price': 99.0,  'volume': 8,  'instrument': 'INST_A'}, # L=99
            {'timestamp': self.sample_start_time + datetime.timedelta(seconds=50), 'price': 101.0, 'volume': 12, 'instrument': 'INST_A'}, # C=101, V=10+5+8+12=35 (Minute 1)

            {'timestamp': self.sample_start_time + datetime.timedelta(minutes=1, seconds=5), 'price': 101.5, 'volume': 7, 'instrument': 'INST_A'},  # O=101.5
            {'timestamp': self.sample_start_time + datetime.timedelta(minutes=1, seconds=25), 'price': 103.0, 'volume': 4, 'instrument': 'INST_A'},  # H=103
            {'timestamp': self.sample_start_time + datetime.timedelta(minutes=1, seconds=45), 'price': 101.0, 'volume': 9, 'instrument': 'INST_A'},  # L=101, C=101, V=7+4+9=20 (Minute 2)

            # Instrument B: 1 分鐘的數據 (跨越到第二分鐘，但只有一筆)
            {'timestamp': self.sample_start_time + datetime.timedelta(seconds=15), 'price': 2000.0, 'volume': 20, 'instrument': 'INST_B'}, # O=2000, H=2000
            {'timestamp': self.sample_start_time + datetime.timedelta(seconds=40), 'price': 1995.0, 'volume': 15, 'instrument': 'INST_B'}, # L=1995, C=1995, V=20+15=35 (Minute 1)
            {'timestamp': self.sample_start_time + datetime.timedelta(minutes=1, seconds=30), 'price': 1998.0, 'volume': 25, 'instrument': 'INST_B'}, # O,H,L,C=1998, V=25 (Minute 2)

            # Instrument C: 只有一筆交易，測試單點情況
            {'timestamp': self.sample_start_time + datetime.timedelta(seconds=35), 'price': 50.0, 'volume': 1, 'instrument': 'INST_C'}, # O,H,L,C=50, V=1 (Minute 1)
        ]
        self.sample_ticks_df = pd.DataFrame(self.sample_ticks_data)
        self.sample_ticks_df['timestamp'] = pd.to_datetime(self.sample_ticks_df['timestamp'])

    @patch('apps.time_aggregator.aggregator.DatabaseManager') # <--- Patch DatabaseManager
    def test_read_bronze_ticks(self, MockDatabaseManager):
        """
        測試 read_bronze_ticks 方法是否能正確查詢並返回 DataFrame。
        """
        # 配置 DatabaseManager 的 mock 實例
        mock_db_manager_instance = MockDatabaseManager.return_value
        mock_db_conn = mock_db_manager_instance._connect.return_value # _connect() 返回的連接 mock

        # 模擬 fetchdf() 返回的 DataFrame
        expected_df_data = [{'timestamp': self.sample_start_time, 'price': 100.0, 'volume': 10, 'instrument': 'INST_A'}]
        mock_returned_df = pd.DataFrame(expected_df_data)
        mock_returned_df['timestamp'] = pd.to_datetime(mock_returned_df['timestamp'])

        mock_db_conn.execute.return_value.fetchdf.return_value = mock_returned_df

        # 重新初始化 self.aggregator 以使用 MockDatabaseManager
        # 或者確保 setUp 中的 self.aggregator 在此 patch 生效時創建
        # 由於 patch 是在方法級別，setUp 中創建的 aggregator 不會使用 mock
        # 因此，我們應該在測試方法內部創建 aggregator 實例，或者 patch 在類級別
        # 為了簡單，我們假設 self.aggregator.db_manager 被正確 mock
        # 這需要 self.aggregator 在 patch 上下文內被創建，或其 db_manager 被手動替換

        # 讓我們在測試方法內部創建一個新的 TimeAggregator 實例，它將使用 MockDatabaseManager
        current_aggregator = TimeAggregator(db_path=self.db_path)

        start_query_time = self.sample_start_time - datetime.timedelta(hours=1)
        end_query_time = self.sample_start_time + datetime.timedelta(hours=1)

        result_df = current_aggregator.read_bronze_ticks(start_query_time, end_query_time, "bronze_test_table")

        MockDatabaseManager.assert_called_once_with(db_path=self.db_path) # 驗證 DatabaseManager 初始化
        current_aggregator.db_manager._connect.assert_called_once() # 驗證 _connect 被調用

        mock_db_conn.execute.assert_called_once()
        args, _ = mock_db_conn.execute.call_args
        self.assertIn("SELECT timestamp, price, volume, instrument", args[0])
        self.assertIn("FROM bronze_test_table", args[0])
        self.assertIn("WHERE timestamp >= ? AND timestamp < ?", args[0])
        self.assertEqual(args[1], [start_query_time, end_query_time])

        assert_df_equals(result_df, mock_returned_df)

    @patch('apps.time_aggregator.aggregator.DatabaseManager') # <--- Patch DatabaseManager
    def test_read_bronze_ticks_handles_db_error(self, MockDatabaseManager):
        """
        測試 read_bronze_ticks 在數據庫操作失敗時返回空 DataFrame。
        """
        mock_db_manager_instance = MockDatabaseManager.return_value
        mock_db_conn = mock_db_manager_instance._connect.return_value
        mock_db_conn.execute.return_value.fetchdf.side_effect = Exception("Simulated DB error")

        current_aggregator = TimeAggregator(db_path=self.db_path)

        start_query_time = self.sample_start_time
        end_query_time = self.sample_start_time + datetime.timedelta(minutes=1)

        result_df = self.aggregator.read_bronze_ticks(start_query_time, end_query_time)

        self.assertTrue(result_df.empty)
        self.assertEqual(list(result_df.columns), ['timestamp', 'price', 'volume', 'instrument'])

    def test_aggregate_to_1m_ohlcv_correctness(self):
        """
        核心測試：驗證 aggregate_to_1m_ohlcv 方法的計算邏輯是否正確。
        """
        result_ohlcv_df = self.aggregator.aggregate_to_1m_ohlcv(self.sample_ticks_df.copy()) # 使用副本

        # 預期結果 (基於 self.sample_ticks_df)
        # INST_A, Minute 1 (10:00:00)
        # O=100.0, H=102.0, L=99.0, C=101.0, V=35
        # INST_A, Minute 2 (10:01:00)
        # O=101.5, H=103.0, L=101.0, C=101.0, V=20
        # INST_B, Minute 1 (10:00:00)
        # O=2000.0, H=2000.0, L=1995.0, C=1995.0, V=35
        # INST_B, Minute 2 (10:01:00)
        # O=1998.0, H=1998.0, L=1998.0, C=1998.0, V=25
        # INST_C, Minute 1 (10:00:00)
        # O=50.0, H=50.0, L=50.0, C=50.0, V=1

        expected_data = [
            {'timestamp': pd.Timestamp(self.sample_start_time), 'instrument': 'INST_A', 'open': 100.0, 'high': 102.0, 'low': 99.0, 'close': 101.0, 'volume': 35},
            {'timestamp': pd.Timestamp(self.sample_start_time + datetime.timedelta(minutes=1)), 'instrument': 'INST_A', 'open': 101.5, 'high': 103.0, 'low': 101.0, 'close': 101.0, 'volume': 20},
            {'timestamp': pd.Timestamp(self.sample_start_time), 'instrument': 'INST_B', 'open': 2000.0, 'high': 2000.0, 'low': 1995.0, 'close': 1995.0, 'volume': 35},
            {'timestamp': pd.Timestamp(self.sample_start_time + datetime.timedelta(minutes=1)), 'instrument': 'INST_B', 'open': 1998.0, 'high': 1998.0, 'low': 1998.0, 'close': 1998.0, 'volume': 25},
            {'timestamp': pd.Timestamp(self.sample_start_time), 'instrument': 'INST_C', 'open': 50.0, 'high': 50.0, 'low': 50.0, 'close': 50.0, 'volume': 1},
        ]
        expected_ohlcv_df = pd.DataFrame(expected_data)
        expected_ohlcv_df['timestamp'] = pd.to_datetime(expected_ohlcv_df['timestamp'])

        # 排序以確保比較的一致性
        result_ohlcv_df = result_ohlcv_df.sort_values(by=['instrument', 'timestamp']).reset_index(drop=True)
        expected_ohlcv_df = expected_ohlcv_df.sort_values(by=['instrument', 'timestamp']).reset_index(drop=True)

        assert_df_equals(result_ohlcv_df, expected_ohlcv_df)

    def test_aggregate_to_1m_ohlcv_empty_input(self):
        """ 測試 aggregate_to_1m_ohlcv 使用空 DataFrame 輸入。 """
        empty_df = pd.DataFrame(columns=['timestamp', 'price', 'volume', 'instrument'])
        empty_df['timestamp'] = pd.to_datetime(empty_df['timestamp']) # 確保 timestamp 欄位存在且為 datetime

        result_df = self.aggregator.aggregate_to_1m_ohlcv(empty_df)
        self.assertTrue(result_df.empty)
        self.assertEqual(list(result_df.columns), ['timestamp', 'instrument', 'open', 'high', 'low', 'close', 'volume'])

    def test_aggregate_to_1m_ohlcv_missing_timestamp_column(self):
        """ 測試 aggregate_to_1m_ohlcv 輸入缺少 timestamp 欄位。 """
        df_no_ts = pd.DataFrame({'price': [1.0], 'volume': [10], 'instrument': ['X']})
        with self.assertRaisesRegex(ValueError, "timestamp.*datetime-like"):
            self.aggregator.aggregate_to_1m_ohlcv(df_no_ts)

    def test_aggregate_to_1m_ohlcv_timestamp_not_datetime(self):
        """ 測試 aggregate_to_1m_ohlcv 輸入的 timestamp 欄位不是 datetime 類型。 """
        df_wrong_ts_type = pd.DataFrame({'timestamp': ["2023-01-01"], 'price': [1.0], 'volume': [10], 'instrument': ['X']})
        with self.assertRaisesRegex(ValueError, "timestamp.*datetime-like"):
            self.aggregator.aggregate_to_1m_ohlcv(df_wrong_ts_type)

    def test_aggregate_to_1m_ohlcv_no_trades_in_minute(self):
        """
        測試如果某個 instrument 在某分鐘內完全沒有交易數據，聚合結果是否正確處理 (應被 dropna 清除)。
        """
        ticks_data = [
            {'timestamp': self.sample_start_time + datetime.timedelta(seconds=10), 'price': 100.0, 'volume': 10, 'instrument': 'INST_A'},
            # INST_A 在 10:01:00 沒有交易
            {'timestamp': self.sample_start_time + datetime.timedelta(minutes=2, seconds=10), 'price': 102.0, 'volume': 5, 'instrument': 'INST_A'},
        ]
        ticks_df = pd.DataFrame(ticks_data)
        ticks_df['timestamp'] = pd.to_datetime(ticks_df['timestamp'])

        result_df = self.aggregator.aggregate_to_1m_ohlcv(ticks_df)

        # 預期只有 10:00:00 和 10:02:00 的數據，10:01:00 的空行應被移除
        self.assertEqual(len(result_df), 2)
        self.assertNotIn(pd.Timestamp(self.sample_start_time + datetime.timedelta(minutes=1)), result_df['timestamp'].tolist())


    @patch('apps.time_aggregator.aggregator.DatabaseManager') # <--- Patch DatabaseManager
    def test_write_silver_ohlcv(self, MockDatabaseManager):
        """
        測試 write_silver_ohlcv 方法是否正確創建表並嘗試插入數據。
        """
        mock_db_manager_instance = MockDatabaseManager.return_value
        current_aggregator = TimeAggregator(db_path=self.db_path) # 使用 mock 的 DB Manager

        # 準備一個聚合後的 OHLCV DataFrame 樣本
        ohlcv_data = [{'timestamp': self.sample_start_time, 'instrument': 'INST_A', 'open': 100, 'high': 102, 'low': 99, 'close': 101, 'volume': 35}]
        ohlcv_df = pd.DataFrame(ohlcv_data)
        ohlcv_df['timestamp'] = pd.to_datetime(ohlcv_df['timestamp'])

        silver_table_name = "silver_ohlcv_test"
        current_aggregator.write_silver_ohlcv(ohlcv_df, silver_table_name=silver_table_name)

        # 驗證 db_manager.create_table_if_not_exists 被調用
        current_aggregator.db_manager.create_table_if_not_exists.assert_called_once_with(
            silver_table_name,
            MarketOHLCV1M
        )

        # 驗證 db_manager.insert_data 被調用
        # insert_data 期望一個 Pydantic 模型列表
        expected_records = [MarketOHLCV1M(**row) for row in ohlcv_df.to_dict(orient='records')]
        current_aggregator.db_manager.insert_data.assert_called_once_with(
            silver_table_name,
            expected_records
        )

    @patch('apps.time_aggregator.aggregator.DatabaseManager') # <--- Patch DatabaseManager
    def test_write_silver_ohlcv_empty_df(self, MockDatabaseManager):
        """ 測試 write_silver_ohlcv 使用空 DataFrame 輸入時不執行任何數據庫操作。 """
        mock_db_manager_instance = MockDatabaseManager.return_value
        current_aggregator = TimeAggregator(db_path=self.db_path)

        empty_ohlcv_df = pd.DataFrame(columns=['timestamp', 'instrument', 'open', 'high', 'low', 'close', 'volume'])

        current_aggregator.write_silver_ohlcv(empty_ohlcv_df, "silver_empty_test")

        # create_table_if_not_exists 和 insert_data 不應被調用，因為 df 為空會提前返回
        current_aggregator.db_manager.create_table_if_not_exists.assert_not_called()
        current_aggregator.db_manager.insert_data.assert_not_called()

# test_pydantic_to_duckdb_schema_conversion 測試案例已被移除


class TestTimeAggregatorRunScript(unittest.TestCase):
    """
    測試 apps.time_aggregator.run.py 主執行腳本的流程。
    """

    @patch('apps.time_aggregator.run.TimeAggregator')
    @patch('apps.time_aggregator.run.os.remove') # 模擬 os.remove
    @patch('apps.time_aggregator.run.os.path.exists') # 模擬 os.path.exists
    def test_run_main_flow(self, mock_path_exists, mock_os_remove, MockTimeAggregator):
        """
        測試 run.py 的 main() 函式是否按預期順序調用 TimeAggregator 的方法。
        """
        # 設置：讓 os.path.exists 返回 False，這樣 os.remove 不會被調用
        mock_path_exists.return_value = False

        # 模擬 TimeAggregator 實例及其方法
        mock_aggregator_instance = MockTimeAggregator.return_value.__enter__.return_value

        # 模擬 aggregate_to_1m_ohlcv 返回一個非空的 DataFrame，以觸發 write_silver_ohlcv
        mock_ohlcv_output_df = pd.DataFrame({'col1': [1]}) # 內容不重要，只需非空
        mock_aggregator_instance.aggregate_to_1m_ohlcv.return_value = mock_ohlcv_output_df

        # 執行 run.py 中的 main 函式
        time_aggregator_run.main()

        # 驗證 TimeAggregator 是否以預期路徑實例化
        MockTimeAggregator.assert_called_once_with(db_path="market_data.duckdb")

        # 驗證 aggregate_to_1m_ohlcv 是否被調用
        # 參數是 ANY，因為模擬的 DataFrame 在 run.py 中創建，這裡不便精確比較
        mock_aggregator_instance.aggregate_to_1m_ohlcv.assert_called_once_with(ANY)

        # 驗證 write_silver_ohlcv 是否被調用
        mock_aggregator_instance.write_silver_ohlcv.assert_called_once_with(
            mock_ohlcv_output_df, # 應傳入 aggregate_to_1m_ohlcv 的返回結果
            silver_table_name="silver_market_ohlcv_1m"
        )

    @patch('apps.time_aggregator.run.TimeAggregator')
    @patch('apps.time_aggregator.run.os.remove')
    @patch('apps.time_aggregator.run.os.path.exists')
    def test_run_main_flow_empty_aggregation_skips_write(self, mock_path_exists, mock_os_remove, MockTimeAggregator):
        """
        測試當聚合結果為空時，run.py 的 main() 是否跳過寫入步驟。
        """
        mock_path_exists.return_value = False
        mock_aggregator_instance = MockTimeAggregator.return_value.__enter__.return_value

        # 模擬 aggregate_to_1m_ohlcv 返回一個空的 DataFrame
        empty_df = pd.DataFrame()
        mock_aggregator_instance.aggregate_to_1m_ohlcv.return_value = empty_df

        time_aggregator_run.main()

        MockTimeAggregator.assert_called_once_with(db_path="market_data.duckdb")
        mock_aggregator_instance.aggregate_to_1m_ohlcv.assert_called_once_with(ANY)

        # 驗證 write_silver_ohlcv *沒有* 被調用
        mock_aggregator_instance.write_silver_ohlcv.assert_not_called()

    @patch('apps.time_aggregator.run.TimeAggregator') # 仍然需要模擬 TimeAggregator 本身
    @patch('apps.time_aggregator.run.os.remove')
    @patch('apps.time_aggregator.run.os.path.exists')
    def test_run_main_cleans_db_files_when_run_as_main(self, mock_path_exists, mock_os_remove, MockTimeAggregator):
        """
        測試當 run.py 作為主腳本運行時，是否會嘗試清理數據庫文件。
        這個測試有點棘手，因為 __name__ == "__main__" 的判斷。
        我們將模擬 os.path.exists 返回 True，並檢查 os.remove 是否被調用。
        """
        # 模擬文件存在
        mock_path_exists.side_effect = [True, True] # 第一次給 .duckdb, 第二次給 .wal

        # 模擬 TimeAggregator 的上下文管理器，避免其他調用
        mock_aggregator_instance = MockTimeAggregator.return_value.__enter__.return_value
        mock_aggregator_instance.aggregate_to_1m_ohlcv.return_value = pd.DataFrame({'a':[1]})


        # 為了觸發 __main__ 塊中的 os.remove，我們需要模擬 run.py 被直接執行
        # 這裡我們通過直接調用 time_aggregator_run.main()，並依賴其內部的
        # if __name__ == "__main__": 判斷。在測試環境中，導入時 __name__ 通常不是 "__main__"。
        # 為了正確測試，我們需要確保 main() 函數中的清理邏輯是在 __name__ == "__main__" 條件下。
        # run.py 已經這樣設計了。

        # 保存原始的 __name__
        original_name = time_aggregator_run.__name__
        try:
            # 篡改 __name__ 以模擬直接運行
            time_aggregator_run.__name__ = "__main__"
            time_aggregator_run.main()
        finally:
            # 恢復原始的 __name__
            time_aggregator_run.__name__ = original_name

        # 驗證 os.remove 被調用
        expected_remove_calls = [
            call("market_data.duckdb"),
            call("market_data.duckdb.wal")
        ]
        mock_os_remove.assert_has_calls(expected_remove_calls, any_order=True)
        self.assertEqual(mock_os_remove.call_count, 2)


if __name__ == '__main__':
    unittest.main()
