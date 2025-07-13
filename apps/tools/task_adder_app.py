from core.queue.sqlite_queue import SQLiteQueue
from core.logger import LogManager # 導入

QUEUE_DB_PATH = "output/task_queue.db"

# 修改主函數
def add_tasks(log_manager: LogManager):
    queue = SQLiteQueue(db_path=QUEUE_DB_PATH)
    log_manager.log("INFO", "正在新增測試任務...")
    for i in range(5):
        task_data = {"strategy": "SMA_crossover", "symbol": f"STOCK_{i}"}
        queue.put(task_data)
        log_manager.log("INFO", f"  已新增任務: {task_data}")
    log_manager.log("SUCCESS", "所有任務已新增。")
