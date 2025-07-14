import duckdb
from core.logger import LogManager

DB_PATH = "prometheus_fire.duckdb"
TABLE_NAME = "backtest_results"

def clear_results(log_manager: LogManager):
    """清除所有已儲存的回測結果。"""
    log_manager.log("WARNING", f"準備清除資料表 '{TABLE_NAME}'...")
    try:
        conn = duckdb.connect(DB_PATH)
        # 使用 DROP TABLE IF EXISTS 安全地刪除資料表
        conn.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
        conn.close()
        log_manager.log("SUCCESS", f"資料表 '{TABLE_NAME}' 已成功清除。")
    except Exception as e:
        log_manager.log("ERROR", f"清除結果時發生錯誤: {e}")
