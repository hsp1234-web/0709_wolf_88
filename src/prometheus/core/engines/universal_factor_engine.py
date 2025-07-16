# 檔案: src/prometheus/core/engines/universal_factor_engine.py
# --- 抽象程式碼草圖 ---

# 概念：
# 為現有引擎的每個計算方法增加詳細的日誌輸出。

import pandas as pd
import pandas_ta
from prometheus.core.logging.log_manager import LogManager

class UniversalFactorEngine:
    def __init__(self):
        self.logger = LogManager.get_instance().get_logger(self.__class__.__name__)

    def calculate(self, df):
        self.logger.info(f"引擎啟動，接收到維度為 {df.shape} 的數據。")

        df = self._calculate_volatility(df)
        df = self._calculate_momentum(df)

        self.logger.info(f"所有計算完成，最終維度為 {df.shape}。")
        return df

    def _calculate_volatility(self, df):
        self.logger.info(f"進入波動率計算，維度: {df.shape}")
        # ... 執行計算 ...
        df['factor_vol_20d'] = df['Close'].rolling(window=20).std()
        self.logger.info(f"波動率計算後，維度: {df.shape}，新增欄位: ['factor_vol_20d']")
        return df

    def _calculate_momentum(self, df):
        """
        計算動能因子。
        戰術修正：確保使用穩健的方式將計算結果合併回主 DataFrame，
        例如使用 .join() 或 pd.merge()，並處理好潛在的索引問題。
        """
        self.logger.info(f"進入動能計算，維度: {df.shape}")

        new_factors = pd.DataFrame(index=df.index)

        # 檢查是否有 'ta' accessor
        if not hasattr(df, 'ta'):
            self.logger.error("Pandas DataFrame缺少 'ta' accessor，請確保 pandas-ta 已被正確安裝並導入。")
            return df

        new_factors['factor_mom_20d'] = df['Close'].pct_change(periods=20)
        new_factors['factor_mom_60d'] = df['Close'].pct_change(periods=60)
        new_factors['factor_mom_252d'] = df['Close'].pct_change(periods=252)

        # 使用 .join() 確保基於索引的正確合併
        df_with_factors = df.join(new_factors)

        self.logger.info(f"動能計算後，維度: {df_with_factors.shape}，新增欄位: {new_factors.columns.to_list()}")

        # 確保返回的是合併後的 DataFrame
        return df_with_factors
