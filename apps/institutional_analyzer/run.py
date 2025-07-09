# apps/institutional_analyzer/run.py
import argparse
import sys
import os
from datetime import datetime
# from pathlib import Path # Path 在標準樣板碼中未使用，如果後續代碼需要則取消註解
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

from apps.institutional_analyzer.analyzer import InstitutionalAnalyzer

def main():
    parser = argparse.ArgumentParser(description="機構法人買賣超數據分析器")
    parser.add_argument("--stock-id", required=True, type=str, help="要分析的股票代碼 (例如 2330)。")
    parser.add_argument("--start-date", required=True, type=str, help="查詢開始日期 (YYYY-MM-DD)。")
    parser.add_argument("--end-date", required=True, type=str, help="查詢結束日期 (YYYY-MM-DD)。")
    parser.add_argument("--api-token", type=str, default=os.getenv("FINMIND_API_TOKEN"), help="您的 FinMind API Token (可選，預設從 FINMIND_API_TOKEN 環境變數讀取)。")

    args = parser.parse_args()

    print(f"指令：執行機構法人買賣超分析...")
    print(f"股票代碼: {args.stock_id}")
    print(f"開始日期: {args.start_date}")
    print(f"結束日期: {args.end_date}")
    if args.api_token:
        print(f"API Token: 使用提供的 Token (長度: {len(args.api_token)})")
    else:
        print("API Token: 未提供，將依賴 FinMindClient 的內部邏輯 (可能使用環境變數或報錯)")

    try:
        # 驗證日期格式
        datetime.strptime(args.start_date, "%Y-%m-%d")
        datetime.strptime(args.end_date, "%Y-%m-%d")
    except ValueError:
        print("錯誤：日期格式不正確。請使用 YYYY-MM-DD 格式。", file=sys.stderr)
        sys.exit(1)

    token_to_use = args.api_token
    if not token_to_use:
        # 如果命令行未提供 token，且環境變數也沒有（FinMindClient 初始化時會檢查）
        # analyzer 初始化時若 token 為 None 且環境變數也無，FinMindClient 會報錯
        # 所以這裡若 args.api_token 為 None，就明確傳遞 None 給 Analyzer，讓它處理
        print("提示：未通過 --api-token 參數提供 API token，將依賴 FINMIND_API_TOKEN 環境變數。")


    try:
        analyzer = InstitutionalAnalyzer(
            stock_id=args.stock_id,
            start_date=args.start_date,
            end_date=args.end_date,
            api_token=token_to_use # 傳遞 token (可能是 None)
        )
        analyzer.run_analysis()
        print(f"機構法人買賣超分析 ({args.stock_id}, {args.start_date} 至 {args.end_date}) 執行完畢。")

    except ValueError as ve: # 例如 FinMindClient 初始化時 token 缺失
        print(f"執行分析時發生錯誤 (ValueError): {ve}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"執行分析時發生未預期錯誤: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
