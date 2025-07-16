# core/pipelines/pipeline.py
from __future__ import annotations

import logging
from typing import List, Any
import pandas as pd

from prometheus.core.pipelines.base_step import BaseETLStep, BaseStep


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

    async def run(self, initial_data=None, context: dict | None = None) -> None:
        """
        執行完整的数据處理流程。
        """
        import asyncio
        data = initial_data
        if context is None:
            context = {}

        self.logger.info(f"數據管線開始執行，共 {len(self._steps)} 個步驟。")
        # step_name 在循環外部可能未定義，因此在此處初始化
        step_name = "Unknown"
        try:
            for i, step in enumerate(self._steps, 1):
                # 修正: 獲取類名應為 step.__class__.__name__
                step_name = step.__class__.__name__
                self.logger.info(
                    f"--- [步驟 {i}/{len(self._steps)}]：正在執行 {step_name} ---"
                )
                if asyncio.iscoroutinefunction(step.execute):
                    data = await step.execute(data, **context)
                else:
                    data = step.execute(data, **context)
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


class Pipeline:
    """
    一個同步的、可組合的數據處理管線執行器。
    """

    def __init__(self, steps: List[BaseStep]):
        """
        初始化管線。

        :param steps: 一個包含多個 BaseStep 子類實例的列表。
        """
        self.steps = steps
        self.logger = logging.getLogger(self.__class__.__name__)
        self.context = {}

    async def run(self, initial_data: Any = None) -> Any:
        """
        執行完整的數據處理流程。
        """
        data = initial_data
        self.logger.info(f"Pipeline 開始執行，共 {len(self.steps)} 個步驟。")

        for i, step in enumerate(self.steps, 1):
            step_name = step.__class__.__name__
            self.logger.info(f"--- [步驟 {i}/{len(self.steps)}]：正在執行 {step_name} ---")

            try:
                if isinstance(data, pd.DataFrame):
                    result = step.run(data, self.context)
                    if hasattr(result, '__aiter__'):
                        processed_list = [item async for item in result]
                        data = pd.concat(processed_list) if all(isinstance(i, pd.DataFrame) for i in processed_list) else processed_list
                    else:
                        data = await result
                elif isinstance(data, list):
                    processed_list = [await step.run(item, self.context) for item in data]
                    data = pd.concat(processed_list) if all(isinstance(i, pd.DataFrame) for i in processed_list) else processed_list
                else:
                    data = await step.run(data, self.context)

                self.logger.info(f"步驟 {step_name} 執行完畢。")

            except Exception as e:
                self.logger.error(
                    f"Pipeline 在執行步驟 '{step_name}' 時發生嚴重錯誤：{e}", exc_info=True
                )
                raise

        self.logger.info("Pipeline 所有步驟均已成功執行。")
        return data
