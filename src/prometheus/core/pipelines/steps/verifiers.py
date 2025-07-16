# 檔案: src/prometheus/pipelines/steps/verifiers.py
# --- 抽象程式碼草圖 ---

# 概念：
# 一個用於在管線中驗證 DataFrame 完整性的步驟。

import pandas as pd
from prometheus.core.pipelines.base_step import BaseETLStep
from prometheus.core.logging.log_manager import LogManager

class VerifyDataFrameNotEmptyStep(BaseETLStep):
    def __init__(self):
        self.logger = LogManager.get_instance().get_logger(self.__class__.__name__)

    def execute(self, data: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        執行驗證。如果 DataFrame 為空，則拋出致命錯誤。
        """
        self.logger.info("正在進行記憶體驗證...")

        if data.empty:
            # 核心邏輯：如果數據為空，則主動拋出錯誤，中斷管線
            error_message = "管線中斷：前一環節產出的數據為空！"
            self.logger.error(error_message)
            raise ValueError(error_message)

        self.logger.debug("記憶體驗證通過，數據完整。")
        return data # 將未經修改的數據傳遞給下一步
