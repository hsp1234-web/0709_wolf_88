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

# --- 核心邏輯 ---
def fetch_and_store_ticks():
    """
    獲取並儲存最原始的秒級交易數據（目前為模擬）。
    """
    print("[INFO] 正在啟動 taifex_tick_loader...")
    print("[INFO] 正在連接數據源... (模擬)")
    print("[INFO] 正在獲取秒級 Tick 數據... (模擬)")
    print("[INFO] 正在將數據寫入銅層資料表 bronze_taifex_ticks... (模擬)")
    print("[SUCCESS] 任務完成。")

if __name__ == "__main__":
    fetch_and_store_ticks()
