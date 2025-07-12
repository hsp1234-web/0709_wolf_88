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

from core.pipelines.pipeline import DataPipeline
from core.pipelines.steps.financial_steps import CalculateStressIndexStep

def main(log_manager):
    """配置並運行壓力指數計算管線"""
    log_manager.log("INFO", "Initializing Stress Index Pipeline...")

    stress_index_pipeline = DataPipeline(
        steps=[
            CalculateStressIndexStep(),
        ]
    )

    result = stress_index_pipeline.run()

    if result and result.get("status") == "success":
        log_manager.log("INFO", "✅ 壓力指數計算成功。")
        log_manager.log("INFO", f"   最新壓力指數值: {result.get('stress_index', 'N/A'):.2f}")
    else:
        log_manager.log("ERROR", f"❌ 壓力指數計算失敗。")
        log_manager.log("ERROR", f"   原因: {result.get('reason', '未知錯誤')}")

    log_manager.log("INFO", f"Stress Index Pipeline finished with raw result: {result}")


if __name__ == "__main__":
    # 為了能夠獨立運行此腳本進行測試，我們需要一個備用的 LogManager
    from core.logger import LogManager
    output_dir = project_root / "output"
    log_db_path = output_dir / "logs" / "standalone_test.sqlite"
    archive_dir = output_dir / "logs" / "archive"

    dummy_logger = LogManager(db_path=log_db_path, archive_dir=archive_dir)
    main(log_manager=dummy_logger)
    dummy_logger.archive_to_file()
