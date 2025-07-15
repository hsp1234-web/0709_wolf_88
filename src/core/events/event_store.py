"""
基於 aiosqlite 的持久化事件流實現。
這是系統的「唯一事實來源」。
"""
import json
import asyncio
from typing import List, Tuple

class PersistentEventStream:
    def __init__(self, conn):
        self._conn = conn
        # 使用一個非同步鎖來處理潛在的並發寫入
        self._lock = asyncio.Lock()

    async def initialize(self):
        """初始化事件儲存，建立必要的資料表。"""
        async with self._lock:
            await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                data TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            await self._conn.commit()

    async def append(self, event):
        """將一個事件附加到流的末尾。"""
        event_type = type(event).__name__
        # 將 dataclass 序列化為 JSON 字串
        data = json.dumps(event.__dict__)
        async with self._lock:
            await self._conn.execute(
                "INSERT INTO events (event_type, data) VALUES (?, ?)",
                (event_type, data)
            )
            await self._conn.commit()

    async def subscribe(self, last_seen_id: int, batch_size: int = 100) -> List[Tuple]:
        """從上次看到的位置讀取新事件。"""
        cursor = await self._conn.execute(
            "SELECT id, event_type, data FROM events WHERE id > ? ORDER BY id ASC LIMIT ?",
            (last_seen_id, batch_size)
        )
        return await cursor.fetchall()
