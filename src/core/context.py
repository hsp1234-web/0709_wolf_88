# 檔案: src/core/context.py
import aiosqlite
from src.core.events.event_store import PersistentEventStream
from src.core.db.results_saver import ResultsSaver

class AppContext:
    def __init__(self, db_path: str = "output/results.sqlite"):
        self.db_path = db_path
        self.conn = None
        self.event_stream: PersistentEventStream | None = None
        self.results_saver: ResultsSaver | None = None

    async def __aenter__(self):
        self.conn = await aiosqlite.connect(self.db_path)
        # 啟用 WAL 模式以獲得更好的並發性能
        await self.conn.execute("PRAGMA journal_mode=WAL;")

        # 初始化事件流
        self.event_stream = PersistentEventStream(self.conn)
        await self.event_stream.initialize()

        # 初始化結果儲存器
        self.results_saver = ResultsSaver(self.conn)
        await self.results_saver.initialize()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            await self.conn.close()
