# -*- coding: utf-8 -*-
"""
普羅米修斯之火 - 因子引擎核心

import numpy as np
import pandas as pd # 確保 pandas 已導入
import pandas_ta as ta # 確保 pandas_ta 已導入

# 修正：將 DBManager 的導入移到 __main__ 區塊之外，或者在需要時才導入
# from apps.daily_market_analyzer.db_manager import DBManager
# 由於 FactorEngine 在初始化時接收 db_manager 實例，所以這裡不需要直接導入 DBManager
# 除非有類型提示的需求，但運行時不需要。

本模組定義了 FactorEngine 類別，用於計算各種市場分析因子。
"""

class FactorEngine:
    """
    因子引擎核心類別。
    負責從資料庫讀取市場數據，計算分析因子，並回傳結果。
    """
    def __init__(self, db_manager):
        """
        初始化因子引擎。

        Args:
            db_manager: DBManager 的實例，用於數據庫操作。
        """
        self.db_manager = db_manager

    def get_prices_for_ticker(self, ticker):
        """
        從 MarketPrices_Daily 表格中讀取指定股票的完整 OHLCV 歷史數據。
        （此方法將在後續步驟中實現）
        """
        """
        try:
            # 我們預期 MarketPrices_Daily 只包含日線數據，但明確指定 interval = '1d' 更為穩妥
            # FactorEngine 專注於日線級別的因子計算
            query = f"""
            SELECT datetime, open, high, low, close, volume
            FROM MarketPrices_Daily
            WHERE ticker = ?
            ORDER BY datetime ASC
            """
            # DBManager 實例是 self.db_manager
            result_df = self.db_manager.execute_query(query, params=[ticker])

            if not result_df.empty and 'datetime' in result_df.columns:
                result_df['datetime'] = pd.to_datetime(result_df['datetime'])
                # 確保 datetime 欄位是 UTC 時區，與 DBManager 中其他查詢保持一致
                if result_df['datetime'].dt.tz is None:
                    result_df['datetime'] = result_df['datetime'].dt.tz_localize('UTC')
                else:
                    result_df['datetime'] = result_df['datetime'].dt.tz_convert('UTC')
                # 將 datetime 設置為索引，方便後續 pandas-ta 等函式庫使用
                result_df = result_df.set_index('datetime')

            # 因子計算通常需要 Open, High, Low, Close, Volume
            # 表格欄位名與 yfinance 下載時一致，通常是首字母大寫
            # 查詢時已選取所需欄位，但 pandas-ta 可能對欄位名大小寫敏感，統一為小寫
            result_df.columns = [col.lower() for col in result_df.columns]

            return result_df
        except Exception as e:
            print(f"錯誤 (FactorEngine): 讀取股票 {ticker} 的價格數據失敗: {e}")
            return pd.DataFrame()

    def calculate_price_volatility(self, dataframe, n_days=20):
        """
        計算價格的 N 日歷史波動率。
        （此方法將在後續步驟中實現）
        """
        if dataframe.empty or 'close' not in dataframe.columns:
            print("警告 (FactorEngine): DataFrame 為空或缺少 'close' 欄位，無法計算價格波動率。")
            return None

        # 計算對數收益率
        # 確保 'close' 是 float 類型
        dataframe['log_return'] = np.log(dataframe['close'].astype(float) / dataframe['close'].astype(float).shift(1))

        # 計算 N 日滾動標準差
        price_volatility = dataframe['log_return'].rolling(window=n_days).std()

        # 年化波動率 (假設一年有 252 個交易日)
        # 因子通常不需要年化，而是直接使用 N 日的原始值，這裡我們計算 N 日波動率
        # price_volatility_annualized = price_volatility * np.sqrt(252)

        return price_volatility

    def calculate_volume_volatility(self, dataframe, n_days=20):
        """
        計算成交量的 N 日歷史波動率。
        （此方法將在後續步驟中實現）
        """
        if dataframe.empty or 'volume' not in dataframe.columns:
            print("警告 (FactorEngine): DataFrame 為空或缺少 'volume' 欄位，無法計算成交量波動率。")
            return None

        # 計算成交量變化率，處理分母為0的情況
        # 避免 dataframe['volume'].shift(1) 為 0 的情況
        prev_volume = dataframe['volume'].shift(1)
        # 當 prev_volume 為 0 時，變化率設為 0 (或者 np.nan，然後再處理)
        # 這裡我們假設如果前一天成交量為0，當天成交量變化率也為0 (或者是一個很大的數，如果當天成交量非0)
        # 一個更穩健的做法可能是將成交量+1來避免log(0)或除以0，但這裡我們先計算簡單變化率
        dataframe['volume_change_rate'] = dataframe['volume'].astype(float).pct_change(fill_method=None)

        # 處理 pct_change 可能產生的 inf/-inf (如果前一天是0，當天非0)
        dataframe.replace([np.inf, -np.inf], np.nan, inplace=True) # 將 inf 替換為 NaN

        # 計算 N 日滾動標準差
        volume_volatility = dataframe['volume_change_rate'].rolling(window=n_days).std()

        return volume_volatility

    def calculate_rsi(self, dataframe, n_days=14):
        """
        利用 pandas-ta 函式庫，計算 N 日相對強弱指數 (RSI)。
        （此方法將在後續步驟中實現）
        """
        if dataframe.empty or 'close' not in dataframe.columns:
            print("警告 (FactorEngine): DataFrame 為空或缺少 'close' 欄位，無法計算 RSI。")
            return None

        if not isinstance(dataframe.index, pd.DatetimeIndex):
            print("警告 (FactorEngine): DataFrame 的索引不是 DatetimeIndex，pandas-ta 可能無法正確計算 RSI。")
            # 可以嘗試轉換，但最好由上游保證
            # dataframe.index = pd.to_datetime(dataframe.index)

        try:
            # pandas-ta 會自動尋找名為 'close' 的欄位
            # 結果會是一個 Series，欄位名通常是 'RSI_n_days'，例如 'RSI_14'
            rsi_series = dataframe.ta.rsi(length=n_days)
            return rsi_series
        except Exception as e:
            print(f"錯誤 (FactorEngine): 計算 RSI 失敗: {e}")
            return None

if __name__ == '__main__':
    # 此處可以添加一些用於測試 FactorEngine 的代碼
    print("因子引擎 (FactorEngine) 已定義。")
