# -*- coding: utf-8 -*-
"""
軍火庫裝載機 (Database Loader) 核心模組

此模組負責將標準化的 Parquet 檔案（或其他格式，未來可擴展）
載入到 DuckDB 資料庫中，並處理潛在的入庫衝突。
"""
import duckdb
import pandas as pd # 主要用於讀取 Parquet 以獲取 schema，或者創建臨時 DataFrame
from pathlib import Path
import logging
from typing import Optional, List, Any, Dict
import argparse # 為 run_loading 新增

# 預設的日誌記錄器
DEFAULT_LOGGER = logging.getLogger(__name__)
if not DEFAULT_LOGGER.handlers:
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stream_handler.setFormatter(formatter)
    DEFAULT_LOGGER.addHandler(stream_handler)
    DEFAULT_LOGGER.setLevel(logging.INFO)

class SchemaMismatchError(Exception):
    """自定義異常，用於表示嘗試載入的數據與目標表格的 Schema 不匹配。"""
    pass

def _get_parquet_schema(parquet_path: str, logger: logging.Logger) -> List[Dict[str, str]]:
    """
    讀取 Parquet 檔案的 schema。
    返回一個包含欄位資訊的列表，例如 [{'name': 'col_name', 'type': 'col_type'}, ...]。
    使用 DuckDB 的 DESCRIBE 功能獲取類型，因為它與目標資料庫的類型系統一致。
    """
    try:
        # 使用 DuckDB 的 DESCRIBE 來獲取與資料庫內部類型系統最一致的 schema
        # 這比 pandas.read_parquet().dtypes 更可靠，因為 pandas 的類型可能與 DuckDB 不完全對應
        # 建立一個臨時的記憶體資料庫連接來執行此操作
        temp_conn = duckdb.connect(':memory:')
        # DuckDB 的 DESCRIBE TABLE 或 DESCRIBE SELECT 輸出的欄位：
        # column_name, column_type, null, key, default, extra
        query = f"DESCRIBE SELECT * FROM read_parquet('{parquet_path}')"
        schema_info = temp_conn.execute(query).fetchall()
        temp_conn.close()

        if not schema_info:
            logger.warning(f"無法從 Parquet 檔案 {parquet_path} 中獲取 schema (DESCRIBE 結果為空)。")
            return []

        # 轉換為更標準的格式，主要關心 name 和 type
        # DuckDB DESCRIBE 的結果是 (column_name, column_type, null, key, default, extra)
        # 我們取前兩個
        schema = [{'name': str(col[0]), 'type': str(col[1]).upper()} for col in schema_info]
        logger.debug(f"從 Parquet '{parquet_path}' 獲取的 Schema: {schema}")
        return schema
    except Exception as e:
        logger.error(f"讀取 Parquet 檔案 '{parquet_path}' 的 schema 時發生錯誤: {e}")
        raise # 重新拋出，讓上層處理

def _get_table_schema_from_db(db_conn: duckdb.DuckDBPyConnection, table_name: str, logger: logging.Logger) -> Optional[List[Dict[str, str]]]:
    """
    從資料庫中獲取現有表格的 schema。
    返回與 _get_parquet_schema 格式相同的列表，如果表格不存在則返回 None。
    """
    try:
        # 檢查表格是否存在 (在 information_schema 中表名通常是小寫)
        check_table_query = f"SELECT table_name FROM information_schema.tables WHERE table_name = '{table_name.lower()}'"
        table_exists_result = db_conn.execute(check_table_query).fetchone()

        if not table_exists_result:
            logger.info(f"表格 '{table_name}' 在資料庫中不存在。")
            return None

        # DuckDB PRAGMA table_info('table_name') 的欄位：
        # cid, name, type, notnull, dflt_value, pk
        schema_info = db_conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        if not schema_info: # 理論上如果表存在，不應為空
            logger.warning(f"無法從資料庫中獲取表格 '{table_name}' 的 schema (PRAGMA table_info 結果為空，但表格應存在)。")
            return None # 或者返回空列表 []

        # 轉換為與 Parquet schema 一致的格式
        schema = [{'name': str(col[1]), 'type': str(col[2]).upper()} for col in schema_info]
        logger.debug(f"從資料庫表格 '{table_name}' 獲取的 Schema: {schema}")
        return schema
    except Exception as e:
        logger.error(f"從資料庫獲取表格 '{table_name}' 的 schema 時發生錯誤: {e}")
        raise

def _compare_schemas(parquet_schema: List[Dict[str, str]], table_schema: List[Dict[str, str]], logger: logging.Logger) -> bool:
    """
    比較兩個 schema 是否匹配。
    目前主要比較欄位名稱和數量。類型比較可能更複雜，暫時簡化。
    """
    logger.debug(f"DEBUG _compare_schemas: Parquet schema: {parquet_schema}")
    logger.debug(f"DEBUG _compare_schemas: Table schema: {table_schema}")

    if not parquet_schema and not table_schema: # 兩個都是空的
        logger.debug("DEBUG _compare_schemas: Both schemas are empty, considering them as matching.")
        logger.info("Parquet schema 與目標表格 schema 匹配 (兩者皆空)。") # 修改日誌使其更清晰
        return True

    if not parquet_schema or not table_schema: # 其中一個是空的，另一個不是
        logger.warning(f"Schema 不匹配：其中一個 schema 為空。Parquet empty: {not parquet_schema}, Table empty: {not table_schema}")
        return False

    if len(parquet_schema) != len(table_schema):
        logger.warning(f"Schema 不匹配：欄位數量不同。Parquet: {len(parquet_schema)}, Table: {len(table_schema)}")
        return False

    # 比較欄位名稱 (順序也需要一致)
    # 為了更健壯，可以先將名稱排序後比較，或只比較名稱集合是否相同
    # 目前假設順序也重要
    for i in range(len(parquet_schema)):
        pq_col = parquet_schema[i]
        tbl_col = table_schema[i]
        if pq_col['name'].lower() != tbl_col['name'].lower(): # 不區分大小寫比較欄位名
            logger.warning(f"Schema 不匹配：欄位名稱在位置 {i} 不同。Parquet: '{pq_col['name']}', Table: '{tbl_col['name']}'")
            return False
        # 類型比較：DuckDB 的類型字串可能需要更細緻的比較邏輯，例如 VARCHAR vs VARCHAR(N)
        # 暫時簡化，如果需要嚴格類型匹配，可以在此處添加
        # if pq_col['type'] != tbl_col['type']: # 注意：類型比較已註釋掉
        #     logger.warning(f"Schema 不匹配：欄位 '{pq_col['name']}' 的類型不同。Parquet: {pq_col['type']}, Table: {tbl_col['type']}")
        #     return False

    logger.info("Parquet schema 與目標表格 schema 匹配。")
    return True

def load_parquet_to_db(
    parquet_path_str: str,
    db_path_str: str,
    table_name: str,
    primary_key_column: Optional[str] = None, # 用於冪等性處理
    logger: Optional[logging.Logger] = None
) -> None:
    """
    將 Parquet 檔案的數據載入到 DuckDB 資料庫的指定表格中。

    參數:
        parquet_path_str (str): 輸入的 Parquet 檔案路徑。
        db_path_str (str): DuckDB 資料庫檔案路徑 (若為 ':memory:' 則使用記憶體資料庫)。
        table_name (str): 要載入數據的目標表格名稱。
        primary_key_column (Optional[str]): Parquet 檔案中的主鍵欄位名。
                                           如果提供，將用於處理重複入庫（冪等性）。
        logger (Optional[logging.Logger]): 用於日誌記錄的記錄器實例。
    """
    effective_logger = logger if logger else DEFAULT_LOGGER
    parquet_path = Path(parquet_path_str)

    if not parquet_path.exists() or not parquet_path.is_file():
        effective_logger.error(f"Parquet 檔案不存在或不是一個檔案。檔案路徑: {parquet_path}")
        return

    db_conn: Optional[duckdb.DuckDBPyConnection] = None
    try:
        effective_logger.info(f"準備將 Parquet 檔案 '{parquet_path.name}' 載入到資料庫 '{db_path_str}' 的表格 '{table_name}'。")
        db_conn = duckdb.connect(database=db_path_str, read_only=False)
        effective_logger.info(f"成功連接到資料庫 '{db_path_str}'。")

        # 步驟 1: 獲取 Parquet 檔案的 schema
        pq_schema = _get_parquet_schema(str(parquet_path), effective_logger)
        if not pq_schema:
            # _get_parquet_schema 內部已記錄錯誤
            effective_logger.error(f"無法確定 Parquet 檔案 '{parquet_path.name}' 的 schema，終止載入。")
            if db_conn: db_conn.close()
            return

        # 步驟 2: 獲取 (如果存在) 目標表格在資料庫中的 schema
        db_table_schema = _get_table_schema_from_db(db_conn, table_name, effective_logger)

        # 步驟 3: 處理表格創建或 schema 驗證
        if db_table_schema is None: # 表格不存在
            effective_logger.info(f"表格 '{table_name}' 不存在，將根據 Parquet 檔案 schema 創建。")
            # 使用批次載入方式創建表格並載入數據
            # 確保欄位名在 SQL 中是安全的 (例如，用雙引號括起來)
            # DuckDB 的 read_parquet 函數會自動處理 schema
            db_conn.execute(f"CREATE TABLE \"{table_name}\" AS SELECT * FROM read_parquet('{parquet_path}')")
            effective_logger.info(f"成功創建表格 '{table_name}' 並從 '{parquet_path.name}' 載入數據。")
        else: # 表格已存在，需要 schema 匹配和冪等性處理
            effective_logger.info(f"表格 '{table_name}' 已存在。將進行 schema 驗證和冪等載入。")
            if not _compare_schemas(pq_schema, db_table_schema, effective_logger):
                raise SchemaMismatchError(
                    f"Parquet 檔案 '{parquet_path.name}' 的 schema 與現有表格 '{table_name}' 的 schema 不匹配。"
                )

            # Schema 匹配成功，現在處理冪等性/重複入庫
            if primary_key_column:
                # 確保主鍵存在於 Parquet schema 中
                if not any(col['name'].lower() == primary_key_column.lower() for col in pq_schema):
                    effective_logger.error(f"提供的主鍵欄位 '{primary_key_column}' 不存在於 Parquet 檔案的 schema 中。將執行簡單追加。")
                    # 退化為簡單追加，或者拋出錯誤，取決於業務需求
                    # 這裡選擇記錄錯誤並執行簡單追加，測試案例需要驗證這一點
                    db_conn.execute(f"INSERT INTO \"{table_name}\" SELECT * FROM read_parquet('{parquet_path}')")
                    effective_logger.info(f"主鍵 '{primary_key_column}' 無法驗證，已將 '{parquet_path.name}' 中的所有數據追加到 '{table_name}'。")

                else:
                    # 使用暫存表和 NOT EXISTS 實現冪等插入
                    # DuckDB 0.7.0+ 支持更簡潔的 INSERT OR IGNORE/REPLACE，但需要主鍵約束
                    # 為了通用性和明確性，這裡使用暫存表 + NOT EXISTS
                    staging_table_name = f"staging_{table_name}_{Path(parquet_path).stem.replace('-', '_')}" # 創建一個唯一的暫存表名

                    effective_logger.info(f"使用主鍵 '{primary_key_column}' 進行冪等載入。創建暫存表 '{staging_table_name}'。")
                    db_conn.execute(f"CREATE TEMP TABLE \"{staging_table_name}\" AS SELECT * FROM read_parquet('{parquet_path}')")

                    # 確保主鍵欄位在 SQL 中正確引用 (例如，如果包含特殊字符或空格，雖然通常不建議)
                    safe_pk_column = f'"{primary_key_column}"' # DuckDB 通常對標準標識符不需要引號，但以防萬一

                    insert_query = f"""
                    INSERT INTO "{table_name}"
                    SELECT * FROM "{staging_table_name}" src
                    WHERE NOT EXISTS (
                        SELECT 1 FROM "{table_name}" dest
                        WHERE dest.{safe_pk_column} = src.{safe_pk_column}
                    )
                    """
                    # 如果主鍵可能是 NULL，NOT EXISTS 可能會有意外行為。
                    # DuckDB 中 NULL = NULL 為 NULL，而不是 TRUE。
                    # 如果主鍵可以為 NULL 且需要特殊處理，查詢會更複雜 (e.g., (dest.pk = src.pk OR (dest.pk IS NULL AND src.pk IS NULL)))
                    # 假設主鍵是 NOT NULL 的。

                    db_conn.execute(insert_query)
                    try:
                        inserted_rows_result = db_conn.execute("SELECT last_successful_query_inserted_rows()").fetchone()
                        if inserted_rows_result and inserted_rows_result[0] is not None:
                            effective_logger.info(f"從 '{parquet_path.name}' 向 '{table_name}' 冪等插入了 {inserted_rows_result[0]} 行新數據。")
                        else:
                            effective_logger.info(f"從 '{parquet_path.name}' 向 '{table_name}' 進行冪等插入，未插入新行或無法確定行數 (可能數據已存在或 last_successful_query_inserted_rows 不可用/返回意外)。")
                    except Exception as e_count:
                        effective_logger.warning(f"無法獲取冪等插入的行數 (可能由於 DuckDB 版本過低或錯誤: {e_count})。冪等插入操作已執行。")

                    db_conn.execute(f"DROP TABLE IF EXISTS \"{staging_table_name}\"")

            else: # 表格存在，Schema 匹配，但未提供主鍵 -> 簡單追加
                effective_logger.info(f"未提供主鍵欄位。將 '{parquet_path.name}' 中的所有數據追加到 '{table_name}'。")
                db_conn.execute(f"INSERT INTO \"{table_name}\" SELECT * FROM read_parquet('{parquet_path}')")
                try:
                    inserted_rows_result = db_conn.execute("SELECT last_successful_query_inserted_rows()").fetchone()
                    if inserted_rows_result and inserted_rows_result[0] is not None:
                        effective_logger.info(f"成功追加 {inserted_rows_result[0]} 行數據到 '{table_name}'。")
                    else:
                        effective_logger.info(f"追加數據到 '{table_name}' 完成 (可能插入0行或無法確定行數)。")
                except Exception as e_count:
                    effective_logger.warning(f"無法獲取追加操作的行數 (可能由於 DuckDB 版本過低或錯誤: {e_count})。追加操作已執行。")

    except duckdb.IOException as e_lock:
        effective_logger.error(f"[ERROR] 軍火庫已被鎖定，暫時無法訪問資料庫 '{db_path_str}'。錯誤: {e_lock}")
        # 根據指令，這裡不應引發程序崩潰，而是打印友善報告。
        # 此異常由 duckdb.connect() 拋出，所以 db_conn 可能未初始化。
    except SchemaMismatchError as e_schema:
        effective_logger.error(f"[ERROR] Schema 不匹配導致載入失敗: {e_schema}")
        # 異常已包含足夠信息，這裡不再添加檔案路徑等
        raise # 重新拋出，以便調用者可以捕獲它
    except Exception as e:
        effective_logger.error(f"載入 Parquet 檔案 '{parquet_path.name}' 到資料庫時發生未預期錯誤: {e}", exc_info=True)
        # 考慮是否也應該重新拋出一個通用錯誤，或者根據策略決定
    finally:
        if db_conn is not None:
            try:
                db_conn.close()
                effective_logger.info(f"資料庫連接 '{db_path_str}' 已關閉。")
            except Exception as e_close:
                effective_logger.error(f"關閉資料庫連接 '{db_path_str}' 時發生錯誤: {e_close}")

# 為 ETL pipeline 的 run.py 新增的函數
def run_loading(argv: Optional[List[str]] = None):
    """
    為 loader 模組設計的命令行介面入口點。
    argv 是 parse_known_args() 之後的剩餘參數。
    """
    parser = argparse.ArgumentParser(description="Database Loading Sub-module")
    parser.add_argument("--parquet-file", required=True, help="Path to the input Parquet file.")
    parser.add_argument("--db-path", required=True, help="Path to the DuckDB database file.")
    parser.add_argument("--table-name", required=True, help="Target table name in the database.")
    parser.add_argument("--primary-key", help="Primary key column for idempotent loading.")
    parser.add_argument("--loglevel", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

    args = parser.parse_args(argv)

    cli_logger = logging.getLogger("LOADER_ETL")
    cli_logger.setLevel(getattr(logging, args.loglevel.upper()))
    if not cli_logger.handlers:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        cli_logger.addHandler(ch)

    cli_logger.info(f"ETL Loader: 載入 Parquet 檔案 '{args.parquet_file}' 到資料庫 '{args.db_path}' 的表格 '{args.table_name}'。")
    try:
        load_parquet_to_db(
            args.parquet_file,
            args.db_path,
            args.table_name,
            primary_key_column=args.primary_key,
            logger=cli_logger
        )
        cli_logger.info("ETL Loader: 任務完成。")
    except SchemaMismatchError:
        cli_logger.error("ETL Loader: 任務因 Schema 不匹配而失敗。")
        # 根據需要，這裡可以決定是否要 sys.exit(1) 或讓 run.py 處理
    except Exception as e:
        cli_logger.error(f"ETL Loader: 任務因未預期錯誤而失敗: {e}", exc_info=True)


if __name__ == '__main__':
    # 原始的 __main__ 區塊保持不變，用於獨立測試
    test_dir = Path("temp_loader_test_dir")
    test_dir.mkdir(exist_ok=True)

    db_file = test_dir / "test_main_db.duckdb"
    parquet_file_1 = test_dir / "data1.parquet"
    parquet_file_2_schema_diff = test_dir / "data2_schema_diff.parquet"
    parquet_file_3_more_data = test_dir / "data3_more_data.parquet"

    if db_file.exists():
        db_file.unlink()

    cli_logger = logging.getLogger("LOADER_CLI_TEST")
    cli_logger.setLevel(logging.DEBUG)
    if not cli_logger.handlers:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        cli_logger.addHandler(ch)

    df1_data = {'id': [1, 2, 3], 'value': ['apple', 'banana', 'cherry']}
    df1 = pd.DataFrame(df1_data)
    df1.to_parquet(parquet_file_1)
    cli_logger.info(f"創建了 {parquet_file_1}")

    df2_data = {'id': [10, 11], 'value': ['dog', 'cat'], 'price': [100.0, 150.0]}
    df2 = pd.DataFrame(df2_data)
    df2.to_parquet(parquet_file_2_schema_diff)
    cli_logger.info(f"創建了 {parquet_file_2_schema_diff}")

    df3_data = {'id': [3, 4, 5], 'value': ['coconut', 'date', 'elderberry']}
    df3 = pd.DataFrame(df3_data)
    df3.to_parquet(parquet_file_3_more_data)
    cli_logger.info(f"創建了 {parquet_file_3_more_data}")

    table = "fruits_table"

    cli_logger.info(f"\n--- 測試1: 首次載入 {parquet_file_1} ---")
    load_parquet_to_db(str(parquet_file_1), str(db_file), table, primary_key_column='id', logger=cli_logger)

    cli_logger.info(f"\n--- 測試2: 嘗試載入 schema 不同的 {parquet_file_2_schema_diff} ---")
    try:
        load_parquet_to_db(str(parquet_file_2_schema_diff), str(db_file), table, primary_key_column='id', logger=cli_logger)
    except SchemaMismatchError:
        cli_logger.info("預期內的 SchemaMismatchError 已捕獲。")


    cli_logger.info(f"\n--- 測試3: 再次載入 {parquet_file_1} (冪等性測試) ---")
    load_parquet_to_db(str(parquet_file_1), str(db_file), table, primary_key_column='id', logger=cli_logger)

    cli_logger.info(f"\n--- 測試4: 載入 {parquet_file_3_more_data} (部分重疊ID) ---")
    load_parquet_to_db(str(parquet_file_3_more_data), str(db_file), table, primary_key_column='id', logger=cli_logger)

    cli_logger.info(f"\n--- 測試5: 載入 {parquet_file_1} 到新表 new_fruits_no_pk (無主鍵) ---")
    load_parquet_to_db(str(parquet_file_1), str(db_file), "new_fruits_no_pk", logger=cli_logger)
    cli_logger.info(f"\n--- 測試5b: 再次載入 {parquet_file_1} 到 new_fruits_no_pk (應追加) ---")
    load_parquet_to_db(str(parquet_file_1), str(db_file), "new_fruits_no_pk", logger=cli_logger)

    cli_logger.info(f"\n--- 手動驗證資料庫 '{db_file}' ---")
    try:
        conn_verify = duckdb.connect(str(db_file))
        cli_logger.info(f"表格 '{table}' 內容:")
        cli_logger.info(conn_verify.execute(f"SELECT * FROM \"{table}\"").df())
        cli_logger.info(f"表格 'new_fruits_no_pk' 內容:")
        cli_logger.info(conn_verify.execute(f"SELECT * FROM new_fruits_no_pk").df())
        conn_verify.close()
    except Exception as e_verify:
        cli_logger.error(f"驗證時出錯: {e_verify}")

    cli_logger.info("本地 CLI 測試完成。")
