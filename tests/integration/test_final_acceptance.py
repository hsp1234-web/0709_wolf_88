import pytest
import threading
import time
import duckdb

from src.core.context import AppContext
from src.apps.evolution_app import run_evolution
from src.core.services.backtesting_service import BacktestingService

# --- 常數定義 ---
RESULTS_DB_PATH = "prometheus_fire.duckdb"
RESULTS_TABLE_NAME = "backtest_results"
POPULATION_SIZE = 4 # 使用較小的族群以加速測試
GENERATIONS = 2     # 使用較少的世代數

def test_final_acceptance_for_evolution(app_context: AppContext):
    """
    最終驗收測試：驗證完整的演化 -> 回測管線。
    """
    log_manager = app_context.log_manager
    stop_event = threading.Event()

    # 1. 在背景執行緒中啟動回測服務工作者
    from src.apps.backtest_worker_app import run_worker as run_worker_app
    worker = threading.Thread(target=run_worker_app, args=(app_context,), daemon=True)
    worker.start()
    log_manager.log("INFO", "[Main] 背景工作者執行緒已啟動。")
    time.sleep(1) # 給予工作者一點啟動時間

    # 2. 在主執行緒中，執行完整的演化流程
    log_manager.log("INFO", "[Main] 即將開始執行演化流程...")
    run_evolution(app_context, population_size=POPULATION_SIZE, generations=GENERATIONS)
    log_manager.log("SUCCESS", "[Main] 演化流程已執行完畢。")

    # 3. 驗證結果
    log_manager.log("INFO", "[Main] 正在驗證資料庫結果...")
    # 總共評估的個體數 = 初始族群 + 後續每一代的新生代
    expected_results = POPULATION_SIZE + (GENERATIONS * POPULATION_SIZE)

    count_result = app_context.duckdb_connection.execute(f"SELECT COUNT(*) FROM {RESULTS_TABLE_NAME}").fetchone()

    assert count_result is not None, "無法從結果資料庫查詢到計數！"
    # 由於可能存在無效個體 (slow <= fast)，實際結果數可能小於預期
    assert count_result[0] <= expected_results, f"資料庫中的結果數量 ({count_result[0]}) 超出預期 ({expected_results})！"
    assert count_result[0] > 0, "資料庫中沒有任何回測結果！演化流程可能完全失敗。"
    log_manager.log("SUCCESS", f"[Main] 驗證成功！資料庫中存在 {count_result[0]} 筆有效的回測結果。")
