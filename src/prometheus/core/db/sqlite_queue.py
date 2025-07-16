import sqlite3
import pickle

class SQLiteQueue:
    def __init__(self, db_path, queue_name):
        self.db_path = db_path
        self.queue_name = queue_name
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.queue_name} (
                id INTEGER PRIMARY KEY,
                task BLOB,
                status TEXT DEFAULT 'pending'
            )
        """)

    def put(self, task):
        self.conn.execute(
            f"INSERT INTO {self.queue_name} (task) VALUES (?)",
            (pickle.dumps(task),)
        )
        self.conn.commit()

    def get(self):
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT id, task FROM {self.queue_name} WHERE status = 'pending' ORDER BY id LIMIT 1")
        row = cursor.fetchone()
        if row:
            task_id, task_data = row
            cursor.execute(f"UPDATE {self.queue_name} SET status = 'processing' WHERE id = ?", (task_id,))
            self.conn.commit()
            return task_id, pickle.loads(task_data)
        return None, None

    def ack(self, task_id):
        self.conn.execute(f"UPDATE {self.queue_name} SET status = 'done' WHERE id = ?", (task_id,))
        self.conn.commit()

    def __len__(self):
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {self.queue_name} WHERE status = 'pending'")
        return cursor.fetchone()[0]
