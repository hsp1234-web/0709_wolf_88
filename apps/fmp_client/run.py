# apps/fmp_client/run.py
import argparse
import sys
import os
from datetime import datetime
import pandas as pd
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
    print(f"專案路徑校正時發生錯誤 (apps/fmp_client/run.py): {e}", file=sys.stderr)
# --- 標準化「路徑自我校正」樣板碼 END ---

from apps.fmp_client.client import FMPClient

def save_dataframe(df: pd.DataFrame, output_path: str, data_type: str, symbol: str):
    """
    將 DataFrame 儲存到指定的路徑。

    Args:
        df (pd.DataFrame): 要儲存的 DataFrame。
        output_path (str): 儲存的目錄路徑。
        data_type (str): 數據類型 (用於檔案命名)。
        symbol (str): 商品代碼 (用於檔案命名)。
    """
    if df is None or df.empty:
        print(f"沒有獲取到 {data_type} 數據 ({symbol})，不進行儲存。")
        return

    os.makedirs(output_path, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    # FMP symbol 中可能包含特殊字元 (如 %5EGSPC)，替換掉不適合檔案名稱的字元
    safe_symbol = symbol.replace("%", "pct").replace("^", "caret")
    filename = f"{safe_symbol}_{data_type}_{timestamp}.csv"
    filepath = os.path.join(output_path, filename)

    try:
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        print(f"數據已成功儲存到：{filepath}")
    except Exception as e:
        print(f"儲存數據到 {filepath} 時發生錯誤：{e}")

def main():
    parser = argparse.ArgumentParser(description="Financial Modeling Prep (FMP) API 數據抓取客戶端")

    # 子命令
    subparsers = parser.add_subparsers(dest="command", title="Commands", required=True)

    # 歷史價格子命令
    price_parser = subparsers.add_parser("historical_price", help="獲取歷史價格數據 (股票、ETF、指數)")
    price_parser.add_argument("symbol", type=str, help="商品代碼 (例如 AAPL, SPY, %5EGSPC for S&P 500)")
    price_parser.add_argument("--from_date", type=str, default=None, help="開始日期 (YYYY-MM-DD)")
    price_parser.add_argument("--to_date", type=str, default=None, help="結束日期 (YYYY-MM-DD)")
    price_parser.add_argument("--output_path", type=str, default="data/fmp_data/prices", help="儲存價格數據的目錄路徑")

    # 財報子命令
    financials_parser = subparsers.add_parser("financial_statement", help="獲取財報數據")
    financials_parser.add_argument("symbol", type=str, help="股票代碼 (例如 AAPL)")
    financials_parser.add_argument("statement_type", type=str,
                                    choices=["income-statement", "balance-sheet-statement", "cash-flow-statement"],
                                    help="財報類型 (income-statement, balance-sheet-statement, cash-flow-statement)")
    financials_parser.add_argument("--period", type=str, default="quarter", choices=["quarter", "annual"], help="財報週期 (quarter, annual)")
    financials_parser.add_argument("--limit", type=int, default=20, help="返回的財報期數")
    financials_parser.add_argument("--output_path", type=str, default="data/fmp_data/financials", help="儲存財報數據的目錄路徑")

    # 通用參數
    for p in [parser, price_parser, financials_parser]:
        p.add_argument("--api_key", type=str, default=None, help="FMP API Key。如果未提供，則從環境變數 FMP_API_KEY 讀取。")
        p.add_argument("--api_version", type=str, default="v3", help="FMP API 版本 (例如 v3, v4)。預設 v3。")


    args = parser.parse_args()

    try:
        client = FMPClient(api_key=args.api_key, api_version=args.api_version)
    except ValueError as e:
        print(f"錯誤：{e}")
        sys.exit(1)

    df_result = None
    data_category = "" # 用於檔案命名和訊息

    if args.command == "historical_price":
        print(f"正在獲取 {args.symbol} 的歷史價格數據 (從 {args.from_date} 到 {args.to_date})...")
        data_category = "historical_price"
        df_result = client.get_historical_daily_prices(
            symbol=args.symbol,
            from_date=args.from_date,
            to_date=args.to_date
        )
    elif args.command == "financial_statement":
        print(f"正在獲取 {args.symbol} 的 {args.period} {args.statement_type} (最近 {args.limit} 期)...")
        data_category = f"{args.statement_type}_{args.period}"
        df_result = client.get_financial_statements(
            symbol=args.symbol,
            statement_type=args.statement_type,
            period=args.period,
            limit=args.limit
        )
    else:
        print(f"錯誤：未知的命令 '{args.command}'")
        sys.exit(1)

    if df_result is not None:
        if not df_result.empty:
            print(f"成功獲取數據，共 {len(df_result)} 筆。")
            print(df_result.head())
            save_dataframe(df_result, args.output_path, data_category, args.symbol)
        else:
            print(f"未查詢到任何數據 (Symbol: {args.symbol}, Command: {args.command})。請檢查 API Key 權限或代碼是否正確。")
    else:
        print(f"獲取數據失敗 (Symbol: {args.symbol}, Command: {args.command})。請檢查 API Key、網路連線或 API 限制。")


if __name__ == "__main__":
    # 使用範例 (需在環境變數中設定 FMP_API_KEY 或透過 --api_key 傳入):
    # python apps/fmp_client/run.py historical_price AAPL --from_date 2023-01-01 --to_date 2023-01-31 --output_path temp_data/fmp/prices
    # python apps/fmp_client/run.py historical_price SPY --output_path temp_data/fmp/prices
    # python apps/fmp_client/run.py historical_price "%5EGSPC" --output_path temp_data/fmp/prices --api_key YOUR_FMP_KEY

    # python apps/fmp_client/run.py financial_statement AAPL income-statement --period quarter --limit 4 --output_path temp_data/fmp/financials
    # python apps/fmp_client/run.py financial_statement MSFT balance-sheet-statement --period annual --limit 2 --output_path temp_data/fmp/financials --api_key YOUR_FMP_KEY
    main()

"""
此 `run.py` 腳本為 FMP 客戶端提供了一個命令列介面，具有以下功能：

1.  **子命令 (Subcommands)**:
    *   `historical_price`: 用於獲取股票、ETF 或指數的歷史日線價格。
    *   `financial_statement`: 用於獲取公司的財務報表 (損益表、資產負債表、現金流量表)。

2.  **參數化執行**:
    *   可以指定商品代碼 (`symbol`)、日期範圍 (`from_date`, `to_date`)、財報類型 (`statement_type`)、財報週期 (`period`)、期數限制 (`limit`)。
    *   允許指定輸出目錄 (`output_path`)。
    *   允許透過 `--api_key` 傳遞 API Key，否則從環境變數 `FMP_API_KEY` 讀取。
    *   允許指定 API 版本 (`--api_version`)。

3.  **客戶端調用**: 初始化 `FMPClient` 並調用其相應的方法來獲取數據。

4.  **數據儲存**:
    *   將獲取到的 DataFrame 數據儲存為 CSV 檔案。
    *   檔案儲存路徑根據命令和參數動態生成，例如：
        *   價格數據: `args.output_path` / `{safe_symbol}_historical_price_{timestamp}.csv`
        *   財報數據: `args.output_path` / `{safe_symbol}_{statement_type}_{period}_{timestamp}.csv`
    *   `safe_symbol` 會將商品代碼中的特殊字元替換，以利檔案系統儲存。

執行前，請確保：
- `apps.fmp_client.client` 模組可被正確導入。
- `requests` 和 `pandas` 庫已安裝。
- FMP API Key 已設定 (透過環境變數 `FMP_API_KEY` 或 `--api_key` 參數)。
- 免費版 FMP API Key 可能有諸多限制 (數據延遲、請求頻率、可用 symbol 等)，導致無法獲取數據或數據不完整。
"""
