# src/core/db/db_manager.py
# ==============================================================================
#  【普羅米修斯之火】中央數據庫管理員
# ==============================================================================
import os
from pathlib import Path
from typing import Literal

import duckdb
import pandas as pd

class DBManager:
    def __init__(self, db_path: str | Path = "data/financial_data.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def connect(self):
        if self._connection is None:
            try:
                self._connection = duckdb.connect(database=str(self.db_path), read_only=False)
                print(f"--- 成功連接到數據庫: {self.db_path} ---")
            except Exception as e:
                print(f"錯誤：無法連接到數據庫 {self.db_path}。原因: {e}")
                raise

    def disconnect(self):
        if self._connection:
            self._connection.close()
            print(f"--- 成功斷開數據庫連接: {self.db_path} ---")
            self._connection = None

    def write_dataframe(self, df: pd.DataFrame, table_name: str, mode: Literal["replace", "append"] = "replace"):
        if self._connection is None:
            raise ConnectionError("數據庫未連接。請先調用 connect() 或使用 with 陳述式。")
        if df.empty:
            print(f"警告：試圖寫入一個空的 DataFrame 到 '{table_name}'，操作已跳過。")
            return
        print(f"--- 正在將 DataFrame 寫入表格 '{table_name}' (模式: {mode})... ---")
        try:
            if mode == "replace":
                self._connection.register("temp_df", df)
                self._connection.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM temp_df")
            elif mode == "append":
                self._connection.register("temp_df_append", df)
                self._connection.execute(f"INSERT INTO {table_name} SELECT * FROM temp_df_append")
            else:
                raise ValueError(f"不支援的寫入模式: {mode}。")
            print(f"--- 成功將 {len(df)} 筆記錄寫入 '{table_name}' ---")
        except Exception as e:
            print(f"錯誤：寫入 DataFrame 到表格 '{table_name}' 失敗。原因: {e}")
            raise
        finally:
            self._connection.unregister("temp_df")
            self._connection.unregister("temp_df_append")

    def read_sql(self, sql_query: str) -> pd.DataFrame:
        if self._connection is None:
            raise ConnectionError("數據庫未連接。請先調用 connect() 或使用 with 陳述式。")
        print(f"--- 正在執行 SQL 查詢: {sql_query[:100]}... ---")
        try:
            result_df = self._connection.execute(sql_query).fetchdf()
            print(f"--- 查詢成功，返回 {len(result_df)} 筆記錄 ---")
            return result_df
        except Exception as e:
            print(f"錯誤：執行 SQL 查詢失敗。原因: {e}")
            raise
