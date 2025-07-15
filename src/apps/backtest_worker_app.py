# 檔案: src/apps/backtest_worker_app.py
import time
from pathlib import Path
from src.core.queue.sqlite_queue import SQLiteQueue

def backtest_worker_loop(queue: SQLiteQueue, worker_id: int):
    """
    一個簡單、獨立、永不崩-潰的回測工作者。
    """
    print(f"[Worker-{worker_id}] 回測工作者已啟動，正在等待任務...")

    while True:
        try:
            # 從佇列中獲取任務
            task = queue.get(block=True) # block=True 會讓它一直等到有任務為止

            if task is None:
                # 理論上 block=True 不會返回 None，但作為一個保險
                continue

            item_id, genome_task = task
            print(f"[Worker-{worker_id}] 接收到任務 #{item_id}: {genome_task}")

            # --- 模擬回測工作 ---
            # 如果我們故意在這裡製造一個錯誤
            if "error" in genome_task:
                raise ValueError("這是一個模擬的策略計算錯誤！")

            time.sleep(2) # 模擬耗時的回測計算
            print(f"[Worker-{worker_id}] 任務 #{item_id} 回測完成。")
            # --- 模擬結束 ---

            # 標記任務已完成
            queue.task_done(item_id)

        except Exception as e:
            # 【核心】捕捉所有可能的錯誤
            print(f"!!!!!! [Worker-{worker_id}] 發生嚴重錯誤 !!!!!!")
            print(f"錯誤類型: {type(e).__name__}")
            print(f"錯誤訊息: {e}")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            # 即使發生錯誤，迴圈也會繼續，等待下一個任務
            time.sleep(5) # 發生錯誤後稍作等待，避免快速連續失敗
