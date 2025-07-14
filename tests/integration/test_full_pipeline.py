import pytest
import threading
import time
import duckdb
import json
import os
from src.core.context import AppContext

# --- 常數定義 ---
RESULTS_DB_PATH = "prometheus_fire.duckdb"
RESULTS_TABLE_NAME = "backtest_results"
NUM_TASKS_TO_ADD = 3

def worker_thread_target(ctx: AppContext, stop_event: threading.Event):
    """回測服務工作者執行緒的目標函數，現在接收 AppContext。"""
    from src.core.services.backtesting_service import BacktestingService
    service = BacktestingService(queue=ctx.queue, log_manager=ctx.log_manager)
    while not stop_event.is_set():
        task = service.queue.get()
        if task:
            from src.apps.factor_engine.sma_crossover_factor import calculate_sma_crossover
            from src.core.db.results_saver import save_result

            task_id = task.get('_task_id')
            payload = json.loads(task['payload'])
            task_type = payload.get('type')
            symbol = payload.get("symbol", "UNKNOWN")
            params = payload.get("params", {})

            if task_type == 'SMA_Crossover':
                result = calculate_sma_crossover(symbol=symbol, fast=params.get('fast', 5), slow=params.get('slow', 10))
            else:
                result = {'symbol': symbol, 'pnl': 0, 'sharpe_ratio': 0}

            result['batch_id'] = payload.get('batch_id')
            result['params'] = str(params)
            save_result(result)

            service.queue.task_done(task_id)
        else:
            time.sleep(0.1)

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
    time.sleep(5)

    # 4. 停止工作者
    stop_event.set()
    worker.join(timeout=2)
    assert not worker.is_alive(), "工作者執行緒未能正常停止！"
    log_manager.log("SUCCESS", "[Main] 工作者執行緒已停止。")

    # 5. 驗證資料庫
    conn = duckdb.connect(RESULTS_DB_PATH, read_only=True)
    count_result = conn.execute(f"SELECT COUNT(*) FROM {RESULTS_TABLE_NAME}").fetchone()
    conn.close()

    assert count_result is not None
    assert count_result[0] == NUM_TASKS_TO_ADD
