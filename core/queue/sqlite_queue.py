import sqlite3
import json
import threading
from pathlib import Path
from typing import Optional

from .base import BaseQueue

class SQLiteQueue(BaseQueue):
    """
    一個基於 SQLite 的、支援多執行緒的持久化任務佇列。
    """
    _TABLE_NAME = "task_queue"

    def __init__(self, db_path: str | Path):
        """
        初始化佇列。

        Args:
            db_path (str | Path): SQLite 資料庫檔案的路徑。
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 為每個執行緒建立獨立的資料庫連線
        self.local = threading.local()
        self._create_table()

    def _get_conn(self) -> sqlite3.Connection:
        """為當前執行緒取得或建立資料庫連線。"""
        if not hasattr(self.local, 'conn'):
            self.local.conn = sqlite3.connect(self.db_path, timeout=10)
        return self.local.conn

    def _create_table(self):
        """如果資料表不存在，則建立它。"""
        conn = self._get_conn()
        with conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 為 status 欄位建立索引以加速查詢
            conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_status ON {self._TABLE_NAME} (status)
            """)

    def put(self, task_data: dict) -> None:
        """將任務放入佇列。"""
        payload_str = json.dumps(task_data)
        conn = self._get_conn()
        with conn:
            conn.execute(
                f"INSERT INTO {self._TABLE_NAME} (payload, status) VALUES (?, 'pending')",
                (payload_str,)
            )

    def get(self) -> Optional[dict]:
        """以原子操作從佇列中取得一個任務。"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # 使用事務確保操作的原子性
        with conn:
            # 查詢一個待處理的任務
            cursor.execute(
                f"SELECT id, payload FROM {self._TABLE_NAME} WHERE status = 'pending' ORDER BY id LIMIT 1"
            )
            task = cursor.fetchone()

            if task:
                task_id, payload_str = task
                # 鎖定該任務，防止其他工作者取得
                cursor.execute(
                    f"UPDATE {self._TABLE_NAME} SET status = 'running' WHERE id = ?",
                    (task_id,)
                )
                task_data = json.loads(payload_str)
                task_data['_task_id'] = task_id  # 將內部ID注入任務，以便後續追蹤
                return task_data
        return None

    def task_done(self, task_id: int) -> None:
        """標記任務完成。"""
        conn = self._get_conn()
        with conn:
            conn.execute(
                f"UPDATE {self._TABLE_NAME} SET status = 'completed' WHERE id = ?",
                (task_id,)
            )

    def qsize(self) -> int:
        """返回待處理任務的數量。"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {self._TABLE_NAME} WHERE status = 'pending'")
        count = cursor.fetchone()[0]
        return count

    def close(self):
        """關閉當前執行緒的資料庫連線。"""
        if hasattr(self.local, 'conn'):
            self.local.conn.close()
            del self.local.conn
