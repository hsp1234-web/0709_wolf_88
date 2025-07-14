import logging
import sqlite3
import os
from datetime import datetime
from pathlib import Path
import pytz
import sys

class LogManager:
    """
    一個多進程安全的日誌管理器。
    為每個工作階段 (session) 創建一個唯一的日誌資料庫。
    """
    def __init__(self, session_name: str = "default"):
        self.session_name = session_name
        self.pid = os.getpid() # 獲取當前進程 ID
        self.taipei_tz = pytz.timezone('Asia/Taipei')

        # === 核心變更：生成唯一的日誌檔名 ===
        log_db_filename = f"session_{self.session_name}_{self.pid}.sqlite"
        self.log_db_path = Path("output/logs") / log_db_filename
        self.log_db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self.log_db_path, check_same_thread=False, timeout=10)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.row_factory = sqlite3.Row
        self._init_db()
        self.log("BATTLE", f"LogManager 初始化完成。日誌數據庫: {self.log_db_path}")

    def _init_db(self):
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    level TEXT,
                    message TEXT
                )
            """)

    def log(self, level: str, message: str):
        ts_iso = datetime.now(self.taipei_tz).isoformat()
        ts_display = datetime.fromisoformat(ts_iso).strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{ts_display}] [{level}] {message}") # 即時輸出到終端機
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO logs (timestamp, level, message) VALUES (?, ?, ?)",
                    (ts_iso, level, message)
                )
        except sqlite3.ProgrammingError as e:
            # 如果資料庫已關閉，則打印到控制台
            print(f"FATAL: LogDB 寫入失敗: {e}. Log: [{level}] {message}", file=sys.stderr)
        except Exception as e:
            print(f"FATAL: LogDB 寫入失敗: {e}", file=sys.stderr)


    def close_and_archive(self):
        if not self._conn:
            return

        self.log("BATTLE", "--- 開始歸檔作戰報告 ---")

        archive_dir = Path("output/logs/archive")
        archive_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = datetime.now(self.taipei_tz).strftime("%Y%m%d_%H%M%S")
        archive_filename = f"battle_report_{self.session_name}_{self.pid}_{timestamp_str}.txt"
        archive_path = archive_dir / archive_filename

        try:
            with open(archive_path, "w", encoding="utf-8") as f:
                cursor = self._conn.cursor()
                for row in cursor.execute("SELECT timestamp, level, message FROM logs ORDER BY id"):
                    ts_str = datetime.fromisoformat(row['timestamp']).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    f.write(f"[{ts_str}] [{row['level']}] {row['message']}\n")

            self.log("SUCCESS", f"✅ 作戰報告已成功歸檔至: {archive_path}")

        except Exception as e:
            self.log("ERROR", f"❌ 歸檔作戰日誌失敗: {e}")
        finally:
            if self._conn:
                self._conn.close()
                self._conn = None
                print(f"INFO: 日誌資料庫連線已關閉。報告已歸檔至 {archive_path}")
