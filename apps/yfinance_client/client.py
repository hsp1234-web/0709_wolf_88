# apps/yfinance_client/client.py
# 這個模組包含從 Yahoo Finance 下載市場數據的客戶端邏輯。

import sys
import os

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

# --- 原有的其他 import 語句將在此之後 ---
import yfinance as yf
import duckdb
import pandas as pd
from datetime import datetime
import traceback

# 資料庫檔案路徑
MARKET_DATA_DB = "market_data.duckdb" # 根據作戰命令，儲存到 market_data.duckdb

def fetch_daily_ohlcv(symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    """
    從 Yahoo Finance 抓取指定商品代碼列表在給定日期範圍內的每日 OHLCV 數據。
    能夠處理單一或多個商品代碼。

    Args:
        symbols (list[str]): 商品代碼列表 (例如: ['^GSPC', 'AAPL']).
        start_date (str): 開始日期 (YYYY-MM-DD).
        end_date (str): 結束日期 (YYYY-MM-DD).

    Returns:
        pd.DataFrame: 包含 OHLCV 數據的 DataFrame，欄位包括
                      ['Date', 'symbol', 'Open', 'High', 'Low', 'Close', 'Adj_Close', 'Volume']。
                      若抓取失敗或無數據，則返回空的 DataFrame。
    """
    print(f"開始從 Yahoo Finance 抓取數據：商品 {symbols}, 日期範圍 {start_date} - {end_date}")
    if not isinstance(symbols, list):
        print("錯誤：symbols 參數必須是一個列表。")
        return pd.DataFrame()
    if not symbols:
        print("錯誤：symbols 列表不能為空。")
        return pd.DataFrame()

    try:
        # 使用 yf.Ticker(symbol) 可以更細緻地控制錯誤處理和數據獲取
        all_data_list = []
        for symbol_ticker in symbols:
            print(f"正在抓取 {symbol_ticker}...")
            ticker_obj = yf.Ticker(symbol_ticker)
            # history() 函數參數: period, start, end, interval, etc.
            # 我們使用 start 和 end
            # 移除了 progress=False 參數，因為它不被 Ticker.history() 接受
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
            print("未從任何指定商品抓取到數據。")
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

        print(f"成功抓取並合併 {len(final_df)} 筆數據。")
        return final_df

    except Exception as e:
        print(f"抓取 Yahoo Finance 數據時發生錯誤：{e}")
        traceback.print_exc()
        return pd.DataFrame()

def store_data_to_duckdb(df: pd.DataFrame, table_name: str = "daily_ohlcv", db_file: str = MARKET_DATA_DB):
    """
    將 DataFrame 數據儲存至 DuckDB 資料庫。
    使用 CREATE OR REPLACE TABLE 語句，每次都會覆寫資料表。

    Args:
        df (pd.DataFrame): 要儲存的數據。
        table_name (str): 目標資料表的名稱。
        db_file (str): DuckDB 資料庫檔案路徑。
    """
    try:
        with duckdb.connect(db_file) as con:
            # 確保資料表結構存在，即使 df 是空的
            # 定義 daily_ohlcv 的預期欄位和類型
            # 欄位：Date (DATE), symbol (VARCHAR), Open (DOUBLE), High (DOUBLE), Low (DOUBLE), Close (DOUBLE), Adj_Close (DOUBLE), Volume (BIGINT)
            con.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    Date DATE,
                    symbol VARCHAR,
                    Open DOUBLE,
                    High DOUBLE,
                    Low DOUBLE,
                    Close DOUBLE,
                    Adj_Close DOUBLE,
                    Volume BIGINT
                );
            """)

            if df.empty:
                print(f"從 yfinance 獲取的數據為空。確保資料表 '{table_name}' 在 '{db_file}' 中存在，但不寫入數據。")
                # 即使 df 為空，也要確保表被創建了 (上面的 CREATE TABLE IF NOT EXISTS 處理了)
                # 不再執行 return，而是讓後續的計數邏輯執行
            else:
                # 如果有數據，先刪除該 symbol 已有的數據，再插入新的 (實現 upsert 效果)
                # 假設 df 中包含 'symbol' 和 'Date' 欄位
                # 為了簡化，這裡假設如果 df 非空，則至少包含一個 symbol
                # 並且我們是針對本次抓取的 symbols 進行覆寫
                # 如果 df 包含多個 symbols，這會一次性刪除所有這些 symbols 的舊數據
                if 'symbol' in df.columns and not df['symbol'].empty:
                    unique_symbols_in_df = tuple(df['symbol'].unique())
                    placeholders = ', '.join(['?'] * len(unique_symbols_in_df))
                    delete_query = f"DELETE FROM {table_name} WHERE symbol IN ({placeholders})"
                    con.execute(delete_query, list(unique_symbols_in_df))
                    print(f"已從 '{table_name}' 刪除股票 {unique_symbols_in_df} 的舊數據。")

                # 使用 INSERT INTO 插入新數據
                con.execute(f"INSERT INTO {table_name} SELECT * FROM df")
                print(f"數據已成功寫入/更新至 DuckDB 資料庫 '{db_file}' 的資料表 '{table_name}'。")

            # 驗證寫入的數據量 (或表是否為空)
            count_result = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            if count_result:
                print(f"資料表 '{table_name}' 目前包含 {count_result[0]} 筆數據。")

    except Exception as e:
        print(f"儲存數據至 DuckDB 時發生錯誤：{e}")
        traceback.print_exc()

if __name__ == '__main__':
    # 測試用範例
    # 根據作戰命令的範例商品代碼：S&P 500, 納斯達克, 原油, 黃金, 歐元/美元
    # 對應的 Yahoo Finance Tickers: ^GSPC, ^IXIC, CL=F, GC=F, EURUSD=X
    test_symbols = ['^GSPC', '^IXIC', 'CL=F', 'GC=F', 'EURUSD=X', 'AAPL', '2330.TW']
    # test_symbols = ['^GSPC'] # 測試單一代碼
    # test_symbols = [] # 測試空列表
    # test_symbols = ['NONEXISTENTTICKER'] # 測試不存在的代碼

    start = "2023-11-01" # 縮短日期範圍以加快測試
    end = datetime.today().strftime('%Y-%m-%d')

    print(f"--- 開始 yfinance_client 測試 ---")
    ohlcv_data = fetch_daily_ohlcv(test_symbols, start, end)

    if not ohlcv_data.empty:
        print(f"\n抓取到的數據範例 (共 {len(ohlcv_data)} 筆):")
        print(ohlcv_data.head())
        print(ohlcv_data.tail())
        print("\n數據資訊:")
        ohlcv_data.info()

        # 檢查是否有 Volume 為空的欄位 (例如指數)
        print("\nVolume 欄位空值統計 (每個商品代號):")
        if 'Volume' in ohlcv_data.columns:
            for symbol_name, group in ohlcv_data.groupby('symbol'):
                print(f"  {symbol_name}: {group['Volume'].isnull().sum()} / {len(group)} 空值")
        else:
            print("  數據中不包含 'Volume' 欄位。")

        store_data_to_duckdb(ohlcv_data, "daily_ohlcv") # 使用預設 DB 和表名
    else:
        print("未抓取到任何數據，無法儲存。")

    # 驗證數據是否寫入
    print(f"\n--- DuckDB 數據驗證 ---")
    try:
        with duckdb.connect(MARKET_DATA_DB) as con:
            print(f"從 DuckDB 讀取 '{MARKET_DATA_DB}' 的 'daily_ohlcv' 資料表進行驗證...")

            # 檢查資料表是否存在
            tables_df = con.execute("SHOW TABLES").df()
            if 'daily_ohlcv' not in tables_df['name'].values:
                print("錯誤: 'daily_ohlcv' 資料表未在資料庫中找到。")
            else:
                retrieved_data = con.table("daily_ohlcv").df()
                print(f"成功從 'daily_ohlcv' 讀取 {len(retrieved_data)} 筆數據。")
                if not retrieved_data.empty:
                    print(retrieved_data.head())
                    print("\n欄位資訊：")
                    retrieved_data.info()
                    # 檢查是否有非預期的 None 或 NaT
                    print("\n日期欄位 NaT 檢查:")
                    print(retrieved_data['Date'].isnull().sum())

                # 額外檢查，確認欄位符合預期
                expected_cols = ['Date', 'symbol', 'Open', 'High', 'Low', 'Close', 'Adj_Close', 'Volume']
                actual_cols = retrieved_data.columns.tolist()
                print(f"\n預期欄位: {expected_cols}")
                print(f"實際欄位: {actual_cols}")

                # 檢查每個 symbol 的數據是否存在
                if not retrieved_data.empty:
                    for sym in test_symbols:
                        # 對於 yfinance，有些 ticker 可能無法下載，所以只檢查成功下載的
                        if sym in ohlcv_data['symbol'].unique():
                             symbol_data_count = len(retrieved_data[retrieved_data['symbol'] == sym])
                             print(f"商品 {sym} 在資料庫中的筆數: {symbol_data_count}")
                             if symbol_data_count == 0 and not ohlcv_data[ohlcv_data['symbol'] == sym].empty :
                                 print(f"警告: 商品 {sym} 在原始抓取數據中存在，但在資料庫中筆數為0。")


    except Exception as e:
        print(f"從 DuckDB 驗證讀取時發生錯誤: {e}")
        traceback.print_exc()

    print(f"--- yfinance_client 測試結束 ---")
