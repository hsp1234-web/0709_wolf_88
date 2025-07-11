# -*- coding: utf-8 -*-
"""
作戰日誌與指紋驗證模組

核心職責：
1.  檔案指紋計算：提供一個函數，能接收一個檔案路徑，並計算該檔案的 SHA-256 雜湊值。
2.  日誌資料庫互動：
    *   建立一個專用的日誌資料庫（例如 pipeline_metadata.duckdb）。
    *   提供「查詢指紋是否存在」的功能。
    *   提供「寫入新指紋及元數據（檔名、大小、處理時間）」的功能。
"""
from __future__ import annotations
from typing import Optional # Ensure Dict and Any are imported if used by config
import hashlib
import duckdb
import os

from . import config


def calculate_file_fingerprint(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        raise
    except IOError:
        raise


class MetadataManager:
    conn: duckdb.DuckDBPyConnection
    db_path: Optional[str]
    table_name: str # table_name will be resolved to a str

    def __init__(
        self,
        db_path: Optional[str] = None,
        table_name: Optional[str] = None,
        connection: Optional[duckdb.DuckDBPyConnection] = None,
    ):
        resolved_table_name = table_name if table_name is not None else config.PROCESSED_FILES_TABLE_NAME
        if resolved_table_name is None: # Should not happen if config has a default
             raise ValueError("Table name must be provided or set in config.")
        self.table_name = resolved_table_name


        if connection is not None:
            self.conn = connection
            self.db_path = db_path
        else:
            resolved_db_path = db_path if db_path is not None else config.DATABASE_FILENAME
            if resolved_db_path is None:
                raise ValueError(
                    "Database path must be provided or set in config if no connection is given."
                )
            self.db_path = resolved_db_path
            self.conn = duckdb.connect(database=self.db_path, read_only=False)

        self._initialize_database()

    def _initialize_database(self):
        try:
            self.conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    fingerprint TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    filesize INTEGER,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    etl_version TEXT
                )
            """
            )
        except Exception as e:
            print(f"資料庫初始化錯誤: {e}")
            raise

    def check_fingerprint_exists(self, fingerprint: str) -> bool:
        try:
            result = self.conn.execute(
                f"SELECT 1 FROM {self.table_name} WHERE fingerprint = ?", [fingerprint]
            ).fetchone()
            return result is not None
        except Exception as e:
            print(f"查詢指紋時發生錯誤: {e}")
            return False

    def write_fingerprint(
        self, fingerprint: str, filename: str, filesize: int, etl_version: Optional[str] = None
    ) -> bool:
        resolved_etl_version = (
            etl_version if etl_version is not None else config.DEFAULT_ETL_VERSION
        )
        # Ensure resolved_etl_version is not None before DB insert if DB schema requires it
        if resolved_etl_version is None:
            # Handle case where DEFAULT_ETL_VERSION might also be None or not set
            # For now, let's assume it resolves to a string or DB handles NULL if allowed for etl_version column
            # If etl_version column in DB is NOT NULL, this could be an issue.
            # Based on current schema (TEXT), it likely allows NULL.
            pass

        try:
            self.conn.execute(
                f"""
                INSERT INTO {self.table_name} (fingerprint, filename, filesize, etl_version)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(fingerprint) DO NOTHING;
                """,
                [fingerprint, filename, filesize, resolved_etl_version],
            )
            return True
        except Exception as e:
            print(f"寫入指紋時發生錯誤: {e}")
            return False


if __name__ == "__main__":
    print("正在執行 MetadataManager 簡易測試...")

    TEST_FILE_DIR = "temp_test_data"
    TEST_FILE_NAME = "sample_test_file.txt"
    TEST_FILE_PATH = os.path.join(TEST_FILE_DIR, TEST_FILE_NAME)

    os.makedirs(TEST_FILE_DIR, exist_ok=True)
    with open(TEST_FILE_PATH, "w") as f:
        f.write("這是 MetadataManager 的測試檔案內容。")

    file_size = os.path.getsize(TEST_FILE_PATH)

    print(f"計算檔案 '{TEST_FILE_PATH}' 的指紋...")
    fingerprint1: Optional[str] = None # Declare type here
    try:
        fingerprint1 = calculate_file_fingerprint(TEST_FILE_PATH)
        print(f"  指紋: {fingerprint1}")
    except Exception as e:
        print(f"  計算指紋失敗: {e}")
        # fingerprint1 remains None as initialized

    if fingerprint1:
        print("初始化 MetadataManager (使用記憶體資料庫)...")
        # Ensure config attributes are available for the test
        if not hasattr(config, 'PROCESSED_FILES_TABLE_NAME'):
            config.PROCESSED_FILES_TABLE_NAME = "processed_files_test"
        if not hasattr(config, 'DATABASE_FILENAME'):
            # For in-memory, db_path is explicitly ":memory:", so DATABASE_FILENAME isn't strictly needed by __init__
            # but good to have a fallback for MetadataManager if it were to rely on it without db_path override.
            config.DATABASE_FILENAME = ":memory:"
        if not hasattr(config, 'DEFAULT_ETL_VERSION'):
            config.DEFAULT_ETL_VERSION = "test_v0.1"


        manager = MetadataManager(db_path=":memory:")

        print(f"檢查指紋 '{fingerprint1}' 是否存在...")
        exists = manager.check_fingerprint_exists(fingerprint1)
        print(f"  指紋是否存在: {exists} (預期: False)")
        assert not exists, "測試失敗：新指紋不應存在"

        print(
            f"寫入指紋 '{fingerprint1}' (檔案: {TEST_FILE_NAME}, 大小: {file_size})..."
        )
        success = manager.write_fingerprint(
            fingerprint1, TEST_FILE_NAME, file_size, "v_test"
        )
        print(f"  寫入是否成功: {success} (預期: True)")
        assert success, "測試失敗：指紋寫入失敗"

        print(f"再次檢查指紋 '{fingerprint1}' 是否存在...")
        exists_after_write = manager.check_fingerprint_exists(fingerprint1)
        print(f"  指紋是否存在: {exists_after_write} (預期: True)")
        assert exists_after_write, "測試失敗：寫入後的指紋應存在"

        print(f"嘗試再次寫入重複指紋 '{fingerprint1}'...")
        success_duplicate = manager.write_fingerprint(
            fingerprint1, "sample_test_file_copy.txt", file_size + 100, "v_test_dup"
        )
        print(
            f"  重複寫入是否回報成功: {success_duplicate} (預期: True, 因 ON CONFLICT DO NOTHING)"
        )
        assert success_duplicate, "測試失敗：重複指紋寫入應回報成功"

        TEST_FILE_NAME_2 = "another_sample.txt"
        TEST_FILE_PATH_2 = os.path.join(TEST_FILE_DIR, TEST_FILE_NAME_2)
        with open(TEST_FILE_PATH_2, "w") as f:
            f.write("這是另一個不同的測試檔案。")
        file_size_2 = os.path.getsize(TEST_FILE_PATH_2)

        print(f"計算檔案 '{TEST_FILE_PATH_2}' 的指紋...")
        fingerprint2 = calculate_file_fingerprint(TEST_FILE_PATH_2)
        print(f"  指紋: {fingerprint2}")
        assert fingerprint1 != fingerprint2, "測試失敗：不同檔案應有不同指紋"

        print(f"寫入指紋 '{fingerprint2}'...")
        success2 = manager.write_fingerprint(
            fingerprint2, TEST_FILE_NAME_2, file_size_2, "v_test_2"
        )
        assert success2, "測試失敗：第二個指紋寫入失敗"

        exists2 = manager.check_fingerprint_exists(fingerprint2)
        assert exists2, "測試失敗：第二個指紋寫入後應存在"

        print("所有簡易測試執行完畢。")

    try:
        os.remove(TEST_FILE_PATH)
        os.remove(TEST_FILE_PATH_2)
        os.rmdir(TEST_FILE_DIR)
        print("臨時測試檔案已清理。")
    except OSError as e:
        print(f"清理測試檔案時發生錯誤: {e}")

    print("--- MetadataManager 測試結束 ---")
