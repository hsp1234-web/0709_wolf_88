import sqlite3
from typing import Literal
from pathlib import Path

from src.core.logger import LogManager
from src.core.queue.base import BaseQueue
from src.core.queue.sqlite_queue import SQLiteQueue
from src.core.queue.in_memory_queue import InMemoryQueue
from src.core.db.results_saver import ResultsSaver

class AppContext:
    """作戰上下文 v2.2 (統一關閉協議版)"""
    def __init__(self, session_name: str, mode: Literal['prod', 'test'] = 'prod'):
        self.session_name = session_name
        self.mode = mode
        self.log_manager = LogManager(session_name=session_name)

        if self.mode == 'test':
            self.queue: BaseQueue = InMemoryQueue(name=session_name)
            db_path = ":memory:"
            self.results_saver = ResultsSaver(db_path=db_path, log_manager=self.log_manager)
        else:
            self.queue: BaseQueue = SQLiteQueue(name="task_queue.db")
            db_path = str(Path("output/results.sqlite"))
            self.db_connection = sqlite3.connect(db_path, check_same_thread=False)
            self.results_saver = ResultsSaver(db_path=db_path, log_manager=self.log_manager)
        self.log_manager.log("INFO", f"作戰上下文已在 '{self.mode}' 模式下初始化。")

    def close(self):
        """【新增】統一的資源關閉方法。"""
        self.log_manager.log("INFO", f"作戰上下文 '{self.session_name}' 正在關閉...")
        if hasattr(self, 'db_connection') and self.db_connection:
            self.db_connection.close()
            self.log_manager.log("INFO", "結果資料庫連線已關閉。")
        # 確保日誌管理器最後關閉，以便記錄關閉過程
        self.log_manager.close()
