from dataclasses import dataclass, field
from src.core.logger import LogManager
from src.core.queue.sqlite_queue import SQLiteQueue
import duckdb
import os

# --- 常數定義 ---
# 使用 os.path.join 確保路徑在不同作業系統下都正確
QUEUE_DB_PATH = os.path.join("output", "task_queue.db")
RESULTS_DB_PATH = "prometheus_fire.duckdb"

@dataclass
class AppContext:
    log_manager: LogManager
    # 使用 default_factory 來延遲 duckdb 連線的建立
    # 這可以避免在多執行緒環境下，不同執行緒建立不同設定的連線
    duckdb_connection: duckdb.DuckDBPyConnection = field(default_factory=lambda: duckdb.connect(RESULTS_DB_PATH, read_only=False))

    def __post_init__(self):
        """
        在物件初始化後，設定需要延遲載入或需要 `self` 參考的屬性。
        """
        self.log_manager.log("DEBUG", "正在初始化 SQLiteQueue...")
        self.queue = SQLiteQueue(db_path=QUEUE_DB_PATH)

    def __del__(self):
        """
        在物件被銷毀前，確保關閉資料庫連線。
        """
        if self.duckdb_connection:
            self.duckdb_connection.close()
