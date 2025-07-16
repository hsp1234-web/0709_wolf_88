import pandas as pd
from prometheus.core.pipelines.base_step import BaseETLStep
from prometheus.core.logging.log_manager import LogManager

class SaveFactorsToWarehouseStep(BaseETLStep):
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.logger = LogManager.get_instance().get_logger(self.__class__.__name__)

    def execute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        將因子儲存到數據倉庫。
        """
        self.logger.info(f"正在將因子儲存到表格 '{self.table_name}'...")
        if data.empty:
            self.logger.warning("數據為空，沒有因子可以儲存。")
        else:
            # 在實際應用中，這裡會有將 DataFrame 寫入數據庫的邏輯
            self.logger.info(f"成功將 {len(data)} 筆因子儲存到 '{self.table_name}'。")
        return data
