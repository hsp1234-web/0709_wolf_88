import pandas as pd
from prometheus.core.pipelines.base_step import BaseETLStep
from prometheus.core.logging.log_manager import LogManager
import duckdb
import os

class SaveFactorsToWarehouseStep(BaseETLStep):
    def __init__(self, table_name: str, db_path: str = "data/analytics_warehouse/factors.duckdb"):
        self.table_name = table_name
        self.db_path = db_path
        self.logger = LogManager.get_instance().get_logger(self.__class__.__name__)

        # 確保數據庫目錄存在
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

    def execute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        將因子儲存到數據倉庫。
        """
        self.logger.info(f"正在將因子儲存到數據庫 '{self.db_path}' 的表格 '{self.table_name}'...")
        if data.empty:
            self.logger.warning("數據為空，沒有因子可以儲存。")
        else:
            try:
                with duckdb.connect(self.db_path) as con:
                    # 如果表格已存在，則先刪除
                    con.execute(f"DROP TABLE IF EXISTS {self.table_name}")
                    con.register('factors_df', data.reset_index())
                    con.execute(f"CREATE TABLE {self.table_name} AS SELECT * FROM factors_df")
                    self.logger.info(f"成功將 {len(data)} 筆因子儲存到 '{self.table_name}'。")
            except Exception as e:
                self.logger.error(f"儲存因子時發生錯誤: {e}", exc_info=True)
                raise
        return data
