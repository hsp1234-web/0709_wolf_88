# In apps/backtesting_engine/engine.py
import numpy as np
import pandas as pd


class Backtester:
    """
    一個簡單的向量化回測引擎。
    接收價格數據與交易信號，計算策略的歷史績效。
    """
    def __init__(self, price_series: pd.Series, signal_series: pd.Series, initial_capital: float = 100000.0):
        """
        初始化回測器。
        :param price_series: 包含資產收盤價的時間序列。
        :param signal_series: 包含交易信號 (1: 買進, -1: 賣出, 0: 持有) 的時間序列。
        :param initial_capital: 初始資金。
        """
        self.price_series = price_series
        self.signal_series = signal_series
        self.initial_capital = initial_capital
        self.results = None

    def run(self):
        """執行回測模擬。"""
        print("--- 開始執行回測模擬 ---")
        # 結合價格與信號
        combined_df = pd.DataFrame({'price': self.price_series, 'signal': self.signal_series}).dropna()

        # 計算策略每日報酬率
        # 假設我們在信號出現的下一根 K 棒開盤時交易，此處簡化為持有到下一期
        combined_df['returns'] = np.log(combined_df['price'] / combined_df['price'].shift(1))
        combined_df['strategy_returns'] = combined_df['returns'] * combined_df['signal'].shift(1)

        # 計算資產淨值曲線
        combined_df['cumulative_returns'] = self.initial_capital * (1 + combined_df['strategy_returns']).cumprod()

        self.results = combined_df
        print("✔ 回測模擬完成。")
        return self.results

    def get_performance_metrics(self) -> dict:
        """計算並回傳關鍵績效指標 (KPIs)。"""
        if self.results is None:
            raise ValueError("請先運行 run() 方法。")

        print("--- 正在計算績效指標 ---")
        total_return = (self.results['cumulative_returns'].iloc[-1] / self.initial_capital) - 1

        # 計算夏普比率 (假設無風險利率為 0，年化)
        sharpe_ratio = (self.results['strategy_returns'].mean() / self.results['strategy_returns'].std()) * np.sqrt(252 * 24) # 小時級數據

        # 計算最大回撤
        rolling_max = self.results['cumulative_returns'].cummax()
        drawdown = (self.results['cumulative_returns'] - rolling_max) / rolling_max
        max_drawdown = drawdown.min()

        metrics = {
            "總回報率 (Total Return)": f"{total_return:.2%}",
            "夏普比率 (Sharpe Ratio)": f"{sharpe_ratio:.2f}",
            "最大回撤 (Max Drawdown)": f"{max_drawdown:.2%}",
        }
        print("✔ 績效指標計算完成。")
        return metrics
