# (為簡化操作，將 Loader 和 Transformer 邏輯整合進一個執行腳本)
import sys
import os
# Add the project root to sys.path
# This allows imports like 'from pipelines.module import ...'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import duckdb
import os
import argparse
import zipfile
import pandas as pd
import sqlite3
import io # Added import for io.BytesIO

# --- Loader 邏輯 ---
def run_loader(input_dir, raw_db_path, schema_db_path):
    print("\n--- [階段 2] 執行 Loader ---")
    raw_conn = duckdb.connect(raw_db_path)
    raw_conn.execute("""
    CREATE TABLE IF NOT EXISTS raw_import_log (
        file_path VARCHAR PRIMARY KEY,
        content_blob BLOB,
        format_fingerprint VARCHAR
    );""")

    # 來自 p1_explorer 的函式
    # This import will work if run_elt.py is run from the project root
    # or if the 'pipelines' directory is in PYTHONPATH.
    # Poetry run commands typically execute from the project root.
    from pipelines.p1_explorer.run import prospect_file_content, get_header_fingerprint

    files_loaded = 0
    # Ensure input_dir exists before listing its contents
    if not os.path.exists(input_dir):
        print(f"[WARNING] Loader input directory {input_dir} does not exist. Skipping loading.")
        raw_conn.close()
        return

    for filename in os.listdir(input_dir):
        file_path = os.path.join(input_dir, filename)

        # 簡易版：檢查是否已載入
        if raw_conn.execute(f"SELECT COUNT(*) FROM raw_import_log WHERE file_path = ?", (file_path,)).fetchone()[0] > 0:
            continue

        try:
            file_bytes_content = None
            if zipfile.is_zipfile(file_path):
                with zipfile.ZipFile(file_path, 'r') as zf:
                    if zf.namelist(): # Check if zip file is not empty
                        member = zf.namelist()[0] # Process only the first member
                        file_bytes_content = zf.read(member)
                    else:
                        print(f"[WARNING] Loader: Zip file {filename} is empty.")
                        continue
            else:
                with open(file_path, 'rb') as f:
                    file_bytes_content = f.read()

            if file_bytes_content is None:
                continue

            result = prospect_file_content(file_bytes_content)
            if result['status'] == 'success':
                fingerprint = get_header_fingerprint(result['header'])
                raw_conn.execute("INSERT INTO raw_import_log VALUES (?, ?, ?)", (file_path, file_bytes_content, fingerprint))
                files_loaded += 1
            else:
                print(f"[INFO] Loader: Skipped file {filename} due to content prospecting failure: {result.get('error', 'Unknown error')}")


        except Exception as e:
            print(f"[ERROR] Loader 處理 {filename} 失敗: {e}")

    raw_conn.close()
    print(f"Loader 完成，新載入 {files_loaded} 個檔案。")

# --- Transformer 邏輯 ---
def run_transformer(raw_db_path, schema_db_path, analytics_db_path):
    print("\n--- [階段 3] 執行 Transformer ---")

    # Ensure schema_db_path directory exists
    os.makedirs(os.path.dirname(schema_db_path), exist_ok=True)
    schema_conn = sqlite3.connect(schema_db_path)
    try:
        # Check if schema_registry table exists
        schema_exists = schema_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_registry';").fetchone()
        if not schema_exists:
            print(f"[WARNING] Transformer: schema_registry table not found in {schema_db_path}. Creating an empty one.")
            # If p1_explorer hasn't run or created the table, we might need to create it here to avoid errors.
            # Or, ensure p1_explorer always creates it. For now, let's create it if not exists.
            schema_conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_registry (
                format_fingerprint TEXT PRIMARY KEY,
                header TEXT,
                encoding TEXT,
                file_count INTEGER DEFAULT 1,
                first_seen_file TEXT
            )""")
            schema_conn.commit()
            schema_map = {}
        else:
            schema_map = {row[0]: (row[1].split(','), row[2]) for row in schema_conn.execute("SELECT format_fingerprint, header, encoding FROM schema_registry").fetchall()}
    except sqlite3.Error as e:
        print(f"[ERROR] Transformer: SQLite error accessing schema_registry: {e}")
        schema_conn.close()
        return
    finally:
        schema_conn.close()


    if not schema_map:
        print("[WARNING] 格式註冊表為空或讀取失敗，Transformer 無法執行有效轉換。")
        # return # Decide if we should stop or proceed to create empty analytics_db

    # Ensure raw_db_path directory exists
    os.makedirs(os.path.dirname(raw_db_path), exist_ok=True)
    raw_conn = duckdb.connect(raw_db_path, read_only=False) # Changed to False to allow table creation if not exists

    # Ensure analytics_db_path directory exists
    os.makedirs(os.path.dirname(analytics_db_path), exist_ok=True)
    analytics_conn = duckdb.connect(analytics_db_path)

    # Check if raw_import_log table exists
    raw_table_exists = raw_conn.execute("SELECT table_name FROM information_schema.tables WHERE table_name = 'raw_import_log'").fetchone()
    if not raw_table_exists:
        print(f"[WARNING] Transformer: raw_import_log table not found in {raw_db_path}. Creating an empty one.")
        raw_conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_import_log (
            file_path VARCHAR PRIMARY KEY,
            content_blob BLOB,
            format_fingerprint VARCHAR
        );""")
        # No data to process if the table was just created empty
        raw_conn.close()
        analytics_conn.close()
        print(f"Transformer 完成，成功轉換 0 筆記錄 (raw_import_log was missing or empty).")
        return

    # 範例：只為一種特定格式建立表格
    # 在真實場景中，這裡會有更複雜的邏輯來處理多種不同表格
    analytics_conn.execute("""
    CREATE TABLE IF NOT EXISTS daily_futures (
        "交易日期" VARCHAR,
        "契約代碼" VARCHAR,
        "到期月份(週別)" VARCHAR,
        "開盤價" VARCHAR,
        "最高價" VARCHAR,
        "最低價" VARCHAR,
        "收盤價" VARCHAR,
        "成交量" VARCHAR
        -- 其他欄位...
        -- Changed numeric types to VARCHAR to handle potential non-numeric data from CSV initially
        -- Conversion to numeric should happen after validation or with try-cast
    );""")

    records = raw_conn.execute("SELECT content_blob, format_fingerprint FROM raw_import_log").fetchall()
    transformed_count = 0
    for blob, fingerprint in records:
        if fingerprint not in schema_map:
            print(f"[INFO] Transformer: Fingerprint {fingerprint[:8]}... not in schema_map. Skipping.")
            continue

        # schema_map stores header as a list of strings
        header_list_from_registry, encoding = schema_map[fingerprint]

        try:
            # Use io.BytesIO for pandas to read bytes
            df = pd.read_csv(io.BytesIO(blob), encoding=encoding, thousands=',', header=0, on_bad_lines='skip')

            # Standardize column names from DataFrame (read from actual CSV header)
            df.columns = [str(col).strip().replace('"', '') for col in df.columns]

            # The header_list_from_registry is what we EXPECTED the columns to be.
            # The actual df.columns are what pandas read.
            # For this example, we assume the schema_registry's header is canonical for selection.

            # Select target columns based on the canonical names from schema_registry
            # Ensure these canonical names match what's expected in 'daily_futures'
            target_columns_canonical = ["交易日期", "契約代碼", "到期月份(週別)", "開盤價", "最高價", "最低價", "收盤價", "成交量"]

            # Create a mapping from canonical name to actual name in df
            # This is tricky if column order or names slightly differ.
            # For simplicity, let's assume the schema_registry header list matches the target_columns_canonical
            # and we use these to select columns from df, if they exist.

            df_to_load = pd.DataFrame()
            missing_cols = []
            for canonical_col_name in target_columns_canonical:
                if canonical_col_name in df.columns:
                    df_to_load[canonical_col_name] = df[canonical_col_name]
                else:
                    # If a canonical column is missing in the actual data, add it as None or handle error
                    df_to_load[canonical_col_name] = None
                    missing_cols.append(canonical_col_name)

            if missing_cols:
                print(f"[WARNING] Transformer: Fingerprint {fingerprint[:8]}... missing columns {missing_cols} during mapping. Filled with NULLs.")

            if not df_to_load.empty:
                # Ensure columns in df_to_load match the order and names in 'daily_futures' table
                # DuckDB's insert by name handles column order if table schema is defined.
                # Here, using SELECT * FROM df_to_load, so column order in df_to_load matters if table not strictly defined.
                # However, our CREATE TABLE daily_futures defines the schema.
                analytics_conn.execute(f"INSERT INTO daily_futures ({', '.join(f'\"{c}\"' for c in df_to_load.columns)}) SELECT {', '.join(f'\"{c}\"' for c in df_to_load.columns)} FROM df_to_load")
                transformed_count += 1
            else:
                print(f"[INFO] Transformer: Fingerprint {fingerprint[:8]}... resulted in an empty DataFrame after column mapping. Skipping insert.")

        except pd.errors.EmptyDataError:
            print(f"[WARNING] Transformer: No data or columns found in CSV for fingerprint {fingerprint[:8]}...")
        except Exception as e:
            print(f"[ERROR] Transformer 處理指紋 {fingerprint[:8]}... 的資料時失敗: {e}")

    raw_conn.close()
    analytics_conn.close()
    print(f"Transformer 完成，成功轉換 {transformed_count} 筆記錄。")


def main():
    parser = argparse.ArgumentParser(description="TAIFEX ELT 加工管線 v1.0")
    parser.add_argument('--input-dir', default='data/downloads', help="下載檔案的來源目錄 (供 Loader 使用)")
    parser.add_argument('--raw-db-path', default='data/raw_warehouse/raw_taifex.duckdb', help="原始數據艙資料庫路徑")
    parser.add_argument('--schema-db-path', default='data/metadata/schema_registry.db', help="格式註冊表資料庫路徑")
    parser.add_argument('--analytics-db-path', default='data/analytics_warehouse/analytics_taifex.duckdb', help="分析數據庫路徑")
    args = parser.parse_args()

    # Ensure parent directories for database files exist
    os.makedirs(os.path.dirname(args.raw_db_path), exist_ok=True)
    os.makedirs(os.path.dirname(args.schema_db_path), exist_ok=True)
    os.makedirs(os.path.dirname(args.analytics_db_path), exist_ok=True)

    run_loader(args.input_dir, args.raw_db_path, args.schema_db_path)
    run_transformer(args.raw_db_path, args.schema_db_path, args.analytics_db_path)

if __name__ == "__main__":
    main()
