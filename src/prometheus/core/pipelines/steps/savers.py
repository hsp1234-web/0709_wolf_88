import pandas as pd
from prometheus.core.pipelines.base_step import BaseETLStep, BaseStep
from prometheus.core.logging.log_manager import LogManager
import duckdb
import os
from typing import Dict, Any
from src.prometheus.core.db.db_manager import DBManager


class SaveFactorsToWarehouseStep(BaseETLStep):
    def __init__(self, table_name: str, db_path: str = "data/analytics_warehouse/factors.duckdb"):
        self.table_name = table_name
        self.db_path = db_path
        self.logger = LogManager.get_instance().get_logger(self.__class__.__name__)

        # 確保數據庫目錄存在
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

    def execute(self, data: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        將因子儲存到數據倉庫。
        """
        ticker = kwargs.get("ticker")
        if not ticker:
            self.logger.warning("在上下文中找不到 ticker，無法儲存。")
            return data

        self.logger.info(f"正在將因子儲存到數據庫 '{self.db_path}' 的表格 '{self.table_name}' for ticker {ticker}...")
        if data.empty:
            self.logger.warning("數據為空，沒有因子可以儲存。")
        else:
            try:
                with duckdb.connect(self.db_path) as con:
                    # Add ticker column
                    data_to_save = data.copy()
                    data_to_save['ticker'] = ticker

                    # Check if table exists
                    res = con.execute(f"SELECT table_name FROM information_schema.tables WHERE table_name = '{self.table_name}'").fetchone()
                    if res: # Table exists, so append
                        # Remove existing data for the same ticker to avoid duplicates
                        con.execute(f"DELETE FROM {self.table_name} WHERE ticker = '{ticker}'")
                        con.register('factors_df', data_to_save.reset_index())
                        con.execute(f"INSERT INTO {self.table_name} SELECT * FROM factors_df")
                    else: # Table does not exist, so create
                        con.register('factors_df', data_to_save.reset_index())
                        con.execute(f"CREATE TABLE {self.table_name} AS SELECT * FROM factors_df")

                    self.logger.info(f"成功將 {len(data)} 筆因子儲存到 '{self.table_name}' for ticker {ticker}。")
            except Exception as e:
                self.logger.error(f"儲存因子時發生錯誤: {e}", exc_info=True)
                raise
        return data


class SaveToWarehouseStep(BaseStep):
    """
    一個 Pipeline 步驟，用於將 DataFrame 儲存到資料倉儲。
    """

    def __init__(self, db_manager: DBManager, table_name: str):
        """
        初始化步驟。

        :param db_manager: 資料庫管理器。
        :param table_name: 要儲存的目標表格名稱。
        """
        self.db_manager = db_manager
        self.table_name = table_name
        self.logger = LogManager.get_instance().get_logger(self.__class__.__name__)

    async def run(self, data: pd.DataFrame, context: Dict[str, Any]) -> pd.DataFrame:
        """
        將 DataFrame 儲存到資料倉儲。

        :param data: 要儲存的 DataFrame。
        :param context: Pipeline 的共享上下文。
        :return: 未經修改的原始 DataFrame。
        """
        if data.empty:
            self.logger.warning("數據為空，沒有可以儲存的內容。")
            return data

        try:
            self.logger.info(f"正在將 {len(data)} 筆數據儲存到表格 '{self.table_name}'...")
            self.db_manager.save_data(data, self.table_name)
            self.logger.info("數據儲存成功。")
        except Exception as e:
            self.logger.error(f"儲存數據到倉儲時發生錯誤: {e}", exc_info=True)
            raise

        return data
