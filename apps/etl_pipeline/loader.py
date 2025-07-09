# -*- coding: utf-8 -*-
"""
軍火庫裝載機 (Database Loader) 核心模組 (ETL Pipeline版)

此模組負責將標準化的 Parquet 檔案（或其他格式，未來可擴展）
載入到 DuckDB 資料庫中，並處理潛在的入庫衝突。
"""
import duckdb
import pandas as pd
from pathlib import Path
import logging
from typing import Optional, List, Dict # Removed Any as it was not used
import argparse # 新增 argparse for run_loading
import sys # 新增 sys for logging

# 模組級別 logger
MODULE_LOGGER = logging.getLogger(__name__)
if not MODULE_LOGGER.handlers:
    stream_handler = logging.StreamHandler(sys.stdout) #確保日誌輸出到stdout
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stream_handler.setFormatter(formatter)
    MODULE_LOGGER.addHandler(stream_handler)
    MODULE_LOGGER.setLevel(logging.INFO)

class SchemaMismatchError(Exception):
    """自定義異常，用於表示嘗試載入的數據與目標表格的 Schema 不匹配。"""
    pass

def _get_parquet_schema(parquet_path: str, logger: logging.Logger) -> List[Dict[str, str]]:
    """讀取 Parquet 檔案的 schema。"""
    try:
        temp_conn = duckdb.connect(':memory:')
        query = f"DESCRIBE SELECT * FROM read_parquet('{parquet_path}')"
        schema_info = temp_conn.execute(query).fetchall()
        temp_conn.close()
        if not schema_info:
            logger.warning(f"無法從 Parquet 檔案 {parquet_path} 中獲取 schema (DESCRIBE 結果為空)。")
            return []
        schema = [{'name': str(col[0]), 'type': str(col[1]).upper()} for col in schema_info]
        logger.debug(f"從 Parquet '{parquet_path}' 獲取的 Schema: {schema}")
        return schema
    except Exception as e:
        logger.error(f"讀取 Parquet 檔案 '{parquet_path}' 的 schema 時發生錯誤: {e}")
        raise

def _get_table_schema_from_db(db_conn: duckdb.DuckDBPyConnection, table_name: str, logger: logging.Logger) -> Optional[List[Dict[str, str]]]:
    """從資料庫中獲取現有表格的 schema。"""
    try:
        check_table_query = f"SELECT table_name FROM information_schema.tables WHERE table_name = '{table_name.lower()}'"
        table_exists_result = db_conn.execute(check_table_query).fetchone()
        if not table_exists_result:
            logger.info(f"表格 '{table_name}' 在資料庫中不存在。")
            return None
        schema_info = db_conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        if not schema_info:
            logger.warning(f"無法從資料庫中獲取表格 '{table_name}' 的 schema (PRAGMA table_info 結果為空)。")
            return None
        schema = [{'name': str(col[1]), 'type': str(col[2]).upper()} for col in schema_info]
        logger.debug(f"從資料庫表格 '{table_name}' 獲取的 Schema: {schema}")
        return schema
    except Exception as e:
        logger.error(f"從資料庫獲取表格 '{table_name}' 的 schema 時發生錯誤: {e}")
        raise

def _compare_schemas(parquet_schema: List[Dict[str, str]], table_schema: List[Dict[str, str]], logger: logging.Logger) -> bool:
    """比較兩個 schema 是否匹配。"""
    logger.debug(f"DEBUG _compare_schemas: Parquet schema: {parquet_schema}")
    logger.debug(f"DEBUG _compare_schemas: Table schema: {table_schema}")
    if not parquet_schema and not table_schema:
        logger.info("Parquet schema 與目標表格 schema 匹配 (兩者皆空)。")
        return True
    if not parquet_schema or not table_schema:
        logger.warning(f"Schema 不匹配：其中一個 schema 為空。Parquet empty: {not parquet_schema}, Table empty: {not table_schema}")
        return False
    if len(parquet_schema) != len(table_schema):
        logger.warning(f"Schema 不匹配：欄位數量不同。Parquet: {len(parquet_schema)}, Table: {len(table_schema)}")
        return False
    for i in range(len(parquet_schema)):
        pq_col = parquet_schema[i]
        tbl_col = table_schema[i]
        if pq_col['name'].lower() != tbl_col['name'].lower():
            logger.warning(f"Schema 不匹配：欄位名稱在位置 {i} 不同。Parquet: '{pq_col['name']}', Table: '{tbl_col['name']}'")
            return False
    logger.info("Parquet schema 與目標表格 schema 匹配。")
    return True

def _load_parquet_to_db_internal( # Renamed from load_parquet_to_db
    parquet_path_str: str,
    db_path_str: str,
    table_name: str,
    primary_key_column: Optional[str] = None,
    logger: Optional[logging.Logger] = None # Kept logger argument for flexibility
) -> bool: # Return True for success, False for failure
    """核心邏輯：將 Parquet 檔案的數據載入到 DuckDB 資料庫。"""
    effective_logger = logger if logger else MODULE_LOGGER # Use module logger if specific one isn't passed
    parquet_path = Path(parquet_path_str)

    if not parquet_path.exists() or not parquet_path.is_file():
        effective_logger.error(f"Parquet 檔案不存在或不是一個檔案。檔案路徑: {parquet_path}")
        return False

    db_conn: Optional[duckdb.DuckDBPyConnection] = None
    try:
        effective_logger.info(f"準備將 Parquet 檔案 '{parquet_path.name}' 載入到資料庫 '{db_path_str}' 的表格 '{table_name}'。")
        # 確保資料庫目錄存在
        db_dir = Path(db_path_str).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        db_conn = duckdb.connect(database=db_path_str, read_only=False)
        effective_logger.info(f"成功連接到資料庫 '{db_path_str}'。")

        pq_schema = _get_parquet_schema(str(parquet_path), effective_logger)
        if not pq_schema:
            effective_logger.error(f"無法確定 Parquet 檔案 '{parquet_path.name}' 的 schema，終止載入。")
            if db_conn: db_conn.close()
            return False

        db_table_schema = _get_table_schema_from_db(db_conn, table_name, effective_logger)

        if db_table_schema is None:
            effective_logger.info(f"表格 '{table_name}' 不存在，將根據 Parquet 檔案 schema 創建。")
            db_conn.execute(f"CREATE TABLE \"{table_name}\" AS SELECT * FROM read_parquet('{str(parquet_path)}')")
            effective_logger.info(f"成功創建表格 '{table_name}' 並從 '{parquet_path.name}' 載入數據。")
        else:
            effective_logger.info(f"表格 '{table_name}' 已存在。將進行 schema 驗證和冪等載入。")
            if not _compare_schemas(pq_schema, db_table_schema, effective_logger):
                # Raise SchemaMismatchError to be caught by run_loading
                raise SchemaMismatchError(
                    f"Parquet 檔案 '{parquet_path.name}' 的 schema 與現有表格 '{table_name}' 的 schema 不匹配。"
                )

            if primary_key_column:
                if not any(col['name'].lower() == primary_key_column.lower() for col in pq_schema):
                    effective_logger.error(f"提供的主鍵欄位 '{primary_key_column}' 不存在於 Parquet。執行簡單追加。")
                    db_conn.execute(f"INSERT INTO \"{table_name}\" SELECT * FROM read_parquet('{str(parquet_path)}')")
                else:
                    staging_table_name = f"staging_load_{table_name}_{Path(parquet_path).stem.replace('-', '_')}"
                    effective_logger.info(f"使用主鍵 '{primary_key_column}' 進行冪等載入。暫存表: '{staging_table_name}'。")
                    db_conn.execute(f"CREATE TEMP TABLE \"{staging_table_name}\" AS SELECT * FROM read_parquet('{str(parquet_path)}')")
                    safe_pk_column = f'"{primary_key_column}"'
                    insert_query = f"""
                    INSERT INTO "{table_name}"
                    SELECT * FROM "{staging_table_name}" src
                    WHERE NOT EXISTS (
                        SELECT 1 FROM "{table_name}" dest
                        WHERE dest.{safe_pk_column} = src.{safe_pk_column}
                    );
                    """
                    db_conn.execute(insert_query)
                    # Row count logging can be added here if needed
                    db_conn.execute(f"DROP TABLE IF EXISTS \"{staging_table_name}\"")
                    effective_logger.info(f"冪等載入完成。")
            else:
                effective_logger.info(f"未提供主鍵。將 '{parquet_path.name}' 中的數據追加到 '{table_name}'。")
                db_conn.execute(f"INSERT INTO \"{table_name}\" SELECT * FROM read_parquet('{str(parquet_path)}')")

        return True # Success
    except duckdb.IOException as e_lock:
        effective_logger.error(f"[ERROR] 資料庫 '{db_path_str}' I/O 錯誤或鎖定: {e_lock}")
        return False
    except SchemaMismatchError as e_schema: # Caught from _compare_schemas or raised directly
        effective_logger.error(f"[ERROR] Schema 不匹配導致載入失敗: {e_schema}")
        # No need to re-raise, run_loading will catch this from _load_parquet_to_db_internal
        return False # Indicate failure
    except Exception as e:
        effective_logger.error(f"載入 Parquet '{parquet_path.name}' 時發生未預期錯誤: {e}", exc_info=True)
        return False
    finally:
        if db_conn is not None:
            try:
                db_conn.close()
                effective_logger.info(f"資料庫連接 '{db_path_str}' 已關閉。")
            except Exception as e_close:
                effective_logger.error(f"關閉資料庫連接 '{db_path_str}' 時發生錯誤: {e_close}")


def run_loading(argv: Optional[List[str]] = None) -> bool:
    """
    數據庫加載模組的命令行介面入口點。
    argv: 從命令行傳遞的參數列表 (不含程式名稱本身)。
    返回 True 表示成功，False 表示失敗。
    """
    parser = argparse.ArgumentParser(description="Database Loading Module (ETL Pipeline)")
    parser.add_argument("--parquet-file", required=True, help="Path to the input Parquet file.")
    parser.add_argument("--db-path", required=True, help="Path to the DuckDB database file.")
    parser.add_argument("--table-name", required=True, help="Target table name in the database.")
    parser.add_argument("--primary-key", help="Primary key column for idempotent loading.")
    parser.add_argument("--loglevel", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

    args = parser.parse_args(argv)

    current_logger = MODULE_LOGGER
    log_level_attr = getattr(logging, args.loglevel.upper(), logging.INFO)
    current_logger.setLevel(log_level_attr)

    if not current_logger.handlers: # Ensure handler for direct calls or specific environments
        stream_handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        stream_handler.setFormatter(formatter)
        current_logger.addHandler(stream_handler)
        current_logger.info(f"為 loader 模組 logger 新增了 StreamHandler，等級設為 {args.loglevel.upper()}")

    current_logger.info(f"ETL Loader: 載入 Parquet '{args.parquet_file}' 到 DB '{args.db_path}', 表 '{args.table_name}'。")

    success = False
    try:
        # _load_parquet_to_db_internal now returns a boolean
        success = _load_parquet_to_db_internal(
            args.parquet_file,
            args.db_path,
            args.table_name,
            primary_key_column=args.primary_key,
            logger=current_logger # Pass the configured logger
        )
        if success:
            current_logger.info(f"ETL Loader: 任務成功完成。Parquet: '{args.parquet_file}' -> DB: '{args.db_path}', Table: '{args.table_name}'")
        else:
            # _load_parquet_to_db_internal should have logged the specific error
            current_logger.error(f"ETL Loader: 任務失敗。Parquet: '{args.parquet_file}'")

    except SchemaMismatchError:
        # This specific catch is now less likely here if _load_parquet_to_db_internal handles it and returns False
        # However, keeping it defensively in case _get_parquet_schema or _get_table_schema_from_db are called directly
        # and raise it before _load_parquet_to_db_internal is entered or if it re-raises.
        # Based on current _load_parquet_to_db_internal, it catches SchemaMismatchError and returns False.
        current_logger.error("ETL Loader: 任務因 Schema 不匹配而失敗 (捕獲於 run_loading)。")
        success = False # Ensure success is False
    except Exception as e:
        current_logger.error(f"ETL Loader: 任務因未預期錯誤而失敗 (捕獲於 run_loading): {e}", exc_info=True)
        success = False # Ensure success is False

    return success

# 原有的 if __name__ == '__main__': 區塊已移除
# 獨立測試可通過以下方式：
# if __name__ == '__main__':
#     # 創建臨時目錄和檔案用於測試
#     test_dir = Path("./temp_loader_module_test")
#     test_dir.mkdir(exist_ok=True)
#     dummy_parquet = test_dir / "dummy_data.parquet"
#     dummy_db = test_dir / "dummy_etl_loader.db"
#
#     # 創建假的 Parquet
#     example_df = pd.DataFrame({'colA': [1, 2], 'colB': ['x', 'y']})
#     example_df.to_parquet(dummy_parquet)
#
#     test_args_load = [
#         "--parquet-file", str(dummy_parquet),
#         "--db-path", str(dummy_db),
#         "--table-name", "new_test_table",
#         "--primary-key", "colA",
#         "--loglevel", "DEBUG"
#     ]
#     run_loading(test_args_load)
#
#     # 再次運行以測試冪等性
#     # run_loading(test_args_load)
#
#     print(f"獨立測試完成。請檢查 {dummy_db} 並手動清理 {test_dir}。")
#     # python -m apps.etl_pipeline.loader --parquet-file ./temp_loader_module_test/dummy_data.parquet --db-path ./temp_loader_module_test/dummy_etl_loader.db --table-name new_test_table --primary-key colA
#     pass
