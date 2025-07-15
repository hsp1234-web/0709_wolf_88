import time
from src.core.queue.sqlite_queue import SQLiteQueue
from src.core.services.backtesting_service import BacktestingService
from src.core.utils.data_loader import load_ohlcv_data # 導入數據加載器
from pathlib import Path

def backtest_worker_loop(task_queue: SQLiteQueue, results_queue: SQLiteQueue, price_data, worker_id: int):
    """
    升級版的回測工作者，執行真實的回測計算。
    """
    print(f"[Worker-Backtest-{worker_id}] 回測工作者已啟動...")
    backtester = BacktestingService(price_data)

    while True:
        try:
            task = task_queue.get(block=True)
            if task is None: continue

            item_id, genome_task = task

            if not isinstance(genome_task, dict) or "params" not in genome_task:
                raise TypeError(f"接收到格式錯誤的任務 #{item_id}")

            params = genome_task['params']
            print(f"[Worker-Backtest-{worker_id}] 正在回測任務 #{item_id}: {params}")

            # 【核心改變】調用真實的回測服務
            report = backtester.run_sma_crossover_strategy(
                fast_window=params.get('fast', 10),
                slow_window=params.get('slow', 20)
            )

            result_payload = {
                "genome_id": genome_task.get('id', 'N/A'),
                "params": params,
                "report": report,
                "processed_by": worker_id
            }

            results_queue.put(result_payload)
            print(f"[Worker-Backtest-{worker_id}] 任務 #{item_id} 回測完成。")

        except Exception as e:
            print(f"!!!!!! [Worker-Backtest-{worker_id}] 處理任務時發生錯誤: {e} !!!!!!")
            time.sleep(5)
