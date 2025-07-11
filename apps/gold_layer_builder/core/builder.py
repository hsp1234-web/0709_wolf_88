from __future__ import annotations

import duckdb
import pandas as pd
import datetime
import os
import numpy as np
from typing import Optional, List, Dict, Any, Type # Added List, Dict, Any
from pydantic import BaseModel

from .schemas import GoldMarketOHLCVDaily, GoldMarketFeaturesDaily

PYDANTIC_TO_DUCKDB_TYPE_MAP: Dict[Any, str] = { # Added type hint for map
    datetime.date: "DATE",
    datetime.datetime: "TIMESTAMP",
    float: "DOUBLE",
    int: "INTEGER",
    str: "VARCHAR",
    bool: "BOOLEAN",
}


class GoldLayerBuilder:
    def __init__(self, db_path: str = "market_data.duckdb"):
        self.db_path = db_path
        self._connection: Optional[duckdb.DuckDBPyConnection] = None

    def _connect(self) -> duckdb.DuckDBPyConnection:
        if self._connection is None:
            self._connection = duckdb.connect(database=self.db_path, read_only=False)
        return self._connection

    def close(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> GoldLayerBuilder: # Return self
        self._connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: # Type hints for __exit__
        self.close()

    def _pydantic_to_duckdb_schema(self, model: Type[BaseModel]) -> str:
        columns: List[str] = [] # Type hint for columns
        for field_name, field_obj in model.model_fields.items():
            pydantic_type: Any = field_obj.annotation

            # Handle Optional types by trying to get the inner type
            # This logic might need adjustment based on Pydantic versions and complex types
            if hasattr(pydantic_type, "__origin__") and getattr(pydantic_type, "__origin__", None) is Optional:
                args = getattr(pydantic_type, "__args__", None)
                if args and args[0] is not type(None):
                    pydantic_type = args[0]
            elif hasattr(pydantic_type, "__args__") and type(None) in getattr(pydantic_type, "__args__", []):
                 # For Union[X, NoneType]
                non_none_args = [arg for arg in getattr(pydantic_type, "__args__", []) if arg is not type(None)]
                if non_none_args:
                    pydantic_type = non_none_args[0]


            duckdb_type = PYDANTIC_TO_DUCKDB_TYPE_MAP.get(pydantic_type)
            if duckdb_type is None:
                 # Fallback for complex Optional or Union types not directly in map
                if hasattr(pydantic_type, "__args__"):
                    # Attempt with the first non-None argument if it's a Union
                    non_none_args = [arg for arg in pydantic_type.__args__ if arg is not type(None)]
                    if non_none_args:
                         duckdb_type = PYDANTIC_TO_DUCKDB_TYPE_MAP.get(non_none_args[0])

            if duckdb_type is None:
                raise ValueError(
                    f"不支援的 Pydantic 類型: {field_obj.annotation} (解析為 {pydantic_type}) 用於欄位 '{field_name}'"
                )
            columns.append(f"{field_name} {duckdb_type}")
        return ", ".join(columns)

    def _create_table_if_not_exists(self, table_name: str, model: Type[BaseModel]) -> None: # Added return type
        conn = self._connect()
        try:
            schema_str = self._pydantic_to_duckdb_schema(model)
            query = f"CREATE TABLE IF NOT EXISTS {table_name} ({schema_str})"
            conn.execute(query)
        except Exception as e: # Catch generic Exception
            print(f"[GoldBuilder] 創建資料表 '{table_name}' 失敗: {e}") # Added print for error
            raise

    def read_silver_ohlcv_1m(
        self,
        silver_table_name: str = "silver_market_ohlcv_1m",
        instrument: Optional[str] = None,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
    ) -> pd.DataFrame:
        conn = self._connect()
        conditions: List[str] = []
        params: List[Any] = [] # Changed to List[Any]

        if instrument:
            conditions.append("instrument = ?")
            params.append(instrument)
        if start_date:
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
            if "timestamp" in df_silver.columns:
                df_silver["timestamp"] = pd.to_datetime(df_silver["timestamp"])
            return df_silver
        except Exception as e: # Catch generic Exception
            print(f"[GoldBuilder] 從 '{silver_table_name}' 讀取數據失敗: {e}") # Added print for error
            return pd.DataFrame(columns=["timestamp", "instrument", "open", "high", "low", "close", "volume"])

    def aggregate_to_daily_ohlcv(self, minutely_df: pd.DataFrame) -> pd.DataFrame:
        if minutely_df.empty:
            return pd.DataFrame()
        if "timestamp" not in minutely_df.columns or not pd.api.types.is_datetime64_any_dtype(minutely_df["timestamp"]):
            raise ValueError("輸入的 DataFrame 必須包含 'timestamp' 欄位且其類型應為 datetime-like。")

        daily_ohlcv_list: List[pd.DataFrame] = [] # Type hint
        for instrument, group_df in minutely_df.groupby("instrument"):
            if group_df.empty:
                continue
            if not isinstance(group_df.index, pd.DatetimeIndex):
                group_df = group_df.set_index("timestamp")

            daily_resampled = group_df.resample("D").agg(
                open=("open", "first"), high=("high", "max"),
                low=("low", "min"), close=("close", "last"),
                volume=("volume", "sum"))
            daily_resampled["instrument"] = instrument
            daily_ohlcv_list.append(daily_resampled)

        if not daily_ohlcv_list:
            return pd.DataFrame()

        final_daily_df = pd.concat(daily_ohlcv_list).reset_index()
        final_daily_df.rename(columns={"timestamp": "date"}, inplace=True)
        final_daily_df["date"] = final_daily_df["date"].dt.date
        final_daily_df = final_daily_df.dropna(subset=["open", "high", "low", "close"], how="all")
        final_daily_df = final_daily_df[["date", "instrument", "open", "high", "low", "close", "volume"]]
        return final_daily_df

    def calculate_features(self, daily_ohlcv_df: pd.DataFrame) -> pd.DataFrame:
        if daily_ohlcv_df.empty:
            return daily_ohlcv_df

        all_features_list: List[pd.DataFrame] = [] # Type hint
        daily_ohlcv_df = daily_ohlcv_df.sort_values(by=["instrument", "date"]).reset_index(drop=True)

        for instrument, group_df_orig in daily_ohlcv_df.groupby("instrument"):
            if group_df_orig.empty:
                continue

            group_df = group_df_orig.copy() # Work on a copy to avoid SettingWithCopyWarning

            # Ensure 'close' column exists for ta functions
            if 'close' not in group_df.columns:
                print(f"警告: 標的 {instrument} 缺少 'close' 欄位，無法計算技術指標。")
                all_features_list.append(group_df_orig) # Append original group if features can't be calculated
                continue

            group_df.ta.sma(length=5, close="close", append=True, col_names=("MA5",))
            group_df.ta.sma(length=20, close="close", append=True, col_names=("MA20",))
            group_df.ta.rsi(length=14, close="close", append=True, col_names=("RSI14",))

            all_features_list.append(group_df)

        if not all_features_list:
            return daily_ohlcv_df # Return original if no features were processed

        features_df = pd.concat(all_features_list).reset_index(drop=True)

        # Merge calculated features back to the original daily_ohlcv_df structure if needed
        # This ensures all original columns are preserved, and new feature columns are added/updated.
        # If features_df structure is already complete (contains all original + new columns), direct return is fine.
        # Current logic of all_features_list.append(group_df) means features_df has all columns.
        return features_df


    def write_gold_tables(
        self,
        final_df: pd.DataFrame,
        ohlcv_table_name: str = "gold_market_ohlcv_daily",
        features_table_name: str = "gold_market_features_daily",
    ) -> None: # Added return type
        if final_df.empty:
            return

        conn = self._connect()

        ohlcv_cols = [field for field in GoldMarketOHLCVDaily.model_fields.keys() if field in final_df.columns]
        ohlcv_gold_df = final_df[ohlcv_cols].copy()
        self._create_table_if_not_exists(ohlcv_table_name, GoldMarketOHLCVDaily)
        try:
            for col in ohlcv_gold_df.select_dtypes(include=np.number).columns:
                ohlcv_gold_df[col] = ohlcv_gold_df[col].astype(object).where(ohlcv_gold_df[col].notna(), None)

            # Deduplicate before insert to prevent primary key violations if data is reprocessed
            conn.execute(f"DELETE FROM {ohlcv_table_name} WHERE date IN (SELECT DISTINCT date FROM ohlcv_gold_df_view) AND instrument IN (SELECT DISTINCT instrument FROM ohlcv_gold_df_view)", parameters={'ohlcv_gold_df_view': ohlcv_gold_df})

            conn.register("ohlcv_gold_df_view", ohlcv_gold_df)
            conn.execute(f"INSERT INTO {ohlcv_table_name} SELECT * FROM ohlcv_gold_df_view")
            conn.unregister("ohlcv_gold_df_view")
        except Exception as e:
            print(f"[GoldBuilder] 寫入 '{ohlcv_table_name}' 失敗: {e}")
            raise

        feature_cols = [field for field in GoldMarketFeaturesDaily.model_fields.keys() if field in final_df.columns]
        features_gold_df = final_df[feature_cols].copy()
        self._create_table_if_not_exists(features_table_name, GoldMarketFeaturesDaily)
        try:
            for col in features_gold_df.columns:
                if features_gold_df[col].isnull().any():
                    if pd.api.types.is_numeric_dtype(features_gold_df[col]) or \
                       pd.api.types.is_datetime64_any_dtype(features_gold_df[col]) or \
                       pd.api.types.is_timedelta64_dtype(features_gold_df[col]):
                        features_gold_df[col] = features_gold_df[col].astype(object).where(features_gold_df[col].notna(), None)

            # Deduplicate
            conn.execute(f"DELETE FROM {features_table_name} WHERE date IN (SELECT DISTINCT date FROM features_gold_df_view) AND instrument IN (SELECT DISTINCT instrument FROM features_gold_df_view)", parameters={'features_gold_df_view': features_gold_df})

            conn.register("features_gold_df_view", features_gold_df)
            conn.execute(f"INSERT INTO {features_table_name} SELECT * FROM features_gold_df_view")
            conn.unregister("features_gold_df_view")
        except Exception as e:
            print(f"[GoldBuilder] 寫入 '{features_table_name}' 失敗: {e}")
            raise

if __name__ == "__main__":
    print("--- [Test] GoldLayerBuilder 獨立測試開始 ---")
    test_db_path = "test_market_data_gold_builder.duckdb"
    silver_table = "silver_market_ohlcv_1m_test_gold"
    gold_ohlcv_table = "gold_market_ohlcv_daily_test"
    gold_features_table = "gold_market_features_daily_test"

    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    if os.path.exists(f"{test_db_path}.wal"):
        os.remove(f"{test_db_path}.wal")

    try:
        with GoldLayerBuilder(db_path=test_db_path) as builder:
            conn = builder._connect()
            conn.execute(f"CREATE TABLE {silver_table} (timestamp TIMESTAMP, instrument VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume INTEGER)")

            sim_dates = [datetime.datetime(2023, 1, d, h, m) for d in range(1, 25) for h in range(9, 10) for m in range(0, 60, 15)]
            mock_silver_data: List[tuple] = [] # Type hint
            for i, dt in enumerate(sim_dates):
                price_base = 100 + (i // 4)
                mock_silver_data.append((dt, "GOLD_TEST", price_base + (i % 4), price_base + (i % 4) + 1, price_base + (i % 4) - 1, price_base + (i % 4) + 0.5, 100 + i))

            silver_df_prep = pd.DataFrame(mock_silver_data, columns=["timestamp", "instrument", "open", "high", "low", "close", "volume"])
            conn.register("silver_df_prep_view", silver_df_prep)
            conn.execute(f"INSERT INTO {silver_table} SELECT * FROM silver_df_prep_view")
            conn.unregister("silver_df_prep_view")
            print(f"[Test Setup] 成功插入 {len(silver_df_prep)} 筆假分鐘數據到 '{silver_table}'。")

            print("\n[Test Read Silver] 正在測試 read_silver_ohlcv_1m...")
            read_silver_df = builder.read_silver_ohlcv_1m(silver_table_name=silver_table)
            print(f"[Test Read Silver] 從銀層讀取到 {len(read_silver_df)} 筆分鐘數據。")
            assert len(read_silver_df) == len(silver_df_prep), "讀取的銀層數據量不匹配"

            print("\n[Test Aggregate Daily] 正在測試 aggregate_to_daily_ohlcv...")
            daily_ohlcv_df = builder.aggregate_to_daily_ohlcv(read_silver_df)
            print(f"[Test Aggregate Daily] 聚合得到 {len(daily_ohlcv_df)} 筆日線 OHLCV 數據。")
            assert len(daily_ohlcv_df) == 24, "日線聚合後的記錄數不正確"
            assert "date" in daily_ohlcv_df.columns
            assert isinstance(daily_ohlcv_df["date"].iloc[0], datetime.date)

            print("\n[Test Calculate Features] 正在測試 calculate_features...")
            features_inclusive_df = builder.calculate_features(daily_ohlcv_df.copy())
            print(f"[Test Calculate Features] 計算特徵後得到 {len(features_inclusive_df)} 筆記錄。")
            assert "MA5" in features_inclusive_df.columns
            assert "MA20" in features_inclusive_df.columns
            assert "RSI14" in features_inclusive_df.columns
            assert features_inclusive_df["MA20"].notna().sum() == (24 - 19), "MA20 非空值數量不符預期"
            assert features_inclusive_df["RSI14"].notna().sum() == (24 - 14), "RSI14 非空值數量不符預期"

            print("\n[Test Write Gold] 正在測試 write_gold_tables...")
            builder.write_gold_tables(features_inclusive_df, ohlcv_table_name=gold_ohlcv_table, features_table_name=gold_features_table)

            gold_ohlcv_count_result = conn.execute(f"SELECT COUNT(*) FROM {gold_ohlcv_table}").fetchone()
            gold_features_count_result = conn.execute(f"SELECT COUNT(*) FROM {gold_features_table}").fetchone()

            assert gold_ohlcv_count_result is not None, "Gold OHLCV count result is None"
            assert gold_features_count_result is not None, "Gold Features count result is None"

            gold_ohlcv_count = gold_ohlcv_count_result[0]
            gold_features_count = gold_features_count_result[0]

            print(f"[Test Write Gold] 金層 OHLCV 表 '{gold_ohlcv_table}' 記錄數: {gold_ohlcv_count}")
            print(f"[Test Write Gold] 金層特徵表 '{gold_features_table}' 記錄數: {gold_features_count}")
            assert gold_ohlcv_count == len(features_inclusive_df), "寫入金層 OHLCV 表的記錄數不匹配"
            assert gold_features_count == len(features_inclusive_df), "寫入金層特徵表的記錄數不匹配"

        print("\n--- [Test] GoldLayerBuilder 獨立測試執行完畢。 ---")

    except Exception as e:
        print(f"GoldLayerBuilder 測試過程中發生錯誤: {e}")
        raise
    finally:
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
        if os.path.exists(f"{test_db_path}.wal"):
            os.remove(f"{test_db_path}.wal")
