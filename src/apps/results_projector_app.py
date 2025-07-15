import time
from src.core.queue.sqlite_queue import SQLiteQueue

def projector_loop(queue: SQLiteQueue, worker_id: int):
    """
    一個簡單、獨立、永不崩潰的結果投影工作者。
    """
    print(f"[Worker-{worker_id}] 結果投影工作者已啟動，正在等待任務...")

    while True:
        try:
            # 從佇列中獲取任務
            task = queue.get(block=True)

            if task is None:
                continue

            item_id, result_task = task
            print(f"[Worker-{worker_id}] 接收到結果任務 #{item_id}: {result_task}")

            # --- 模擬結果投影工作 ---
            if "error" in result_task:
                raise ValueError("這是一個模擬的結果投影錯誤！")

            time.sleep(1) # 模擬耗時的結果投影
            print(f"[Worker-{worker_id}] 任務 #{item_id} 結果投影完成。")
            # --- 模擬結束 ---

            queue.task_done(item_id)

        except Exception as e:
            print(f"!!!!!! [Worker-{worker_id}] 發生嚴重錯誤 !!!!!!")
            print(f"錯誤類型: {type(e).__name__}")
            print(f"錯誤訊息: {e}")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            time.sleep(5)
