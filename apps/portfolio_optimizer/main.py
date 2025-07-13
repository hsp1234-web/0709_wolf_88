# -*- coding: utf-8 -*-
"""
模擬的投資組合優化器應用主模組
"""

import sys
from pathlib import Path

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    project_root = Path.cwd()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
# --- 標準化「路徑自我校正」樣板碼 END ---

from core.logger import LogManager


def run_optimization(log_manager: LogManager):
    """
    模擬執行投資組合優化的核心業務邏輯。
    """
    log_manager.log(
        "INFO", "投資組合優化器：核心業務邏輯 `run_optimization` 已開始執行..."
    )
    log_manager.log(
        "INFO", "投資組合優化器：核心業務邏輯 `run_optimization` 已成功完成。"
    )
    return {"status": "success", "message": "投資組合優化執行完畢"}


if __name__ == "__main__":
    # Setup for standalone execution
    output_dir = project_root / "output"
    log_db_path = output_dir / "logs" / "standalone_test.sqlite"
    archive_dir = output_dir / "logs" / "archive"
    dummy_logger = LogManager(db_path=log_db_path, archive_dir=archive_dir)

    dummy_logger.log("INFO", "--- 模擬直接執行 portfolio_optimizer.main ---")
    try:
        run_optimization(log_manager=dummy_logger)
    except Exception as e:
        dummy_logger.log("ERROR", f"執行投資組合優化時發生未預期錯誤: {e}")
    finally:
        dummy_logger.archive_to_file()
