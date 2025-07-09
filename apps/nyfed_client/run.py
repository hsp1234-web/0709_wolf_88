# apps/nyfed_client/run.py
# 命令列介面，用於執行 nyfed_client 的數據抓取和儲存任務。

import argparse
import sys # 標準樣板碼需要 sys
import os # 標準樣板碼需要 os
from pathlib import Path # 標準樣板碼需要 Path

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    # 獲取目前腳本的絕對路徑
    current_script_path = Path(__file__).resolve()
    # 假設此腳本位於 apps/[app_name] 目錄下，專案根目錄是其再上兩層
    project_root = current_script_path.parent.parent.parent
    # 將專案根目錄加入 sys.path
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError: # __file__ is not defined, common in interactive shells or certain execution contexts
    project_root = Path(os.getcwd())
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    print(f"警告：__file__ 未定義，專案路徑校正可能不準確。已將 {project_root} 加入 sys.path。", file=sys.stderr)
except Exception as e:
    print(f"專案路徑校正時發生錯誤 (apps/nyfed_client/run.py): {e}", file=sys.stderr)
# --- 標準化「路徑自我校正」樣板碼 END ---

from apps.nyfed_client.client import fetch_all_primary_dealer_data, store_data_to_duckdb, MARKET_DATA_DB, TABLE_NAME

def main():
    parser = argparse.ArgumentParser(description="NY Fed 一級交易商數據抓取客戶端")
    parser.add_argument(
        "--db_file",
        default=MARKET_DATA_DB,
        help=f"DuckDB 資料庫檔案路徑 (預設: {MARKET_DATA_DB})"
    )
    parser.add_argument(
        "--table_name",
        default=TABLE_NAME,
        help=f"儲存數據的資料表名稱 (預設: {TABLE_NAME})"
    )

    args = parser.parse_args()

    print(f"命令列執行 nyfed_client：")
    print(f"  資料庫檔案: {args.db_file}")
    print(f"  資料表名稱: {args.table_name}")

    dealer_data = fetch_all_primary_dealer_data()

    if not dealer_data.empty:
        store_data_to_duckdb(dealer_data, args.table_name, args.db_file)
        print("nyfed_client 執行完畢，數據已儲存。")
    else:
        print("未抓取到任何一級交易商數據，nyfed_client 執行完畢但未儲存任何內容。")

if __name__ == "__main__":
    main()
