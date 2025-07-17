# tests/integration/pipelines/test_example_flow.py
import pandas as pd

from prometheus.core.pipelines.base_step import BaseETLStep  # 修正導入
from prometheus.core.pipelines.pipeline import DataPipeline


# 模擬一個 Loader 步驟
class MockLoader(BaseETLStep):  # 修正繼承
    def execute(self, data=None):  # 修正方法名稱以匹配 BaseETLStep
        # 在真實場景中，這裡會從 API 或檔案讀取
        print("--- [Step 1] Executing MockLoader ---")
        d = {
            "timestamp": pd.to_datetime(["2025-07-11 10:00:00", "2025-07-11 10:00:01"]),
            "value": [10, 11],
        }
        return pd.DataFrame(d).set_index("timestamp")


# 模擬一個 Aggregator 步驟
class MockAggregator(BaseETLStep):  # 修正繼承
    def execute(self, data):  # 修正方法名稱以匹配 BaseETLStep
        print("--- [Step 2] Executing MockAggregator ---")
        # 在真實場景中，這裡會執行複雜的聚合邏輯
        return data["value"].sum()


def test_full_etl_flow_replaces_old_pipeline():
    """
    此整合測試驗證了基於 core.pipelines 的標準流程，
    其功能等同於已被廢棄的 apps/etl_pipeline。
    """
    print("\n--- [Test] Verifying core pipeline functionality ---")

    # 1. 定義管線步驟
    pipeline_steps = [
        MockLoader(),
        MockAggregator(),
    ]

    import asyncio
    # 2. 實例化並執行管線
    pipeline = DataPipeline(steps=pipeline_steps)
    result = asyncio.run(pipeline.run())

    # 3. 驗證最終結果
    expected_result = 21
    assert (
        result == expected_result
    ), f"Pipeline result '{result}' did not match expected '{expected_result}'"
    print(f"--- [Success] Pipeline final result is {result}, as expected. ---")
