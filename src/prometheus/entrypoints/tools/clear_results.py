import os
import shutil
from src.prometheus.core.logging.log_manager import LogManager

logger = LogManager.get_instance().get_logger("ClearResults")

RESULTS_DB_PATH = "output/results.sqlite"
QUEUE_DIR = "data/queues"
LOG_DIR = "data/logs"
CHECKPOINT_DIR = "data/checkpoints"
REPORTS_DIR = "data/reports"


def clear_all_results():
    """
    清除所有生成的結果、佇列、日誌和檢查點。
    """
    logger.info("開始清除所有執行數據...")

    def remove_path(path_str, is_dir=False):
        if is_dir:
            if os.path.isdir(path_str):
                shutil.rmtree(path_str)
                logger.info(f"已刪除並清空目錄: {path_str}")
        else:
            if os.path.exists(path_str):
                os.remove(path_str)
                logger.info(f"已刪除檔案: {path_str}")

    try:
        remove_path(RESULTS_DB_PATH, is_dir=False)
        remove_path(QUEUE_DIR, is_dir=True)
        remove_path(LOG_DIR, is_dir=True)
        remove_path(CHECKPOINT_DIR, is_dir=True)
        remove_path(REPORTS_DIR, is_dir=True)

        # 重建空目錄
        os.makedirs(QUEUE_DIR, exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)
        os.makedirs(CHECKPOINT_DIR, exist_ok=True)
        os.makedirs(REPORTS_DIR, exist_ok=True)

        logger.info("清除程序完成。")
    except Exception as e:
        logger.error(f"清除過程中發生錯誤: {e}", exc_info=True)
