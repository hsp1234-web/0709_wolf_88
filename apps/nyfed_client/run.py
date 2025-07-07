# apps/nyfed_client/run.py
# 命令列介面，用於執行 nyfed_client 的數據抓取和儲存任務。

import argparse
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
