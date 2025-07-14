import sqlite3
import json
import threading
from .base import BaseQueue

class SQLiteQueue(BaseQueue):
    def __init__(self, db_path='queue.db'):
        self.db_path = db_path
        self.lock = threading.Lock()
        with self._get_connection() as conn:
            self._create_table(conn)

    def _get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _create_table(self, conn):
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL,
                is_done BOOLEAN NOT NULL DEFAULT 0
            )
        """)
        conn.commit()

    def put(self, task):
        with self.lock:
            with self._get_connection() as conn:
                payload_str = json.dumps(task)
                cursor = conn.cursor()
                cursor.execute("INSERT INTO tasks (payload) VALUES (?)", (payload_str,))
                conn.commit()

    def get(self):
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, payload FROM tasks WHERE is_done = 0 ORDER BY id ASC LIMIT 1")
                task = cursor.fetchone()
                if task:
                    task_id, payload_str = task
                    try:
                        payload = json.loads(payload_str)
                        # Ensure payload is a dictionary before unpacking
                        if isinstance(payload, dict):
                            return {**payload, '_task_id': task_id}
                        else:
                            return {'payload': payload, '_task_id': task_id}
                    except json.JSONDecodeError:
                        return {'payload': payload_str, '_task_id': task_id}
                return None

    def task_done(self, task_id):
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE tasks SET is_done = 1 WHERE id = ?", (task_id,))
                conn.commit()

    def __len__(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tasks WHERE is_done = 0")
            count = cursor.fetchone()[0]
            return count

    def is_empty(self):
        return len(self) == 0

    def qsize(self):
        return self.__len__()

    def close(self):
        pass # No-op for now, as we are using a shared connection
