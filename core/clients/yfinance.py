# core/clients/yfinance.py
# 此模組包含從 Yahoo Finance 下載市場數據的客戶端邏輯。

import yfinance as yf
import pandas as pd
from datetime import datetime
import traceback

def fetch_daily_ohlcv(symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    """
    從 Yahoo Finance 抓取指定商品代碼列表在給定日期範圍內的每日 OHLCV (開盤價, 最高價, 最低價, 收盤價, 成交量) 數據。
    能夠處理單一或多個商品代碼。

    Args:
        symbols (list[str]): 商品代碼列表 (例如: ['^GSPC', 'AAPL'])。
        start_date (str): 開始日期 (格式: YYYY-MM-DD)。
        end_date (str): 結束日期 (格式: YYYY-MM-DD)。

    Returns:
        pd.DataFrame: 包含 OHLCV 數據的 DataFrame，欄位包括
                      ['Date', 'symbol', 'Open', 'High', 'Low', 'Close', 'Adj_Close', 'Volume']。
                      若抓取失敗或無數據，則返回一個空的 DataFrame。
    """
    print(f"資訊：開始從 Yahoo Finance 抓取數據：商品 {symbols}, 日期範圍 {start_date} - {end_date}")
    if not isinstance(symbols, list):
        print("錯誤：symbols 參數必須是一個列表。")
        return pd.DataFrame()
    if not symbols:
        print("錯誤：symbols 列表不能為空。")
        return pd.DataFrame()

    try:
        all_data_list = []
        for symbol_ticker in symbols:
            print(f"資訊：正在抓取 {symbol_ticker}...")
            ticker_obj = yf.Ticker(symbol_ticker)
            # history() 函數參數: period, start, end, interval, etc.
            # 我們使用 start 和 end
            hist_data = ticker_obj.history(start=start_date, end=end_date, auto_adjust=False)

            if hist_data.empty:
                print(f"警告：商品 {symbol_ticker} 在 {start_date} - {end_date} 範圍內未找到數據。")
                continue

            hist_data.reset_index(inplace=True) # 將 Date 從索引變為欄位
            hist_data['symbol'] = symbol_ticker # 新增 symbol 欄位

            # yfinance 返回的 Date 欄位可能是 datetime unaware 或 aware，統一為 UTC naive
            if hist_data['Date'].dt.tz is not None:
                 hist_data['Date'] = hist_data['Date'].dt.tz_convert(None)

            all_data_list.append(hist_data)

        if not all_data_list:
            print("資訊：未從任何指定商品抓取到數據。")
            return pd.DataFrame()

        final_df = pd.concat(all_data_list, ignore_index=True)

        # 標準化欄位名稱並選擇所需欄位
        final_df.rename(columns={
            'Adj Close': 'Adj_Close', # yfinance 可能使用 'Adj Close'
            'Date': 'Date',
            'Open': 'Open',
            'High': 'High',
            'Low': 'Low',
            'Close': 'Close',
            'Volume': 'Volume'
        }, inplace=True)

        # 確保 'Date' 欄位是 datetime64[ns] 型別
        final_df['Date'] = pd.to_datetime(final_df['Date'])

        # 根據作戰命令，需要的欄位是 OHLCV，Adj Close 也很常用
        required_cols = ['Date', 'symbol', 'Open', 'High', 'Low', 'Close', 'Adj_Close', 'Volume']

        # 篩選出實際存在的欄位，以避免錯誤，並按指定順序排列
        cols_to_keep = [col for col in required_cols if col in final_df.columns]
        missing_cols = [col for col in required_cols if col not in cols_to_keep]
        if missing_cols:
            print(f"警告：抓取的數據中缺少以下預期欄位: {missing_cols}。這些欄位將不會包含在結果中。")
            # 例如，某些指數可能沒有 Volume

        final_df = final_df[cols_to_keep]

        print(f"資訊：成功抓取並合併 {len(final_df)} 筆數據。")
        return final_df

    except Exception as e:
        print(f"錯誤：抓取 Yahoo Finance 數據時發生錯誤：{e}")
        traceback.print_exc()
        return pd.DataFrame()
