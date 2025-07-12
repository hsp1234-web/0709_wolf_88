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

import hashlib
import os
from typing import Optional  # Ensure Dict and Any are imported if used by config

import duckdb

from core.config import config as core_config  # 導入核心配置
from core.logger import get_logger

logger = get_logger(__name__)


def calculate_file_fingerprint(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        fp = sha256_hash.hexdigest()
        logger.debug(f"計算檔案 '{file_path}' 的指紋為: {fp}")
        return fp
    except FileNotFoundError:
        logger.error(f"計算指紋時檔案未找到: {file_path}", exc_info=True)
        raise
    except IOError:
        logger.error(f"計算指紋時發生 IO 錯誤: {file_path}", exc_info=True)
        raise


class MetadataManager:
    conn: duckdb.DuckDBPyConnection
    db_path: Optional[str]
    table_name: str  # table_name will be resolved to a str

    def __init__(
        self,
        db_path: Optional[str] = None,
        table_name: Optional[str] = None,
        connection: Optional[duckdb.DuckDBPyConnection] = None,
    ):
        # 從核心配置讀取，如果參數未提供
        default_table_name_from_core = core_config.get(
            "pipeline_metadata_manager.table_name", "processed_files_fallback"
        )
        resolved_table_name = (
            table_name if table_name is not None else default_table_name_from_core
        )

        if resolved_table_name == "processed_files_fallback" and table_name is None:
            logger.warning(
                f"pipeline_metadata_manager.table_name 未在 config.yml 中設定，且未通過參數提供。使用預設後備名稱: {resolved_table_name}"
            )

        self.table_name = resolved_table_name
        logger.debug(f"MetadataManager 使用表格名稱: {self.table_name}")

        if connection is not None:
            self.conn = connection
            self.db_path = db_path  # db_path might be None if connection is passed
            logger.info(
                f"MetadataManager 使用已存在的資料庫連接。DB 路徑 (如果提供): {self.db_path}"
            )
        else:
            default_db_path_from_core = core_config.get(
                "pipeline_metadata_manager.database_path", "metadata_fallback.sqlite"
            )
            resolved_db_path = (
                db_path if db_path is not None else default_db_path_from_core
            )

            if resolved_db_path == "metadata_fallback.sqlite" and db_path is None:
                logger.warning(
                    f"pipeline_metadata_manager.database_path 未在 config.yml 中設定，且未通過參數提供。使用預設後備路徑: {resolved_db_path}"
                )

            if resolved_db_path is None:  # 雖然 core_config.get 有 default，但以防萬一
                logger.critical("MetadataManager 初始化失敗: 資料庫路徑無法解析。")
                raise ValueError(
                    "Database path must be provided or set in config if no connection is given."
                )
            self.db_path = resolved_db_path
            logger.info(f"MetadataManager 連接到資料庫: {self.db_path}")
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
            logger.info(f"資料庫表格 '{self.table_name}' 已初始化/確認存在。")
        except Exception as e:
            logger.error(
                f"資料庫表格 '{self.table_name}' 初始化錯誤: {e}", exc_info=True
            )
            raise

    def check_fingerprint_exists(self, fingerprint: str) -> bool:
        try:
            result = self.conn.execute(
                f"SELECT 1 FROM {self.table_name} WHERE fingerprint = ?", [fingerprint]
            ).fetchone()
            exists = result is not None
            logger.debug(
                f"指紋 '{fingerprint}' 在表格 '{self.table_name}' 中 {'存在' if exists else '不存在'} 。"
            )
            return exists
        except Exception as e:
            logger.error(f"查詢指紋 '{fingerprint}' 時發生錯誤: {e}", exc_info=True)
            return False  # 保守起見，查詢失敗時假設不存在或讓上層處理

    def write_fingerprint(
        self,
        fingerprint: str,
        filename: str,
        filesize: int,
        etl_version: Optional[str] = None,
    ) -> bool:
        default_etl_version_from_core = core_config.get(
            "pipeline_metadata_manager.default_etl_version", "unknown_etl_fallback"
        )
        resolved_etl_version = (
            etl_version if etl_version is not None else default_etl_version_from_core
        )

        if resolved_etl_version == "unknown_etl_fallback" and etl_version is None:
            logger.warning(
                f"pipeline_metadata_manager.default_etl_version 未在 config.yml 中設定，且未通過參數提供。使用預設後備版本: {resolved_etl_version}"
            )

        if (
            resolved_etl_version is None
        ):  # Should not happen with fallback, but as a safeguard
            logger.warning(
                "ETL 版本解析為 None，將使用 NULL (或資料庫預設) 寫入資料庫。"
            )
            # No explicit pass needed, NULL will be inserted if DB schema allows

        logger.debug(
            f"準備寫入指紋: {fingerprint}, 檔案: {filename}, 大小: {filesize}, ETL 版本: {resolved_etl_version}"
        )
        try:
            self.conn.execute(
                f"""
                INSERT INTO {self.table_name} (fingerprint, filename, filesize, etl_version)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(fingerprint) DO NOTHING;
                """,
                [fingerprint, filename, filesize, resolved_etl_version],
            )
            # DuckDB's cursor.rowcount is not reliably set for INSERT ON CONFLICT DO NOTHING
            # We assume success if no exception is raised.
            # To check if a row was actually inserted (vs conflict occurred), a SELECT would be needed.
            # For now, "success" means the operation completed without error.
            logger.info(
                f"指紋 '{fingerprint}' (檔案: {filename}) 已嘗試寫入表格 '{self.table_name}'。"
            )
            return True
        except Exception as e:
            logger.error(
                f"寫入指紋 '{fingerprint}' (檔案: {filename}) 時發生錯誤: {e}",
                exc_info=True,
            )
            return False

    def close(self):
        if hasattr(self, "conn") and self.conn:
            try:
                self.conn.close()
                logger.info(
                    f"資料庫連接已關閉 (路徑: {self.db_path or '使用外部連接'})。"
                )
            except Exception as e:
                logger.error(f"關閉資料庫連接時發生錯誤: {e}", exc_info=True)


if __name__ == "__main__":
    logger.info("正在執行 MetadataManager 簡易測試...")

    TEST_FILE_DIR = "temp_test_data_metadata_manager"  # 避免與其他測試衝突
    TEST_FILE_NAME = "sample_test_file_metadata.txt"
    TEST_FILE_PATH = os.path.join(TEST_FILE_DIR, TEST_FILE_NAME)

    os.makedirs(TEST_FILE_DIR, exist_ok=True)
    with open(TEST_FILE_PATH, "w") as f:
        f.write("這是 MetadataManager 的測試檔案內容。")

    file_size = os.path.getsize(TEST_FILE_PATH)

    logger.info(f"計算檔案 '{TEST_FILE_PATH}' 的指紋...")
    fingerprint1: Optional[str] = None  # Declare type here
    try:
        fingerprint1 = calculate_file_fingerprint(TEST_FILE_PATH)
        logger.info(f"  指紋: {fingerprint1}")
    except Exception as e:
        logger.error(f"  計算指紋失敗: {e}", exc_info=True)
        # fingerprint1 remains None as initialized

    manager: Optional[MetadataManager] = None  # For finally block
    if fingerprint1:
        logger.info("初始化 MetadataManager (使用記憶體資料庫)...")
        # 本地 config 的模擬不再需要，因為 MetadataManager 直接從 core_config 或參數獲取配置
        # manager = MetadataManager(db_path=":memory:")
        # 為了測試，可以明確指定 table_name，或者依賴 core_config 中的設定和後備邏輯
        # 如果 core_config.yml 中已設定 pipeline_metadata_manager.table_name，則以下 table_name 參數可選
        manager = MetadataManager(
            db_path=":memory:", table_name="test_processed_files_main_block"
        )

        logger.info(f"檢查指紋 '{fingerprint1}' 是否存在...")
        exists = manager.check_fingerprint_exists(fingerprint1)
        logger.info(f"  指紋是否存在: {exists} (預期: False)")
        assert not exists, "測試失敗：新指紋不應存在"

        logger.info(
            f"寫入指紋 '{fingerprint1}' (檔案: {TEST_FILE_NAME}, 大小: {file_size})..."
        )
        success = manager.write_fingerprint(
            fingerprint1, TEST_FILE_NAME, file_size, "v_test"
        )
        logger.info(f"  寫入是否成功: {success} (預期: True)")
        assert success, "測試失敗：指紋寫入失敗"

        logger.info(f"再次檢查指紋 '{fingerprint1}' 是否存在...")
        exists_after_write = manager.check_fingerprint_exists(fingerprint1)
        logger.info(f"  指紋是否存在: {exists_after_write} (預期: True)")
        assert exists_after_write, "測試失敗：寫入後的指紋應存在"

        logger.info(f"嘗試再次寫入重複指紋 '{fingerprint1}'...")
        success_duplicate = manager.write_fingerprint(
            fingerprint1, "sample_test_file_copy.txt", file_size + 100, "v_test_dup"
        )
        logger.info(
            f"  重複寫入是否回報成功: {success_duplicate} (預期: True, 因 ON CONFLICT DO NOTHING)"
        )
        assert success_duplicate, "測試失敗：重複指紋寫入應回報成功"

        TEST_FILE_NAME_2 = "another_sample_metadata.txt"
        TEST_FILE_PATH_2 = os.path.join(TEST_FILE_DIR, TEST_FILE_NAME_2)
        with open(TEST_FILE_PATH_2, "w") as f:
            f.write("這是另一個不同的測試檔案。")
        file_size_2 = os.path.getsize(TEST_FILE_PATH_2)

        logger.info(f"計算檔案 '{TEST_FILE_PATH_2}' 的指紋...")
        fingerprint2 = calculate_file_fingerprint(TEST_FILE_PATH_2)
        logger.info(f"  指紋: {fingerprint2}")
        assert fingerprint1 != fingerprint2, "測試失敗：不同檔案應有不同指紋"

        logger.info(f"寫入指紋 '{fingerprint2}'...")
        success2 = manager.write_fingerprint(
            fingerprint2, TEST_FILE_NAME_2, file_size_2, "v_test_2"
        )
        assert success2, "測試失敗：第二個指紋寫入失敗"

        exists2 = manager.check_fingerprint_exists(fingerprint2)
        assert exists2, "測試失敗：第二個指紋寫入後應存在"

        logger.info("所有簡易測試執行完畢。")

    try:
        if manager:
            manager.close()
        os.remove(TEST_FILE_PATH)
        os.remove(TEST_FILE_PATH_2)
        os.rmdir(TEST_FILE_DIR)
        logger.info("臨時測試檔案已清理。")
    except OSError as e:
        logger.error(f"清理測試檔案時發生錯誤: {e}", exc_info=True)
    except (
        NameError
    ):  # TEST_FILE_PATH etc might not be defined if fingerprint1 calculation failed
        logger.warning("部分測試檔案可能未創建，清理步驟跳過部分內容。")

    logger.info("--- MetadataManager 測試結束 ---")
