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

                    # --- [核心改造] ---
                    # 為了實現穩健的 UPSERT，我們必須在創建時就定義主鍵。
                    # 我們假設 'date' 和 'symbol' 是必然存在的核心欄位。
                    create_sql = f"""
                    CREATE TABLE {table_name} (
                        date TIMESTAMP,
                        symbol VARCHAR,
                        PRIMARY KEY (date, symbol)
                    );
                    """
                    con.execute(create_sql)
                    self.logger.info(f"成功創建表格 '{table_name}' 並定義了 (date, symbol) 複合主鍵。")

                    # 註冊 DataFrame 以便後續插入
                    con.register('df_to_insert', data)

                    # 動態添加其餘欄位
                    initial_cols = {'date', 'symbol'}
                    remaining_cols = [col for col in data.columns if col not in initial_cols]

                    for col in remaining_cols:
                        col_dtype = data[col].dtype
                        sql_type = self._map_dtype_to_sql(col_dtype)
                        con.execute(f"ALTER TABLE {table_name} ADD COLUMN \"{col}\" {sql_type};")

                    # 插入完整數據
                    all_cols = ['date', 'symbol'] + remaining_cols
                    col_names_str = ", ".join(f'"{c}"' for c in all_cols)
                    con.execute(f"INSERT INTO {table_name} ({col_names_str}) SELECT {col_names_str} FROM df_to_insert")

                    self.logger.info(f"成功將 {len(data)} 筆初始數據插入到新創建的 '{table_name}' 表格中。")
                    # 在創建後，重新獲取欄位資訊以進行後續的合併操作
                    db_columns = self._get_table_columns(con, table_name)
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

                    # --- [核心改造] ---
                    # 使用 DuckDB 的 ON CONFLICT (UPSERT) 語法實現高效、原子性的數據合併。
                    con.register('df_to_upsert', data)

                    all_columns = [f'"{c}"' for c in data.columns]
                    update_columns = [col for col in all_columns if col.lower() not in ('"date"', '"symbol"')]

                    if not update_columns:
                        self.logger.warning("沒有需要更新的欄位（除了主鍵），將只執行插入操作。")
                        # 如果只有主鍵，那麼 ON CONFLICT 就不需要 DO UPDATE
                        upsert_sql = f"""
                        INSERT INTO {table_name} ({', '.join(all_columns)})
                        SELECT {', '.join(all_columns)} FROM df_to_upsert
                        ON CONFLICT (date, symbol) DO NOTHING;
                        """
                    else:
                        set_clause = ", ".join([f'{col} = excluded.{col}' for col in update_columns])
                        upsert_sql = f"""
                        INSERT INTO {table_name} ({', '.join(all_columns)})
                        SELECT {', '.join(all_columns)} FROM df_to_upsert
                        ON CONFLICT (date, symbol) DO UPDATE SET
                            {set_clause};
                        """

                    con.execute(upsert_sql)
                    self.logger.info(f"成功將 {len(data)} 筆數據 UPSERT 到 '{table_name}'。")
        except Exception as e:
            self.logger.error(f"儲存數據時發生錯誤: {e}", exc_info=True)
            raise

    def _get_table_columns(self, con, table_name):
        """查詢並返回資料庫表的欄位列表（全部轉為小寫）。"""
        try:
            table_info = con.execute(f"PRAGMA table_info('{table_name}')").fetchall()
            # 將所有列名轉為小寫，以實現不區分大小寫的比較
            return [str(info[1]).lower() for info in table_info]
        except duckdb.CatalogException:
            return []

    def fetch_table(self, table_name: str) -> pd.DataFrame:
        """
        從數據庫中讀取整個表格並返回一個 Pandas DataFrame。

        Args:
            table_name (str): 要讀取的表格名稱。

        Returns:
            pd.DataFrame: 包含表格數據的 DataFrame。如果表格不存在或為空，則返回一個空的 DataFrame。
        """
        try:
            with duckdb.connect(self.db_path, read_only=True) as con:
                # 檢查表格是否存在
                tables = con.execute("SHOW TABLES").fetchall()
                if (table_name,) not in tables:
                    self.logger.warning(f"表格 '{table_name}' 在數據庫中不存在。")
                    return pd.DataFrame()

                df = con.table(table_name).to_df()
                self.logger.info(f"成功從 '{table_name}' 表格中讀取 {len(df)} 筆數據。")
                return df
        except Exception as e:
            self.logger.error(f"讀取表格 '{table_name}' 時發生錯誤: {e}", exc_info=True)
            return pd.DataFrame() # 在出錯時返回一個空的 DataFrame

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
