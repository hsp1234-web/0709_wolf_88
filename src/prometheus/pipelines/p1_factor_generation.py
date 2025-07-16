# 檔案: src/prometheus/pipelines/p1_factor_generation.py
# --- 抽象程式碼草圖 ---

# 概念：
# 修改現有管線，加入新的驗證步驟。

from prometheus.core.pipelines.pipeline import DataPipeline
from prometheus.core.pipelines.steps.loaders import LoadRawDataFromWarehouseStep
# from prometheus.core.pipelines.steps.factor_calculators import CalculateUniversalFactorsStep
from prometheus.core.pipelines.steps.verifiers import VerifyDataFrameNotEmptyStep
from prometheus.core.pipelines.steps.savers import SaveFactorsToWarehouseStep
from prometheus.core.pipelines.base_step import BaseETLStep
import pandas as pd

from prometheus.core.engines.universal_factor_engine import UniversalFactorEngine

class CalculateUniversalFactorsStep(BaseETLStep):
    def __init__(self):
        self.engine = UniversalFactorEngine()

    def execute(self, data: pd.DataFrame | None = None) -> pd.DataFrame | None:
        if data is None or data.empty:
            return pd.DataFrame()

        # 呼叫因子引擎進行計算
        factor_df = self.engine.calculate(data)
        return factor_df


# 重新定義管線，加入驗證步驟
p1_factor_generation_pipeline = DataPipeline(
    steps=[
        LoadRawDataFromWarehouseStep(ticker="SPY"),
        CalculateUniversalFactorsStep(),
        # 在計算之後、儲存之前，注入真理血清
        VerifyDataFrameNotEmptyStep(),
        SaveFactorsToWarehouseStep(table_name="universal_factors"),
    ]
)
