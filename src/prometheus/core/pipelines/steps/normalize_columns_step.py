# src/prometheus/core/pipelines/steps/normalize_columns_step.py

import pandas as pd
from typing import Dict, Any
import logging

from prometheus.core.pipelines.base_step import BaseStep

logger = logging.getLogger(__name__)

class NormalizeColumnsStep(BaseStep):
    """
    一個 Pipeline 步驟，用於將 DataFrame 的所有欄位名稱標準化為小寫。
    它同時實現了 run 和 execute 方法，以兼容不同的 Pipeline 設計。
    """

    def __init__(self):
        """
        初始化步驟。
        """
        pass

    def _normalize(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        執行標準化的核心邏輯。
        """
        if not isinstance(data, pd.DataFrame) or data.empty:
            logger.warning("輸入的數據不是一個有效的 DataFrame 或為空，跳過標準化。")
            return data

        logger.info("正在將所有欄位名稱轉換為小寫...")
        original_columns = data.columns.tolist()
        data.columns = [col.lower() for col in original_columns]
        new_columns = data.columns.tolist()

        if original_columns != new_columns:
            logger.info(f"欄位已標準化：從 {original_columns} -> {new_columns}")
        else:
            logger.info("所有欄位名稱已經是小寫，無需更改。")

        return data

    async def run(self, data: pd.DataFrame, context: Dict[str, Any] = None) -> pd.DataFrame:
        """
        異步執行欄位名稱標準化 (兼容 BaseStep)。
        """
        return self._normalize(data)

    def execute(self, data: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        同步執行欄位名稱標準化 (兼容 BaseETLStep)。
        """
        return self._normalize(data)
