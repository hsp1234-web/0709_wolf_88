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

    def run(self, data, context):
        """
        執行載入步驟。

        :param data: 上一個步驟的數據。
        :param context: 管線上下文。
        """
        all_factors = context.get('all_factors')
        target_series = all_factors[[self.target_factor]].dropna()
        context.set('target_series', target_series[self.target_factor])
        return data
