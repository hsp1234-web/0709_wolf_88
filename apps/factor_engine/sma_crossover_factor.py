# In apps/factor_engine/sma_crossover_factor.py
import pandas as pd
from core.analysis.data_engine import DataEngine
from core.config import config

def calculate_sma_crossover(ticker: str = 'spy', start_date: str = '2025-06-01', end_date: str = '2025-07-11', short_window: int = 20, long_window: int = 50):
    """
    計算並回傳指定標的在給定時間範圍內的雙移動平均線交叉信號。

    核心邏輯:
    1. 初始化 DataEngine。
    2. 透過 DataEngine 獲取所需時間範圍內的小時級收盤價。
       (這將自動利用我們的 DuckDB 快取)。
    3. 使用 Pandas 計算短期和長期 SMA。
    4. 產生交叉信號 (+1: 黃金交叉, -1: 死亡交叉)。
    5. 回傳一個包含所有計算結果的 DataFrame。
    """
    print(f"--- 開始計算 {ticker.upper()} 的 {short_window}H/{long_window}H SMA 交叉因子 ---")

    # 步驟 1: 初始化
    from core.clients.yfinance import YFinanceClient
    from core.clients.fred import FredClient
    from core.clients.taifex_db import TaifexDBClient

    yf_client = YFinanceClient()
    fred_client = FredClient(api_key=config.get("api_keys.fred"))
    taifex_client = TaifexDBClient()
    engine = DataEngine(yf_client=yf_client, fred_client=fred_client, taifex_client=taifex_client)

    # 步驟 2: 獲取數據 (此處需要 DataEngine 新增一個能獲取時間序列的方法)
    # 假設 DataEngine 已被擴充，擁有 get_hourly_series 方法
    price_series = engine.get_hourly_series(ticker, 'close', start_date, end_date)
    if price_series is None or price_series.empty:
        print(f"無法獲取 {ticker} 的數據。")
        engine.close()
        return None

    # 步驟 3: 計算 SMA
    result_df = price_series.to_frame(name=f'{ticker}_close')
    result_df['short_sma'] = result_df[f'{ticker}_close'].rolling(window=short_window).mean()
    result_df['long_sma'] = result_df[f'{ticker}_close'].rolling(window=long_window).mean()

    # 步驟 4: 產生信號
    # 當短期均線 > 長期均線，我們標記為 1 (多頭)
    result_df['position'] = 0
    result_df.loc[result_df['short_sma'] > result_df['long_sma'], 'position'] = 1
    # 產生交叉信號，當倉位發生變化時記錄
    result_df['signal'] = result_df['position'].diff()

    engine.close()
    print("--- 因子計算完成 ---")
    return result_df

if __name__ == '__main__':
    # 為了可獨立執行與測試
    factor_result = calculate_sma_crossover()
    if factor_result is not None:
        print("計算結果預覽：")
        # 僅顯示有信號的時刻
        print(factor_result[factor_result['signal'] != 0].tail())
