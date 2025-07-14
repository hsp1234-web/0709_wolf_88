from dataclasses import dataclass, field
from functools import lru_cache

from src.core.logger import LogManager
from src.core.queue.sqlite_queue import SQLiteQueue
from src.core.queue.base import BaseQueue

# 定義常數以避免硬編碼
QUEUE_DB_PATH = "output/task_queue.db"

@dataclass
class AppContext:
    """
    作戰上下文：一個集中容器，持有所有共享服務的實例。
    """
    log_manager: LogManager
    queue: BaseQueue = field(init=False)

    def __post_init__(self):
        """
        在物件初始化後，設定需要延遲載入或需要 `self` 參考的屬性。
        """
        self.log_manager.log("DEBUG", "正在初始化 SQLiteQueue...")
        self.queue = SQLiteQueue(db_path=QUEUE_DB_PATH)
