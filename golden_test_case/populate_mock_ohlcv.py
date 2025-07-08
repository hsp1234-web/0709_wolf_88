import duckdb
import pandas as pd
from datetime import datetime, date

def populate_ohlcv_1d(db_path: str):
    """
    在指定的 DuckDB 資料庫中創建 ohlcv_1d 表格並填充模擬的 0050.TW 數據。
    """
    ohlcv_data = [
        # timestamp (datetime), product_id (str), open (float), high (float), low (float), close (float), volume (int)
        (datetime(2023, 1, 1), '0050', 120.0, 122.5, 119.5, 121.0, 50000),
        (datetime(2023, 1, 2), '0050', 121.2, 123.0, 120.8, 122.5, 65000),
        (datetime(2023, 1, 3), '0050', 122.3, 124.5, 122.0, 123.8, 72000),
        (datetime(2023, 1, 4), '0050', 123.5, 123.9, 121.5, 122.0, 58000),
        (datetime(2023, 1, 5), '0050', 122.0, 122.8, 120.5, 121.2, 62000),
    ]

    # 創建 DataFrame 是為了方便使用 DuckDB 的 executemany 或 append 功能，
    # 儘管對於少量數據，直接 INSERT INTO 也可以。
    # DuckDB 的 Python API 可以直接接受 Python datetime 物件。
    # product_id 存儲時不帶 .TW，符合 report_generator 的內部轉換邏輯。

    try:
        with duckdb.connect(database=db_path, read_only=False) as con:
            print(f"成功連接到資料庫: {db_path}")

            con.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_1d (
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
            print("表格 'ohlcv_1d' 已確認/創建。")

            # 為了冪等性，先嘗試刪除可能存在的相同日期的 0050 數據
            min_date = ohlcv_data[0][0].strftime('%Y-%m-%d')
            max_date = ohlcv_data[-1][0].strftime('%Y-%m-%d')
            con.execute(f"DELETE FROM ohlcv_1d WHERE product_id = '0050' AND date_trunc('day', timestamp) BETWEEN '{min_date}' AND '{max_date}'")
            print(f"已刪除 '0050' 在 {min_date} 至 {max_date} 的舊數據 (如有)。")

            # 插入新數據
            # executemany 需要一個 list of lists/tuples
            con.executemany("INSERT INTO ohlcv_1d VALUES (?, ?, ?, ?, ?, ?, ?)", ohlcv_data)

            print(f"成功插入 {len(ohlcv_data)} 筆模擬 OHLCV (0050.TW) 數據到 'ohlcv_1d' 表格。")

            # 驗證插入
            result = con.execute("SELECT count(*) FROM ohlcv_1d WHERE product_id = '0050'").fetchone()
            if result:
                print(f"驗證：'ohlcv_1d' 表中 '0050' 的記錄數為: {result[0]}")
            else:
                print("驗證失敗：無法讀取 '0050' 的記錄數。")

    except Exception as e:
        print(f"在 populate_ohlcv_1d 過程中發生錯誤: {e}")
        raise

if __name__ == "__main__":
    # 此處的路徑是相對於執行此腳本的位置。
    # 在實際管線中，run_pipeline.py 會提供正確的 DB 路徑。
    # 為了獨立測試此腳本，我們可以假設 DB 在當前目錄。
    mock_db_for_script_test = "analytics_mart_mock_ohlcv.duckdb"
    import os
    if os.path.exists(mock_db_for_script_test):
        os.remove(mock_db_for_script_test)
        print(f"已刪除舊的測試資料庫: {mock_db_for_script_test}")

    print(f"開始填充模擬 OHLCV 數據到: {mock_db_for_script_test}")
    populate_ohlcv_1d(mock_db_for_script_test)
    print(f"模擬 OHLCV 數據填充完畢。請檢查資料庫檔案: {mock_db_for_script_test}")

    # 簡單驗證
    try:
        with duckdb.connect(mock_db_for_script_test) as con:
            df_verify = con.execute("SELECT * FROM ohlcv_1d WHERE product_id = '0050' ORDER BY timestamp").fetchdf()
            print("\n驗證數據:")
            print(df_verify)
            if len(df_verify) == 5:
                print("\n數據條數正確 (5筆)。")
            else:
                print(f"\n錯誤：數據條數不正確，應為5筆，實際為 {len(df_verify)} 筆。")
    except Exception as e:
        print(f"驗證時發生錯誤: {e}")

    # 提醒使用者此測試資料庫是臨時的
    # print(f"\n注意：如果直接運行此腳本，會在當前目錄生成 {mock_db_for_script_test}。")
    # print("在完整的黃金測試案例中，此腳本會被 run_pipeline.py 調用，操作目標 analytics_mart.duckdb。")
    # 在CI/自動化測試中，可以考慮測試後刪除 mock_db_for_script_test
    # if os.path.exists(mock_db_for_script_test):
    #     os.remove(mock_db_for_script_test)
    #     print(f"已清理臨時測試資料庫: {mock_db_for_script_test}")
    pass
