import duckdb
import pandas as pd
import pandas_ta as ta # 用於計算技術指標
import datetime
import numpy as np # <--- 新增導入
from typing import Optional, Type, List, Dict
from pydantic import BaseModel

# 從新的核心 schemas 導入
from core.schemas.gold_schemas import GoldMarketOHLCVDaily, GoldMarketFeaturesDaily
# GoldLayerBuilder 需要讀取銀層數據，因此也需要銀層的 schema
from core.schemas.silver_schemas import MarketOHLCV1M # 用於 read_silver_ohlcv_1m 的返回類型或內部處理
from core.db_manager import DatabaseManager # <--- 導入 DatabaseManager

# PYDANTIC_TO_DUCKDB_TYPE_MAP 已被移除

class GoldLayerBuilder:
    """
    負責讀取銀層分鐘數據，聚合成日線，計算特徵，並存儲至金層。
    """
    def __init__(self, db_path: str = "market_data.duckdb"):
        self.db_manager = DatabaseManager(db_path=db_path)
        # print(f"[GoldBuilder] 初始化，使用 DatabaseManager，數據庫路徑: {db_path}")

    def __enter__(self):
        self.db_manager.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db_manager.__exit__(exc_type, exc_val, exc_tb)

    def _get_db_connection(self) -> duckdb.DuckDBPyConnection:
        """ 輔助方法：獲取 DatabaseManager 維護的連接。 """
        return self.db_manager._connect()

    # _pydantic_to_duckdb_schema 和 _create_table_if_not_exists 已被移除
    # 將使用 self.db_manager.create_table_if_not_exists

    def read_silver_ohlcv_1m(self, silver_table_name: str = "silver_market_ohlcv_1m",
                               instrument: Optional[str] = None,
                               start_date: Optional[datetime.date] = None,
                               end_date: Optional[datetime.date] = None) -> pd.DataFrame:
        """
        讀取 silver_market_ohlcv_1m 表的數據。
        可以按 instrument 和日期範圍進行過濾。
        """
        conn = self._get_db_connection() # <--- 使用新的連接獲取方式
        # print(f"[GoldBuilder] 準備從 '{silver_table_name}' 讀取數據...")

        conditions = []
        params = []

        if instrument:
            conditions.append("instrument = ?")
            params.append(instrument)
        if start_date:
            # DuckDB 的 timestamp 和 date 比較需要小心
            # 如果 silver_table_name 中的 timestamp 是 datetime.datetime
            # 而 start_date 是 datetime.date，需要轉換
            conditions.append("CAST(timestamp AS DATE) >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("CAST(timestamp AS DATE) <= ?")
            params.append(end_date)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
        SELECT timestamp, instrument, open, high, low, close, volume
        FROM {silver_table_name}
        {where_clause}
        ORDER BY instrument, timestamp ASC
        """

        try:
            df_silver = conn.execute(query, params).fetchdf()
            # print(f"[GoldBuilder] 成功讀取 {len(df_silver)} 筆數據從 '{silver_table_name}'。")
            if 'timestamp' in df_silver.columns:
                 df_silver['timestamp'] = pd.to_datetime(df_silver['timestamp'])
            return df_silver
        except Exception as e:
            # print(f"[GoldBuilder] 從 '{silver_table_name}' 讀取數據失敗: {e}")
            return pd.DataFrame(columns=['timestamp', 'instrument', 'open', 'high', 'low', 'close', 'volume'])

    def aggregate_to_daily_ohlcv(self, minutely_df: pd.DataFrame) -> pd.DataFrame:
        """
        將分鐘級 OHLCV DataFrame 聚合為日線級別。
        """
        if minutely_df.empty:
            # print("[GoldBuilder] 輸入的分鐘級 DataFrame 為空，無法聚合日線。")
            return pd.DataFrame()

        if 'timestamp' not in minutely_df.columns or not pd.api.types.is_datetime64_any_dtype(minutely_df['timestamp']):
            raise ValueError("輸入的 DataFrame 必須包含 'timestamp' 欄位且其類型應為 datetime-like。")

        # print(f"[GoldBuilder] 準備將 {len(minutely_df)} 筆分鐘數據聚合為日線...")

        daily_ohlcv_list = []
        for instrument, group_df in minutely_df.groupby('instrument'):
            if group_df.empty:
                continue

            # 確保 timestamp 是索引
            if not isinstance(group_df.index, pd.DatetimeIndex):
                group_df = group_df.set_index('timestamp')

            # 'D' 表示日曆日 (Calendar day frequency)
            daily_resampled = group_df.resample('D').agg(
                open=('open', 'first'),
                high=('high', 'max'),
                low=('low', 'min'),
                close=('close', 'last'),
                volume=('volume', 'sum')
            )
            daily_resampled['instrument'] = instrument
            daily_ohlcv_list.append(daily_resampled)

        if not daily_ohlcv_list:
            # print("[GoldBuilder] 沒有數據可聚合成日線。")
            return pd.DataFrame()

        final_daily_df = pd.concat(daily_ohlcv_list).reset_index()
        # 將 'timestamp' (現在是日期的開始) 列名改為 'date' 並轉換為 date 對象
        final_daily_df.rename(columns={'timestamp': 'date'}, inplace=True)
        final_daily_df['date'] = final_daily_df['date'].dt.date

        # 移除所有價格欄位都為 NaN 的行 (通常是沒有交易的日期)
        final_daily_df = final_daily_df.dropna(subset=['open', 'high', 'low', 'close'], how='all')

        # 確保欄位順序
        final_daily_df = final_daily_df[['date', 'instrument', 'open', 'high', 'low', 'close', 'volume']]

        # print(f"[GoldBuilder] 成功聚合得到 {len(final_daily_df)} 筆日線 OHLCV 數據。")
        return final_daily_df

    def calculate_features(self, daily_ohlcv_df: pd.DataFrame) -> pd.DataFrame:
        """
        接收日線級 OHLCV DataFrame，計算技術指標，並將結果作為新欄位添加回去。
        指標計算是按 instrument 分組進行的。
        """
        if daily_ohlcv_df.empty:
            # print("[GoldBuilder] 輸入的日線 OHLCV DataFrame 為空，無法計算特徵。")
            return daily_ohlcv_df # 返回自身以保持鏈式操作

        # print(f"[GoldBuilder] 準備為 {len(daily_ohlcv_df)} 筆日線數據計算技術特徵...")

        all_features_list = []
        # 確保數據按 instrument 和 date 排序，這對很多技術指標計算很重要
        daily_ohlcv_df = daily_ohlcv_df.sort_values(by=['instrument', 'date']).reset_index(drop=True)

        for instrument, group_df in daily_ohlcv_df.groupby('instrument'):
            if group_df.empty:
                continue

            # print(f"[GoldBuilder] 正在為標的: {instrument} 計算特徵 (數據點: {len(group_df)})")
            # 確保 group_df 的索引是 date (如果不是，則設置它，但 pandas-ta 通常可以直接處理欄位)
            # group_df = group_df.set_index('date') # pandas-ta 可以處理非索引的 'close'

            # 計算 MA5 和 MA20
            group_df.ta.sma(length=5, close='close', append=True, col_names=('MA5',))
            group_df.ta.sma(length=20, close='close', append=True, col_names=('MA20',))

            # 計算 RSI14
            group_df.ta.rsi(length=14, close='close', append=True, col_names=('RSI14',))

            # pandas-ta 會將計算結果 (例如 MA5_5, RSI_14) 直接附加到 DataFrame
            # 我們需要將其重命名為 Pydantic 模型中定義的名稱 (ma5, rsi14)
            # 如果 col_names 被正確使用，則不需要重命名
            # 檢查列名，例如 group_df.columns
            # print(f"[GoldBuilder] {instrument} 計算後欄位: {group_df.columns.tolist()}")


            # 選擇 Pydantic 模型中定義的相關欄位
            # 確保 'date' 和 'instrument' 也在其中
            feature_cols = ['date', 'instrument']
            for field_name in GoldMarketFeaturesDaily.model_fields.keys():
                if field_name not in ['date', 'instrument'] and field_name.upper() in group_df.columns: # pandas-ta 可能輸出大寫
                    group_df.rename(columns={field_name.upper(): field_name}, inplace=True)
                if field_name in group_df.columns: # 確保欄位存在才添加
                     if field_name not in feature_cols:
                        feature_cols.append(field_name)

            all_features_list.append(group_df[feature_cols])

        if not all_features_list:
            # print("[GoldBuilder] 沒有計算出任何特徵數據。")
            # 返回原始 DataFrame，但可能沒有任何新特徵欄位
            # 或者返回一個空的帶有預期特徵欄位的 DataFrame
            # 為了安全，如果沒有特徵，就只返回原始數據的 date 和 instrument
            return daily_ohlcv_df[['date', 'instrument']].copy()


        features_df = pd.concat(all_features_list).reset_index(drop=True)

        # 將 NaN 轉換為 None 以符合 Pydantic Optional[float] 的期望 (如果直接寫入數據庫，DuckDB 通常能處理 NaN)
        # 但如果後續要轉換為 Pydantic 模型列表，None 更合適
        # for col in ['ma5', 'ma20', 'rsi14']:
        #     if col in features_df.columns:
        #         features_df[col] = features_df[col].apply(lambda x: None if pd.isna(x) else x)

        # print(f"[GoldBuilder] 成功計算並合併特徵，生成 {len(features_df)} 筆記錄。")
        # 合併回原始的 daily_ohlcv_df，確保所有欄位都在
        # 這裡的 features_df 應該已經包含了 date 和 instrument，以及計算出的特徵
        # 我們需要將這些特徵合併到 daily_ohlcv_df

        # 合併 daily_ohlcv_df 和 features_df
        # features_df 已經包含了 date, instrument 和計算出的特徵
        # daily_ohlcv_df 包含 date, instrument, o, h, l, c, v
        # 我們需要一個包含所有這些欄位的 DataFrame

        # 因為 features_df 是從 daily_ohlcv_df 的 group 計算並選擇列得到的，
        # 它只包含 date, instrument 和實際計算出的特徵列。
        # 我們可以直接將 features_df 中的特徵列合併到 daily_ohlcv_df

        # 確保 daily_ohlcv_df 也按相同方式排序，以便安全合併 (如果索引丟失)
        daily_ohlcv_df = daily_ohlcv_df.sort_values(by=['instrument', 'date']).reset_index(drop=True)

        # 找出 features_df 中新增的特徵欄位 (不包括 'date', 'instrument')
        feature_only_cols = [col for col in features_df.columns if col not in ['date', 'instrument']]

        # 合併：將 features_df 中的特徵欄位加到 daily_ohlcv_df
        # 假設 features_df 和 daily_ohlcv_df 的行序是一致的（因為都是按 instrument, date 排序）
        # 或者使用 pd.merge
        if not features_df.empty:
            # print(f"[GoldBuilder] Merging daily OHLCV (len: {len(daily_ohlcv_df)}) with features (len: {len(features_df)})")
            # print(f"[GoldBuilder] Daily OHLCV columns: {daily_ohlcv_df.columns.tolist()}")
            # print(f"[GoldBuilder] Features columns: {features_df.columns.tolist()}")

            # 如果 features_df 只包含 date, instrument 和特徵，並且與 daily_ohlcv_df 的 date, instrument 匹配
            # 則可以直接賦值或合併
            # 由於 features_df 是從 daily_ohlcv_df 的 group 創建的，它應該具有相同的 date 和 instrument
            # 但可能由於 dropna 等操作導致行數不完全一致。標準做法是 merge。

            merged_df = pd.merge(daily_ohlcv_df, features_df[['date', 'instrument'] + feature_only_cols],
                                 on=['date', 'instrument'], how='left')
            # print(f"[GoldBuilder] Merged DF length: {len(merged_df)}")
            return merged_df
        else:
            # print("[GoldBuilder] Features DF is empty, returning original daily OHLCV DF.")
            # 如果沒有計算出任何特徵，確保所有預期的特徵欄位都存在且為 NaN/None
            for feature_col_name in GoldMarketFeaturesDaily.model_fields.keys():
                if feature_col_name not in ['date', 'instrument'] and feature_col_name not in daily_ohlcv_df.columns:
                    daily_ohlcv_df[feature_col_name] = pd.NA # 或者 np.nan
            return daily_ohlcv_df


    def write_gold_tables(self, final_df: pd.DataFrame,
                          ohlcv_table_name: str = "gold_market_ohlcv_daily",
                          features_table_name: str = "gold_market_features_daily"):
        """
        將包含日線 OHLCV 和特徵的最終 DataFrame，分別寫入金層的兩個資料表中。
        """
        if final_df.empty:
            # print("[GoldBuilder] 最終 DataFrame 為空，無需寫入金層表。")
            return

        # conn = self._connect() # 不再需要直接使用 conn

        # 1. 準備並寫入 gold_market_ohlcv_daily 表
        ohlcv_cols = [field for field in GoldMarketOHLCVDaily.model_fields.keys() if field in final_df.columns]
        ohlcv_gold_df = final_df[ohlcv_cols].copy()
        # print(f"[GoldBuilder] 準備寫入 {len(ohlcv_gold_df)} 筆數據到 '{ohlcv_table_name}'...")
        self.db_manager.create_table_if_not_exists(ohlcv_table_name, GoldMarketOHLCVDaily) # <--- 使用 db_manager

        # 將 DataFrame 轉換為 Pydantic 模型列表
        # 處理 NaN/NaT: Pydantic 模型中 Optional 字段應為 None
        ohlcv_gold_df_cleaned = ohlcv_gold_df.replace({np.nan: None}) # 全局替換 NaN
        # 對於日期類型，確保 NaT 也被轉為 None
        if 'date' in ohlcv_gold_df_cleaned.columns:
             ohlcv_gold_df_cleaned['date'] = ohlcv_gold_df_cleaned['date'].apply(lambda x: None if pd.isna(x) else x)

        ohlcv_records = [GoldMarketOHLCVDaily(**row) for row in ohlcv_gold_df_cleaned.to_dict(orient='records')]

        if ohlcv_records:
            try:
                self.db_manager.insert_data(ohlcv_table_name, ohlcv_records) # <--- 使用 db_manager
                # print(f"[GoldBuilder] 成功寫入數據到 '{ohlcv_table_name}'。")
            except Exception as e:
                # print(f"[GoldBuilder] 寫入 '{ohlcv_table_name}' 失敗: {e}")
                raise
        else:
            # print(f"[GoldBuilder] 沒有 OHLCV 數據可寫入 '{ohlcv_table_name}'。")
            pass

        # 2. 準備並寫入 gold_market_features_daily 表
        feature_cols = [field for field in GoldMarketFeaturesDaily.model_fields.keys() if field in final_df.columns]
        features_gold_df = final_df[feature_cols].copy()
        # print(f"[GoldBuilder] 準備寫入 {len(features_gold_df)} 筆數據到 '{features_table_name}'...")
        self.db_manager.create_table_if_not_exists(features_table_name, GoldMarketFeaturesDaily) # <--- 使用 db_manager

        # 清理 NaN/NaT
        features_gold_df_cleaned = features_gold_df.replace({np.nan: None})
        if 'date' in features_gold_df_cleaned.columns:
            features_gold_df_cleaned['date'] = features_gold_df_cleaned['date'].apply(lambda x: None if pd.isna(x) else x)
        # 確保其他 Optional float 欄位中的 NaN 也被正確處理 (replace 應該已經處理了)

        feature_records = [GoldMarketFeaturesDaily(**row) for row in features_gold_df_cleaned.to_dict(orient='records')]

        if feature_records:
            try:
                self.db_manager.insert_data(features_table_name, feature_records) # <--- 使用 db_manager
                # print(f"[GoldBuilder] 成功寫入數據到 '{features_table_name}'。")
            except Exception as e:
                # print(f"[GoldBuilder] 寫入 '{features_table_name}' 失敗: {e}")
                raise
        else:
            # print(f"[GoldBuilder] 沒有特徵數據可寫入 '{features_table_name}'。")
            pass

# 簡單的測試/使用範例
if __name__ == '__main__':
    import numpy as np
    print("--- [Test] GoldLayerBuilder 獨立測試開始 ---")

    test_db_path = "test_market_data_gold_builder.duckdb"
    silver_table = "silver_market_ohlcv_1m_test_gold"
    gold_ohlcv_table = "gold_market_ohlcv_daily_test"
    gold_features_table = "gold_market_features_daily_test"

    import os
    if os.path.exists(test_db_path): os.remove(test_db_path)
    if os.path.exists(f"{test_db_path}.wal"): os.remove(f"{test_db_path}.wal")

    try:
        with GoldLayerBuilder(db_path=test_db_path) as builder:
            conn = builder._get_db_connection() # <--- 更新連接獲取方式

            # 1. 準備銀層假數據
            print(f"\n[Test Setup] 正在準備銀層假數據到 '{silver_table}'...")
            conn.execute(f"""
            CREATE TABLE {silver_table} (
                timestamp TIMESTAMP, instrument VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume INTEGER
            )""")

            sim_dates = [datetime.datetime(2023, 1, d, h, m) for d in range(1, 25) for h in range(9,10) for m in range(0,60,15)] # 約 24 天 * 4 條/天
            mock_silver_data = []
            for i, dt in enumerate(sim_dates):
                price_base = 100 + (i // 4) # 每天價格基數略微增加
                mock_silver_data.append((dt, "GOLD_TEST", price_base + (i%4), price_base + (i%4) + 1, price_base + (i%4) -1, price_base + (i%4) + 0.5, 100 + i))

            silver_df_prep = pd.DataFrame(mock_silver_data, columns=['timestamp', 'instrument', 'open', 'high', 'low', 'close', 'volume'])
            conn.register('silver_df_prep_view', silver_df_prep)
            conn.execute(f"INSERT INTO {silver_table} SELECT * FROM silver_df_prep_view")
            conn.unregister('silver_df_prep_view')
            print(f"[Test Setup] 成功插入 {len(silver_df_prep)} 筆假分鐘數據到 '{silver_table}'。")

            # 2. 測試 read_silver_ohlcv_1m
            print(f"\n[Test Read Silver] 正在測試 read_silver_ohlcv_1m...")
            read_silver_df = builder.read_silver_ohlcv_1m(silver_table_name=silver_table)
            print(f"[Test Read Silver] 從銀層讀取到 {len(read_silver_df)} 筆分鐘數據。")
            assert len(read_silver_df) == len(silver_df_prep), "讀取的銀層數據量不匹配"

            # 3. 測試 aggregate_to_daily_ohlcv
            print(f"\n[Test Aggregate Daily] 正在測試 aggregate_to_daily_ohlcv...")
            daily_ohlcv_df = builder.aggregate_to_daily_ohlcv(read_silver_df)
            print(f"[Test Aggregate Daily] 聚合得到 {len(daily_ohlcv_df)} 筆日線 OHLCV 數據。")
            # print(daily_ohlcv_df.head())
            # 應該有 24 天的數據
            assert len(daily_ohlcv_df) == 24, "日線聚合後的記錄數不正確"
            assert 'date' in daily_ohlcv_df.columns
            assert isinstance(daily_ohlcv_df['date'].iloc[0], datetime.date)


            # 4. 測試 calculate_features
            print(f"\n[Test Calculate Features] 正在測試 calculate_features...")
            features_inclusive_df = builder.calculate_features(daily_ohlcv_df.copy()) # 傳副本
            print(f"[Test Calculate Features] 計算特徵後得到 {len(features_inclusive_df)} 筆記錄。")
            # print(features_inclusive_df[['date', 'instrument', 'close', 'MA5', 'MA20', 'RSI14']].tail(10))
            assert 'MA5' in features_inclusive_df.columns
            assert 'MA20' in features_inclusive_df.columns
            assert 'RSI14' in features_inclusive_df.columns
            # MA20 在前19天應該是 NaN/None
            # print(f"MA20 non-NA count: {features_inclusive_df['MA20'].notna().sum()}")
            # print(f"Expected MA20 non-NA: {24-19}")
            assert features_inclusive_df['MA20'].notna().sum() == (24 - 19), "MA20 非空值數量不符預期"
            assert features_inclusive_df['RSI14'].notna().sum() == (24-14), "RSI14 非空值數量不符預期"


            # 5. 測試 write_gold_tables
            print(f"\n[Test Write Gold] 正在測試 write_gold_tables...")
            builder.write_gold_tables(features_inclusive_df,
                                      ohlcv_table_name=gold_ohlcv_table,
                                      features_table_name=gold_features_table)

            gold_ohlcv_count = conn.execute(f"SELECT COUNT(*) FROM {gold_ohlcv_table}").fetchone()[0] # type: ignore
            gold_features_count = conn.execute(f"SELECT COUNT(*) FROM {gold_features_table}").fetchone()[0] # type: ignore
            print(f"[Test Write Gold] 金層 OHLCV 表 '{gold_ohlcv_table}' 記錄數: {gold_ohlcv_count}")
            print(f"[Test Write Gold] 金層特徵表 '{gold_features_table}' 記錄數: {gold_features_count}")
            assert gold_ohlcv_count == len(features_inclusive_df), "寫入金層 OHLCV 表的記錄數不匹配"
            assert gold_features_count == len(features_inclusive_df), "寫入金層特徵表的記錄數不匹配"

            # 抽查一條記錄的 MA5 和 RSI14
            # last_record_features = conn.execute(f"SELECT MA5, RSI14 FROM {gold_features_table} ORDER BY date DESC LIMIT 1").fetchdf()
            # print("[Test Write Gold] 最後一條記錄的特徵預覽:")
            # print(last_record_features)
            # 手動驗證 pandas-ta 的結果比較複雜，這裡主要測試流程完整性

        print("\n--- [Test] GoldLayerBuilder 獨立測試執行完畢。 ---")

    except Exception as e:
        print(f"GoldLayerBuilder 測試過程中發生錯誤: {e}")
        raise
    finally:
        if os.path.exists(test_db_path): os.remove(test_db_path)
        if os.path.exists(f"{test_db_path}.wal"): os.remove(f"{test_db_path}.wal")
