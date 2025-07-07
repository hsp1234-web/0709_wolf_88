# apps/yfinance_client/run.py
# 命令列介面，用於執行 yfinance_client 的數據抓取任務。

import argparse
from datetime import datetime
import sys # 導入 sys
from pathlib import Path # 導入 Path

import os # 標準樣板碼需要 os

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
    print(f"專案路徑校正時發生錯誤 (apps/yfinance_client/run.py): {e}", file=sys.stderr)
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
