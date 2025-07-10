# 唯一的公開執行入口
import os
import sys

# --- 路徑自我校正 ---
# 確保腳本無論從何處執行，都能正確找到專案根目錄並將其添加到 sys.path
# 這對於後續導入 core 模組至關重要

# 獲取目前腳本的絕對路徑
current_script_path = os.path.abspath(__file__)

# 從目前腳本路徑向上查找專案根目錄（假設根目錄包含 "apps" 和 "core" 資料夾）
# 我們預期 'apps/taifex_tick_loader/run.py'，所以往上三層是根目錄
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_script_path)))

# 如果專案根目錄不在 sys.path 中，則添加它
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import datetime
from apps.taifex_tick_loader.core.db_manager import DatabaseManager
from apps.taifex_tick_loader.core.schemas import TaifexTick

# --- 核心邏輯 ---
def fetch_and_store_ticks():
    """
    獲取並儲存最原始的秒級交易數據。
    """
    print("[INFO] 正在啟動 taifex_tick_loader...")
    db_path = "market_data.duckdb"  # 實際應用中可能來自配置
    table_name = "bronze_taifex_ticks"

    try:
        with DatabaseManager(db_path=db_path) as db_manager:
            print(f"[INFO] 正在確保資料表 '{table_name}' 存在...")
            db_manager.create_table_if_not_exists(table_name, TaifexTick)
            print(f"[SUCCESS] 資料表 '{table_name}' 已準備就緒。")

            # 模擬數據獲取
            print("[INFO] 正在模擬獲取秒級 Tick 數據...")
            simulated_ticks = [
                TaifexTick(timestamp=datetime.datetime(2023, 10, 1, 9, 0, 0, 100000), price=16500.0, volume=2, instrument="TXF202310", tick_type="Trade"),
                TaifexTick(timestamp=datetime.datetime(2023, 10, 1, 9, 0, 1, 200000), price=16501.0, volume=3, instrument="TXF202310", tick_type="Trade"),
                TaifexTick(timestamp=datetime.datetime(2023, 10, 1, 9, 0, 2, 300000), price=16500.5, volume=1, instrument="TXF202310", tick_type="Trade"),
            ]
            print(f"[INFO] 成功模擬獲取 {len(simulated_ticks)} 筆 Tick 數據。")

            if simulated_ticks:
                print(f"[INFO] 正在將 {len(simulated_ticks)} 筆數據寫入資料表 '{table_name}'...")
                db_manager.insert_ticks(table_name, simulated_ticks)
                print(f"[SUCCESS] 成功寫入 {len(simulated_ticks)} 筆 Tick 數據到 '{table_name}'。")
            else:
                print("[INFO] 沒有模擬數據可供寫入。")

        print("[SUCCESS] taifex_tick_loader 任務完成。")

    except Exception as e:
        print(f"[ERROR] taifex_tick_loader 執行過程中發生錯誤: {e}")
        # 在實際應用中，這裡可能需要更複雜的錯誤處理機制
        # 例如：重試、發送警報等

if __name__ == "__main__":
    # 清理舊的測試數據庫文件 (如果存在)，以便每次運行都是乾淨的狀態
    # 這主要用於本地測試，實際部署時可能不需要
    import os
    if os.path.exists("market_data.duckdb"):
        os.remove("market_data.duckdb")
    if os.path.exists("market_data.duckdb.wal"):
        os.remove("market_data.duckdb.wal")

    fetch_and_store_ticks()
