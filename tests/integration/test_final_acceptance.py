import pytest
import threading
import time
from src.core.context import AppContext
from src.apps import backtest_worker_app

def test_final_acceptance_for_evolution(app_context: AppContext):
    log_manager = app_context.log_manager

    # BATTLE PHASE: 模擬多個世代的基因演算法執行
    num_generations = 3
    population_size = 5

    # Start the worker in a separate thread
    worker_thread = threading.Thread(target=backtest_worker_app.main, args=(app_context,), daemon=True)
    worker_thread.start()

    for gen in range(num_generations):
        log_manager.log("BATTLE", f"===== 世代 {gen+1}/{num_generations} =====")
        for i in range(population_size):
            backtest_id = f"gen{gen+1}_ind{i+1}"
            # 傳送一個簡化的基因體進行測試
            app_context.queue.put({
                "individual": {
                    "strategy_name": "RSI_MeanReversion",
                    "indicators": [{"name": "RSI", "params": {"window": 14}}],
                    "entry_rules": [{"name": "RSI_CrossUnder", "value": 30}],
                    "exit_rules": [{"name": "RSI_CrossOver", "value": 70}]
                },
                "backtest_id": backtest_id
            })

    # FINAL CHECK: 等待所有任務處理完畢
    time.sleep(5)
    while app_context.queue.qsize() > 0:
        time.sleep(1)

    app_context.queue.put(None) # 傳送關閉信號
    worker_thread.join(timeout=15)

    # ASSERTION: 驗證結果是否已儲存
    results_count = app_context.results_saver.count_results()
    log_manager.log("SUCCESS", f"✅ 最終驗收測試完成。共儲存 {results_count} 筆回測結果。")
    assert results_count >= 15
