import pytest
import threading
import time
import duckdb

from src.core.context import AppContext
from src.core.services.backtesting_service import BacktestingService

# --- 常數 ---
NUM_TASKS_TO_ADD = 3
RESULTS_DB_PATH = "prometheus_fire.duckdb"
RESULTS_TABLE_NAME = "backtest_results"

def worker_thread_target(ctx: AppContext, stop_event: threading.Event):
    """回測服務工作者執行緒的目標函數。"""
    ctx.log_manager.log("INFO", "[Worker] 背景工作者已啟動。")
    service = BacktestingService(
        queue=ctx.queue,
        log_manager=ctx.log_manager,
        db_connection=ctx.duckdb_connection
    )
    while not stop_event.is_set():
        task = service.queue.get()
        if task:
            service.process_task(task)
        else:
            time.sleep(0.1)
    ctx.log_manager.log("INFO", "[Worker] 背景工作者已停止。")

def test_end_to_end_pipeline(app_context: AppContext):
    """
    執行端到端管線測試，現在使用由工廠提供的乾淨上下文。
    """
    from src.apps.tools.task_adder_app import add_tasks

    log_manager = app_context.log_manager
    stop_event = threading.Event()

    # 1. 啟動背景工作者
    worker = threading.Thread(
        target=worker_thread_target,
        args=(app_context, stop_event),
        daemon=True
    )
    worker.start()
    log_manager.log("INFO", "[Main] 工作者執行緒已啟動。")

    # 2. 派發任務
    add_tasks(app_context)
    log_manager.log("INFO", f"[Main] 已新增 {NUM_TASKS_TO_ADD} 個任務。")

    # 3. 等待任務處理
    # 給予足夠的時間讓所有任務被處理
    time.sleep(5)

    # 4. 停止工作者
    stop_event.set()
    worker.join(timeout=2)
    assert not worker.is_alive(), "工作者執行緒未能正常停止！"
    log_manager.log("SUCCESS", "[Main] 工作者執行緒已停止。")

    # 5. 驗證資料庫
    count_result = app_context.duckdb_connection.execute(f"SELECT COUNT(*) FROM {RESULTS_TABLE_NAME}").fetchone()
    assert count_result is not None, "無法查詢到結果數量！"
    assert count_result[0] == NUM_TASKS_TO_ADD, f"預期有 {NUM_TASKS_TO_ADD} 個結果，但實際只有 {count_result[0]} 個。"
    log_manager.log("SUCCESS", f"驗證成功！資料庫中有 {count_result[0]} 個回測結果。")
