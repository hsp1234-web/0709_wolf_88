# apps/yfinance_client/run.py
# 命令列介面，用於執行 yfinance_client 的數據抓取任務。

import argparse
from datetime import datetime
import sys
import os # 保留 os 導入，因為 Path(__file__) 可能需要它 (儘管通常不需要)
# from pathlib import Path # Path is imported below in the new block

# --- 新版 pathlib 標準化路徑定義 ---
from pathlib import Path # 導入 Path

# 路徑自我校正樣板碼
try:
    # 使用 Path 物件來獲取專案根目錄
    # /app/apps/some_client/run.py -> /app
    project_root = Path(__file__).resolve().parents[2]
    # 將 Path 物件轉換為字串加入 sys.path
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except Exception as e: # NameError is a subclass of Exception, so this catches it too
    print(f"專案路徑校正時發生錯誤: {e}", file=sys.stderr)
    # Try a fallback for interactive shells if __file__ is not defined
    if 'project_root' not in locals() and isinstance(e, NameError):
        print("嘗試備用路徑校正方法 (適用於互動式執行)...")
        project_root = Path(os.getcwd()) # Fallback to current working directory
        if not (project_root / 'apps').is_dir(): # Heuristic: check if 'apps' subdir exists
             # If cwd is apps/yfinance_client, then project_root is parent.parent
             if (project_root.name == 'yfinance_client' and (project_root.parent.name == 'apps')):
                 project_root = project_root.parent.parent
             # If cwd is apps, then project_root is parent
             elif project_root.name == 'apps':
                 project_root = project_root.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        print(f"備用路徑校正完成，project_root 設定為: {project_root}")
    else: # If it's another exception or project_root was somehow defined but path add failed.
        sys.exit(1)


# 統一的資料庫路徑定義 (使用 Path 物件)
DATABASE_PATH = project_root / 'market_data.duckdb'
# --- 標準化路徑定義結束 ---

from apps.yfinance_client.client import fetch_daily_ohlcv, store_data_to_duckdb

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
        default=DATABASE_PATH, # 使用標準化路徑
        help=f"DuckDB 資料庫檔案路徑 (預設: {DATABASE_PATH})"
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
        store_data_to_duckdb(ohlcv_data, args.db_file, args.table_name) # 調整參數順序
        print("yfinance_client 執行完畢。")
    else:
        print("未抓取到任何數據，yfinance_client 執行完畢但未儲存任何內容。")

if __name__ == "__main__":
    main()
