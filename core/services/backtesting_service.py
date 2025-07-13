import time
from core.queue.base import BaseQueue

class BacktestingService:
    def __init__(self, queue: BaseQueue):
        self.queue = queue
        print("回測服務已啟動，等待任務...")

    def run(self):
        while True:
            task = self.queue.get()
            if task:
                task_id = task.get('_task_id')
                print(f"  [處理中] 任務 {task_id}: {task}")
                time.sleep(2) # 模擬回測運算
                self.queue.task_done(task_id)
                print(f"  [已完成] 任務 {task_id}")
            else:
                time.sleep(1) # 佇列為空，稍後再試
