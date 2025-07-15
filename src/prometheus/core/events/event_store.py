"""
基於 aiosqlite 的持久化事件流實現。
這是系統的「唯一事實來源」。
"""

import asyncio
import json
from typing import List, Tuple


class PersistentEventStream:
    def __init__(self, conn):
        self._conn = conn
        # 使用一個非同步鎖來處理潛在的並發寫入
        self._lock = asyncio.Lock()

    async def initialize(self):
        """初始化事件儲存與檢查點儲存。"""
        async with self._lock:
            await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                data TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS consumer_checkpoints (
                consumer_id TEXT PRIMARY KEY,
                last_processed_id INTEGER NOT NULL
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
                (event_type, data),
            )
            await self._conn.commit()

    async def subscribe(self, last_seen_id: int, batch_size: int = 100) -> List[Tuple]:
        """從上次看到的位置讀取新事件。"""
        cursor = await self._conn.execute(
            "SELECT id, event_type, data FROM events WHERE id > ? ORDER BY id ASC LIMIT ?",
            (last_seen_id, batch_size),
        )
        return await cursor.fetchall()

    async def get_checkpoint(self, consumer_id: str) -> int:
        """獲取指定消費者的最後處理事件ID。"""
        cursor = await self._conn.execute(
            "SELECT last_processed_id FROM consumer_checkpoints WHERE consumer_id = ?",
            (consumer_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def update_checkpoint(self, consumer_id: str, last_processed_id: int):
        """更新指定消費者的檢查點。"""
        async with self._lock:
            await self._conn.execute(
                """
                INSERT INTO consumer_checkpoints (consumer_id, last_processed_id)
                VALUES (?, ?)
                ON CONFLICT(consumer_id) DO UPDATE SET last_processed_id = excluded.last_processed_id
                """,
                (consumer_id, last_processed_id),
            )
            await self._conn.commit()

    async def get_total_event_count(self) -> int:
        """獲取事件流中的事件總數。"""
        cursor = await self._conn.execute("SELECT MAX(id) FROM events")
        row = await cursor.fetchone()
        return row[0] if row and row[0] is not None else 0

    async def get_all_checkpoints(self) -> dict[str, int]:
        """獲取所有消費者的檢查點。"""
        cursor = await self._conn.execute(
            "SELECT consumer_id, last_processed_id FROM consumer_checkpoints"
        )
        return dict(await cursor.fetchall())
