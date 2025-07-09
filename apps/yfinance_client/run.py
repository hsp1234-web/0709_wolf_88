# apps/yfinance_client/run.py
# 命令列介面，用於執行 yfinance_client 的數據抓取任務。

import argparse
from datetime import datetime
import sys
# from pathlib import Path # Path 在此腳本中未使用
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

from apps.yfinance_client.client import fetch_daily_ohlcv, store_data_to_duckdb, MARKET_DATA_DB

def main():
    parser = argparse.ArgumentParser(description="Yahoo Finance 數據抓取客戶端")
    parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="商品代碼列表 (例如: ^GSPC AAPL 2330.TW)"
    )
    parser.add_argument(
        "--start_date",
        required=True,
        help="開始日期 (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end_date",
        default=datetime.today().strftime('%Y-%m-%d'),
        help="結束日期 (YYYY-MM-DD)，預設為今天"
    )
    parser.add_argument(
        "--db_file",
        default=MARKET_DATA_DB,
        help=f"DuckDB 資料庫檔案路徑 (預設: {MARKET_DATA_DB})"
    )
    parser.add_argument(
        "--table_name",
        default="daily_ohlcv",
        help="儲存數據的資料表名稱 (預設: daily_ohlcv)"
    )

    args = parser.parse_args()

    print(f"命令列執行 yfinance_client：")
    print(f"  商品代碼: {args.symbols}")
    print(f"  開始日期: {args.start_date}")
    print(f"  結束日期: {args.end_date}")
    print(f"  資料庫檔案: {args.db_file}")
    print(f"  資料表名稱: {args.table_name}")

    # 驗證日期格式
    try:
        datetime.strptime(args.start_date, "%Y-%m-%d")
        datetime.strptime(args.end_date, "%Y-%m-%d")
    except ValueError:
        print("錯誤：日期格式必須是 YYYY-MM-DD。")
        return

    ohlcv_data = fetch_daily_ohlcv(args.symbols, args.start_date, args.end_date)

    if not ohlcv_data.empty:
        store_data_to_duckdb(ohlcv_data, args.table_name, args.db_file)
        print("yfinance_client 執行完畢。")
    else:
        print("未抓取到任何數據，yfinance_client 執行完畢但未儲存任何內容。")

if __name__ == "__main__":
    main()
