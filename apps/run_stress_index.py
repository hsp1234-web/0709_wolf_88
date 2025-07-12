# apps/run_stress_index.py
import sys
from pathlib import Path

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    # Fallback for environments where __file__ is not defined
    project_root = Path.cwd()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
# --- 標準化「路徑自我校正」樣板碼 END ---

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

    if result and result.get("status") == "success":
        logger.info("✅ 壓力指數計算成功。")
        logger.info(f"   最新壓力指數值: {result.get('stress_index', 'N/A'):.2f}")
    else:
        logger.error(f"❌ 壓力指數計算失敗。")
        logger.error(f"   原因: {result.get('reason', '未知錯誤')}")

    logger.info(f"Stress Index Pipeline finished with raw result: {result}")


if __name__ == "__main__":
    main()
