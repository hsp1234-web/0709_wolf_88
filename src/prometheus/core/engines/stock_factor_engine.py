# src/prometheus/core/engines/stock_factor_engine.py

import pandas as pd
import logging
from typing import Dict, Any, List

from src.prometheus.core.analyzers.base_analyzer import BaseAnalyzer
from src.prometheus.core.clients.client_factory import ClientFactory

logger = logging.getLogger(__name__)


class StockFactorEngine(BaseAnalyzer):
    """
    股票因子引擎，專門計算與個股相關的財務因子。
    """

    def __init__(self, client_factory: ClientFactory):
        """
        初始化股票因子引擎。

        :param client_factory: 客戶端工廠，用於獲取 yfinance 和 FinMind 的客戶端。
        """
        super().__init__(analyzer_name="StockFactorEngine")
        self.client_factory = client_factory
        self.yfinance_client = self.client_factory.get_client('yfinance')
        self.finmind_client = self.client_factory.get_client('finmind')

    def _load_data(self) -> pd.DataFrame:
        """
        此方法在此引擎中不使用，因為數據由 Pipeline 提供。
        """
        self.logger.debug("StockFactorEngine._load_data called, but not used in pipeline context.")
        return pd.DataFrame()

    def _perform_analysis(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        此方法被 run 方法覆蓋，因此不會被直接調用。
        """
        self.logger.debug("StockFactorEngine._perform_analysis called, but logic is in run.")
        return data

    def _save_results(self, results: pd.DataFrame) -> None:
        """
        此方法在此引擎中不使用，因為結果由 Pipeline 保存。
        """
        self.logger.debug("StockFactorEngine._save_results called, but not used in pipeline context.")
        pass

    async def run(self, data: pd.DataFrame, config: Dict[str, Any] = None) -> pd.DataFrame:
        """
        執行因子計算。

        :param data: 包含股票價格數據的 DataFrame，索引為日期，應包含 'symbol' 欄位。
        :param config: 可選的配置字典。
        :return: 包含新計算因子的 DataFrame。
        """
        if 'symbol' not in data.columns:
            raise ValueError("輸入的 DataFrame 必須包含 'symbol' 欄位。")

        # 複製數據以避免修改原始 DataFrame
        result_df = data.copy()

        # 計算基本面因子
        result_df = await self._calculate_fundamental_factors(result_df)

        # 計算技術面因子 (如果需要)
        # ...

        return result_df

    async def _calculate_fundamental_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        計算並合併所有基本面因子。
        """
        symbol = df['symbol'].iloc[0]
        self.logger.info(f"開始為股票 {symbol} 計算基本面因子...")

        # 獲取 yfinance 的 ticker 物件
        ticker = self.yfinance_client.get_ticker(symbol)

        # 計算本益比 (P/E Ratio)
        pe_ratio = self._calculate_pe_ratio(ticker)
        df['factor_pe_ratio'] = pe_ratio

        # 計算股價淨值比 (P/B Ratio)
        pb_ratio = self._calculate_pb_ratio(ticker)
        df['factor_pb_ratio'] = pb_ratio

        # 計算月營收年增率 (僅限台股)
        if '.TW' in symbol:
            df = await self._calculate_monthly_revenue_yoy(df, symbol)
        else:
            df['factor_monthly_revenue_yoy'] = None


        self.logger.info(f"股票 {symbol} 的基本面因子計算完成。")
        return df

    def _calculate_pe_ratio(self, ticker: Any) -> float | None:
        """
        使用 yfinance.info 獲取 P/E Ratio (TTM)。
        """
        try:
            # TTM = Trailing Twelve Months
            pe = ticker.info.get('trailingPE')
            self.logger.debug(f"成功獲取 P/E Ratio: {pe}")
            return pe
        except Exception as e:
            self.logger.warning(f"無法獲取 P/E Ratio: {e}")
            return None

    def _calculate_pb_ratio(self, ticker: Any) -> float | None:
        """
        使用 yfinance.info 獲取 P/B Ratio。
        """
        try:
            pb = ticker.info.get('priceToBook')
            self.logger.debug(f"成功獲取 P/B Ratio: {pb}")
            return pb
        except Exception as e:
            self.logger.warning(f"無法獲取 P/B Ratio: {e}")
            return None

    async def _calculate_monthly_revenue_yoy(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        計算台股的月營收年增率 (YoY)。
        """
        stock_id = symbol.replace('.TW', '')
        # 我們只需要最新的日期來獲取對應月份的營收
        latest_date = pd.to_datetime(df.index.max(), unit='ns')

        try:
            # 使用 FinMind 客戶端獲取月營收數據
            revenue_data = await self.finmind_client.get_monthly_revenue(stock_id, latest_date.year - 2, latest_date.month)
            if revenue_data.empty:
                self.logger.warning(f"股票 {symbol} 在 {latest_date} 附近無月營收數據。")
                df['factor_monthly_revenue_yoy'] = None
                return df

            # 將營收數據的日期設為索引
            revenue_data['date'] = pd.to_datetime(revenue_data['date'])
            revenue_data.set_index('date', inplace=True)

            # 計算年增率
            # 找到與 df 中每個日期對應的月份
            df['year'] = df.index.year
            df['month'] = df.index.month

            def get_revenue_yoy(row):
                current_month_revenue = revenue_data[
                    (revenue_data.index.year == row['year']) &
                    (revenue_data.index.month == row['month'])
                ]

                last_year_month_revenue = revenue_data[
                    (revenue_data.index.year == row['year'] - 1) &
                    (revenue_data.index.month == row['month'])
                ]

                if not current_month_revenue.empty and not last_year_month_revenue.empty:
                    current_revenue = current_month_revenue['revenue'].iloc[0]
                    last_year_revenue = last_year_month_revenue['revenue'].iloc[0]
                    if last_year_revenue != 0:
                        return (current_revenue - last_year_revenue) / last_year_revenue
                return None

            df['factor_monthly_revenue_yoy'] = df.apply(get_revenue_yoy, axis=1)
            df.drop(columns=['year', 'month'], inplace=True)

            self.logger.debug(f"成功計算股票 {symbol} 的月營收年增率。")

        except Exception as e:
            self.logger.error(f"計算股票 {symbol} 的月營收年增率時出錯: {e}")
            df['factor_monthly_revenue_yoy'] = None

        return df
