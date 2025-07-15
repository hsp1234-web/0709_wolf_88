import time
from src.core.queue.sqlite_queue import SQLiteQueue

def evolution_loop(queue: SQLiteQueue, worker_id: int):
    """
    一個簡單、獨立、永不崩潰的演化工作者。
    """
    print(f"[Worker-{worker_id}] 演化工作者已啟動，正在等待任務...")

    while True:
        try:
            # 從佇列中獲取任務
            task = queue.get(block=True)

            if task is None:
                continue

            item_id, evolution_task = task
            print(f"[Worker-{worker_id}] 接收到演化任務 #{item_id}: {evolution_task}")

            # --- 模擬演化工作 ---
            if "error" in evolution_task:
                raise ValueError("這是一個模擬的演化計算錯誤！")

            time.sleep(3) # 模擬耗時的演化計算
            print(f"[Worker-{worker_id}] 任務 #{item_id} 演化完成。")
            # --- 模擬結束 ---

            queue.task_done(item_id)

        except Exception as e:
            print(f"!!!!!! [Worker-{worker_id}] 發生嚴重錯誤 !!!!!!")
            print(f"錯誤類型: {type(e).__name__}")
            print(f"錯誤訊息: {e}")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            time.sleep(5)
