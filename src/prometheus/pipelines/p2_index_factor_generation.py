import pandas as pd
from prometheus.core.pipelines.pipeline import DataPipeline
from prometheus.core.pipelines.base_step import BaseETLStep
from prometheus.core.pipelines.steps.loaders import LoadRawDataFromWarehouseStep
from prometheus.pipelines.steps.aggregators import MultiSourceAggregatorStep
from prometheus.core.pipelines.steps.savers import SaveFactorsToWarehouseStep
from prometheus.core.engines.index_factor_engine import IndexFactorEngine

class CalculateIndexFactorsStep(BaseETLStep):
    def __init__(self):
        self.engine = IndexFactorEngine()

    def execute(self, data: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame | None:
        if data is None or data.empty:
            return pd.DataFrame()

        # 呼叫因子引擎進行計算
        factor_df = self.engine.calculate(data)
        return factor_df

p2_index_factor_pipeline = DataPipeline(
    steps=[
        LoadRawDataFromWarehouseStep(),
        MultiSourceAggregatorStep(
            auxiliary_tickers={
                "vix": "^VIX",
                "move": "^MOVE",
                "skew": "SKEW",
            }
        ),
        CalculateIndexFactorsStep(),
        SaveFactorsToWarehouseStep(table_name="index_specific_factors"),
    ]
)
