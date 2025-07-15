# core/pipelines/pipeline.py
from __future__ import annotations

import logging
from typing import List

from prometheus.core.pipelines.base_step import BaseETLStep


class DataPipeline:
    """
    一個可組合的數據處理管線執行器。
    它可以按順序執行一系列的 ETL 步驟。
    """

    def __init__(self, steps: List[BaseETLStep]):
        """
        初始化數據管線。

        Args:
            steps: 一個包含多個 BaseETLStep 子類實例的列表。
        """
        self._steps = steps
        self.logger = logging.getLogger(self.__class__.__name__)

    def run(self) -> None:
        """
        執行完整的数据處理流程。
        """
        self.logger.info(f"數據管線開始執行，共 {len(self._steps)} 個步驟。")
        data = None
        # step_name 在循環外部可能未定義，因此在此處初始化
        step_name = "Unknown"
        try:
            for i, step in enumerate(self._steps, 1):
                # 修正: 獲取類名應為 step.__class__.__name__
                step_name = step.__class__.__name__
                self.logger.info(
                    f"--- [步驟 {i}/{len(self._steps)}]：正在執行 {step_name} ---"
                )
                data = step.execute(data)
                self.logger.info(f"步驟 {step_name} 執行完畢。")

            self.logger.info("數據管線所有步驟均已成功執行。")
            return data  # 返回最後一個步驟的結果

        except Exception as e:
            self.logger.error(
                f"數據管線在執行步驟 '{step_name}' 時發生嚴重錯誤：{e}", exc_info=True
            )
            # 考慮到管線執行失敗時的健壯性，這裡可以選擇重新拋出異常
            # 或者根據需求決定是否要抑制異常並繼續（儘管通常建議拋出）
            raise
