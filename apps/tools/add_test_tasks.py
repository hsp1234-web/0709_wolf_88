from core.queue.sqlite_queue import SQLiteQueue

QUEUE_DB_PATH = "output/task_queue.db"

def main():
    queue = SQLiteQueue(db_path=QUEUE_DB_PATH)
    print("正在新增測試任務...")
    for i in range(5):
        task_data = {"strategy": "SMA_crossover", "symbol": f"STOCK_{i}"}
        queue.put(task_data)
        print(f"  已新增任務: {task_data}")
    print("所有任務已新增。")

if __name__ == "__main__":
    main()
