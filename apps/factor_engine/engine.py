from __future__ import annotations

# -*- coding: utf-8 -*-
"""
普羅米修斯之火 - 因子引擎核心
"""
# 標準庫導入 (如果有的話，例如 import os, sys)
# (空一行)
# 第三方庫導入
import numpy as np
import pandas as pd
# import pandas_ta as ta # Pandas TA 通过 accessor (df.ta) 使用，通常不需要在此直接导入

# (空一行)
# 本地應用/庫導入
from apps.daily_market_analyzer.db_manager import DBManager

# 本模組定義了 FactorEngine 類別，用於計算各種市場分析因子。

class FactorEngine:
    """
    因子引擎核心類別。
    負責從資料庫讀取市場數據，計算分析因子，並回傳結果。
    """
    def __init__(self, db_manager: DBManager):
        """
        初始化因子引擎。

        Args:
            db_manager: DBManager 的實例，用於數據庫操作。
        """
        self.db_manager = db_manager

    def get_prices_for_ticker(self, ticker: str) -> pd.DataFrame:
        """
        從 MarketPrices_Daily 表格中讀取指定股票的完整 OHLCV 歷史數據。
        """
        try:
            query = """
            SELECT datetime, open, high, low, close, volume
            FROM MarketPrices_Daily
            WHERE ticker = ?
            ORDER BY datetime ASC
            """
            result_df = self.db_manager.execute_query(query, params=[ticker])

            if not result_df.empty and "datetime" in result_df.columns:
                result_df["datetime"] = pd.to_datetime(result_df["datetime"])
                if result_df["datetime"].dt.tz is None:
                    result_df["datetime"] = result_df["datetime"].dt.tz_localize("UTC")
                else:
                    result_df["datetime"] = result_df["datetime"].dt.tz_convert("UTC")
                result_df = result_df.set_index("datetime")

            result_df.columns = [col.lower() for col in result_df.columns]
            return result_df
        except Exception as e:
            print(f"錯誤 (FactorEngine): 讀取股票 {ticker} 的價格數據失敗: {e}")
            return pd.DataFrame()

    def calculate_price_volatility(
        self, dataframe: pd.DataFrame, n_days: int = 20
    ) -> pd.Series | None:
        if dataframe.empty or "close" not in dataframe.columns:
            print(
                "警告 (FactorEngine): DataFrame 為空或缺少 'close' 欄位，無法計算價格波動率。"
            )
            return None
        dataframe["log_return"] = np.log(
            dataframe["close"].astype(float) / dataframe["close"].astype(float).shift(1)
        )
        price_volatility = dataframe["log_return"].rolling(window=n_days).std()
        return price_volatility

    def calculate_volume_volatility(
        self, dataframe: pd.DataFrame, n_days: int = 20
    ) -> pd.Series | None:
        if dataframe.empty or "volume" not in dataframe.columns:
            print(
                "警告 (FactorEngine): DataFrame 為空或缺少 'volume' 欄位，無法計算成交量波動率。"
            )
            return None
        dataframe["volume_change_rate"] = (
            dataframe["volume"].astype(float).pct_change(fill_method=None)
        )
        dataframe.replace([np.inf, -np.inf], np.nan, inplace=True)
        volume_volatility = dataframe["volume_change_rate"].rolling(window=n_days).std()
        return volume_volatility

    def calculate_rsi(
        self, dataframe: pd.DataFrame, n_days: int = 14
    ) -> pd.Series | None:
        if dataframe.empty or "close" not in dataframe.columns:
            print("警告 (FactorEngine): DataFrame 為空或缺少 'close' 欄位，無法計算 RSI。")
            return None
        if not isinstance(dataframe.index, pd.DatetimeIndex):
            print(
                "警告 (FactorEngine): DataFrame 的索引不是 DatetimeIndex，pandas-ta 可能無法正確計算 RSI。"
            )
            return None
        try:
            if not hasattr(dataframe, "ta"):
                print(
                    "錯誤 (FactorEngine): DataFrame 缺少 'ta' 擴展。Pandas TA 可能未正確加載或與 Pandas 版本不兼容。"
                )
                return None
            # pandas_ta 需要在環境中被安裝，即使這裡沒有顯式 import pandas_ta as ta
            rsi_series = dataframe.ta.rsi(length=n_days)
            return rsi_series
        except Exception as e:
            print(f"錯誤 (FactorEngine): 計算 RSI 失敗: {e}")
            return None

    def get_treasury_yields(self) -> pd.DataFrame:
        try:
            query = """
            SELECT date, term, yield
            FROM TreasuryYields_Daily
            ORDER BY date ASC, term ASC;
            """
            raw_yields_df = self.db_manager.execute_query(query)
            if raw_yields_df.empty:
                print("警告 (FactorEngine): TreasuryYields_Daily 表格中沒有數據。")
                return pd.DataFrame()
            raw_yields_df["date"] = pd.to_datetime(raw_yields_df["date"])
            if raw_yields_df["date"].dt.tz is None:
                raw_yields_df["date"] = raw_yields_df["date"].dt.tz_localize("UTC")
            else:
                raw_yields_df["date"] = raw_yields_df["date"].dt.tz_convert("UTC")
            def format_term(term_str):
                if "Yr" in term_str:
                    return term_str.replace(" Yr", "Y")
                elif "Mo" in term_str:
                    return term_str.replace(" Mo", "M")
                return term_str
            raw_yields_df["term_formatted"] = raw_yields_df["term"].apply(format_term)
            yields_pivot_df = raw_yields_df.pivot_table(
                index="date", columns="term_formatted", values="yield"
            )
            print(
                f"INFO (FactorEngine): 成功從 TreasuryYields_Daily 讀取並轉換了 {len(yields_pivot_df)} 筆殖利率數據。"
            )
            return yields_pivot_df
        except Exception as e:
            print(f"錯誤 (FactorEngine): 讀取公債殖利率數據失敗: {e}")
            return pd.DataFrame()

    def calculate_yield_spreads(
        self, yields_dataframe: pd.DataFrame
    ) -> pd.DataFrame:
        if yields_dataframe.empty:
            print("警告 (FactorEngine): 殖利率數據為空，無法計算利差。")
            return pd.DataFrame()
        spreads_df = pd.DataFrame(index=yields_dataframe.index)
        calculation_successful = False
        if "10Y" in yields_dataframe.columns and "2Y" in yields_dataframe.columns:
            yield_10y = pd.to_numeric(yields_dataframe["10Y"], errors="coerce")
            yield_2y = pd.to_numeric(yields_dataframe["2Y"], errors="coerce")
            spreads_df["spread_10y_2y"] = yield_10y - yield_2y
            calculation_successful = True
            print("INFO (FactorEngine): 已計算 spread_10y_2y。")
        else:
            print(
                "警告 (FactorEngine): 缺少 '10Y' 或 '2Y' 殖利率數據，無法計算 spread_10y_2y。"
            )
            if "spread_10y_2y" not in spreads_df.columns:
                spreads_df["spread_10y_2y"] = np.nan
        if "10Y" in yields_dataframe.columns and "3M" in yields_dataframe.columns:
            yield_10y = pd.to_numeric(yields_dataframe["10Y"], errors="coerce")
            yield_3m = pd.to_numeric(yields_dataframe["3M"], errors="coerce")
            spreads_df["spread_10y_3m"] = yield_10y - yield_3m
            calculation_successful = True
            print("INFO (FactorEngine): 已計算 spread_10y_3m。")
        else:
            print(
                "警告 (FactorEngine): 缺少 '10Y' 或 '3M' 殖利率數據，無法計算 spread_10y_3m。"
            )
            if "spread_10y_3m" not in spreads_df.columns:
                spreads_df["spread_10y_3m"] = np.nan
        if not calculation_successful and not yields_dataframe.empty:
            print(
                "警告 (FactorEngine): 未能成功計算任何利差，因為缺少必要的殖利率期限數據。"
            )
        elif calculation_successful:
            print(
                f"INFO (FactorEngine): 成功計算了 {len(spreads_df.dropna(how='all'))} 筆利差數據。"
            )
        return spreads_df

    def calculate_credit_spread_proxy(self) -> pd.DataFrame:
        proxy_df = pd.DataFrame()
        hyg_ticker = "HYG"
        lqd_ticker = "LQD"
        print("INFO (FactorEngine): 開始計算信用利差代理指標 (HYG/LQD 價格比率)...")
        hyg_prices_df = self.get_prices_for_ticker(hyg_ticker)
        if hyg_prices_df.empty or "close" not in hyg_prices_df.columns:
            print(f"警告 (FactorEngine): 未能獲取 {hyg_ticker} 的收盤價數據。")
            return pd.DataFrame()
        hyg_close = hyg_prices_df[["close"]].rename(columns={"close": "hyg_close"})
        lqd_prices_df = self.get_prices_for_ticker(lqd_ticker)
        if lqd_prices_df.empty or "close" not in lqd_prices_df.columns:
            print(f"警告 (FactorEngine): 未能獲取 {lqd_ticker} 的收盤價數據。")
            return pd.DataFrame()
        lqd_close = lqd_prices_df[["close"]].rename(columns={"close": "lqd_close"})
        merged_prices = pd.merge(
            hyg_close, lqd_close, left_index=True, right_index=True, how="inner"
        )
        if merged_prices.empty:
            print(
                f"警告 (FactorEngine): {hyg_ticker} 和 {lqd_ticker} 沒有共同交易日期。"
            )
            return pd.DataFrame()
        merged_prices["hyg_close"] = pd.to_numeric(
            merged_prices["hyg_close"], errors="coerce"
        )
        merged_prices["lqd_close"] = pd.to_numeric(
            merged_prices["lqd_close"], errors="coerce"
        )
        proxy_df["HYG_LQD_price_ratio"] = merged_prices["hyg_close"] / merged_prices[
            "lqd_close"
        ].replace(0, np.nan)
        proxy_df.dropna(subset=["HYG_LQD_price_ratio"], inplace=True)
        if proxy_df.empty:
            print("警告 (FactorEngine): 計算出的 HYG/LQD 價格比率數據為空。")
            return pd.DataFrame()
        print(
            f"INFO (FactorEngine): 成功計算了 {len(proxy_df)} 筆 HYG/LQD 價格比率數據。"
        )
        return proxy_df

if __name__ == "__main__":
    print("因子引擎 (FactorEngine) 已定義。")
