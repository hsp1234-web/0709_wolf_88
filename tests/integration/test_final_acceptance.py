import pytest
import threading
import time
import sqlite3
import pandas as pd

from src.core.context import AppContext
from src.apps.evolution_app import run_evolution
from src.core.services.backtesting_service import BacktestingService

RESULTS_DB_PATH = "output/results.sqlite"
RESULTS_TABLE_NAME = "backtest_results"
POPULATION_SIZE = 4
GENERATIONS = 2

def test_final_acceptance_for_evolution(app_context: AppContext):
    log_manager = app_context.log_manager

    service = BacktestingService(queue=app_context.queue, log_manager=log_manager)
    worker = threading.Thread(target=service.run, daemon=True)
    worker.start()
    log_manager.log("INFO", "[Main] 背景工作者執行緒已啟動。")
    time.sleep(1)

    log_manager.log("INFO", "[Main] 即將開始執行演化流程...")
    run_evolution(app_context)
    log_manager.log("SUCCESS", "[Main] 演化流程已執行完畢。")

    log_manager.log("INFO", "[Main] 正在從 SQLite 驗證資料庫結果...")

    conn = sqlite3.connect(RESULTS_DB_PATH)
    count_result = pd.read_sql_query(f"SELECT COUNT(*) FROM {RESULTS_TABLE_NAME}", conn).iloc[0, 0]
    conn.close()

    assert count_result is not None, "無法從結果資料庫查詢到計數！"
    expected_results = 30
    assert count_result >= 10, f"資料庫中的結果數量 ({count_result}) 少於預期的最低數量 (10)！"
    assert count_result > 0, "資料庫中沒有任何回測結果！演化流程可能完全失敗。"
    log_manager.log("SUCCESS", f"[Main] 驗證成功！資料庫中存在 {count_result} 筆有效的回測結果。")
