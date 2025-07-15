# 檔案: apps/optimizer_app.py

from core.logger import LogManager
from core.queue.sqlite_queue import SQLiteQueue
from core.services.optimizer_service import StrategyOptimizer

QUEUE_DB_PATH = "output/task_queue.db"


def run_optimizer(log_manager: LogManager):
    """
    初始化並執行一次策略優化流程。
    """
    queue = SQLiteQueue(db_path=QUEUE_DB_PATH)
    optimizer = StrategyOptimizer(queue=queue, log_manager=log_manager)
    optimizer.run_once()
