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
        將 DataFrame 儲存到 DuckDB 資料庫。
        """
        if data.empty:
            self.logger.warning("數據為空，沒有可以儲存的內容。")
            return

        try:
            with duckdb.connect(self.db_path) as con:
                # 檢查表格是否存在
                res = con.execute(f"SELECT table_name FROM information_schema.tables WHERE table_name = '{table_name}'").fetchone()
                if res: # 表格存在，附加數據
                    # 刪除與新數據中符號相同的現有數據以避免重複
                    symbols = data['symbol'].unique()
                    for symbol in symbols:
                        con.execute(f"DELETE FROM {table_name} WHERE symbol = '{symbol}'")
                    con.register('new_data_df', data.reset_index())
                    con.execute(f"INSERT INTO {table_name} SELECT * FROM new_data_df")
                else: # 表格不存在，創建它
                    con.register('new_data_df', data.reset_index())
                    con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM new_data_df")

                self.logger.info(f"成功將 {len(data)} 筆數據儲存到 '{table_name}'。")
        except Exception as e:
            self.logger.error(f"儲存數據時發生錯誤: {e}", exc_info=True)
            raise
