# src/prometheus/core/engines/crypto_factor_engine.py

import pandas as pd
import logging
from typing import Dict, Any

from src.prometheus.core.analyzers.base_analyzer import BaseAnalyzer
from src.prometheus.core.clients.client_factory import ClientFactory


logger = logging.getLogger(__name__)


class CryptoFactorEngine(BaseAnalyzer):
    """
    加密貨幣因子引擎，專門計算與加密貨幣相關的因子。
    """

    def __init__(self, client_factory: ClientFactory):
        """
        初始化加密貨幣因子引擎。
        """
        super().__init__(analyzer_name="CryptoFactorEngine")
        self.client_factory = client_factory
        self.yfinance_client = self.client_factory.get_client('yfinance')

    def _load_data(self) -> pd.DataFrame:
        """
        此方法在此引擎中不使用，因為數據由 Pipeline 提供。
        """
        self.logger.debug("CryptoFactorEngine._load_data called, but not used in pipeline context.")
        return pd.DataFrame()

    def _perform_analysis(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        此方法被 run 方法覆蓋，因此不會被直接調用。
        """
        self.logger.debug("CryptoFactorEngine._perform_analysis called, but logic is in run.")
        return data

    def _save_results(self, results: pd.DataFrame) -> None:
        """
        此方法在此引擎中不使用，因為結果由 Pipeline 保存。
        """
        self.logger.debug("CryptoFactorEngine._save_results called, but not used in pipeline context.")
        pass

    async def run(self, data: pd.DataFrame, config: Dict[str, Any] = None) -> pd.DataFrame:
        """
        執行因子計算。

        :param data: 包含加密貨幣價格數據的 DataFrame，索引為日期，應包含 'symbol' 欄位。
        :param config: 可選的配置字典。
        :return: 包含新計算因子的 DataFrame。
        """
        if 'symbol' not in data.columns:
            raise ValueError("輸入的 DataFrame 必須包含 'symbol' 欄位。")

        symbol = data['symbol'].iloc[0]
        self.logger.info(f"開始為加密貨幣 {symbol} 計算因子...")

        # 複製數據以避免修改原始 DataFrame
        result_df = data.copy()

        # 計算與納斯達克指數的相關性
        result_df = await self._calculate_nasdaq_correlation(result_df)

        # 計算恐懼與貪婪指數代理
        result_df = self._calculate_fear_greed_proxy(result_df)

        self.logger.info(f"加密貨幣 {symbol} 的因子計算完成。")
        return result_df

    async def _calculate_nasdaq_correlation(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        計算與納斯達克100指數期貨 (NQ=F) 的 30 日滾動相關性。
        """
        self.logger.debug("正在計算與納斯達克指數的相關性...")
        try:
            # 獲取 NQ=F 的數據
            start_date = df.index.min()
            end_date = df.index.max()
            nasdaq_data = await self.yfinance_client.fetch_data('NQ=F', start_date=start_date, end_date=end_date)
            if nasdaq_data is None or nasdaq_data.empty:
                self.logger.warning("無法獲取納斯達克數據 (NQ=F)，跳過相關性計算。")
                df['factor_corr_nq'] = None
                return df

            # 確保兩個 DataFrame 的索引都是日期時間類型且沒有重複
            df.index = pd.to_datetime(df.index)
            df = df[~df.index.duplicated(keep='first')]

            nasdaq_data.index = pd.to_datetime(nasdaq_data.index)
            nasdaq_data = nasdaq_data[~nasdaq_data.index.duplicated(keep='first')]

            # 合併數據並計算日收益率
            merged_df = pd.merge(df[['close']], nasdaq_data[['close']], left_index=True, right_index=True, suffixes=('_crypto', '_nasdaq'))
            merged_df['crypto_returns'] = merged_df['close_crypto'].pct_change()
            merged_df['nasdaq_returns'] = merged_df['close_nasdaq'].pct_change()

            # 計算 30 日滾動相關性
            correlation = merged_df['crypto_returns'].rolling(window=30).corr(merged_df['nasdaq_returns'])

            # 將計算出的相關性合併回原始 DataFrame
            df['factor_corr_nq'] = correlation

            self.logger.debug("成功計算與納斯達克指數的相關性。")

        except Exception as e:
            self.logger.error(f"計算納斯達克相關性時出錯: {e}", exc_info=True)
            df['factor_corr_nq'] = None

        return df

    def _calculate_fear_greed_proxy(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        計算 7 日的已實現波動率，作為市場情緒的代理指標。
        已實現波動率越高，通常表示市場恐懼情緒越濃。
        """
        self.logger.debug("正在計算恐懼與貪婪指數代理（7日已實現波動率）...")
        try:
            # 計算日收益率
            returns = df['close'].pct_change()
            # 計算 7 日滾動標準差（波動率）
            volatility = returns.rolling(window=7).std()
            df['factor_fear_greed_proxy'] = volatility
            self.logger.debug("成功計算恐懼與貪婪指數代理。")
        except Exception as e:
            self.logger.error(f"計算恐懼與貪婪指數代理時出錯: {e}", exc_info=True)
            df['factor_fear_greed_proxy'] = None
        return df
