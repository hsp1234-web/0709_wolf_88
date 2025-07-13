# 檔案: tests/integration/test_full_pipeline.py
import pytest
import threading
import time
import duckdb
import os
from pathlib import Path

from core.logger import LogManager
from core.queue.sqlite_queue import SQLiteQueue
from core.services.backtesting_service import BacktestingService
from apps.tools.task_adder_app import add_tasks
from apps.tools.clear_results import clear_results

# --- 常數定義 ---
QUEUE_DB_PATH = "output/test_queue.db"
RESULTS_DB_PATH = "prometheus_fire.duckdb"
RESULTS_TABLE_NAME = "backtest_results"
NUM_TASKS_TO_ADD = 5

@pytest.fixture(scope="function")
def test_env():
    """
    一個 Pytest Fixture，在每次測試前清理環境，並在測試後執行清理。
    """
    # 建立一個用於測試的 LogManager
    test_log_db_path = Path("output/test_integration_log.db")
    test_archive_dir = Path("output/test_log_archive")
    log_manager = LogManager(db_path=test_log_db_path, archive_dir=test_archive_dir)

    # 測試前：清理舊結果
    clear_results(log_manager)

    # 清理任務佇列 (透過刪除檔案)
    if QUEUE_DB_PATH:
        if os.path.exists(QUEUE_DB_PATH):
            os.remove(QUEUE_DB_PATH)

    yield log_manager # 將 log_manager 提供給測試函數使用

    # 測試後：再次清理
    clear_results(log_manager)
    if QUEUE_DB_PATH:
        if os.path.exists(QUEUE_DB_PATH):
            os.remove(QUEUE_DB_PATH)

def worker_thread_target(log_manager: LogManager, stop_event: threading.Event):
    """
    回測服務工作者執行緒的目標函數。
    修改了原始服務，使其可以被優雅地停止。
    """
    queue = SQLiteQueue(db_path=QUEUE_DB_PATH)
    # 模擬 BacktestingService 的核心邏輯，但增加停止條件
    log_manager.log("INFO", "[Worker] 工作者執行緒已啟動。")
    processed_count = 0
    while not stop_event.is_set():
        task = queue.get()
        if task:
            # 導入並執行計算
            from apps.factor_engine.sma_crossover_factor import calculate_sma_crossover
            from core.db.results_saver import save_result

            task_id = task.get('_task_id')
            symbol = task.get("symbol", "UNKNOWN")
            params = task.get("params", {})

            result = calculate_sma_crossover(symbol=symbol, **params)
            result['params'] = str(params) # DuckDB 不支援 dict，轉為字串
            save_result(result)

            queue.task_done(task_id)
            log_manager.log("INFO", f"[Worker] 已處理任務 {task_id}")
            processed_count += 1
        else:
            time.sleep(0.1) # 短暫休眠
    log_manager.log("INFO", f"[Worker] 工作者執行緒已停止，共處理 {processed_count} 個任務。")


def test_end_to_end_pipeline(test_env):
    """
    執行端到端管線測試。
    """
    log_manager = test_env
    stop_event = threading.Event()

    # 建立 output 目錄
    os.makedirs("output", exist_ok=True)


    # 1. 在背景執行緒中啟動回測服務工作者
    worker = threading.Thread(
        target=worker_thread_target,
        args=(log_manager, stop_event),
        daemon=True
    )
    worker.start()
    log_manager.log("INFO", "[Main] 工作者執行緒已啟動。")

    # 2. 派發計算任務
    # 臨時修改 task_adder_app 中的佇列路徑
    from apps.tools import task_adder_app
    original_queue_path = task_adder_app.QUEUE_DB_PATH
    task_adder_app.QUEUE_DB_PATH = QUEUE_DB_PATH
    add_tasks(log_manager)
    task_adder_app.QUEUE_DB_PATH = original_queue_path # 還原路徑
    log_manager.log("INFO", f"[Main] 已新增 {NUM_TASKS_TO_ADD} 個任務。")

    # 3. 等待一段時間，讓工作者有足夠的時間處理所有任務
    log_manager.log("INFO", "[Main] 等待 5 秒讓任務處理完成...")
    time.sleep(5)

    # 4. 停止工作者執行緒
    log_manager.log("INFO", "[Main] 正在停止工作者執行緒...")
    stop_event.set()
    worker.join(timeout=2) # 等待執行緒結束
    assert not worker.is_alive(), "工作者執行緒未能正常停止！"
    log_manager.log("SUCCESS", "[Main] 工作者執行緒已停止。")

    # 5. 驗證結果資料庫
    log_manager.log("INFO", "[Main] 正在驗證資料庫結果...")
    # 檢查資料庫檔案是否存在
    assert os.path.exists(RESULTS_DB_PATH), f"結果資料庫檔案 '{RESULTS_DB_PATH}' 不存在！"

    conn = duckdb.connect(RESULTS_DB_PATH, read_only=True)
    try:
        count_result = conn.execute(f"SELECT COUNT(*) FROM {RESULTS_TABLE_NAME}").fetchone()
    except duckdb.CatalogException:
        count_result = (0,) # 如果資料表不存在，視為 0 筆
    finally:
        conn.close()

    assert count_result is not None, "無法從結果資料庫查詢到計數！"
    assert count_result[0] == NUM_TASKS_TO_ADD, f"預期有 {NUM_TASKS_TO_ADD} 筆結果，但實際只有 {count_result[0]} 筆！"
    log_manager.log("SUCCESS", f"[Main] 驗證成功！資料庫中存在 {count_result[0]} 筆結果。")
