# -*- coding: utf-8 -*-
"""
核心基礎設施：數據庫管理器 (v1.0)
"""

import logging
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from core.config import get_database_path

logger = logging.getLogger(__name__)


class DBManager:
    """
    一個統一的數據庫管理器，專為 DuckDB 設計。
    負責處理所有數據庫連接和 I/O 操作。
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化 DBManager。

        Args:
            db_path (Optional[str]): 數據庫檔案的路徑。
                                     如果為 None，將從 config.yml 讀取。
        """
        self.db_path = db_path or get_database_path()
        self.connection: Optional[duckdb.DuckDBPyConnection] = None
        self._connect()

    def _connect(self):
        """建立到 DuckDB 數據庫的連接。"""
        try:
            db_file = Path(self.db_path)
            # 確保數據庫所在的目錄存在
            db_file.parent.mkdir(parents=True, exist_ok=True)
            self.connection = duckdb.connect(database=str(db_file), read_only=False)
            logger.info(f"成功連接到 DuckDB 數據庫: {self.db_path}")
        except Exception as e:
            logger.error(
                f"連接到 DuckDB 數據庫 {self.db_path} 失敗: {e}", exc_info=True
            )
            raise

    def write_dataframe(
        self,
        df: pd.DataFrame,
        table_name: str,
        if_exists: str = "replace",
        create_index: bool = True,
    ):
        """
        將 Pandas DataFrame 寫入到數據庫中的指定數據表。

        Args:
            df (pd.DataFrame): 要寫入的 DataFrame。
            table_name (str): 目標數據表的名稱。
            if_exists (str): 如果表已存在時的操作 ('fail', 'replace', 'append')。
                             預設為 'replace'。
            create_index (bool): 是否在 DataFrame 的索引上創建數據庫索引。
                                 預設為 True。
        """
        if self.connection is None:
            logger.error("數據庫未連接，無法寫入 DataFrame。")
            raise ConnectionError("數據庫未連接。")

        if df.empty:
            logger.warning(f"傳入的 DataFrame 為空，不會寫入到數據表 '{table_name}'。")
            return

        try:
            # DuckDB 的 to_table 功能會自動處理 if_exists
            # 我們需要先註冊 DataFrame 為一個臨時視圖，然後用 CREATE OR REPLACE TABLE 寫入
            # 這樣更穩健

            temp_view_name = f"temp_view_{table_name}"
            self.connection.register(temp_view_name, df)

            if if_exists == "replace":
                self.connection.execute(
                    f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM {temp_view_name}"
                )
            elif if_exists == "append":
                self.connection.execute(
                    f"INSERT INTO {table_name} SELECT * FROM {temp_view_name}"
                )
            else:  # 'fail'
                self.connection.execute(
                    f"CREATE TABLE {table_name} AS SELECT * FROM {temp_view_name}"
                )

            logger.info(
                f"成功將 {len(df)} 筆記錄寫入到數據表 '{table_name}' (模式: {if_exists})。"
            )

            if create_index and df.index.name:
                index_name = df.index.name
                # DuckDB 會自動為 PRIMARY KEY 創建索引，但這裡我們為日期索引創建一個常規索引
                # 確保索引名稱是有效的 SQL 標識符
                safe_index_name = "".join(c if c.isalnum() else "_" for c in index_name)
                self.connection.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{safe_index_name} ON {table_name} ({safe_index_name})"
                )
                logger.info(
                    f"在數據表 '{table_name}' 的 '{index_name}' 欄位上創建索引。"
                )

        except Exception as e:
            logger.error(
                f"寫入 DataFrame 到數據表 '{table_name}' 失敗: {e}", exc_info=True
            )
            raise
        finally:
            # 清理臨時視圖
            self.connection.unregister(temp_view_name)

    def close(self):
        """關閉數據庫連接。"""
        if self.connection:
            self.connection.close()
            logger.info(f"已關閉到數據庫 {self.db_path} 的連接。")
            self.connection = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    # 配置日誌以進行本地測試
    logging.basicConfig(level=logging.INFO)

    # 創建一個模擬的 DataFrame
    mock_df = pd.DataFrame(
        {"value1": [1, 2, 3], "value2": [4.0, 5.0, 6.0]},
        index=pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
    )
    mock_df.index.name = "Date"

    # 使用 with 語句自動管理連接
    try:
        with DBManager() as db_manager:
            print(f"--- [測試] 使用數據庫: {db_manager.db_path} ---")

            # 測試寫入
            print("\n--- 測試寫入 DataFrame (模式: replace) ---")
            db_manager.write_dataframe(mock_df, "test_table")

            # 測試讀取驗證
            result_df = db_manager.connection.table("test_table").to_df()
            print("\n從數據庫讀取回來的數據:")
            print(result_df)

            assert len(result_df) == len(mock_df)
            print("\n寫入與讀取驗證成功！")

    except Exception as e:
        print(f"\n測試過程中發生錯誤: {e}")
