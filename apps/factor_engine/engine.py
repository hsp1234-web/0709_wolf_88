# -*- coding: utf-8 -*-
"""
普羅米修斯之火 - 因子引擎核心

import numpy as np
import pandas as pd # 確保 pandas 已導入
import pandas_ta as ta # 確保 pandas_ta 已導入

from apps.daily_market_analyzer.db_manager import DBManager # 確保 DBManager 已導入，用於類型提示和潛在的獨立測試

# 本模組定義了 FactorEngine 類別，用於計算各種市場分析因子。
# """ # Docstring 格式修正

class FactorEngine:
    """
    因子引擎核心類別。
    負責從資料庫讀取市場數據，計算分析因子，並回傳結果。
    """
    def __init__(self, db_manager: 'DBManager'): # 添加類型提示
        """
        初始化因子引擎。

        Args:
            db_manager: DBManager 的實例，用於數據庫操作。
        """
        self.db_manager = db_manager

    def get_prices_for_ticker(self, ticker: str) -> 'pd.DataFrame': # 添加類型提示
        """
        從 MarketPrices_Daily 表格中讀取指定股票的完整 OHLCV 歷史數據。
        """
        try:
            # 我們預期 MarketPrices_Daily 只包含日線數據
            # FactorEngine 專注於日線級別的因子計算
            query = f"""
            SELECT datetime, open, high, low, close, volume
            FROM MarketPrices_Daily
            WHERE ticker = ?
            ORDER BY datetime ASC
            """
            result_df = self.db_manager.execute_query(query, params=[ticker])

            if not result_df.empty and 'datetime' in result_df.columns:
                result_df['datetime'] = pd.to_datetime(result_df['datetime'])
                if result_df['datetime'].dt.tz is None:
                    result_df['datetime'] = result_df['datetime'].dt.tz_localize('UTC')
                else:
                    result_df['datetime'] = result_df['datetime'].dt.tz_convert('UTC')
                result_df = result_df.set_index('datetime')

            result_df.columns = [col.lower() for col in result_df.columns]
            return result_df
        except Exception as e:
            print(f"錯誤 (FactorEngine): 讀取股票 {ticker} 的價格數據失敗: {e}")
            return pd.DataFrame()

    def calculate_price_volatility(self, dataframe: 'pd.DataFrame', n_days: int = 20) -> 'pd.Series | None':
        """
        計算價格的 N 日歷史波動率。
        """
        if dataframe.empty or 'close' not in dataframe.columns:
            print("警告 (FactorEngine): DataFrame 為空或缺少 'close' 欄位，無法計算價格波動率。")
            return None

        # 計算對數收益率
        # 確保 'close' 是 float 類型
        dataframe['log_return'] = np.log(dataframe['close'].astype(float) / dataframe['close'].astype(float).shift(1))

        # 計算 N 日滾動標準差
        price_volatility = dataframe['log_return'].rolling(window=n_days).std()

        return price_volatility

    def calculate_volume_volatility(self, dataframe: 'pd.DataFrame', n_days: int = 20) -> 'pd.Series | None':
        """
        計算成交量的 N 日歷史波動率。
        """
        if dataframe.empty or 'volume' not in dataframe.columns:
            print("警告 (FactorEngine): DataFrame 為空或缺少 'volume' 欄位，無法計算成交量波動率。")
            return None

        # 計算成交量變化率
        dataframe['volume_change_rate'] = dataframe['volume'].astype(float).pct_change(fill_method=None)

        # 處理 pct_change 可能產生的 inf/-inf (如果前一天是0，當天非0)
        dataframe.replace([np.inf, -np.inf], np.nan, inplace=True) # 將 inf 替換為 NaN

        # 計算 N 日滾動標準差
        volume_volatility = dataframe['volume_change_rate'].rolling(window=n_days).std()

        return volume_volatility

    def calculate_rsi(self, dataframe: 'pd.DataFrame', n_days: int = 14) -> 'pd.Series | None':
        """
        利用 pandas-ta 函式庫，計算 N 日相對強弱指數 (RSI)。
        """
        if dataframe.empty or 'close' not in dataframe.columns:
            print("警告 (FactorEngine): DataFrame 為空或缺少 'close' 欄位，無法計算 RSI。")
            return None

        if not isinstance(dataframe.index, pd.DatetimeIndex):
            print("警告 (FactorEngine): DataFrame 的索引不是 DatetimeIndex，pandas-ta 可能無法正確計算 RSI。")
            return None # 或者嘗試轉換，但更傾向於由調用者保證數據格式正確

        try:
            # pandas-ta 會自動尋找名為 'close' 的欄位
            rsi_series = dataframe.ta.rsi(length=n_days)
            return rsi_series
        except Exception as e:
            print(f"錯誤 (FactorEngine): 計算 RSI 失敗: {e}")
            return None

    def get_treasury_yields(self) -> 'pd.DataFrame': # 添加類型提示
        """
        從 TreasuryYields_Daily 表格中獲取所有期限的公債殖利率數據。
        將數據轉換為以 date 為索引，各期限殖利率為欄位的 DataFrame。
        """
        try:
            # 查詢 TreasuryYields_Daily 表格中的所有數據
            # 假設 'term' 欄位是文字描述 (例如 '10 Yr', '2 Yr', '3 Mo')
            # 假設 'yield' 欄位是殖利率數值
            # 假設 'date' 欄位是日期
            query = """
            SELECT date, term, yield
            FROM TreasuryYields_Daily
            ORDER BY date ASC, term ASC;
            """
            raw_yields_df = self.db_manager.execute_query(query)

            if raw_yields_df.empty:
                print("警告 (FactorEngine): TreasuryYields_Daily 表格中沒有數據。")
                return pd.DataFrame()

            # 將 'date' 欄位轉換為 datetime 物件
            raw_yields_df['date'] = pd.to_datetime(raw_yields_df['date'])
            # 確保 date 欄位是 UTC 時區，如果它還沒有時區信息
            if raw_yields_df['date'].dt.tz is None:
                raw_yields_df['date'] = raw_yields_df['date'].dt.tz_localize('UTC')
            else:
                raw_yields_df['date'] = raw_yields_df['date'].dt.tz_convert('UTC')


            # 將數據進行 pivot 操作，以 date 為索引，term 為欄位，yield 為值
            # 這需要確保 term 的值是乾淨且適合做欄位名的
            # 例如，將 '10 Yr' 轉換為 '10Y', '3 Mo' 轉換為 '3M'
            # 這裡我們假設 TreasuryYields_Daily 中的 term 已經是適合做欄位名的格式
            # 或者我們可以在這裡進行轉換
            # 為了與作戰計畫中的因子名稱 (spread_10y_2y, spread_10y_3m) 對應，
            # 我們預期欄位名應為 '10Y', '2Y', '3M' 等。
            # 這裡假設 TreasuryYields_Daily 中的 term 格式為 'X Yr' 或 'X Mo'
            def format_term(term_str):
                if 'Yr' in term_str:
                    return term_str.replace(' Yr', 'Y')
                elif 'Mo' in term_str:
                    return term_str.replace(' Mo', 'M')
                return term_str # 其他情況保持原樣

            raw_yields_df['term_formatted'] = raw_yields_df['term'].apply(format_term)

            yields_pivot_df = raw_yields_df.pivot_table(
                index='date',
                columns='term_formatted',
                values='yield'
            )

            # 確保欄位名符合預期 (例如 '10Y', '2Y', '3M')
            # 如果 pivot_table 後欄位名不符合預期，可能需要在此處進行調整
            # 例如，如果 TreasuryYields_Daily 中 term 的值是 '10 Year' 而不是 '10 Yr'
            # 則 format_term 函數需要相應調整，或者在此處重命名欄位

            print(f"INFO (FactorEngine): 成功從 TreasuryYields_Daily 讀取並轉換了 {len(yields_pivot_df)} 筆殖利率數據。")
            return yields_pivot_df

        except Exception as e:
            print(f"錯誤 (FactorEngine): 讀取公債殖利率數據失敗: {e}")
            # 返回一個空的 DataFrame 以避免後續操作出錯
            return pd.DataFrame()

    def calculate_yield_spreads(self, yields_dataframe: 'pd.DataFrame') -> 'pd.DataFrame':
        """
        計算殖利率曲線的關鍵利差。

        Args:
            yields_dataframe: 包含以日期為索引，不同期限殖利率為欄位的 DataFrame。
                              預期欄位名格式為 '10Y', '2Y', '3M' 等。

        Returns:
            一個包含計算出的利差的 DataFrame，索引為日期。
            欄位名為 'spread_10y_2y' 和 'spread_10y_3m'。
        """
        if yields_dataframe.empty:
            print("警告 (FactorEngine): 殖利率數據為空，無法計算利差。")
            return pd.DataFrame()

        spreads_df = pd.DataFrame(index=yields_dataframe.index)
        calculation_successful = False

        # 計算 10年期與2年期公債利差 (spread_10y_2y)
        if '10Y' in yields_dataframe.columns and '2Y' in yields_dataframe.columns:
            # 確保數據是數值類型，非數值轉為 NaN
            yield_10y = pd.to_numeric(yields_dataframe['10Y'], errors='coerce')
            yield_2y = pd.to_numeric(yields_dataframe['2Y'], errors='coerce')
            spreads_df['spread_10y_2y'] = yield_10y - yield_2y
            calculation_successful = True
            print("INFO (FactorEngine): 已計算 spread_10y_2y。")
        else:
            print("警告 (FactorEngine): 缺少 '10Y' 或 '2Y' 殖利率數據，無法計算 spread_10y_2y。")
            # 即使無法計算，也創建一個全為 NaN 的欄位，以保持 DataFrame 結構一致性
            if 'spread_10y_2y' not in spreads_df.columns:
                 spreads_df['spread_10y_2y'] = np.nan


        # 計算 10年期與3個月期公債利差 (spread_10y_3m)
        if '10Y' in yields_dataframe.columns and '3M' in yields_dataframe.columns:
            yield_10y = pd.to_numeric(yields_dataframe['10Y'], errors='coerce')
            yield_3m = pd.to_numeric(yields_dataframe['3M'], errors='coerce')
            spreads_df['spread_10y_3m'] = yield_10y - yield_3m
            calculation_successful = True
            print("INFO (FactorEngine): 已計算 spread_10y_3m。")
        else:
            print("警告 (FactorEngine): 缺少 '10Y' 或 '3M' 殖利率數據，無法計算 spread_10y_3m。")
            if 'spread_10y_3m' not in spreads_df.columns:
                spreads_df['spread_10y_3m'] = np.nan

        if not calculation_successful and not yields_dataframe.empty:
            print("警告 (FactorEngine): 未能成功計算任何利差，因為缺少必要的殖利率期限數據。")
            # 如果一個都沒算成功，但輸入不為空，返回的 DataFrame 至少有索引和全 NaN 的列
        elif yields_dataframe.empty: # 這個條件其實在函數開頭已經處理了
            pass # 已在開頭處理
        else:
            print(f"INFO (FactorEngine): 成功計算了 {len(spreads_df.dropna(how='all'))} 筆利差數據。")

        # 移除完全是 NaT/NaN 的列 (如果有的話，比如所有利差都沒算成功)
        # 但我們希望即使計算失敗，欄位也存在，所以不移除
        # spreads_df.dropna(axis=1, how='all', inplace=True)

        return spreads_df

    def calculate_credit_spread_proxy(self) -> 'pd.DataFrame':
        """
        計算信用利差的代理指標。
        目前實現為 HYG (高收益債ETF) 相對於 LQD (投資級公司債ETF) 的價格比率。
        未來可以擴展到計算收益率利差。

        Returns:
            一個包含 'HYG_LQD_price_ratio' 的 DataFrame，索引為日期。
        """
        proxy_df = pd.DataFrame()
        hyg_ticker = 'HYG'
        lqd_ticker = 'LQD'

        print(f"INFO (FactorEngine): 開始計算信用利差代理指標 (HYG/LQD 價格比率)...")

        # 1. 讀取 HYG 的價格數據
        hyg_prices_df = self.get_prices_for_ticker(hyg_ticker)
        if hyg_prices_df.empty or 'close' not in hyg_prices_df.columns:
            print(f"警告 (FactorEngine): 未能獲取 {hyg_ticker} 的收盤價數據，無法計算信用利差代理。")
            return pd.DataFrame()
        # 我們只需要 'close' 價格，並重命名以避免合併時衝突
        hyg_close = hyg_prices_df[['close']].rename(columns={'close': 'hyg_close'})

        # 2. 讀取 LQD 的價格數據
        lqd_prices_df = self.get_prices_for_ticker(lqd_ticker)
        if lqd_prices_df.empty or 'close' not in lqd_prices_df.columns:
            print(f"警告 (FactorEngine): 未能獲取 {lqd_ticker} 的收盤價數據，無法計算信用利差代理。")
            return pd.DataFrame()
        lqd_close = lqd_prices_df[['close']].rename(columns={'close': 'lqd_close'})

        # 3. 合併兩種價格數據
        # 使用外連接 (outer join) 保留所有日期，然後處理 NaN (儘管對於價格比率，內連接 inner join 更合適)
        # 由於我們需要兩個價格都存在才能計算比率，所以使用內連接 (inner join)
        merged_prices = pd.merge(hyg_close, lqd_close, left_index=True, right_index=True, how='inner')

        if merged_prices.empty:
            print(f"警告 (FactorEngine): {hyg_ticker} 和 {lqd_ticker} 沒有共同的交易日期，無法計算價格比率。")
            return pd.DataFrame()

        # 4. 計算價格比率
        # 確保分母不為零且數據為數值型
        merged_prices['hyg_close'] = pd.to_numeric(merged_prices['hyg_close'], errors='coerce')
        merged_prices['lqd_close'] = pd.to_numeric(merged_prices['lqd_close'], errors='coerce')

        # 處理 LQD 收盤價可能為0或NaN的情況
        # 如果 lqd_close 是 NaN 或者 0，則比率結果為 NaN
        proxy_df['HYG_LQD_price_ratio'] = merged_prices['hyg_close'] / merged_prices['lqd_close'].replace(0, np.nan)

        # 移除完全是 NaN 的行 (如果 hyg_close 或 lqd_close 轉換後是 NaN)
        proxy_df.dropna(subset=['HYG_LQD_price_ratio'], inplace=True)

        if proxy_df.empty:
            print(f"警告 (FactorEngine): 計算出的 HYG/LQD 價格比率數據為空 (可能因為價格為零或非數值)。")
            return pd.DataFrame()

        print(f"INFO (FactorEngine): 成功計算了 {len(proxy_df)} 筆 HYG/LQD 價格比率數據。")
        return proxy_df


if __name__ == '__main__':
    # 此處可以添加一些用於測試 FactorEngine 的代碼
    print("因子引擎 (FactorEngine) 已定義。")
