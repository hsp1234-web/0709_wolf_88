# src/prometheus/core/pipelines/steps/splitters.py

import pandas as pd
import logging
from typing import Dict, Any, List

from src.prometheus.core.pipelines.base_step import BaseStep

logger = logging.getLogger(__name__)


class GroupBySymbolStep(BaseStep):
    """
    一個 Pipeline 步驟，用於將 DataFrame 按 'symbol' 欄位分組。
    """

    async def run(self, data: pd.DataFrame, context: Dict[str, Any]):
        """
        將輸入的 DataFrame 按 'symbol' 分組。

        :param data: 包含 'symbol' 欄位的 DataFrame。
        :param context: Pipeline 的共享上下文。
        :return: 一個 DataFrame 的列表，每個 DataFrame 對應一個 symbol。
        """
        logger.info("正在執行 GroupBySymbolStep...")

        if 'symbol' not in data.columns:
            raise ValueError("輸入的 DataFrame 必須包含 'symbol' 欄位。")

        grouped = data.groupby('symbol')

        logger.info(f"成功將數據分為 {len(grouped)} 組。")
        for _, group in grouped:
            yield group
