# apps/finmind_client/run.py
import argparse
import sys
import os
from datetime import datetime
import pandas as pd

# 將專案根目錄加到 sys.path，以便導入 client
# 假設 run.py 在 apps/finmind_client/ 目錄下，專案根目錄是向上兩層
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from apps.finmind_client.client import FinMindClient

def save_dataframe(df: pd.DataFrame, output_path: str, data_type: str, stock_id: str):
    """
    將 DataFrame 儲存到指定的路徑。

    Args:
        df (pd.DataFrame): 要儲存的 DataFrame。
        output_path (str): 儲存的目錄路徑。
        data_type (str): 數據類型 (用於檔案命名)。
        stock_id (str): 股票代碼 (用於檔案命名)。
    """
    if df is None or df.empty:
        print(f"沒有獲取到 {data_type} 數據 ({stock_id})，不進行儲存。")
        return

    # 建立輸出目錄 (如果不存在)
    os.makedirs(output_path, exist_ok=True)

    # 檔案名稱格式：{stock_id}_{data_type}_{timestamp}.csv
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{stock_id}_{data_type}_{timestamp}.csv"
    filepath = os.path.join(output_path, filename)

    try:
        df.to_csv(filepath, index=False, encoding='utf-8-sig') # utf-8-sig 確保 Excel 開啟中文正常
        print(f"數據已成功儲存到：{filepath}")
    except Exception as e:
        print(f"儲存數據到 {filepath} 時發生錯誤：{e}")

def main():
    parser = argparse.ArgumentParser(description="FinMind API 數據抓取客戶端")
    parser.add_argument("data_type", type=str,
                        choices=[
                            "institutional_investors", "daily_stock_price",
                            "balance_sheet", "income_statement", "cash_flow_statement",
                            "month_revenue"
                        ],
                        help="要抓取的數據類型。 "
                             "institutional_investors: 三大法人買賣超, "
                             "daily_stock_price: 個股日成交資訊, "
                             "balance_sheet: 資產負債表, "
                             "income_statement: 綜合損益表, "
                             "cash_flow_statement: 現金流量表, "
                             "month_revenue: 月營收")
    parser.add_argument("stock_id", type=str, help="股票代碼 (例如 2330)。")
    parser.add_argument("start_date", type=str, help="開始日期 (格式 YYYY-MM-DD)。對於財報，此日期用於查詢該日期之後的財報。")
    parser.add_argument("--end_date", type=str, default=None, help="結束日期 (格式 YYYY-MM-DD)。預設為今天。對於財報類型，此參數通常不使用。")
    parser.add_argument("--output_path", type=str, default="data/finmind_data",
                        help="儲存數據的目錄路徑。預設為 data/finmind_data。")
    parser.add_argument("--api_token", type=str, default=None, help="FinMind API Token。如果未提供，則從環境變數 FINMIND_API_TOKEN 讀取。")

    args = parser.parse_args()

    try:
        client = FinMindClient(api_token=args.api_token)
    except ValueError as e:
        print(f"錯誤：{e}")
        sys.exit(1)

    print(f"正在處理請求：數據類型={args.data_type}, 股票代碼={args.stock_id}, 開始日期={args.start_date}, 結束日期={args.end_date}")

    df_result = None
    if args.data_type == "institutional_investors":
        df_result = client.get_taiwan_stock_institutional_investors_buy_sell(
            data_id=args.stock_id,
            start_date=args.start_date,
            end_date=args.end_date
        )
    elif args.data_type == "daily_stock_price":
        # 提醒：這不是券商分點數據
        print("提醒：正在獲取每日股價數據，這並非券商分點進出數據。")
        df_result = client.get_taiwan_stock_per_day(
            data_id=args.stock_id,
            start_date=args.start_date,
            end_date=args.end_date
        )
    elif args.data_type == "balance_sheet":
        df_result = client.get_financial_statement(
            data_id=args.stock_id,
            start_date=args.start_date,
            statement_type="BalanceSheet"
        )
    elif args.data_type == "income_statement":
        df_result = client.get_financial_statement(
            data_id=args.stock_id,
            start_date=args.start_date,
            statement_type="ComprehensiveIncomeStatement" # FinMind 使用此名稱
        )
    elif args.data_type == "cash_flow_statement":
        df_result = client.get_financial_statement(
            data_id=args.stock_id,
            start_date=args.start_date,
            statement_type="CashFlowsStatement"
        )
    elif args.data_type == "month_revenue":
        df_result = client.get_taiwan_stock_month_revenue(
            data_id=args.stock_id,
            start_date=args.start_date,
            end_date=args.end_date
        )
    else:
        print(f"錯誤：未知的數據類型 '{args.data_type}'")
        sys.exit(1)

    if df_result is not None:
        if not df_result.empty:
            print(f"成功獲取數據，共 {len(df_result)} 筆。")
            print(df_result.head())
            save_dataframe(df_result, args.output_path, args.data_type, args.stock_id)
        else:
            print(f"未查詢到任何數據 (股票代碼: {args.stock_id}, 數據類型: {args.data_type})。")
    else:
        print(f"獲取數據失敗 (股票代碼: {args.stock_id}, 數據類型: {args.data_type})。請檢查 API Token 或網路連線。")

if __name__ == "__main__":
    # 使用範例 (需在環境變數中設定 FINMIND_API_TOKEN 或透過 --api_token 傳入):
    # python apps/finmind_client/run.py institutional_investors 2330 2023-10-01 --end_date 2023-10-05 --output_path temp_data/finmind
    # python apps/finmind_client/run.py balance_sheet 2330 2022-01-01 --output_path temp_data/finmind
    # python apps/finmind_client/run.py month_revenue 2330 2022-01-01 --output_path temp_data/finmind
    main()

"""
此 `run.py` 腳本提供了一個命令列介面，用於：
1.  接收用戶指定的參數（數據類型、股票代碼、日期範圍、輸出路徑、API Token）。
2.  初始化 `FinMindClient`。
3.  調用客戶端中相應的方法來獲取數據。
4.  將獲取到的 DataFrame 數據儲存為 CSV 檔案。

檔案儲存路徑結構: `--output_path` 指定的目錄 / `{stock_id}_{data_type}_{timestamp}.csv`

執行前，請確保：
- `apps.finmind_client.client` 模組可被正確導入 (已透過 `sys.path.insert` 處理)。
- `requests` 和 `pandas` 庫已安裝。
- FinMind API Token 已設定 (透過環境變數 `FINMIND_API_TOKEN` 或 `--api_token` 參數)。
"""
