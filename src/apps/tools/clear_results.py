import duckdb
from src.core.context import AppContext

DB_PATH = "prometheus_fire.duckdb"
TABLE_NAME = "backtest_results"

def clear_results(ctx: AppContext):
    ctx.log_manager.log("INFO", f"準備清除 {DB_PATH} 中的結果...")
    try:
        with duckdb.connect(database=DB_PATH, read_only=False) as con:
            con.execute(f"DROP TABLE IF EXISTS {TABLE_NAME};")
        ctx.log_manager.log("SUCCESS", f"已成功清除表格 '{TABLE_NAME}'。")
    except Exception as e:
        ctx.log_manager.log("ERROR", f"清除時發生錯誤: {e}")
