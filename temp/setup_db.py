from apps.daily_market_analyzer.db_manager import DBManager
import os

# 確保障礙物錄存在
os.makedirs("temp", exist_ok=True)

db_path = "temp/test_stability.duckdb"

# 如果已存在一個無效的資料庫檔案，先刪除它
if os.path.exists(db_path):
    os.remove(db_path)

db_manager = DBManager(db_path=db_path)
db_manager._setup_database()

print(f"資料庫 {db_path} 初始化完成。")
