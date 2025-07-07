# apps/finmind_client/run.py
import argparse
import sys
import os

# --- 路徑自我校正樣板碼 START ---
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
except Exception as e:
    print(f"專案路徑校正時發生錯誤: {e}", file=sys.stderr)
# --- 路徑自我校正樣板碼 END ---

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
