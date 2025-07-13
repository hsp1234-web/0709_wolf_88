from core.queue.sqlite_queue import SQLiteQueue
q = SQLiteQueue(db_path="output/task_queue.db")
print(q.qsize())
