from core.queue.sqlite_queue import SQLiteQueue
from core.services.backtesting_service import BacktestingService
from core.logger import LogManager # 導入

QUEUE_DB_PATH = "output/task_queue.db"

# 修改主函數，使其能接收 log_manager
def run_worker(log_manager: LogManager):
    queue = SQLiteQueue(db_path=QUEUE_DB_PATH)
    service = BacktestingService(queue=queue, log_manager=log_manager)
    service.run()
