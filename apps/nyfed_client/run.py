# apps/nyfed_client/run.py
# 命令列介面，用於執行 nyfed_client 的數據抓取和儲存任務。

import argparse
import sys
import os
# from pathlib import Path # Path is imported in the new block below

# --- 新版 pathlib 標準化路徑定義 ---
from pathlib import Path # 導入 Path

# 路徑自我校正樣板碼
try:
    # 使用 Path 物件來獲取專案根目錄
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except Exception as e: # Catches NameError as well
    print(f"專案路徑校正時發生錯誤: {e}", file=sys.stderr)
    # Fallback for interactive/different execution contexts
    if 'project_root' not in locals() and isinstance(e, NameError):
        print("嘗試備用路徑校正方法...")
        project_root = Path(os.getcwd())
        # Adjust project_root if cwd is deeper, e.g., apps/nyfed_client or apps
        if (project_root.name == 'nyfed_client' and project_root.parent.name == 'apps'):
            project_root = project_root.parent.parent
        elif project_root.name == 'apps':
            project_root = project_root.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        print(f"備用路徑校正完成，project_root 設定為: {project_root}")
    else:
        sys.exit(1)

# 統一的資料庫路徑定義 (使用 Path 物件)
DATABASE_PATH = project_root / 'market_data.duckdb'
# --- 標準化路徑定義結束 ---

from apps.nyfed_client.client import fetch_all_primary_dealer_data, store_data_to_duckdb, TABLE_NAME

def main():
    parser = argparse.ArgumentParser(description="NY Fed 一級交易商數據抓取客戶端")
    parser.add_argument(
        "--db_file",
        default=str(DATABASE_PATH), # 使用標準化路徑並轉為字串
        help=f"DuckDB 資料庫檔案路徑 (預設: {str(DATABASE_PATH)})"
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
        store_data_to_duckdb(dealer_data, args.db_file, args.table_name) # 調整參數順序
        print("nyfed_client 執行完畢，數據已儲存。")
    else:
        print("未抓取到任何一級交易商數據，nyfed_client 執行完畢但未儲存任何內容。")

if __name__ == "__main__":
    main()
