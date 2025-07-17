# -*- coding: utf-8 -*-
"""
回測服務：負責評估單一策略的歷史績效。
"""
import pandas as pd
import numpy as np
from prometheus.core.db.db_manager import DBManager
from prometheus.models.strategy_models import Strategy, PerformanceReport

class BacktestingService:
    """
    一個獨立、高效的回測服務。
    此服務是整個演化系統的心臟，專職負責精準評估任何單一策略（基因組）的歷史績效。
    """
    def __init__(self, db_manager: DBManager):
        """
        初始化回測服務。

        Args:
            db_manager (DBManager): 用於從數據倉儲讀取因子與價格數據的數據庫管理器。
        """
        self.db_manager = db_manager

    def _load_data(self, strategy: Strategy) -> pd.DataFrame:
        """
        從數據庫加載並合併因子與目標資產價格數據。
        """
        # 1. 加載所有因子數據
        all_factors_df = self.db_manager.fetch_table('factors')

        # 2. 篩選出策略所需的因子
        required_factors = all_factors_df[['date', 'symbol'] + strategy.factors]

        # 3. 加載目標資產的價格數據 (假設價格也存在 'factors' 表中，以 'close' 欄位表示)
        #    在真實場景中，這可能會從一個專門的價格表中獲取
        target_prices_df = all_factors_df[all_factors_df['symbol'] == strategy.target_asset][['date', 'close']]

        # 4. 合併數據
        merged_df = pd.merge(required_factors[required_factors['symbol'] == strategy.target_asset], target_prices_df, on='date')
        merged_df['date'] = pd.to_datetime(merged_df['date'])
        merged_df = merged_df.set_index('date').sort_index()

        return merged_df

    def run(self, strategy: Strategy) -> PerformanceReport:
        """
        執行一次完整的策略回測。
        """
        # 1. 數據加載
        data = self._load_data(strategy)
        if data.empty:
            print(f"WARN: 找不到策略 {strategy.target_asset} 的數據，跳過回測。")
            return PerformanceReport()

        # 2. 訊號生成 (正規化 + 加權)
        # 對因子進行 z-score 正規化
        for factor in strategy.factors:
            data[f'{factor}_norm'] = (data[factor] - data[factor].mean()) / data[factor].std()

        # 計算加權後的組合訊號
        data['signal'] = 0
        for factor in strategy.factors:
            data['signal'] += data[f'{factor}_norm'] * strategy.weights.get(factor, 0)

        # 3. 投資組合模擬
        # 計算目標資產的日報酬率
        data['asset_returns'] = data['close'].pct_change()

        # 根據訊號計算策略報酬率 (假設 T+1 生效)
        # 訊號為正 -> 做多, 訊號為負 -> 做空
        data['strategy_returns'] = data['signal'].shift(1) * data['asset_returns']

        # 4. 績效計算
        # 處理可能出現的 NaN 或 Inf
        data.replace([np.inf, -np.inf], np.nan, inplace=True)
        data.dropna(inplace=True)

        if data.empty:
            return PerformanceReport()

        # 計算累積報酬
        cumulative_returns = (1 + data['strategy_returns']).cumprod()

        # 計算年化報酬
        days = (data.index[-1] - data.index[0]).days
        annualized_return = (cumulative_returns.iloc[-1]) ** (365.0 / days) - 1 if days > 0 else 0.0

        # 計算年化夏普比率 (假設無風險利率為 0)
        annualized_volatility = data['strategy_returns'].std() * np.sqrt(252)
        sharpe_ratio = (annualized_return / annualized_volatility) if annualized_volatility != 0 else 0.0

        # 計算最大回撤
        peak = cumulative_returns.expanding(min_periods=1).max()
        drawdown = (cumulative_returns - peak) / peak
        max_drawdown = drawdown.min()

        return PerformanceReport(
            sharpe_ratio=float(sharpe_ratio),
            annualized_return=float(annualized_return),
            max_drawdown=float(max_drawdown),
            total_trades=len(data) # 簡化為交易天數
        )
