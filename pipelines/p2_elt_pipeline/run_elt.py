# (為簡化操作，將 Loader 和 Transformer 邏輯整合進一個執行腳本)
import sys
import os
# Add the project root to sys.path
# This allows imports like 'from pipelines.module import ...'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import duckdb  # noqa: E402
import os  # noqa: E402
import argparse  # noqa: E402
import zipfile  # noqa: E402
import pandas as pd  # noqa: E402
import sqlite3  # noqa: E402
import io  # noqa: E402 # Added import for io.BytesIO

# --- Loader 邏輯 ---
# Moved import to top level for module-wide use
from pipelines.p1_explorer.run import prospect_file_content, get_header_fingerprint  # noqa: E402

def run_loader(input_dir, raw_db_path, schema_db_path):
    print("\n--- [階段 2] 執行 Loader ---")
    raw_conn = duckdb.connect(raw_db_path)
    raw_conn.execute("""
    CREATE TABLE IF NOT EXISTS raw_import_log (
        file_path VARCHAR PRIMARY KEY,
        content_blob BLOB,
        format_fingerprint VARCHAR
    );""")

    # 來自 p1_explorer 的函式 (now imported at top level)
    # This import will work if run_elt.py is run from the project root
    # or if the 'pipelines' directory is in PYTHONPATH.
    # Poetry run commands typically execute from the project root.
    # from pipelines.p1_explorer.run import prospect_file_content, get_header_fingerprint # Now at top

    # --- Load known fingerprints from schema_registry.db (P1's output) ---
    known_fingerprints = set()
    if not os.path.exists(schema_db_path):
        print(f"[WARNING] Loader: Schema registry DB {schema_db_path} not found. No files will be loaded.")
    else:
        try:
            schema_conn = sqlite3.connect(schema_db_path)
            # Check if schema_registry table exists before querying
            table_exists_cursor = schema_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_registry';")
            if table_exists_cursor.fetchone():
                known_fingerprints = {row[0] for row in schema_conn.execute("SELECT format_fingerprint FROM schema_registry").fetchall()}
            else:
                print(f"[WARNING] Loader: 'schema_registry' table not found in {schema_db_path}. No files will be loaded based on schema.")
            schema_conn.close()
        except sqlite3.Error as e:
            print(f"[ERROR] Loader: Error reading schema registry {schema_db_path}: {e}. No files will be loaded.")

    if not known_fingerprints:
        print("[INFO] Loader: No known fingerprints loaded from schema registry. Only files matching these will be processed.")

    files_loaded = 0
    # Ensure input_dir exists before listing its contents
    if not os.path.exists(input_dir):
        print(f"[WARNING] Loader input directory {input_dir} does not exist. Skipping loading.")
        raw_conn.close()
        return

    for filename in os.listdir(input_dir):
        file_path = os.path.join(input_dir, filename)

        if not os.path.isfile(file_path): # Skip directories
            continue

        # 簡易版：檢查是否已載入
        if raw_conn.execute("SELECT COUNT(*) FROM raw_import_log WHERE file_path = ?", (file_path,)).fetchone()[0] > 0:
            print(f"[INFO] Loader: File {filename} already in raw_import_log. Skipping.")
            continue

        try:
            file_bytes_content = None
            # P1's logic for identifying processable files (simplified here)
            # For actual use, P2 loader might need its own robust file type identification
            # or rely more directly on P1's output manifest if P1 generated one.
            if zipfile.is_zipfile(file_path):
                try:
                    with zipfile.ZipFile(file_path, 'r') as zf:
                        if zf.namelist():
                            member = zf.namelist()[0] # Process only the first member for prospecting
                            # Check if member is csv or txt before reading
                            if member.lower().endswith(('.csv', '.txt')):
                                file_bytes_content = zf.read(member)
                            else:
                                print(f"[INFO] Loader: Member {member} in zip {filename} is not CSV/TXT. Skipping zip for schema check.")
                                continue # Skip this zip if first member isn't CSV/TXT
                        else:
                            print(f"[WARNING] Loader: Zip file {filename} is empty. Skipping.")
                            continue
                except zipfile.BadZipFile:
                    print(f"[WARN] Loader: File {filename} is a bad zip file. Skipping.")
                    continue
            elif filename.lower().endswith(('.csv', '.txt')):
                with open(file_path, 'rb') as f:
                    file_bytes_content = f.read()
            else:
                # Skip files not matching expected types for prospecting by P1 logic
                print(f"[INFO] Loader: File {filename} is not a processable type (zip, csv, txt) for schema check. Skipping.")
                continue

            if file_bytes_content is None:
                # This case might be hit if a zip file had no processable members.
                print(f"[INFO] Loader: No content to process for {filename} after type checks. Skipping.")
                continue

            result = prospect_file_content(file_bytes_content) # Prospect content
            if result['status'] == 'success':
                fingerprint = get_header_fingerprint(result['header'])
                # --- Key Change: Only load if fingerprint is known from P1 ---
                if fingerprint in known_fingerprints:
                    raw_conn.execute("INSERT INTO raw_import_log VALUES (?, ?, ?)", (file_path, file_bytes_content, fingerprint))
                    files_loaded += 1
                    print(f"[INFO] Loader: Loaded {filename} (fingerprint: {fingerprint[:8]}...) as it's a known schema.")
                else:
                    print(f"[INFO] Loader: Skipped {filename} (fingerprint: {fingerprint[:8]}...) as its schema is not in the registry.")
            else:
                print(f"[INFO] Loader: Skipped file {filename} due to content prospecting failure: {result.get('error', 'Unknown error')}")

        except Exception as e:
            print(f"[ERROR] Loader 處理 {filename} 失敗: {e}")

    raw_conn.close()
    print(f"Loader 完成，新載入 {files_loaded} 個檔案。")

# --- Transformer 邏輯 ---
# Helper to get the specific fingerprint for daily_futures from schema_map
def get_target_fingerprint(schema_map, target_header_str):
    target_fingerprint = get_header_fingerprint(target_header_str)
    if target_fingerprint in schema_map:
        return target_fingerprint
    # Fallback: check if any header in schema_map matches after splitting and joining
    # This is a bit loose but might catch cases where P1 stores header differently
    for fp, (header_list, _) in schema_map.items():
        if get_header_fingerprint(",".join(header_list)) == target_fingerprint:
            return fp
    return None

def run_transformer(raw_db_path, schema_db_path, analytics_db_path):
    print("\n--- [階段 3] 執行 Transformer ---")

    # Load schema_map from schema_registry.db
    os.makedirs(os.path.dirname(schema_db_path), exist_ok=True)
    schema_conn_transformer = sqlite3.connect(schema_db_path)
    try:
        schema_exists = schema_conn_transformer.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_registry';").fetchone()
        if not schema_exists:
            print(f"[WARNING] Transformer: schema_registry table not found in {schema_db_path}. Transformer cannot operate.")
            schema_conn_transformer.close()
            return # Cannot proceed without schema

        # Store header as string as P1 does, split later if needed by specific logic
        schema_map = {row[0]: (row[1], row[2]) for row in schema_conn_transformer.execute("SELECT format_fingerprint, header, encoding FROM schema_registry").fetchall()}
    except sqlite3.Error as e:
        print(f"[ERROR] Transformer: SQLite error accessing schema_registry: {e}")
        schema_conn_transformer.close()
        return
    finally:
        schema_conn_transformer.close()

    if not schema_map:
        print("[WARNING] Transformer: 格式註冊表為空或讀取失敗，Transformer 無法執行有效轉換。")
        # Create analytics_db anyway for consistency, but it will be empty.
        # os.makedirs(os.path.dirname(analytics_db_path), exist_ok=True)
        # duckdb.connect(analytics_db_path).close() # Ensure db file is created
        return

    # Define the specific header for 'daily_futures'
    # This must exactly match how P1 explorer generates the header string for this data type
    daily_futures_header_str = "交易日期,契約代碼,到期月份(週別),開盤價,最高價,最低價,收盤價,成交量"
    target_daily_futures_fingerprint = get_target_fingerprint(schema_map, daily_futures_header_str)

    if not target_daily_futures_fingerprint:
        print(f"[WARNING] Transformer: Did not find fingerprint for daily_futures_header '{daily_futures_header_str}' in schema_map. Cannot process daily_futures.")
        # Proceed to create empty table but don't try to load data for it.
    else:
        print(f"[INFO] Transformer: Target fingerprint for daily_futures is {target_daily_futures_fingerprint[:8]}...")


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
        print("Transformer 完成，成功轉換 0 筆記錄 (raw_import_log was missing or empty).")
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
        # --- Key Change: Only process if fingerprint matches the target for daily_futures ---
        if fingerprint != target_daily_futures_fingerprint:
            if fingerprint in schema_map: # It's a known schema, just not the one we're processing now
                print(f"[INFO] Transformer: Skipping record with fingerprint {fingerprint[:8]}... as it's not the target daily_futures fingerprint ({target_daily_futures_fingerprint[:8]}...).")
            else: # Should not happen if loader only loads known FPs, but as a safeguard:
                print(f"[INFO] Transformer: Fingerprint {fingerprint[:8]}... not in schema_map (and not target). Skipping.")
            continue

        # At this point, fingerprint MUST be target_daily_futures_fingerprint
        # And it must be in schema_map if target_daily_futures_fingerprint was found
        if target_daily_futures_fingerprint not in schema_map:
            # This should ideally not be reached if target_daily_futures_fingerprint is None and we checked above.
            # However, if target_daily_futures_fingerprint was somehow non-None but still not in schema_map.
            print(f"[ERROR] Transformer: Target fingerprint {target_daily_futures_fingerprint[:8]} not found in schema_map. This is unexpected. Skipping.")
            continue

        header_str_from_registry, encoding = schema_map[fingerprint]
        # header_list_from_registry = header_str_from_registry.split(',') # If needed

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
