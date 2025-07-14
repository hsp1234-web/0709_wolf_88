# 檔案: src/core/context.py
import aiosqlite
from typing import Literal
from pathlib import Path

from src.core.queue.async_event_bus import AsyncEventBus
from src.core.db.results_saver import ResultsSaver
# LogManager 暫時不改，因為日誌的非同步改造較複雜，我們先專注於核心流程

class AppContext:
    """作戰上下文 v3.0 (非同步版)"""
    def __init__(self, session_name: str, mode: Literal['prod', 'test'] = 'prod'):
        self.session_name = session_name
        self.mode = mode
        self.queue = AsyncEventBus(name=session_name)
        # self.log_manager = ... # 暫時移除日誌以簡化重構

    async def __aenter__(self):
        """實現異步上下文管理器進入協議"""
        db_path = ":memory:" if self.mode == 'test' else str(Path("output/results.sqlite"))
        self.db_connection = await aiosqlite.connect(db_path)
        self.results_saver = ResultsSaver(connection=self.db_connection)
        await self.results_saver.setup_database()
        print(f"作戰上下文已在 '{self.mode}' 模式下非同步初始化。")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """實現異步上下文管理器退出協議，確保資源關閉"""
        print(f"作戰上下文 '{self.session_name}' 正在關閉...")
        if self.db_connection:
            await self.db_connection.close()
            print("結果資料庫連線已關閉。")
