# apps/yfinance_client/run.py
# 命令列介面，用於執行 yfinance_client 的數據抓取任務。

import argparse
from datetime import datetime
from .client import fetch_daily_ohlcv, store_data_to_duckdb, MARKET_DATA_DB

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
