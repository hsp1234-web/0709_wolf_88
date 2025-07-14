import duckdb
from src.core.context import AppContext

DB_PATH = "prometheus_fire.duckdb"
TABLE_NAME = "backtest_results"

def show_results(ctx: AppContext):
    ctx.log_manager.log("INFO", f"正在從 {DB_PATH} 查詢結果...")
    try:
        with duckdb.connect(database=DB_PATH, read_only=True) as con:
            # 顯示表格的 Schema
            ctx.log_manager.log("INFO", f"表格 '{TABLE_NAME}' 的結構:")
            con.execute(f"PRAGMA table_info('{TABLE_NAME}');").pl()

            # 顯示最近 10 筆結果
            ctx.log_manager.log("INFO", "最近 10 筆回測結果:")
            con.execute(f"SELECT * FROM {TABLE_NAME} ORDER BY id DESC LIMIT 10;").pl()

    except duckdb.CatalogException:
        ctx.log_manager.log("WARNING", f"找不到表格 '{TABLE_NAME}'。請先執行回測。")
    except Exception as e:
        ctx.log_manager.log("ERROR", f"查詢時發生錯誤: {e}")
