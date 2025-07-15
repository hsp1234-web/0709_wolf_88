# 檔案: src/core/queue/sqlite_queue.py
import sqlite3
import pickle
import time
from pathlib import Path
from typing import Any, Optional

class SQLiteQueue:
    """
    一個基於 SQLite 的、進程/執行緒安全的、持久化的訊息佇列。
    """
    def __init__(self, db_path: Path):
        self._db_path = db_path
        # isolation_level=None 啟用 autocommit 模式
        # check_same_thread=False 允許在多執行緒中使用
        self._conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload BLOB NOT NULL,
                is_done BOOLEAN DEFAULT 0
            )
        """)

    def put(self, item: Any):
        """將一個項目放入佇列。"""
        payload = pickle.dumps(item)
        self._conn.execute("INSERT INTO queue (payload) VALUES (?)", (payload,))

    def get(self, block: bool = True, timeout: float = 0.1) -> Optional[Any]:
        """
        從佇列中獲取一個未完成的項目，並將其鎖定 (但不刪除)。
        返回 (item_id, item) 或 None。
        """
        while True:
            # 使用 BEGIN IMMEDIATE 來獲取一個寫入鎖，防止其他執行緒同時獲取任務
            cursor = self._conn.execute("BEGIN IMMEDIATE;")
            try:
                cursor.execute("SELECT id, payload FROM queue WHERE is_done = 0 ORDER BY id ASC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    item_id, payload = row
                    # 這裡我們先不更新 is_done，而是由 task_done 來完成
                    # 這樣可以模擬一個任務被"取出"並處理的過程
                    self._conn.commit()
                    return item_id, pickle.loads(payload)
                else:
                    self._conn.commit() # 沒有任務，釋放鎖
                    if not block:
                        return None
                    time.sleep(timeout) # 等待一小段時間再重試
            except sqlite3.OperationalError as e:
                # 如果是資料庫被鎖定，則稍後重試
                if "database is locked" in str(e):
                    self._conn.rollback()
                    time.sleep(timeout)
                    continue
                else:
                    raise

    def task_done(self, item_id: int):
        """標記一個任務已完成。"""
        self._conn.execute("UPDATE queue SET is_done = 1 WHERE id = ?", (item_id,))

    def close(self):
        """關閉資料庫連線。"""
        self._conn.close()
