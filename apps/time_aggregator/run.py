# apps/time_aggregator/run.py

import duckdb
import pandas as pd
import argparse
import os
from pathlib import Path

# 假設數據庫檔案位於專案根目錄下的 "data" 資料夾中
# 在實際部署中，這個路徑可能需要更彈性的配置方式
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
SOURCE_DB_PATH = DEFAULT_DATA_DIR / "taifex_historical.duckdb"
ANALYTICS_DB_PATH = DEFAULT_DATA_DIR / "analytics_mart.duckdb"

TIME_PERIODS = {
    "1min": "1T",
    "5min": "5T",
    "15min": "15T",
    "1h": "1H",
    "4h": "4H",
    "1d": "1D",
}

def create_ohlcv_tables(con: duckdb.DuckDBPyConnection):
    """
    在 analytics_mart.duckdb 中為每個時間週期創建 OHLCV 資料表。
    """
    for period_name in TIME_PERIODS.keys():
        table_name = f"ohlcv_{period_name}"
        try:
            con.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    timestamp TIMESTAMP,
                    product_id VARCHAR,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume BIGINT,
                    PRIMARY KEY (timestamp, product_id)
                );
            """)
            print(f"資料表 '{table_name}' 已創建或已存在。")
        except Exception as e:
            print(f"創建資料表 '{table_name}' 時發生錯誤: {e}")

def aggregate_ticks_to_ohlcv(
    source_db_path: Path,
    analytics_db_path: Path,
    product_id: str,
    start_date: str,
    end_date: str
):
    """
    讀取 Tick 數據，聚合成 OHLCV，並存儲到 analytics_mart.duckdb。
    """
    if not source_db_path.exists():
        print(f"錯誤：來源資料庫 '{source_db_path}' 不存在。")
        return

    print(f"正在連接到來源資料庫: {source_db_path}")
    print(f"正在連接到分析資料庫: {analytics_db_path}")

    # 確保 analytics_db 的目錄存在
    analytics_db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with duckdb.connect(database=str(source_db_path), read_only=True) as source_con, \
             duckdb.connect(database=str(analytics_db_path), read_only=False) as analytics_con:

            print(f"成功連接到資料庫。")
            create_ohlcv_tables(analytics_con)

            # 假設 Tick 資料表名稱為 'ticks' 且包含 'timestamp', 'product_id', 'price', 'qty' 欄位
            # 時間戳欄位應為 datetime64[ns] 或可轉換的類型
            query = f"""
            SELECT timestamp, price, qty AS volume
            FROM ticks
            WHERE product_id = '{product_id}'
            AND timestamp >= '{start_date}'
            AND timestamp < '{end_date}'
            ORDER BY timestamp;
            """
            print(f"正在執行查詢: {query}")
            ticks_df = source_con.execute(query).fetchdf()

            if ticks_df.empty:
                print(f"在指定日期範圍內沒有找到商品 '{product_id}' 的數據。")
                return

            print(f"成功讀取 {len(ticks_df)} 筆 Tick 數據。")

            # 將 'timestamp' 轉換為 pandas datetime 物件
            ticks_df['timestamp'] = pd.to_datetime(ticks_df['timestamp'])
            ticks_df.set_index('timestamp', inplace=True)

            for period_name, period_code in TIME_PERIODS.items():
                print(f"正在聚合 {period_name} ({period_code}) 的 OHLCV 數據...")
                ohlc = ticks_df['price'].resample(period_code).ohlc()
                volume = ticks_df['volume'].resample(period_code).sum()

                # 合併 OHLC 和 Volume
                ohlcv = pd.concat([ohlc, volume], axis=1)
                ohlcv.rename(columns={'qty': 'volume'}, inplace=True) # 確保 volume 欄位名稱正確
                ohlcv.dropna(subset=['open'], inplace=True) # 移除沒有交易的K棒

                if ohlcv.empty:
                    print(f"商品 '{product_id}' 在聚合週期 '{period_name}' 後沒有數據。")
                    continue

                ohlcv.reset_index(inplace=True)
                ohlcv['product_id'] = product_id

                # 確保欄位順序和類型符合資料表定義
                ohlcv = ohlcv[['timestamp', 'product_id', 'open', 'high', 'low', 'close', 'volume']]

                table_name = f"ohlcv_{period_name}"
                print(f"正在將數據寫入資料表 '{table_name}'...")

                # 使用 DuckDB 的 append 功能，如果資料重複會根據 PRIMARY KEY (timestamp, product_id) 忽略或更新 (取決於 DuckDB 版本和設定)
                # 為了確保幂等性，我們這裡先刪除符合條件的舊數據 (如果存在)
                # 注意：這種刪除方式在非常大的資料表上可能效率不高，但對於此專案階段應該足夠
                min_ts = ohlcv['timestamp'].min()
                max_ts = ohlcv['timestamp'].max()

                delete_query = f"""
                DELETE FROM {table_name}
                WHERE product_id = '{product_id}'
                AND timestamp >= '{min_ts}' AND timestamp <= '{max_ts}';
                """
                # print(f"執行刪除查詢: {delete_query}") # Debugging
                analytics_con.execute(delete_query)

                analytics_con.append(table_name, ohlcv)
                print(f"成功將 {len(ohlcv)} 筆數據寫入 '{table_name}'。")

        print("時間序列聚合完成。")

    except Exception as e:
        print(f"處理過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description="時間序列聚合器：將 Tick 數據聚合成 OHLCV。")
    parser.add_argument("product_id", type=str, help="要處理的商品代碼 (例如：MXF1)")
    parser.add_argument("start_date", type=str, help="開始日期 (YYYY-MM-DD)")
    parser.add_argument("end_date", type=str, help="結束日期 (YYYY-MM-DD) (不包含此日)")
    parser.add_argument("--source_db", type=str, default=str(SOURCE_DB_PATH), help="來源 Tick 資料庫路徑")
    parser.add_argument("--analytics_db", type=str, default=str(ANALYTICS_DB_PATH), help="分析結果資料庫路徑")

    args = parser.parse_args()

    source_db_path = Path(args.source_db)
    analytics_db_path = Path(args.analytics_db)

    # 建立 data 目錄 (如果不存在)
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 為了測試，如果來源資料庫不存在，創建一個假的
    if not source_db_path.exists() and str(source_db_path) == str(SOURCE_DB_PATH):
        print(f"警告：指定的來源資料庫 {source_db_path} 不存在。將創建一個包含範例數據的假資料庫。")
        try:
            with duckdb.connect(str(source_db_path)) as con:
                con.execute("""
                    CREATE TABLE ticks (
                        timestamp TIMESTAMP,
                        product_id VARCHAR,
                        price DOUBLE,
                        qty BIGINT
                    );
                """)
                # 插入一些範例數據 (例如 'MXF1' 在 '2023-01-01')
                sample_data = [
                    ('2023-01-01 08:45:00', 'MXF1', 14000.0, 10),
                    ('2023-01-01 08:45:01', 'MXF1', 14001.0, 5),
                    ('2023-01-01 08:45:02', 'MXF1', 14000.5, 8),
                    ('2023-01-01 08:46:00', 'MXF1', 14002.0, 12),
                    ('2023-01-01 09:00:00', 'MXF1', 14010.0, 20), # 跨越不同分鐘
                    ('2023-01-01 09:00:05', 'MXF1', 14011.0, 15),
                    ('2023-01-01 09:16:00', 'MXF1', 14020.0, 20), # 跨越15分鐘
                    ('2023-01-01 10:00:00', 'MXF1', 14050.0, 30), # 跨越小時
                    ('2023-01-01 13:00:00', 'MXF1', 14000.0, 50), # 跨越4小時
                    ('2023-01-02 08:45:00', 'MXF1', 14100.0, 10), # 跨越日
                ]
                for row in sample_data:
                    con.execute("INSERT INTO ticks VALUES (?, ?, ?, ?)", row)
                print(f"已創建包含範例數據的假資料庫: {source_db_path}")
        except Exception as e:
            print(f"創建假資料庫時發生錯誤: {e}")
            return # 如果無法創建假資料庫，則無法繼續

    aggregate_ticks_to_ohlcv(
        source_db_path,
        analytics_db_path,
        args.product_id,
        args.start_date,
        args.end_date
    )

if __name__ == "__main__":
    # 設定 Pandas 以顯示所有欄位，方便調試
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    main()
