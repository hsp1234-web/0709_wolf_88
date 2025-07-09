# apps/nyfed_client/run.py
# 命令列介面，用於執行 nyfed_client 的數據抓取和儲存任務。

import argparse
import sys
import os

# --- 標準化「路徑自我校正」樣板碼 START ---
# 取得目前腳本檔案的目錄
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 自動偵測專案根目錄 (假設 .git 在根目錄，或存在 README.md)
project_root = current_script_dir
max_levels_up = 5 # 防止無限迴圈，可根據專案深度調整
for _ in range(max_levels_up):
    # 檢查是否存在 .git 目錄或 AGENTS.md (或 README.md) 作為根目錄標記
    if os.path.isdir(os.path.join(project_root, '.git')) or \
       os.path.isfile(os.path.join(project_root, 'AGENTS.md')) or \
       os.path.isfile(os.path.join(project_root, 'README.md')):
        break
    parent_dir = os.path.dirname(project_root)
    if parent_dir == project_root: # 已達檔案系統頂層
        project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..'))
        print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑: {project_root}")
        break
    project_root = parent_dir
else: # 如果迴圈正常結束 (未 break)
    project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..')) # 後備方案
    print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑: {project_root}")

if project_root not in sys.path:
    sys.path.insert(0, project_root)
# print(f"DEBUG: 專案根目錄 {project_root} 已添加到 sys.path")
# --- 標準化「路徑自我校正」樣板碼 END ---
# from pathlib import Path # Path 在標準樣板碼中未使用，如果後續代碼需要則取消註解

from .client import fetch_all_primary_dealer_data, store_data_to_duckdb, MARKET_DATA_DB, TABLE_NAME

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
