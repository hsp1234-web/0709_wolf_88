import duckdb
import pandas as pd
import datetime
from typing import Optional, Type, List
from pydantic import BaseModel

# 從同一應用程式的 schemas 導入
from .schemas import MarketOHLCV1M

# 與 taifex_tick_loader 中相似的 Pydantic 到 DuckDB 類型映射
# 為了避免重複，理想情況下這個映射可以放到一個共享的 core.utils 或類似的地方
# 但目前為了此微服務的獨立性，暫時在此處重定義
PYDANTIC_TO_DUCKDB_TYPE_MAP = {
    datetime.datetime: "TIMESTAMP",
    float: "DOUBLE",
    int: "INTEGER",
    str: "VARCHAR",
    bool: "BOOLEAN",
}

class TimeAggregator:
    """
    負責讀取銅層秒級數據，將其聚合為 1 分鐘 OHLCV，並存儲至銀層。
    """
    def __init__(self, db_path: str = "market_data.duckdb"):
        """
        初始化 TimeAggregator。

        Args:
            db_path (str): DuckDB 數據庫文件的路徑。
        """
        self.db_path = db_path
        self._connection: Optional[duckdb.DuckDBPyConnection] = None
        # print(f"[TimeAggregator] 初始化，數據庫路徑: {self.db_path}")

    def _connect(self) -> duckdb.DuckDBPyConnection:
        """ 建立並返回一個 DuckDB 連接。 """
        if self._connection is None:
            # print(f"[TimeAggregator] 正在連接到 DuckDB: {self.db_path}")
            self._connection = duckdb.connect(database=self.db_path, read_only=False) # 聚合器需要寫入
        return self._connection

    def close(self):
        """ 關閉 DuckDB 連接。 """
        if self._connection is not None:
            # print("[TimeAggregator] 正在關閉 DuckDB 連接。")
            self._connection.close()
            self._connection = None

    def __enter__(self):
        # print("[TimeAggregator] 進入上下文管理器，建立連接。")
        self._connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # print("[TimeAggregator] 退出上下文管理器，關閉連接。")
        self.close()

    def _pydantic_to_duckdb_schema(self, model: Type[BaseModel]) -> str:
        """ 將 Pydantic 模型轉換為 DuckDB 表的欄位定義字串。 """
        columns = []
        for field_name, field_obj in model.model_fields.items():
            pydantic_type = field_obj.annotation
            duckdb_type = PYDANTIC_TO_DUCKDB_TYPE_MAP.get(pydantic_type)
            if duckdb_type is None:
                raise ValueError(f"不支援的 Pydantic 類型: {pydantic_type} 用於欄位 '{field_name}'")
            columns.append(f"{field_name} {duckdb_type}")
        return ", ".join(columns)

    def _create_table_if_not_exists(self, table_name: str, model: Type[BaseModel]):
        """ 根據 Pydantic 模型自動生成 CREATE TABLE SQL 語句並執行。 """
        conn = self._connect()
        try:
            schema_str = self._pydantic_to_duckdb_schema(model)
            query = f"CREATE TABLE IF NOT EXISTS {table_name} ({schema_str})"
            # print(f"[TimeAggregator] 執行 SQL: {query}")
            conn.execute(query)
            # print(f"[TimeAggregator] 資料表 '{table_name}' 已成功檢查/創建。")
        except Exception as e:
            # print(f"[TimeAggregator] 創建資料表 '{table_name}' 失敗: {e}")
            raise

    def read_bronze_ticks(self, start_time: datetime.datetime, end_time: datetime.datetime,
                          bronze_table_name: str = "bronze_taifex_ticks") -> pd.DataFrame:
        """
        讀取 bronze_taifex_ticks 表在指定時間範圍內的數據。

        Args:
            start_time (datetime.datetime): 查詢開始時間。
            end_time (datetime.datetime): 查詢結束時間。
            bronze_table_name (str): 銅層秒級數據表名。

        Returns:
            pd.DataFrame: 包含秒級 Tick 數據的 DataFrame。
                          欄位應包含 'timestamp', 'price', 'volume', 'instrument'。
        """
        conn = self._connect()
        # print(f"[TimeAggregator] 準備從 '{bronze_table_name}' 讀取 {start_time} 到 {end_time} 的數據")
        query = f"""
        SELECT timestamp, price, volume, instrument
        FROM {bronze_table_name}
        WHERE timestamp >= ? AND timestamp < ?
        ORDER BY timestamp ASC
        """
        try:
            # DuckDB 的 Python API 可以直接將查詢結果轉換為 Pandas DataFrame
            df_ticks = conn.execute(query, [start_time, end_time]).fetchdf()
            # print(f"[TimeAggregator] 成功讀取 {len(df_ticks)} 筆數據從 '{bronze_table_name}'。")
            if 'timestamp' in df_ticks.columns:
                 df_ticks['timestamp'] = pd.to_datetime(df_ticks['timestamp'])
            return df_ticks
        except Exception as e:
            # print(f"[TimeAggregator] 從 '{bronze_table_name}' 讀取數據失敗: {e}")
            # 在實際應用中，如果表不存在或查詢失敗，可能需要更穩健的錯誤處理
            # 例如，返回一個空的 DataFrame 並記錄警告/錯誤
            return pd.DataFrame(columns=['timestamp', 'price', 'volume', 'instrument'])


    def aggregate_to_1m_ohlcv(self, ticks_df: pd.DataFrame) -> pd.DataFrame:
        """
        將 Tick 數據 DataFrame 聚合為 1 分鐘 OHLCV DataFrame。

        Args:
            ticks_df (pd.DataFrame): 包含 'timestamp', 'price', 'volume', 'instrument' 的 Tick 數據。
                                     'timestamp' 欄位必須是 datetime-like。

        Returns:
            pd.DataFrame: 包含 1 分鐘 OHLCV 數據的 DataFrame。
                          欄位為 ['timestamp', 'instrument', 'open', 'high', 'low', 'close', 'volume']。
        """
        if ticks_df.empty:
            # print("[TimeAggregator] 輸入的 Tick DataFrame 為空，無法進行聚合。")
            return pd.DataFrame(columns=['timestamp', 'instrument', 'open', 'high', 'low', 'close', 'volume'])

        if 'timestamp' not in ticks_df.columns or not pd.api.types.is_datetime64_any_dtype(ticks_df['timestamp']):
            raise ValueError("輸入的 DataFrame 必須包含 'timestamp' 欄位且其類型應為 datetime-like。")

        # print(f"[TimeAggregator] 準備聚合 {len(ticks_df)} 筆 Tick 數據。")

        # 確保 timestamp 是索引，以便使用 resample
        if not isinstance(ticks_df.index, pd.DatetimeIndex):
            ticks_df = ticks_df.set_index('timestamp')

        # 按 instrument 分組，然後再按時間聚合
        ohlcv_list = []
        for instrument, group_df in ticks_df.groupby('instrument'):
            # print(f"[TimeAggregator] 正在聚合標的: {instrument}, Tick 數量: {len(group_df)}")
            # 價格聚合
            price_resampled = group_df['price'].resample('1min').agg(
                open='first',
                high='max',
                low='min',
                close='last'
            )
            # 成交量聚合
            volume_resampled = group_df['volume'].resample('1min').sum()

            # 合併價格和成交量
            ohlcv_instrument_df = pd.concat([price_resampled, volume_resampled.rename('volume')], axis=1)

            # 添加 instrument 欄位
            ohlcv_instrument_df['instrument'] = instrument

            ohlcv_list.append(ohlcv_instrument_df)

        if not ohlcv_list:
            # print("[TimeAggregator] 沒有數據可聚合。")
            return pd.DataFrame(columns=['timestamp', 'instrument', 'open', 'high', 'low', 'close', 'volume'])

        final_ohlcv_df = pd.concat(ohlcv_list)

        # 重置索引，使 'timestamp' 變回普通欄位
        final_ohlcv_df = final_ohlcv_df.reset_index()

        # 確保欄位順序符合 MarketOHLCV1M 模型
        final_ohlcv_df = final_ohlcv_df[['timestamp', 'instrument', 'open', 'high', 'low', 'close', 'volume']]

        # 移除所有值都是 NaN 的行 (通常是沒有交易的分鐘)
        final_ohlcv_df = final_ohlcv_df.dropna(subset=['open', 'high', 'low', 'close'], how='all')

        # print(f"[TimeAggregator] 成功聚合得到 {len(final_ohlcv_df)} 筆 1 分鐘 OHLCV 數據。")
        return final_ohlcv_df


    def write_silver_ohlcv(self, ohlcv_df: pd.DataFrame, silver_table_name: str = "silver_market_ohlcv_1m"):
        """
        將聚合後的 OHLCV DataFrame 寫入 silver_market_ohlcv_1m 表中。
        會先根據 MarketOHLCV1M 模型創建該表（如果不存在）。

        Args:
            ohlcv_df (pd.DataFrame): 包含 1 分鐘 OHLCV 數據的 DataFrame。
            silver_table_name (str): 銀層 OHLCV 表名。
        """
        if ohlcv_df.empty:
            # print(f"[TimeAggregator] OHLCV DataFrame 為空，無需寫入 '{silver_table_name}'。")
            return

        conn = self._connect()

        # 1. 確保目標表存在且結構正確
        # print(f"[TimeAggregator] 正在檢查/創建銀層資料表 '{silver_table_name}'...")
        self._create_table_if_not_exists(silver_table_name, MarketOHLCV1M)

        # 2. 寫入數據
        # print(f"[TimeAggregator] 準備將 {len(ohlcv_df)} 筆聚合數據寫入 '{silver_table_name}'...")
        try:
            # DuckDB 可以直接從 Pandas DataFrame 插入數據
            # 使用 register + INSERT INTO SELECT * 模式，或 conn.append()
            # conn.append(silver_table_name, ohlcv_df) # 較新版本的 DuckDB
            conn.register('ohlcv_df_temp_view', ohlcv_df)
            conn.execute(f"INSERT INTO {silver_table_name} SELECT * FROM ohlcv_df_temp_view")
            conn.unregister('ohlcv_df_temp_view')
            # print(f"[TimeAggregator] 成功將 {len(ohlcv_df)} 筆數據寫入 '{silver_table_name}'。")
        except Exception as e:
            # print(f"[TimeAggregator] 將數據寫入 '{silver_table_name}' 失敗: {e}")
            raise

# 簡單的測試/使用範例
if __name__ == '__main__':
    print("--- [Test] TimeAggregator 獨立測試開始 ---")

    # 準備測試用的 DuckDB 環境
    test_db_path = "test_market_data_aggregator.duckdb"
    bronze_table = "bronze_taifex_ticks_test_agg"
    silver_table = "silver_market_ohlcv_1m_test_agg"

    # 清理舊的測試數據庫文件
    import os
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    if os.path.exists(f"{test_db_path}.wal"):
        os.remove(f"{test_db_path}.wal")

    try:
        with TimeAggregator(db_path=test_db_path) as aggregator:
            conn = aggregator._connect() # 獲取連接以手動準備數據

            # 1. 準備銅層假數據 (模擬 taifex_tick_loader 的輸出)
            print(f"\n[Test Setup] 正在準備銅層假數據到 '{bronze_table}'...")
            # 需要一個與 TaifexTick 類似的結構，至少有 timestamp, price, volume, instrument
            # 為了測試，我們不需要嚴格的 Pydantic 模型，只需創建表並插入數據
            conn.execute(f"""
            CREATE TABLE {bronze_table} (
                timestamp TIMESTAMP,
                price DOUBLE,
                volume INTEGER,
                instrument VARCHAR
            )
            """)

            start_dt = datetime.datetime(2023, 10, 1, 9, 0, 0)
            mock_ticks_data = []
            # 標的 TXF202310
            mock_ticks_data.extend([
                (start_dt + datetime.timedelta(seconds=10), 16700.0, 5, "TXF202310"),
                (start_dt + datetime.timedelta(seconds=20), 16702.0, 2, "TXF202310"), # High for 1st min
                (start_dt + datetime.timedelta(seconds=30), 16698.0, 3, "TXF202310"), # Low for 1st min
                (start_dt + datetime.timedelta(seconds=55), 16701.0, 1, "TXF202310"), # Close for 1st min
                (start_dt + datetime.timedelta(minutes=1, seconds=5), 16705.0, 4, "TXF202310"), # Open for 2nd min
                (start_dt + datetime.timedelta(minutes=1, seconds=15), 16706.0, 6, "TXF202310"),
            ])
            # 標的 MXF202310
            mock_ticks_data.extend([
                (start_dt + datetime.timedelta(seconds=15), 3340.0, 10, "MXF202310"),
                (start_dt + datetime.timedelta(seconds=45), 3345.0, 12, "MXF202310"),
            ])

            conn.register('mock_ticks_df_view', pd.DataFrame(mock_ticks_data, columns=['timestamp', 'price', 'volume', 'instrument']))
            conn.execute(f"INSERT INTO {bronze_table} SELECT * FROM mock_ticks_df_view")
            conn.unregister('mock_ticks_df_view')
            print(f"[Test Setup] 成功插入 {len(mock_ticks_data)} 筆假 Tick 數據到 '{bronze_table}'。")

            # 2. 測試 read_bronze_ticks
            print(f"\n[Test Read] 正在測試 read_bronze_ticks...")
            query_start_time = start_dt
            query_end_time = start_dt + datetime.timedelta(minutes=2) # 包含第二分鐘的開始
            read_ticks_df = aggregator.read_bronze_ticks(query_start_time, query_end_time, bronze_table_name=bronze_table)
            print(f"[Test Read] 從銅層讀取到 {len(read_ticks_df)} 筆 Tick 數據。")
            # print(read_ticks_df.head())
            assert len(read_ticks_df) == len(mock_ticks_data), "讀取的 Tick 數量不匹配"

            # 3. 測試 aggregate_to_1m_ohlcv
            print(f"\n[Test Aggregate] 正在測試 aggregate_to_1m_ohlcv...")
            ohlcv_df = aggregator.aggregate_to_1m_ohlcv(read_ticks_df)
            print(f"[Test Aggregate] 聚合得到 {len(ohlcv_df)} 筆 1 分鐘 OHLCV 數據。")
            print("聚合結果預覽:")
            print(ohlcv_df)

            # 預期 TXF202310 的第一分鐘: O=16700, H=16702, L=16698, C=16701, V=5+2+3+1=11
            # 預期 TXF202310 的第二分鐘: O=16705, H=16706, L=16705, C=16706, V=4+6=10
            # 預期 MXF202310 的第一分鐘: O=3340, H=3345, L=3340, C=3345, V=10+12=22
            assert len(ohlcv_df) == 3, "聚合後的 OHLCV 記錄數不正確"
            txf_first_min = ohlcv_df[(ohlcv_df['instrument'] == "TXF202310") & (ohlcv_df['timestamp'] == pd.Timestamp(start_dt))]
            assert not txf_first_min.empty
            assert txf_first_min.iloc[0]['open'] == 16700.0
            assert txf_first_min.iloc[0]['high'] == 16702.0
            assert txf_first_min.iloc[0]['low'] == 16698.0
            assert txf_first_min.iloc[0]['close'] == 16701.0
            assert txf_first_min.iloc[0]['volume'] == 11

            # 4. 測試 write_silver_ohlcv
            print(f"\n[Test Write] 正在測試 write_silver_ohlcv...")
            aggregator.write_silver_ohlcv(ohlcv_df, silver_table_name=silver_table)

            # 驗證數據是否已寫入銀層表
            silver_count_result = conn.execute(f"SELECT COUNT(*) FROM {silver_table}").fetchone()
            if silver_count_result:
                print(f"[Test Write] 銀層資料表 '{silver_table}' 中的記錄數: {silver_count_result[0]}")
                assert silver_count_result[0] == len(ohlcv_df), "寫入銀層的記錄數不匹配"
            else:
                raise AssertionError(f"無法從 '{silver_table}' 讀取記錄數。")

            print("\n[Test Write] 銀層數據預覽:")
            silver_data_preview = conn.execute(f"SELECT * FROM {silver_table} ORDER BY instrument, timestamp").fetchdf()
            print(silver_data_preview)

        print("\n--- [Test] TimeAggregator 獨立測試執行完畢。 ---")

    except Exception as e:
        print(f"TimeAggregator 測試過程中發生錯誤: {e}")
        raise
    finally:
        # 清理測試數據庫文件
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
        if os.path.exists(f"{test_db_path}.wal"):
            os.remove(f"{test_db_path}.wal")
