from dataclasses import dataclass
from functools import lru_cache

from src.core.logger import LogManager
# === 核心變更：確保導入的是我們最新的 SQLiteQueue ===
from src.core.queue.sqlite_queue import SQLiteQueue
from src.core.queue.base import BaseQueue
from src.core.db.results_saver import ResultsSaver

# 定義常數以避免硬編碼
QUEUE_DB_PATH = "output/task_queue.db"
RESULTS_DB_PATH = "output/prometheus_fire.duckdb"

@dataclass
class AppContext:
    log_manager: LogManager

    _queue: BaseQueue = None
    _results_saver: ResultsSaver = None
    db_connection = None

    @property
    def queue(self) -> BaseQueue:
        """
        提供任務佇列的實例。
        採用延遲載入 (Lazy Loading) 模式，只在第一次被呼叫時初始化。
        """
        if self._queue is None:
            self.log_manager.log("DEBUG", "正在初始化企業級 SQLiteQueue...")
            self._queue = SQLiteQueue(db_path=QUEUE_DB_PATH)
        return self._queue

    @property
    def results_saver(self) -> ResultsSaver:
        """
        提供結果儲存器的實例。
        採用延遲載入模式。
        """
        if self._results_saver is None:
            self.log_manager.log("DEBUG", "正在初始化 ResultsSaver...")
            self._results_saver = ResultsSaver(db_path=RESULTS_DB_PATH, log_manager=self.log_manager)
        return self._results_saver

    def get_db_connection(self):
        """
        提供 DuckDB 資料庫連線的實例。
        採用延遲載入模式。
        """
        if self.db_connection is None:
            import duckdb
            # Enable multithreading and disable file locking
            self.db_connection = duckdb.connect(database=":memory:", read_only=False)
        return self.db_connection
