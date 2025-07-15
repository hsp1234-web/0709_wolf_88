import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


import sqlite3
import datetime

class LogManager:
    """一個集中式的日誌管理器，確保全應用程式使用統一的日誌設定。"""

    def __init__(
        self,
        session_name: str,
        log_dir: str = "logs",
        log_file: str = "prometheus.log",
        db_path: str = "output/logs",
        log_level=logging.INFO,
    ):
        self.session_name = session_name
        os.makedirs(db_path, exist_ok=True)
        db_name = f"session_{session_name}_{os.getpid()}.sqlite"
        self.db_path = os.path.join(db_path, db_name)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._setup_database()
        print(f"[BATTLE] LogManager 初始化完成。日誌數據庫: {self.db_path}")

        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        self.log_file_path = log_path / log_file
        self.log_level = log_level
        self._loggers = {}

    def _setup_database(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                level TEXT,
                message TEXT
            )
        """)
        self.conn.commit()

    def log_to_db(self, level: str, message: str, exc_info: bool = False):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO logs (level, message) VALUES (?, ?)", (level, message)
            )
            self.conn.commit()
        except Exception as e:
            print(f"FATAL: LogDB 寫入失敗: {e}")

    def close(self):
        """【新增】統一的資源關閉方法。"""
        self.log_to_db("BATTLE", "--- 開始歸檔作戰報告 ---")
        self.archive_to_file()
        if self.conn:
            self.conn.close()
            print("INFO: 日誌資料庫連線已關閉。報告已歸檔。")

    def archive_to_file(self):
        archive_dir = "output/logs/archive"
        os.makedirs(archive_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = os.path.join(
            archive_dir,
            f"battle_report_{self.session_name}_{os.getpid()}_{timestamp}.txt",
        )

        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT timestamp, level, message FROM logs ORDER BY timestamp ASC"
            )
            with open(archive_path, "w", encoding="utf-8") as f:
                for row in cursor.fetchall():
                    f.write(f"[{row[0]}] [{row[1]}] {row[2]}\n")
            self.log_to_db("SUCCESS", f"✅ 作戰報告已成功歸檔至: {archive_path}")
        except Exception as e:
            print(f"ERROR: 歸檔日誌時出錯: {e}")

    def get_logger(self, name: str) -> logging.Logger:
        if name in self._loggers:
            return self._loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(self.log_level)

        # 防止在測試或多重初始化中重複添加 handlers
        if not logger.handlers:
            # 檔案 handler
            handler = RotatingFileHandler(
                self.log_file_path,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

            # 主控台 handler
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)

        self._loggers[name] = logger
        return logger
