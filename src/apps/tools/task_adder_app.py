from core.queue.sqlite_queue import SQLiteQueue
from core.logger import LogManager
import random

QUEUE_DB_PATH = "output/task_queue.db"

def add_tasks(log_manager: LogManager):
    queue = SQLiteQueue(db_path=QUEUE_DB_PATH)
    log_manager.log("INFO", "正在新增包含動態參數的測試任務...")

    # 定義不同的策略參數組合
    param_sets = [
        {"fast": 5, "slow": 10},
        {"fast": 10, "slow": 20},
        {"fast": 5, "slow": 20},
    ]

    for i in range(5):
        # 為每個任務隨機選擇一個參數組
        params = random.choice(param_sets)
        task_data = {
            "strategy": "SMA_crossover",
            "symbol": f"STOCK_{i}",
            "params": params  # 將參數字典加入任務
        }
        queue.put(task_data)
        log_manager.log("INFO", f"  已新增任務: {task_data}")

    log_manager.log("SUCCESS", "所有任務已新增。")
