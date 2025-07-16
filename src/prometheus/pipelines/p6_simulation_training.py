# -*- coding: utf-8 -*-
from prometheus.core.pipelines.pipeline import Pipeline
from prometheus.pipelines.steps.load_all_factors_step import LoadAllFactorsStep
from prometheus.pipelines.steps.load_historical_target_step import LoadHistoricalTargetStep
from prometheus.pipelines.steps.train_factor_simulator_step import TrainFactorSimulatorStep

import asyncio

async def main(target_factor: str):
    """
    執行因子模擬模型訓練生產線。

    :param target_factor: 要模擬的目標因子名稱。
    """
    pipeline = Pipeline(
        steps=[
            LoadAllFactorsStep(),
            LoadHistoricalTargetStep(target_factor=target_factor),
            TrainFactorSimulatorStep(target_factor=target_factor),
        ]
    )
    await pipeline.run()

def run_main(target_factor: str):
    asyncio.run(main(target_factor))

if __name__ == "__main__":
    # 這裡可以添加一個簡單的測試，例如：
    # main(target_factor="T10Y2Y")
    pass
