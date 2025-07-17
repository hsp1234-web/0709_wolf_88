# -*- coding: utf-8 -*-
from prometheus.core.pipelines.base_step import BaseStep

class LoadHistoricalTargetStep(BaseStep):
    """
    載入目標因子的歷史數據。
    """

    def __init__(self, target_factor: str):
        """
        初始化 LoadHistoricalTargetStep。

        :param target_factor: 要載入的目標因子名稱。
        """
        super().__init__()
        self.target_factor = target_factor

    async def run(self, data, context):
        """
        執行載入步驟。

        :param data: 上一個步驟的數據。
        :param context: 管線上下文。
        """
        all_factors = context.get('all_factors')
        target_factor_lower = self.target_factor.lower()

        if target_factor_lower not in all_factors.columns:
            raise KeyError(f"目標因子 '{target_factor_lower}' 在 all_factors 中找不到。可用的因子有: {all_factors.columns.tolist()}")

        target_series = all_factors[[target_factor_lower]].dropna()
        context['target_series'] = target_series[target_factor_lower]
        return data
