import time

from prometheus.core.queue.sqlite_queue import SQLiteQueue
from prometheus.services.backtesting_service import BacktestingService

# 【核心】定義一個所有工作者都認可的、明確的關閉信號
POISON_PILL = "STOP_WORKING"


def backtest_worker_loop(
    task_queue: SQLiteQueue, results_queue: SQLiteQueue, price_data, worker_id: int
):
    """
    一個遵守鋼鐵契約的回測工作者：永不放棄，直到收到毒丸。
    """
    print(f"[Worker-Backtest-{worker_id}] 回測工作者已啟動，正在等待任務...")
    backtester = BacktestingService(price_data)

    # 【核心改變】這是一個更簡單、更穩健的迴圈
    while True:
        try:
            # 【核心改變】get() 現在會一直阻塞，直到拿到任務或毒丸
            task = task_queue.get(block=True)

            # 【核心改變】檢查是否收到了下班指令
            if task == POISON_PILL:
                print(f"[Worker-Backtest-{worker_id}] 收到關閉信號，正在優雅退出...")
                break  # 退出 while 迴圈

            # 【核心改變】在解包前，先確保 task 不是 None 或其他非預期類型
            if not isinstance(task, (list, tuple)) or len(task) != 2:
                print(f"[Worker-Backtest-{worker_id}] 收到無效任務格式，已忽略: {task}")
                continue

            item_id, genome_task = task

            if not isinstance(genome_task, dict):
                print(
                    f"[Worker-Backtest-{worker_id}] 收到無效的 genome_task 格式，已忽略: {genome_task}"
                )
                continue

            params = genome_task.get("params", {})
            print(f"[Worker-Backtest-{worker_id}] 正在回測任務 #{item_id}: {params}")

            try:
                report = backtester.run_sma_crossover_strategy(
                    fast_window=params.get("fast", 10),
                    slow_window=params.get("slow", 20),
                )
            except Exception as e:
                print(
                    f"!!!!!! [Worker-Backtest-{worker_id}] 回測函數內部出錯: {e} !!!!!!"
                )
                report = {"error": str(e), "is_valid": False}

            result_payload = {
                "genome_id": genome_task.get("id"),
                "params": params,
                "report": report,
                "processed_by": worker_id,
            }
            results_queue.put(result_payload)
            print(f"[Worker-Backtest-{worker_id}] 任務 #{item_id} 回測完成。")

        except Exception as e:
            # 這是捕捉佇列操作或任務解包等更嚴重錯誤的地方
            print(f"!!!!!! [Worker-Backtest-{worker_id}] 發生嚴重錯誤: {e} !!!!!!")
            # 嚴重錯誤後，短暫休息，避免癱瘓系統
            time.sleep(10)

    print(f"[Worker-Backtest-{worker_id}] 已成功關閉。")
