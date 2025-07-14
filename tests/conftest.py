import pytest
import os
import sys
from src.core.context import AppContext, QUEUE_DB_PATH
from src.core.logger import LogManager
from src.apps.tools.clear_results import clear_results

# 將專案根目錄添加到 sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

@pytest.fixture(scope="function")
def app_context() -> AppContext:
    """
    「測試上下文工廠」 Fixture。
    在每個測試函數執行前，此 Fixture 會：
    1. 徹底清理舊的資料庫和任務佇列。
    2. 建立一個全新的、隔離的 AppContext 實例。
    3. 將此實例提供給測試函數使用。
    """
    # 1. 執行清理
    # 使用一個臨時的 LogManager 進行清理操作
    cleanup_log_manager = LogManager(db_path="output/cleanup.log.db", archive_dir="output/log_archive")
    clear_results(AppContext(log_manager=cleanup_log_manager))
    if os.path.exists(QUEUE_DB_PATH):
        os.remove(QUEUE_DB_PATH)

    # 2. 建立新的、乾淨的上下文
    test_log_manager = LogManager(db_path="output/test.log.db", archive_dir="output/log_archive")
    context = AppContext(log_manager=test_log_manager)

    # 3. 將上下文交付給測試
    yield context

    # 4. 測試結束後，可以執行額外的清理 (可選)
    test_log_manager.log("INFO", "測試會話結束。")
