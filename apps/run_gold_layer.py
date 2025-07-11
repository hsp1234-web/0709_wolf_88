# apps/run_gold_layer.py
from core.pipelines.pipeline import DataPipeline
from core.pipelines.steps.financial_steps import BuildGoldLayerStep
# 根據實際情況，可能需要其他步驟，如 Loader
# from core.pipelines.steps.loaders import SomeLoaderStep

def main():
    """配置並運行黃金層數據建構管線"""
    print("--- [App] Initializing Gold Layer Pipeline ---")

    gold_layer_pipeline = DataPipeline(steps=[
        # SomeLoaderStep(), # 範例：第一步可能是加載數據
        BuildGoldLayerStep(),
    ])

    result = gold_layer_pipeline.run()
    print(f"--- [App] Gold Layer Pipeline finished with result: {result} ---")

if __name__ == "__main__":
    main()
