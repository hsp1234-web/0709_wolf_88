# apps/finmind_client/run.py
import argparse
import sys
import os
from pathlib import Path # 標準樣板碼需要 Path

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    # 獲取目前腳本的絕對路徑
    current_script_path = Path(__file__).resolve()
    # 假設此腳本位於 apps/[app_name] 目錄下，專案根目錄是其再上兩層
    project_root = current_script_path.parent.parent.parent
    # 將專案根目錄加入 sys.path
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError: # __file__ is not defined, common in interactive shells or certain execution contexts
    project_root = Path(os.getcwd())
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    print(f"警告：__file__ 未定義，專案路徑校正可能不準確。已將 {project_root} 加入 sys.path。", file=sys.stderr)
except Exception as e:
    print(f"專案路徑校正時發生錯誤 (apps/finmind_client/run.py): {e}", file=sys.stderr)
# --- 標準化「路徑自我校正」樣板碼 END ---

from apps.finmind_client.client import FinMindClient

def main():
    parser = argparse.ArgumentParser(description="FinMind API 數據抓取測試腳本")
    parser.add_argument("stock_id", type=str, help="要查詢的股票代碼 (例如 2330)。")
    parser.add_argument("start_date", type=str, help="查詢開始日期 (YYYY-MM-DD)。")
    parser.add_argument("--api_token", type=str, default=None, help="您的 FinMind API Token。")

    args = parser.parse_args()

    print("指令：執行 FinMind Client 點火測試...")
    try:
        # 為了測試，即使沒有 real token 也要能初始化
        # 在實際使用時，應確保 token 已設定在環境變數或參數中
        token_to_use = args.api_token or os.getenv("FINMIND_API_TOKEN")
        if not token_to_use:
            print("警告：未提供 API Token，將使用一個虛擬 token 進行初始化測試。")
            token_to_use = "DUMMY_TOKEN_FOR_TESTING"

        client = FinMindClient(api_token=token_to_use)
        print(f"FinMindClient 初始化成功 (使用 Token: {'*' * (len(token_to_use) - 4)}{token_to_use[-4:]})。")
        print("點火測試成功：模組可被成功加載與初始化。")

    except Exception as e:
        print(f"點火測試失敗：{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
