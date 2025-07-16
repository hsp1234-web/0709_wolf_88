import duckdb
import os
import pandas as pd
from prometheus.core.logging.log_manager import LogManager

class DBManager:
    def __init__(self, db_path: str = "data/analytics_warehouse/factors.duckdb"):
        self.db_path = db_path
        self.logger = LogManager.get_instance().get_logger(self.__class__.__name__)

        # 確保數據庫目錄存在
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

    def save_data(self, data: pd.DataFrame, table_name: str):
        """
        一個類型感知的穩健寫入函數，能夠自動偵察、演進並寫入數據。
        """
        if data.empty:
            self.logger.warning("數據為空，沒有可以儲存的內容。")
            return

        try:
            with duckdb.connect(self.db_path) as con:
                db_columns = self._get_table_columns(con, table_name)

                if not db_columns:
                    self.logger.info(f"表格 '{table_name}' 不存在，將根據 DataFrame 結構創建。")
                    con.register('df_to_create', data)
                    con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df_to_create")
                    self.logger.info(f"成功創建表格 '{table_name}' 並儲存了 {len(data)} 筆數據。")
                else:
                    df_columns = data.columns.tolist()
                    new_columns = set(df_columns) - set(db_columns)

                    if new_columns:
                        self.logger.info(f"偵測到新欄位: {new_columns}。正在演進表格結構...")
                        for col in new_columns:
                            col_dtype = data[col].dtype
                            sql_type = self._map_dtype_to_sql(col_dtype)
                            con.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} {sql_type};")
                        self.logger.info("表格結構演進完成。")
                        db_columns = self._get_table_columns(con, table_name)

                    # For existing tables, upsert data
                    # 1. Create a temporary table with the new data
                    con.register('new_data_view', data)
                    con.execute("CREATE OR REPLACE TEMP TABLE new_data_temp AS SELECT * FROM new_data_view")

                    # 2. Delete rows from the main table that have matching keys in the temp table
                    # Assuming 'symbol' and 'date' are the composite primary key
                    if 'symbol' in db_columns and 'date' in db_columns:
                        con.execute(f"""
                            DELETE FROM {table_name}
                            WHERE (symbol, date) IN (SELECT symbol, date FROM new_data_temp)
                        """)
                        self.logger.info(f"從 '{table_name}' 中刪除了重複的舊數據。")

                    # 3. Insert all data from the temp table
                    cols_to_insert = ", ".join(data.columns)
                    con.execute(f"INSERT INTO {table_name} ({cols_to_insert}) SELECT {cols_to_insert} FROM new_data_temp")

                    self.logger.info(f"成功將 {len(data)} 筆數據寫入到 '{table_name}'。")
        except Exception as e:
            self.logger.error(f"儲存數據時發生錯誤: {e}", exc_info=True)
            raise

    def _get_table_columns(self, con, table_name):
        """查詢並返回資料庫表的欄位列表。"""
        try:
            table_info = con.execute(f"PRAGMA table_info('{table_name}')").fetchall()
            return [info[1] for info in table_info]
        except duckdb.CatalogException:
            return []

    def _map_dtype_to_sql(self, dtype):
        """將 Pandas 的 dtype 轉換為 SQL 類型字串。"""
        if pd.api.types.is_integer_dtype(dtype):
            return 'BIGINT'
        elif pd.api.types.is_float_dtype(dtype):
            return 'DOUBLE'
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            return 'TIMESTAMP'
        elif pd.api.types.is_string_dtype(dtype) or pd.api.types.is_object_dtype(dtype):
            return 'VARCHAR'
        else:
            return 'VARCHAR'
