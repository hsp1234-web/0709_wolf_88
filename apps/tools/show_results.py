import duckdb
import pandas as pd
from core.logger import LogManager

DB_PATH = "prometheus_fire.duckdb"
TABLE_NAME = "backtest_results"

def show_results(log_manager: LogManager):
    log_manager.log("INFO", f"正在從 {DB_PATH} 查詢結果...")
    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
        df = conn.execute(f"SELECT * FROM {TABLE_NAME}").fetchdf()
        conn.close()

        if df.empty:
            log_manager.log("WARNING", "資料庫中尚無任何結果。")
        else:
            log_manager.log("SUCCESS", "查詢完成。")
            print("\n--- 回測結果 ---")
            print(df.to_string())
            print("----------------\n")
    except Exception as e:
        log_manager.log("ERROR", f"查詢結果時發生錯誤: {e}")
