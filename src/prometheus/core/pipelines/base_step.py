# core/pipelines/base_step.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

import pandas as pd


class BaseStep(ABC):
    """
    同步數據處理管線中單個步驟的抽象基礎類。
    """

    @abstractmethod
    async def run(self, data: Any, context: Dict[str, Any]) -> Any:
        """
        執行此步驟的核心邏輯。

        :param data: 上一個步驟傳入的數據。
        :param context: Pipeline 的共享上下文。
        :return: 處理完成後，傳遞給下一步驟的數據。
        """
        pass


class BaseETLStep(BaseStep):
    """
    數據處理管線中單個步驟的抽象基礎類。
    每個繼承此類的具體步驟，都必須實現一個 execute 方法。
    """

    @abstractmethod
    def execute(self, data: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame | None:
        """
        執行此步驟的核心邏輯。

        Args:
            data: 上一個步驟傳入的數據，對於第一個步驟，此項為 None。
            **kwargs: 可選的關鍵字參數。

        Returns:
            處理完成後，傳遞給下一步驟的數據。如果此步驟為終點，可返回 None。
        """
        pass

    def run(self, data: Any, context: Dict[str, Any]) -> Any:
        return self.execute(data, **context)
