import pandas as pd
from prometheus.core.pipelines.pipeline import DataPipeline
from prometheus.core.pipelines.base_step import BaseETLStep
from prometheus.core.pipelines.steps.loaders import LoadRawDataFromWarehouseStep
from prometheus.pipelines.steps.aggregators import MultiSourceAggregatorStep
from prometheus.core.pipelines.steps.savers import SaveFactorsToWarehouseStep
from prometheus.core.engines.bond_factor_engine import BondFactorEngine

class CalculateBondFactorsStep(BaseETLStep):
    def __init__(self):
        self.engine = BondFactorEngine()

    def execute(self, data: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame | None:
        if data is None or data.empty:
            return pd.DataFrame()

        # 呼叫因子引擎進行計算
        factor_df = self.engine.calculate(data)
        return factor_df

p3_bond_factor_pipeline = DataPipeline(
    steps=[
        LoadRawDataFromWarehouseStep(),
        MultiSourceAggregatorStep(
            auxiliary_tickers={
                "yield_curve_slope": "T10Y2Y",
                "credit_spread": "BAMLH0A0HYM2",
                "real_yield": "DFII10",
            }
        ),
        CalculateBondFactorsStep(),
        SaveFactorsToWarehouseStep(table_name="bond_specific_factors"),
    ]
)
