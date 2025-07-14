from dataclasses import dataclass, field
import duckdb
import os

from src.core.logger import LogManager
from src.core.queue.sqlite_queue import SQLiteQueue
from src.core.queue.base import BaseQueue

# 定義常數以避免硬編碼
QUEUE_DB_PATH = "output/task_queue.db"
RESULTS_DB_PATH = "prometheus_fire.duckdb"

@dataclass
class AppContext:
    """
    作戰上下文：一個集中容器，持有所有共享服務的實例。
    """
    log_manager: LogManager
    _queue: BaseQueue = field(init=False, repr=False, default=None)
    db_connection: duckdb.DuckDBPyConnection = field(init=False, repr=False, default=None)

    def __post_init__(self):
        self.db_connection = None

    @property
    def queue(self) -> BaseQueue:
        """
        提供任務佇列的實例。
        採用延遲載入 (Lazy Loading) 模式，只在第一次被呼叫時初始化。
        """
        if self._queue is None:
            self.log_manager.log("DEBUG", "正在初始化 SQLiteQueue...")
            self._queue = SQLiteQueue(db_path=QUEUE_DB_PATH)
        return self._queue

    @queue.setter
    def queue(self, value: BaseQueue):
        """允許在測試中替換佇列的實例。"""
        self._queue = value

    def get_db_connection(self) -> duckdb.DuckDBPyConnection:
        """
        提供 DuckDB 資料庫連線的實例。
        採用延遲載入模式。
        """
        if self.db_connection is None:
            self.log_manager.log("DEBUG", f"正在連接到 DuckDB 資料庫: {RESULTS_DB_PATH}...")
            self.db_connection = duckdb.connect(RESULTS_DB_PATH, read_only=False)
        return self.db_connection

    def close_db(self):
        """關閉資料庫連線。"""
        if self.db_connection is not None:
            self.db_connection.close()
            self.db_connection = None
            self.log_manager.log("DEBUG", "DuckDB 資料庫連線已關閉。")
