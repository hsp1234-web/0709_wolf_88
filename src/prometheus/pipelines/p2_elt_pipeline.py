import argparse  # noqa: E402
import io  # noqa: E402 # Added import for io.BytesIO
import os  # noqa: E402

import pandas as pd  # noqa: E402

from prometheus.core.db.data_warehouse import AnalyticsDataWarehouse, RawDataWarehouse
from prometheus.core.db.schema_registry import SchemaRegistry

# --- Loader 邏輯 ---
# Moved import to top level for module-wide use
from prometheus.core.utils.file_processors import (
    prospect_file_content,
    read_file_content,
)
from prometheus.pipelines.p1_explorer import get_header_fingerprint


def run_loader(input_dir, raw_db_path, schema_db_path):
    print("\n--- [階段 2] 執行 Loader ---")
    raw_wh = RawDataWarehouse(raw_db_path)
    schema_registry = SchemaRegistry(schema_db_path)

    known_fingerprints = schema_registry.get_known_fingerprints()
    if not known_fingerprints:
        print("[INFO] Loader: No known fingerprints loaded from schema registry. Only files matching these will be processed.")

    files_loaded = 0
    if not os.path.exists(input_dir):
        print(f"[WARNING] Loader input directory {input_dir} does not exist. Skipping loading.")
        raw_wh.close()
        schema_registry.close()
        return

    for filename in os.listdir(input_dir):
        file_path = os.path.join(input_dir, filename)

        if not os.path.isfile(file_path):  # Skip directories
            continue

        if raw_wh.is_file_processed(file_path):
            print(f"[INFO] Loader: File {filename} already in raw_import_log. Skipping.")
            continue

        try:
            file_bytes_content = read_file_content(file_path)
            if file_bytes_content is None:
                continue

            result = prospect_file_content(file_bytes_content)
            if result["status"] == "success":
                fingerprint = get_header_fingerprint(result["header"])
                if fingerprint in known_fingerprints:
                    raw_wh.log_processed_file(file_path, file_bytes_content, fingerprint)
                    files_loaded += 1
                    print(f"[INFO] Loader: Loaded {filename} (fingerprint: {fingerprint[:8]}...) as it's a known schema.")
                else:
                    print(f"[INFO] Loader: Skipped {filename} (fingerprint: {fingerprint[:8]}...) as its schema is not in the registry.")
            else:
                print(f"[INFO] Loader: Skipped file {filename} due to content prospecting failure: {result.get('error', 'Unknown error')}")

        except Exception as e:
            print(f"[ERROR] Loader 處理 {filename} 失敗: {e}")

    raw_wh.close()
    schema_registry.close()
    print(f"Loader 完成，新載入 {files_loaded} 個檔案。")


# --- Transformer 邏輯 ---
def run_transformer(raw_db_path, schema_db_path, analytics_db_path):
    print("\n--- [階段 3] 執行 Transformer ---")
    schema_registry = SchemaRegistry(schema_db_path)
    raw_wh = RawDataWarehouse(raw_db_path)
    analytics_wh = AnalyticsDataWarehouse(analytics_db_path)

    schema_map = schema_registry.get_all_schemas()
    if not schema_map:
        print("[WARNING] Transformer: 格式註冊表為空或讀取失敗，Transformer 無法執行有效轉換。")
        schema_registry.close()
        raw_wh.close()
        analytics_wh.close()
        return

    daily_futures_header_str = "交易日期,契約代碼,到期月份(週別),開盤價,最高價,最低價,收盤價,成交量"
    target_daily_futures_fingerprint = get_header_fingerprint(daily_futures_header_str)

    if target_daily_futures_fingerprint not in schema_map:
        print(f"[WARNING] Transformer: Did not find fingerprint for daily_futures_header '{daily_futures_header_str}' in schema_map. Cannot process daily_futures.")
    else:
        print(f"[INFO] Transformer: Target fingerprint for daily_futures is {target_daily_futures_fingerprint[:8]}...")

    analytics_wh.create_daily_futures_table()

    records = raw_wh.execute_query("SELECT content_blob, format_fingerprint FROM raw_import_log").fetchall()
    transformed_count = 0
    for blob, fingerprint in records:
        if fingerprint != target_daily_futures_fingerprint:
            continue

        if fingerprint not in schema_map:
            continue

        header_str_from_registry, encoding = schema_map[fingerprint]
        try:
            df = pd.read_csv(io.BytesIO(blob), encoding=encoding, thousands=",", header=0, on_bad_lines="skip")
            df.columns = [str(col).strip().replace('"', "") for col in df.columns]

            target_columns_canonical = [
                "交易日期", "契約代碼", "到期月份(週別)", "開盤價",
                "最高價", "最低價", "收盤價", "成交量",
            ]

            df_to_load = pd.DataFrame()
            for canonical_col_name in target_columns_canonical:
                if canonical_col_name in df.columns:
                    df_to_load[canonical_col_name] = df[canonical_col_name]
                else:
                    df_to_load[canonical_col_name] = None

            if not df_to_load.empty:
                analytics_wh.insert_daily_futures(df_to_load)
                transformed_count += 1

        except pd.errors.EmptyDataError:
            print(f"[WARNING] Transformer: No data or columns found in CSV for fingerprint {fingerprint[:8]}...")
        except Exception as e:
            print(f"[ERROR] Transformer 處理指紋 {fingerprint[:8]}... 的資料時失敗: {e}")

    raw_wh.close()
    analytics_wh.close()
    schema_registry.close()
    print(f"Transformer 完成，成功轉換 {transformed_count} 筆記錄。")


def run_elt_pipeline(input_dir: str, raw_db_path: str, schema_db_path: str, analytics_db_path: str):
    # Ensure parent directories for database files exist
    os.makedirs(os.path.dirname(raw_db_path), exist_ok=True)
    os.makedirs(os.path.dirname(schema_db_path), exist_ok=True)
    os.makedirs(os.path.dirname(analytics_db_path), exist_ok=True)

    run_loader(input_dir, raw_db_path, schema_db_path)
    run_transformer(raw_db_path, schema_db_path, analytics_db_path)


def main():
    parser = argparse.ArgumentParser(description="TAIFEX ELT 加工管線 v1.0")
    parser.add_argument(
        "--input-dir",
        default="data/downloads",
        help="下載檔案的來源目錄 (供 Loader 使用)",
    )
    parser.add_argument(
        "--raw-db-path",
        default="data/raw_warehouse/raw_taifex.duckdb",
        help="原始數據艙資料庫路徑",
    )
    parser.add_argument(
        "--schema-db-path",
        default="data/metadata/schema_registry.db",
        help="格式註冊表資料庫路徑",
    )
    parser.add_argument(
        "--analytics-db-path",
        default="data/analytics_warehouse/analytics_taifex.duckdb",
        help="分析數據庫路徑",
    )
    args = parser.parse_args()
    run_elt_pipeline(args.input_dir, args.raw_db_path, args.schema_db_path, args.analytics_db_path)


if __name__ == "__main__":
    main()
