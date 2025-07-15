import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional


class SQLiteQueue:
    """
    一個基於 SQLite 的、支持阻塞和毒丸關閉的持久化佇列。
    """

    def __init__(self, db_path: str | Path, table_name: str = "queue"):
        self.db_path = Path(db_path)
        self.table_name = table_name
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # 允許多執行緒共享同一個連線，並增加超時
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def put(self, item: Any):
        """將一個項目放入佇列。"""
        with self.conn:
            self.conn.execute(
                f"INSERT INTO {self.table_name} (item) VALUES (?)", (json.dumps(item),)
            )

    def get(self, block: bool = True, timeout: Optional[float] = None) -> Optional[Any]:
        """
        從佇列中取出一個項目。
        如果 block=True，則會等待直到有項目可用。
        """
        start_time = time.time()
        while True:
            try:
                with self.conn:
                    cursor = self.conn.cursor()
                    cursor.execute(
                        f"SELECT id, item FROM {self.table_name} ORDER BY id LIMIT 1"
                    )
                    row = cursor.fetchone()

                    if row:
                        item_id, item_json = row
                        cursor.execute(
                            f"DELETE FROM {self.table_name} WHERE id = ?", (item_id,)
                        )
                        return json.loads(item_json)
            except sqlite3.Error as e:
                # 如果發生資料庫錯誤，短暫等待後重試
                print(f"Database error in get(): {e}")
                time.sleep(0.1)

            if not block:
                return None

            if timeout and (time.time() - start_time) > timeout:
                return None

            time.sleep(0.1)  # 避免過於頻繁地查詢

    def qsize(self) -> int:
        """返回佇列中的項目數量。"""
        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            return cursor.fetchone()[0]

    def close(self):
        """關閉資料庫連線。"""
        if self.conn:
            self.conn.close()
            self.conn = None
