# apps/run_stress_index.py
from core.pipelines.pipeline import DataPipeline
from core.pipelines.steps.financial_steps import CalculateStressIndexStep

def main():
    """配置並運行壓力指數計算管線"""
    print("--- [App] Initializing Stress Index Pipeline ---")

    stress_index_pipeline = DataPipeline(steps=[
        CalculateStressIndexStep(),
    ])

    result = stress_index_pipeline.run()
    print(f"--- [App] Stress Index Pipeline finished with result: {result} ---")

if __name__ == "__main__":
    main()
