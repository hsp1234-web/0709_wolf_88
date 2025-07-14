import duckdb
from src.core.context import AppContext
import os

DB_PATH = "prometheus_fire.duckdb"
TABLE_NAME = "backtest_results"

def clear_results(ctx: AppContext):
    """清除資料庫中的回測結果表。"""
    try:
        if os.path.exists(DB_PATH):
            conn = duckdb.connect(DB_PATH, read_only=False)
            # 使用 DROP TABLE IF EXISTS 來避免在表不存在時出錯
            conn.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
            conn.close()
            ctx.log_manager.log("SUCCESS", f"已成功清除 '{TABLE_NAME}'。")
        else:
            ctx.log_manager.log("INFO", "資料庫檔案不存在，無需清除。")
    except Exception as e:
        ctx.log_manager.log("ERROR", f"清除結果時發生錯誤: {e}")
