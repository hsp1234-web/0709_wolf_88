# -*- coding: utf-8 -*-
from prometheus.core.pipelines.base_step import BaseStep
from prometheus.services.factor_simulator import FactorSimulator

class TrainFactorSimulatorStep(BaseStep):
    """
    訓練因子模擬器模型。
    """

    def __init__(self, target_factor: str):
        """
        初始化 TrainFactorSimulatorStep。

        :param target_factor: 要模擬的目標因子名稱。
        """
        super().__init__()
        self.target_factor = target_factor
        self.simulator = FactorSimulator()

    async def run(self, data, context):
        """
        執行訓練步驟。

        :param data: 上一個步驟的數據。
        :param context: 管線上下文。
        """
        all_factors = context.get('all_factors')
        target_series = context.get('target_series')

        if target_series.empty:
            print(f"警告：目標因子 '{self.target_factor}' 的數據為空，跳過模型訓練。")
            return data

        # 排除目標因子本身作為預測變數
        predictors_df = all_factors.drop(columns=[self.target_factor.lower()])

        self.simulator.train(target_series, predictors_df)
        return data
