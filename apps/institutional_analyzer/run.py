# apps/institutional_analyzer/run.py
import argparse
import sys
import os
from datetime import datetime
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
    print(f"專案路徑校正時發生錯誤 (apps/institutional_analyzer/run.py): {e}", file=sys.stderr)
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
