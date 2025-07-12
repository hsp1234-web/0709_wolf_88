# core/pipelines/base_step.py
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseETLStep(ABC):
    """
    數據處理管線中單個步驟的抽象基礎類。
    每個繼承此類的具體步驟，都必須實現一個 execute 方法。
    """

    @abstractmethod
    def execute(self, data: pd.DataFrame | None = None) -> pd.DataFrame | None:
        """
        執行此步驟的核心邏輯。

        Args:
            data: 上一個步驟傳入的數據，對於第一個步驟，此項為 None。

        Returns:
            處理完成後，傳遞給下一步驟的數據。如果此步驟為終點，可返回 None。
        """
        pass
