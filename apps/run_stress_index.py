# apps/run_stress_index.py
from core.logger import get_logger
from core.pipelines.pipeline import DataPipeline
from core.pipelines.steps.financial_steps import CalculateStressIndexStep

logger = get_logger(__name__)


def main():
    """配置並運行壓力指數計算管線"""
    logger.info("Initializing Stress Index Pipeline...")

    stress_index_pipeline = DataPipeline(
        steps=[
            CalculateStressIndexStep(),
        ]
    )

    result = stress_index_pipeline.run()
    logger.info(f"Stress Index Pipeline finished with result: {result}")


if __name__ == "__main__":
    main()
