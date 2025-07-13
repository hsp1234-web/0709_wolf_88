# core/logger.py

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytz


class LogManager:
    """
    後端日誌管理器，負責將日誌寫入 SQLite 並在任務結束時歸檔。
    設計為在後端獨立運作。
    """
    def __init__(self, db_path: Path, archive_dir: Path):
        self.db_path = db_path
        self.archive_dir = archive_dir
        self.taipei_tz = pytz.timezone('Asia/Taipei')

        os.makedirs(self.db_path.parent, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.row_factory = sqlite3.Row
        self._setup_database()
        self.log("BATTLE", f"LogManager 初始化完成。日誌數據庫: {self.db_path}")

    def _setup_database(self):
        with self._conn:
            self._conn.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, timestamp TEXT, level TEXT, message TEXT)")

    def log(self, level: str, message: str):
        ts_iso = datetime.now(self.taipei_tz).isoformat()
        ts_display = datetime.fromisoformat(ts_iso).strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{ts_display}] [{level}] {message}") # 即時輸出到終端機
        try:
            with self._conn:
                self._conn.execute("INSERT INTO logs (timestamp, level, message) VALUES (?, ?, ?)", (ts_iso, level, message))
        except Exception as e:
            print(f"FATAL: LogDB 寫入失敗: {e}", file=sys.stderr)

    def archive_to_file(self):
        """將資料庫中的所有日誌歸檔到一個文字檔中。"""
        self.log("BATTLE", "--- 開始歸檔作戰報告 ---")
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT timestamp, level, message FROM logs ORDER BY id ASC")
            all_logs = [dict(row) for row in cursor.fetchall()]

            if not all_logs:
                self.log("INFO", "日誌資料庫為空，無需生成戰報檔案。")
                return

            ts_file = datetime.now(self.taipei_tz).strftime('%Y%m%d_%H%M%S')
            filename = f"battle_report_{ts_file}.txt"
            archive_filepath = self.archive_dir / filename

            with open(archive_filepath, "w", encoding="utf-8") as f:
                f.write("--- 作戰報告 ---\n")
                f.write(f"生成時間: {datetime.now(self.taipei_tz).isoformat()}\n")
                f.write("========================================\n\n")
                for log_item in all_logs:
                    ts_str = datetime.fromisoformat(log_item['timestamp']).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    f.write(f"[{ts_str}] [{log_item['level']}] {log_item['message']}\n")

            self.log("SUCCESS", f"✅ 作戰報告已成功歸檔至: {archive_filepath}")
        except Exception as e:
            self.log("ERROR", f"❌ 歸檔作戰日誌失敗: {e}")
        finally:
            if self._conn:
                self._conn.close()
                self.log("INFO", "日誌資料庫連線已關閉。")
