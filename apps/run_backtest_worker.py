from core.queue.sqlite_queue import SQLiteQueue
from core.services.backtesting_service import BacktestingService

# 注意: 這裡的路徑應與 config.yml 一致
QUEUE_DB_PATH = "output/task_queue.db"

def main():
    queue = SQLiteQueue(db_path=QUEUE_DB_PATH)
    service = BacktestingService(queue=queue)
    service.run()

if __name__ == "__main__":
    main()
