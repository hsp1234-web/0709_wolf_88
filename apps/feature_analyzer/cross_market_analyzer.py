# apps/feature_analyzer/cross_market_analyzer.py
# 這個模組負責計算不同市場核心資產之間的滾動相關性。

import duckdb
import pandas as pd
import itertools

# 資料庫設定
DEFAULT_MARKET_DATA_DB = "market_data.duckdb" # 來源資料庫
DEFAULT_ANALYTICS_MART_DB = "analytics_mart.duckdb" # 目標資料庫
OHLCV_TABLE_NAME = "daily_ohlcv"
CORRELATION_TABLE_NAME = "cross_market_correlation"

# 核心資產列表 (Yahoo Finance tickers)
CORE_ASSETS = ['^TWII', '^GSPC', '^IXIC', 'CL=F', 'GC=F']

def fetch_ohlcv_data_for_assets(assets: list[str], market_db_path: str) -> pd.DataFrame:
    """
    從指定的 market_data 資料庫的 daily_ohlcv 表中提取指定資產的收盤價數據。
    """
    if not assets:
        print("錯誤：資產列表不可為空。")
        return pd.DataFrame()

    placeholders = ', '.join(['?'] * len(assets))
    query = f"""
    SELECT Date, symbol, Adj_Close
    FROM {OHLCV_TABLE_NAME}
    WHERE symbol IN ({placeholders})
    ORDER BY Date, symbol;
    """
    try:
        with duckdb.connect(market_db_path, read_only=True) as con: # 使用傳入的 market_db_path
            df = con.execute(query, assets).fetchdf()

        if df.empty:
            print(f"警告：在資料庫 {market_db_path} 的 {OHLCV_TABLE_NAME} 表中未找到資產 {assets} 的數據。")
            return pd.DataFrame()

        # 將數據轉換為寬表格式：Date 作为 index, symbols 作为 columns, Adj_Close 作为 values
        pivot_df = df.pivot(index='Date', columns='symbol', values='Adj_Close')

        # 填充缺失值：滾動相關性計算對 NaN 敏感。
        # 可以使用 ffill (forward fill) 或其他策略。ffill 較為常用。
        pivot_df.ffill(inplace=True)
        # 初始的 NaN (如果某資產開始日期較晚) 可能仍存在，後續計算時需注意。
        # 或者在計算前 dropna()，但這可能導致不同資產對的計算期間不同。
        # 另一種方法是確保所有資產都有足夠長的共同歷史數據。

        print(f"成功從 {OHLCV_TABLE_NAME} (來源: {market_db_path}) 為資產 {assets} 提取並轉換了 {len(pivot_df)} 天的數據。")
        return pivot_df
    except Exception as e:
        print(f"從 DuckDB ({market_db_path}) 提取 OHLCV 數據時發生錯誤: {e}")
        traceback.print_exc()
        return pd.DataFrame()

def calculate_rolling_correlation(price_df: pd.DataFrame, window: int = 30) -> pd.DataFrame:
    """
    計算提供的價格 DataFrame 中所有資產對之間的滾動相關係數。
    Args:
        price_df (pd.DataFrame): 索引為日期，欄位為資產代碼，值為價格的 DataFrame。
        window (int): 滾動窗口大小。
    Returns:
        pd.DataFrame: 包含日期、資產對、相關係數和週期的 DataFrame。
    """
    if price_df.empty or price_df.shape[1] < 2:
        print("錯誤：價格數據不足以計算相關性 (至少需要兩個資產)。")
        return pd.DataFrame()

    # 計算日收益率，因為相關性通常基於收益率而非價格本身
    returns_df = price_df.pct_change().dropna() # dropna() 移除第一個 NaN 行 (因 pct_change 產生)

    if returns_df.empty or returns_df.shape[0] < window : # 確保有足夠數據進行滾動計算
        print(f"警告：收益率數據不足 (少於滾動窗口 {window} 天)，無法計算滾動相關性。")
        return pd.DataFrame()

    all_correlations = []
    asset_pairs = list(itertools.combinations(returns_df.columns, 2))

    for asset1, asset2 in asset_pairs:
        # 計算兩個資產收益率的滾動相關性
        # rolling().corr() 需要兩個 Series
        rolling_corr = returns_df[asset1].rolling(window=window).corr(returns_df[asset2])

        # 移除結果初期的 NaN (因滾動窗口不足)
        rolling_corr_clean = rolling_corr.dropna()

        if not rolling_corr_clean.empty:
            corr_df_pair = pd.DataFrame({
                'date': rolling_corr_clean.index,
                'asset_pair': f"{asset1}-{asset2}",
                'correlation_coefficient': rolling_corr_clean.values,
                'period': window
            })
            all_correlations.append(corr_df_pair)
        else:
            print(f"警告：資產對 {asset1}-{asset2} 在窗口 {window} 下的滾動相關性計算結果為空。")

    if not all_correlations:
        print("未能計算出任何資產對的滾動相關性。")
        return pd.DataFrame()

    final_corr_df = pd.concat(all_correlations, ignore_index=True)
    print(f"成功計算 {len(asset_pairs)} 個資產對的滾動相關性，共產生 {len(final_corr_df)} 筆相關性數據。")
    return final_corr_df

def store_correlation_data(df: pd.DataFrame, analytics_db_path: str, table_name: str = CORRELATION_TABLE_NAME):
    """
    將計算出的相關係數數據儲存到指定的 analytics_mart 資料庫。
    """
    if df.empty:
        print(f"沒有相關性數據可儲存至資料表 {table_name}。")
        return

    try:
        with duckdb.connect(analytics_db_path) as con: # 使用傳入的 analytics_db_path
            con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")
            print(f"相關性數據已成功儲存至 DuckDB 資料庫 '{analytics_db_path}' 的資料表 '{table_name}'。")
            count_result = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            if count_result:
                print(f"資料表 '{table_name}' 目前包含 {count_result[0]} 筆數據。")
    except Exception as e:
        print(f"儲存相關性數據至 DuckDB ({analytics_db_path}) 時發生錯誤：{e}")
        traceback.print_exc()

def run_cross_market_correlation_analysis(
    assets_to_analyze: list[str] = None,
    window: int = 30,
    market_db_path: str = DEFAULT_MARKET_DATA_DB,
    analytics_db_path: str = DEFAULT_ANALYTICS_MART_DB
    ):
    """
    執行跨市場相關性分析的主函數。
    """
    print("\n--- 開始跨市場相關性分析 ---")
    if assets_to_analyze is None:
        assets_to_analyze = CORE_ASSETS

    print(f"目標資產: {assets_to_analyze}, 滾動窗口: {window} 天")
    print(f"來源市場數據庫: {market_db_path}")
    print(f"目標分析數據庫: {analytics_db_path}")

    price_data = fetch_ohlcv_data_for_assets(assets_to_analyze, market_db_path)

    if price_data.empty or price_data.shape[1] < 2:
        print("無法繼續相關性分析，因獲取的價格數據不足。")
        return

    correlation_results = calculate_rolling_correlation(price_data, window)

    if not correlation_results.empty:
        store_correlation_data(correlation_results, analytics_db_path)
        print("跨市場相關性分析執行完畢。")
    else:
        print("跨市場相關性分析執行完畢，但未產生任何可儲存的相關性結果。")

if __name__ == '__main__':
    # 測試用資產列表，可以從 yfinance_client 的測試結果中選擇一些已確認存在的 ticker
    # 例如：'^GSPC', 'GC=F', '2330.TW' (假設這些已由 yfinance_client 抓取並存儲)
    # 確保 market_data.duckdb 和 daily_ohlcv 表已存在且包含數據

    # 為了測試，首先確保 daily_ohlcv 有數據
    # (此處的獨立測試將使用預設資料庫名稱)

    print("執行 cross_market_analyzer.py 獨立測試 (使用預設DB路徑)...")
    test_assets = ['^GSPC', 'GC=F', '^TWII', 'CL=F', '^IXIC']
    run_cross_market_correlation_analysis(
        assets_to_analyze=test_assets,
        window=30,
        market_db_path=DEFAULT_MARKET_DATA_DB, # 明確使用預設值
        analytics_db_path=DEFAULT_ANALYTICS_MART_DB # 明確使用預設值
    )

    print(f"\n--- DuckDB 數據驗證 (cross_market_correlation, DB: {DEFAULT_ANALYTICS_MART_DB}) ---")
    try:
        with duckdb.connect(DEFAULT_ANALYTICS_MART_DB) as con: # 連接到預設分析資料庫
            print(f"從 DuckDB 讀取 '{DEFAULT_ANALYTICS_MART_DB}' 的 '{CORRELATION_TABLE_NAME}' 資料表進行驗證...")
            tables_df = con.execute("SHOW TABLES").df()
            if CORRELATION_TABLE_NAME not in tables_df['name'].values:
                print(f"錯誤: '{CORRELATION_TABLE_NAME}' 資料表未在資料庫中找到。")
            else:
                retrieved_data = con.table(CORRELATION_TABLE_NAME).df()
                print(f"成功從 '{CORRELATION_TABLE_NAME}' 讀取 {len(retrieved_data)} 筆數據。")
                if not retrieved_data.empty:
                    print(retrieved_data.head())
                    retrieved_data.info()
                    print("\n資產對抽樣:")
                    print(retrieved_data['asset_pair'].value_counts().head())
    except Exception as e:
        print(f"從 DuckDB 驗證讀取相關性數據時發生錯誤: {e}")
        traceback.print_exc()

    print("--- cross_market_analyzer.py 測試結束 ---")
