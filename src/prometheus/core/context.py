# 檔案: src/core/context.py
import os

import aiosqlite

from prometheus.core.events.event_store import PersistentEventStream


class AppContext:
    _instance = None

    def __init__(self, db_path: str = "output/results.sqlite", config_path: str = "config.yml"):
        self.db_path = db_path
        from prometheus.core.config import ConfigManager
        self.config = ConfigManager(config_path=config_path)._config
        self.conn = None
        self.event_stream: PersistentEventStream | None = None

    async def __aenter__(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self.conn = await aiosqlite.connect(self.db_path)
        # 啟用 WAL 模式以獲得更好的並發性能
        await self.conn.execute("PRAGMA journal_mode=WAL;")

        # 初始化事件流
        self.event_stream = PersistentEventStream(self.conn)
        await self.event_stream.initialize()

        return self

    @classmethod
    def get_instance(cls, **kwargs):
        if cls._instance is None:
            if 'config_path' not in kwargs:
                kwargs['config_path'] = 'config.yml'
            cls._instance = cls(config_path=kwargs.get('config_path', 'config.yml'))
        return cls._instance

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            await self.conn.close()
