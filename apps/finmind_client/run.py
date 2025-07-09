# apps/finmind_client/run.py
import argparse
import sys
import os
import sys
import os

# --- 標準化「路徑自我校正」樣板碼 START ---
# 取得目前腳本檔案的目錄
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 自動偵測專案根目錄 (假設 .git 在根目錄，或存在 README.md)
project_root = current_script_dir
max_levels_up = 5 # 防止無限迴圈，可根據專案深度調整
for _ in range(max_levels_up):
    # 檢查是否存在 .git 目錄或 AGENTS.md (或 README.md) 作為根目錄標記
    if os.path.isdir(os.path.join(project_root, '.git')) or \
       os.path.isfile(os.path.join(project_root, 'AGENTS.md')) or \
       os.path.isfile(os.path.join(project_root, 'README.md')):
        break
    parent_dir = os.path.dirname(project_root)
    if parent_dir == project_root: # 已達檔案系統頂層
        project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..'))
        print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑: {project_root}")
        break
    project_root = parent_dir
else: # 如果迴圈正常結束 (未 break)
    project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..')) # 後備方案
    print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑: {project_root}")

if project_root not in sys.path:
    sys.path.insert(0, project_root)
# print(f"DEBUG: 專案根目錄 {project_root} 已添加到 sys.path")
# --- 標準化「路徑自我校正」樣板碼 END ---
# from pathlib import Path # Path 在標準樣板碼中未使用，如果後續代碼需要則取消註解

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
