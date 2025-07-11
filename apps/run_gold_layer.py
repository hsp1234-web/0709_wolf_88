# apps/run_gold_layer.py
from core.pipelines.pipeline import DataPipeline
from core.pipelines.steps.financial_steps import BuildGoldLayerStep
from core.logger import get_logger

# 獲取專為此應用配置的 logger
logger = get_logger(__name__)

def main():
    """配置並運行黃金層數據建構管線"""
    logger.info("Initializing Gold Layer Pipeline...")

    gold_layer_pipeline = DataPipeline(steps=[
        BuildGoldLayerStep(),
    ])

    result = gold_layer_pipeline.run()
    logger.info(f"Gold Layer Pipeline finished with result: {result}")

if __name__ == "__main__":
    main()
