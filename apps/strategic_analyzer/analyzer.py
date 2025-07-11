# -*- coding: utf-8 -*-
"""
普羅米修斯之火 - 戰略分析器核心

本模組定義了 StrategicAnalyzer 類別，用於將計算出的量化因子，
轉譯成直觀的「紅、黃、綠」燈信號，並提供相應的市場解讀。
"""
from __future__ import annotations # Ensure this is at the top
from typing import Optional, List, Any, Dict # Added Dict
import pandas as pd

# 稍後會需要 DBManager，先註釋掉，待 DBManager 路徑確認或傳入方式確定
# from apps.daily_market_analyzer.db_manager import DBManager


class StrategicAnalyzer:
    """
    戰略分析器核心類別。
    負責從資料庫讀取因子數據，根據預設規則生成紅黃綠信號，並產生解讀。
    """

    def __init__(self, db_manager: Any):
        """
        初始化戰略分析器。

        Args:
            db_manager: DBManager 的實例，用於數據庫操作。
        """
        self.db_manager = db_manager
        print("INFO: 戰略分析器 (StrategicAnalyzer) 初始化完畢。")

    def _get_latest_factor_value(
        self, factor_name: str, ticker: Optional[str] = None, date_offset: int = 0
    ) -> float | None:
        """
        從 FactorStore_Daily 獲取指定因子最近的值。
        """
        query = """
        SELECT factor_value
        FROM FactorStore_Daily
        WHERE factor_name = ?
        """
        params: List[Any] = [factor_name]

        if ticker:
            query += " AND ticker = ? "
            params.append(ticker)

        query += " ORDER BY date DESC LIMIT 1 OFFSET ?;"
        params.append(date_offset)

        try:
            result_df = self.db_manager.execute_query(query, params)
            if not result_df.empty:
                return float(result_df["factor_value"].iloc[0])
            else:
                return None
        except Exception as e:
            print(
                f"錯誤 (_get_latest_factor_value): 讀取因子 {factor_name} (Ticker: {ticker}) 失敗: {e}"
            )
            return None

    def _get_latest_market_price(
        self, ticker: str, date_offset: int = 0
    ) -> float | None:
        """
        從 MarketPrices_Daily 獲取指定 ticker 的最新收盤價。
        """
        query = """
        SELECT close
        FROM MarketPrices_Daily
        WHERE ticker = ? AND interval = '1d'
        ORDER BY datetime DESC
        LIMIT 1 OFFSET ?;
        """
        params: List[Any] = [ticker, date_offset]
        try:
            result_df = self.db_manager.execute_query(query, params)
            if not result_df.empty:
                return float(result_df["close"].iloc[0])
            else:
                return None
        except Exception as e:
            print(
                f"錯誤 (_get_latest_market_price): 讀取 Ticker {ticker} 收盤價失敗: {e}"
            )
            return None

    def _get_factor_series(
        self, factor_name: str, ticker: Optional[str] = None, limit: int = 20
    ) -> pd.Series:
        """
        從 FactorStore_Daily 獲取指定因子最近的一系列值。
        """
        query = """
        SELECT date, factor_value
        FROM FactorStore_Daily
        WHERE factor_name = ?
        """
        params: List[Any] = [factor_name]

        if ticker:
            query += " AND ticker = ? "
            params.append(ticker)

        query += " ORDER BY date DESC LIMIT ?;"
        params.append(limit)

        try:
            result_df = self.db_manager.execute_query(query, params)
            if not result_df.empty:
                result_df["date"] = pd.to_datetime(result_df["date"])
                return pd.Series(
                    result_df["factor_value"].values, index=result_df["date"]
                ).sort_index()
            else:
                return pd.Series(dtype=float)
        except Exception as e:
            print(
                f"錯誤 (_get_factor_series): 讀取因子系列 {factor_name} (Ticker: {ticker}) 失敗: {e}"
            )
            return pd.Series(dtype=float)

    def generate_daily_signals(
        self, analysis_date_str: Optional[str] = None
    ) -> pd.DataFrame:
        """
        生成每日的紅黃綠信號和解讀。
        """
        signals_data: List[Dict[str, Any]] = []
        current_analysis_date: Optional[pd.Timestamp] = None

        try:
            latest_date_df = self.db_manager.execute_query(
                "SELECT MAX(date) as max_date FROM FactorStore_Daily"
            )
            if (
                not latest_date_df.empty
                and latest_date_df["max_date"].iloc[0] is not None
            ):
                current_analysis_date = pd.to_datetime(
                    latest_date_df["max_date"].iloc[0]
                ).date()
                print(
                    f"INFO (StrategicAnalyzer): 自動設定分析日期為資料庫中最新因子日期: {current_analysis_date}"
                )
            else:
                latest_market_date_df = self.db_manager.execute_query(
                    "SELECT MAX(CAST(datetime AS DATE)) as max_date FROM MarketPrices_Daily WHERE interval = '1d'"
                )
                if (
                    not latest_market_date_df.empty
                    and latest_market_date_df["max_date"].iloc[0] is not None
                ):
                    current_analysis_date = pd.to_datetime(
                        latest_market_date_df["max_date"].iloc[0]
                    ).date()
                    print(
                        f"INFO (StrategicAnalyzer): 自動設定分析日期為資料庫中最新市場行情日期: {current_analysis_date}"
                    )
                else:
                    current_analysis_date = pd.Timestamp.now().date()
                    print(
                        f"警告 (StrategicAnalyzer): 無法從資料庫確定最新日期，使用當前系統日期: {current_analysis_date} 作為分析日期。"
                    )

            if analysis_date_str:
                current_analysis_date = pd.to_datetime(analysis_date_str).date()
                print(
                    f"INFO (StrategicAnalyzer): 使用指定分析日期: {current_analysis_date}"
                )

        except Exception as e:
            print(
                f"錯誤 (StrategicAnalyzer): 確定分析日期失敗: {e}。將使用當前系統日期。"
            )
            current_analysis_date = pd.Timestamp.now().date()

        if current_analysis_date is None:
            print("錯誤 (StrategicAnalyzer): 無法確定分析日期，終止信號生成。")
            return pd.DataFrame(
                columns=["date", "indicator_name", "signal", "value", "commentary"]
            )

        indicator_name_yc = "YIELD_CURVE_SLOPE"
        yc_signal = "YELLOW"
        yc_value: Optional[float] = None
        yc_commentary = "殖利率曲線斜率數據不足或計算失敗。"

        spread_10y_2y_value = self._get_latest_factor_value(
            factor_name="spread_10y_2y", ticker="US_TREASURY", date_offset=0
        )

        if spread_10y_2y_value is not None:
            value_in_percent = spread_10y_2y_value
            yc_value = value_in_percent * 100

            if value_in_percent < 0.0:
                yc_signal = "RED"
                yc_commentary = (
                    f"殖利率曲線倒掛 ({value_in_percent*10000:.2f} bps)。衰退風險上升。"
                )
            elif value_in_percent > 0.0025:
                yc_signal = "GREEN"
                yc_commentary = (
                    f"殖利率曲線陡峭 ({value_in_percent*10000:.2f} bps)。經濟前景健康。"
                )
            else:
                yc_signal = "YELLOW"
                yc_commentary = f"殖利率曲線平坦 ({value_in_percent*10000:.2f} bps)。經濟前景中性/需觀察。"
        else:
            print(
                f"警告 (StrategicAnalyzer): 未能獲取 {indicator_name_yc} 的因子數據 (spread_10y_2y)。"
            )

        signals_data.append(
            {
                "date": current_analysis_date,
                "indicator_name": indicator_name_yc,
                "signal": yc_signal,
                "value": yc_value,
                "commentary": yc_commentary,
            }
        )

        indicator_name_vix = "MARKET_VOLATILITY"
        vix_signal = "YELLOW"
        vix_value: Optional[float] = None
        vix_commentary = "市場恐慌指數 (VIX) 數據不足或計算失敗。"

        vix_close_value = self._get_latest_market_price(ticker="^VIX", date_offset=0)
        vix_value = vix_close_value

        if vix_close_value is not None:
            if vix_close_value > 30:
                vix_signal = "RED"
                vix_commentary = (
                    f"VIX 指數 ({vix_close_value:.2f}) > 30。市場極度恐慌。"
                )
            elif vix_close_value < 20:
                vix_signal = "GREEN"
                vix_commentary = (
                    f"VIX 指數 ({vix_close_value:.2f}) < 20。市場情緒樂觀/自滿。"
                )
            else:
                vix_signal = "YELLOW"
                vix_commentary = (
                    f"VIX 指數 ({vix_close_value:.2f}) 介於 20-30 之間。市場情緒警覺。"
                )
        else:
            print(
                f"警告 (StrategicAnalyzer): 未能獲取 {indicator_name_vix} 的數據 (^VIX 收盤價)。"
            )

        signals_data.append(
            {
                "date": current_analysis_date,
                "indicator_name": indicator_name_vix,
                "signal": vix_signal,
                "value": vix_value,
                "commentary": vix_commentary,
            }
        )

        indicator_name_credit = "CREDIT_RISK_APPETITE"
        credit_signal = "YELLOW"
        credit_value: Optional[float] = None
        credit_commentary = "信用風險偏好數據不足或計算失敗。"
        ma_period = 20

        credit_spread_series = self._get_factor_series(
            factor_name="HYG_LQD_price_ratio", ticker="CREDIT_SPREAD", limit=ma_period
        )

        if (
            not credit_spread_series.empty and len(credit_spread_series) >= 1
        ):
            latest_value = credit_spread_series.iloc[-1]
            credit_value = float(latest_value) if pd.notna(latest_value) else None

            if len(credit_spread_series) >= ma_period:
                ma_20 = credit_spread_series.rolling(window=ma_period).mean().iloc[-1]

                if pd.notna(latest_value) and pd.notna(ma_20):
                    if latest_value < ma_20:
                        credit_signal = "RED"
                        credit_commentary = f"信用利差代理 ({latest_value:.4f}) 低於其 {ma_period}日均線 ({ma_20:.4f})。避險情緒升溫。"
                    else:
                        credit_signal = "GREEN"
                        credit_commentary = f"信用利差代理 ({latest_value:.4f}) 高於或等於其 {ma_period}日均線 ({ma_20:.4f})。風險偏好良好。"
                else:
                    credit_commentary = f"信用風險偏好數據 (值: {latest_value if pd.notna(latest_value) else 'N/A'}, MA({ma_period}): {ma_20 if pd.notna(ma_20) else 'N/A'}) 不足以計算信號。"
                    print(
                        f"警告 (StrategicAnalyzer): {indicator_name_credit} 的最新值或MA({ma_period})為NaN。"
                    )
            else:
                credit_commentary = (
                    f"信用風險偏好數據不足 {ma_period} 日，無法計算 {ma_period}日均線。"
                )
                print(
                    f"警告 (StrategicAnalyzer): {indicator_name_credit} 的數據點 ({len(credit_spread_series)}) 不足 {ma_period} 個，無法計算移動平均。"
                )
        else:
            print(
                f"警告 (StrategicAnalyzer): 未能獲取 {indicator_name_credit} 的因子數據 (HYG_LQD_price_ratio)。"
            )

        signals_data.append(
            {
                "date": current_analysis_date,
                "indicator_name": indicator_name_credit,
                "signal": credit_signal,
                "value": credit_value,
                "commentary": credit_commentary,
            }
        )

        if not signals_data:
            print("警告 (StrategicAnalyzer): 未能生成任何信號數據。")
            return pd.DataFrame(
                columns=["date", "indicator_name", "signal", "value", "commentary"]
            )

        signals_df = pd.DataFrame(signals_data)
        if 'date' in signals_df.columns:
            signals_df['date'] = pd.to_datetime(signals_df['date'])
        return signals_df


if __name__ == "__main__":
    print("戰略分析器 (StrategicAnalyzer) 核心類別已定義。")
