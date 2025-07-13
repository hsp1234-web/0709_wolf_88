import yfinance as yf
import pandas as pd
from core.db.db_manager import DBManager

def run_pipeline(tickers: list[str], table_name: str = "market_daily_ohlcv"):
    """
    執行 Yahoo Finance 數據獲取管線。

    本管線負責下載指定股票代碼的日線 OHLCV 數據，
    並將其寫入指定的資料庫表格中。

    Args:
        tickers (list[str]): 需要下載的股票代碼列表。
        table_name (str): 數據要存入的資料庫表格名稱。
    """
    print("🚀 開始執行 Yahoo Finance ETL 管線...")

    try:
        # 步驟 1: 下載數據
        print(f"📥 正在從 Yahoo Finance 下載 {tickers} 的數據...")
        data = yf.download(tickers, period="5y", group_by='ticker', auto_adjust=True)

        if data.empty:
            print("⚠️ 未下載到任何數據，管線提前結束。")
            return

        # 步驟 2: 數據轉換與整理
        all_data = []
        for ticker in tickers:
            if ticker in data.columns:
                ticker_data = data[ticker].copy()
                ticker_data['ticker'] = ticker
                ticker_data.reset_index(inplace=True)
                all_data.append(ticker_data)

        if not all_data:
            print("⚠️ 數據下載後，未能成功解析任何股票數據。")
            return

        final_df = pd.concat(all_data, ignore_index=True)
        final_df.columns = [col.lower() for col in final_df.columns]

        # 確保核心欄位存在
        required_cols = ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']

        # 解決 MultiIndex 的問題
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(0)

        if final_df.index.name == 'date':
            final_df.reset_index(inplace=True)

        # 確保 'date' 欄位存在
        if 'date' in final_df.columns:
            final_df = final_df[required_cols]
        else:
            # mock_yfinance_download 數據沒有 date
            final_df.reset_index(inplace=True)
            final_df.rename(columns={'index': 'date'}, inplace=True)
            final_df = final_df[required_cols]

        print(f"📊 數據轉換完成，共處理 {len(final_df)} 筆數據。")

        # 步驟 3: 寫入資料庫
        print(f"✍️ 準備將數據寫入資料庫表格 '{table_name}'...")
        db_manager = DBManager()
        db_manager.write_dataframe(final_df, table_name, if_exists="replace")
        print(f"✅ 數據已成功寫入資料庫！")

    except Exception as e:
        print(f"❌ 管線執行失敗：{e}")

    finally:
        print("🏁 Yahoo Finance ETL 管線執行完畢。")

if __name__ == "__main__":
    target_tickers = ["SPY", "QQQ", "AAPL"]
    run_pipeline(target_tickers)
