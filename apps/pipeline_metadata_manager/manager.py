# -*- coding: utf-8 -*-
import hashlib
import os
import sys
from pathlib import Path
from typing import Optional

import duckdb

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    project_root = Path.cwd()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
# --- 標準化「路徑自我校正」樣板碼 END ---

from core.config import config as core_config
from core.logger import LogManager


def calculate_file_fingerprint(file_path: str, log_manager: LogManager) -> str:
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        fp = sha256_hash.hexdigest()
        log_manager.log("DEBUG", f"計算檔案 '{file_path}' 的指紋為: {fp}")
        return fp
    except FileNotFoundError:
        log_manager.log("ERROR", f"計算指紋時檔案未找到: {file_path}")
        raise
    except IOError:
        log_manager.log("ERROR", f"計算指紋時發生 IO 錯誤: {file_path}")
        raise


class MetadataManager:
    def __init__(
        self,
        log_manager: LogManager,
        db_path: Optional[str] = None,
        table_name: Optional[str] = None,
        connection: Optional[duckdb.DuckDBPyConnection] = None,
    ):
        self.log_manager = log_manager
        default_table_name = core_config.get("pipeline_metadata_manager.table_name", "processed_files_fallback")
        self.table_name = table_name if table_name is not None else default_table_name
        self.log_manager.log("DEBUG", f"MetadataManager 使用表格名稱: {self.table_name}")

        if connection:
            self.conn = connection
            self.db_path = db_path
            self.log_manager.log("INFO", f"MetadataManager 使用已存在的資料庫連接。DB 路徑: {self.db_path}")
        else:
            default_db_path = core_config.get("pipeline_metadata_manager.database_path", "metadata_fallback.sqlite")
            self.db_path = db_path if db_path is not None else default_db_path
            if not self.db_path:
                raise ValueError("Database path must be provided or set in config.")
            self.log_manager.log("INFO", f"MetadataManager 連接到資料庫: {self.db_path}")
            self.conn = duckdb.connect(database=self.db_path, read_only=False)
        self._initialize_database()

    def _initialize_database(self):
        try:
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    fingerprint TEXT PRIMARY KEY, filename TEXT NOT NULL, filesize INTEGER,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, etl_version TEXT
                )
            """)
            self.log_manager.log("INFO", f"資料庫表格 '{self.table_name}' 已初始化/確認存在。")
        except Exception as e:
            self.log_manager.log("ERROR", f"資料庫表格 '{self.table_name}' 初始化錯誤: {e}")
            raise

    def check_fingerprint_exists(self, fingerprint: str) -> bool:
        try:
            result = self.conn.execute(f"SELECT 1 FROM {self.table_name} WHERE fingerprint = ?", [fingerprint]).fetchone()
            exists = result is not None
            self.log_manager.log("DEBUG", f"指紋 '{fingerprint}' 在表格 '{self.table_name}' 中 {'存在' if exists else '不存在'} 。")
            return exists
        except Exception as e:
            self.log_manager.log("ERROR", f"查詢指紋 '{fingerprint}' 時發生錯誤: {e}")
            return False

    def write_fingerprint(self, fingerprint: str, filename: str, filesize: int, etl_version: Optional[str] = None) -> bool:
        resolved_etl_version = etl_version if etl_version is not None else core_config.get("pipeline_metadata_manager.default_etl_version", "unknown")
        self.log_manager.log("DEBUG", f"準備寫入指紋: {fingerprint}, 檔案: {filename}, 大小: {filesize}, ETL 版本: {resolved_etl_version}")
        try:
            self.conn.execute(
                f"INSERT INTO {self.table_name} (fingerprint, filename, filesize, etl_version) VALUES (?, ?, ?, ?) ON CONFLICT(fingerprint) DO NOTHING;",
                [fingerprint, filename, filesize, resolved_etl_version],
            )
            self.log_manager.log("INFO", f"指紋 '{fingerprint}' (檔案: {filename}) 已嘗試寫入表格 '{self.table_name}'。")
            return True
        except Exception as e:
            self.log_manager.log("ERROR", f"寫入指紋 '{fingerprint}' (檔案: {filename}) 時發生錯誤: {e}")
            return False

    def close(self):
        if hasattr(self, "conn") and self.conn:
            try:
                self.conn.close()
                self.log_manager.log("INFO", f"資料庫連接已關閉 (路徑: {self.db_path or '外部連接'})。")
            except Exception as e:
                self.log_manager.log("ERROR", f"關閉資料庫連接時發生錯誤: {e}")


if __name__ == "__main__":
    # Setup for standalone execution
    output_dir = project_root / "output"
    log_db_path = output_dir / "logs" / "standalone_test.sqlite"
    archive_dir = output_dir / "logs" / "archive"
    dummy_logger = LogManager(db_path=log_db_path, archive_dir=archive_dir)

    dummy_logger.log("INFO", "正在執行 MetadataManager 簡易測試...")
    TEST_FILE_DIR = project_root / "temp_test_data_metadata_manager"
    TEST_FILE_PATH = TEST_FILE_DIR / "sample_test_file_metadata.txt"
    TEST_FILE_DIR.mkdir(exist_ok=True)
    TEST_FILE_PATH.write_text("這是 MetadataManager 的測試檔案內容。")

    try:
        fingerprint1 = calculate_file_fingerprint(str(TEST_FILE_PATH), dummy_logger)
        manager = MetadataManager(log_manager=dummy_logger, db_path=":memory:", table_name="test_table")

        exists = manager.check_fingerprint_exists(fingerprint1)
        dummy_logger.log("INFO", f"指紋是否存在: {exists} (預期: False)")
        assert not exists

        success = manager.write_fingerprint(fingerprint1, TEST_FILE_PATH.name, TEST_FILE_PATH.stat().st_size, "v_test")
        dummy_logger.log("INFO", f"寫入是否成功: {success} (預期: True)")
        assert success

        exists_after = manager.check_fingerprint_exists(fingerprint1)
        dummy_logger.log("INFO", f"再次檢查指紋是否存在: {exists_after} (預期: True)")
        assert exists_after

        manager.close()
        dummy_logger.log("INFO", "所有簡易測試執行完畢。")
    except Exception as e:
        dummy_logger.log("ERROR", f"測試過程中發生錯誤: {e}")
    finally:
        if TEST_FILE_PATH.exists(): TEST_FILE_PATH.unlink()
        if TEST_FILE_DIR.exists(): TEST_FILE_DIR.rmdir()
        dummy_logger.log("INFO", "--- MetadataManager 測試結束 ---")
        dummy_logger.archive_to_file()
