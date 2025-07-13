# apps/run_gold_layer.py
import sys
from pathlib import Path

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    project_root = Path.cwd()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
# --- 標準化「路徑自我校正」樣板碼 END ---

from core.pipelines.pipeline import DataPipeline
from core.pipelines.steps.financial_steps import BuildGoldLayerStep


def main(log_manager):
    """配置並運行黃金層數據建構管線"""
    log_manager.log("INFO", "Initializing Gold Layer Pipeline...")

    gold_layer_pipeline = DataPipeline(
        steps=[
            BuildGoldLayerStep(),
        ]
    )

    result = gold_layer_pipeline.run()
    log_manager.log("INFO", f"Gold Layer Pipeline finished with result: {result}")


if __name__ == "__main__":
    from core.logger import LogManager

    output_dir = project_root / "output"
    log_db_path = output_dir / "logs" / "standalone_test.sqlite"
    archive_dir = output_dir / "logs" / "archive"

    dummy_logger = LogManager(db_path=log_db_path, archive_dir=archive_dir)
    main(log_manager=dummy_logger)
    dummy_logger.archive_to_file()
