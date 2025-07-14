import sqlite3
import json
import uuid
from pathlib import Path
from typing import Optional, Dict

from .base import BaseQueue

class SQLiteQueue(BaseQueue):
    """
    一個基於 SQLite 的、絕對穩健的持久化任務佇列。
    其核心依賴 SQLite 的事務性與明確的狀態管理欄位。
    """
    def __init__(self, db_path: str | Path = "output/task_queue.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # 允許多執行緒共享同一個連線，並增加超時
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',  -- 'pending'|'running'|'completed'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def put(self, task_data: Dict) -> str:
        """將一個新任務放入佇列，並返回任務 ID。"""
        task_id = str(uuid.uuid4())
        with self.conn:
            self.conn.execute(
                "INSERT INTO tasks (id, payload) VALUES (?, ?)",
                (task_id, json.dumps(task_data))
            )
        return task_id

    def get(self) -> Optional[Dict]:
        """以原子操作從佇列中取出一個任務。"""
        with self.conn:
            cursor = self.conn.cursor()
            # 找出一個待處理的任務
            cursor.execute("""
                SELECT id, payload FROM tasks
                WHERE status = 'pending'
                ORDER BY created_at
                LIMIT 1
            """)
            task = cursor.fetchone()

            if task:
                task_id, payload_str = task
                # 鎖定該任務
                self.conn.execute(
                    "UPDATE tasks SET status = 'running' WHERE id = ?",
                    (task_id,)
                )
                task_data = json.loads(payload_str)
                task_data['_task_id'] = task_id # 將 ID 注入
                return task_data
        return None

    def task_done(self, task_id: str) -> None:
        """標記一個任務已完成。"""
        with self.conn:
            self.conn.execute(
                "UPDATE tasks SET status = 'completed' WHERE id = ?",
                (task_id,)
            )

    def qsize(self) -> int:
        """返回待處理任務的數量。"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
        return cursor.fetchone()[0]
