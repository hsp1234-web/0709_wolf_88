import os
from src.core.context import AppContext

RESULTS_DB_PATH = "output/results.sqlite"

def clear_results(ctx: AppContext):
    ctx.log_manager.log("WARNING", f"準備刪除交易型結果資料庫: {RESULTS_DB_PATH}...")
    try:
        if os.path.exists(RESULTS_DB_PATH):
            os.remove(RESULTS_DB_PATH)
            ctx.log_manager.log("SUCCESS", f"資料庫檔案 '{RESULTS_DB_PATH}' 已成功刪除。")
        else:
            ctx.log_manager.log("INFO", f"資料庫檔案 '{RESULTS_DB_PATH}' 不存在，無需刪除。")
    except Exception as e:
        ctx.log_manager.log("ERROR", f"刪除資料庫檔案時發生錯誤: {e}")
