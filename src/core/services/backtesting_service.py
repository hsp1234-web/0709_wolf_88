import pandas as pd
import vectorbt as vbt
import pandas_ta as ta

class BacktestingService:
    """
    一個封裝了因子計算與向量化回測的核心服務。
    """
    def __init__(self, price_data: pd.DataFrame):
        if not isinstance(price_data, pd.DataFrame) or 'close' not in price_data.columns:
            raise ValueError("必須提供包含 'close' 欄位的 Pandas DataFrame。")
        self.price_data = price_data

    def run_sma_crossover_strategy(self, fast_window: int, slow_window: int) -> dict:
        """
        執行一個簡單的均線交叉策略。

        :param fast_window: 快速移動平均線的窗口大小。
        :param slow_window: 慢速移動平均線的窗口大小。
        :return: 一個包含關鍵績效指標 (KPIs) 的字典。
        """
        if fast_window >= slow_window:
            # 這是一個無效的策略，直接返回差的績效
            return {
                "sharpe_ratio": -1.0,
                "total_return": -1.0,
                "max_drawdown": -1.0,
                "win_rate": 0.0,
                "is_valid": False
            }

        try:
            # 1. 計算因子 (SMA)
            fast_sma = self.price_data.ta.sma(length=fast_window)
            slow_sma = self.price_data.ta.sma(length=slow_window)

            # 2. 產生交易信號
            entries = fast_sma > slow_sma
            exits = fast_sma < slow_sma

            # 3. 執行向量化回測
            portfolio = vbt.Portfolio.from_signals(
                self.price_data['close'],
                entries=entries,
                exits=exits,
                freq='D', # 假設是日線數據
                init_cash=100000 # 初始資金
            )

            # 4. 提取並返回績效統計
            stats = portfolio.stats()

            return {
                "sharpe_ratio": round(stats['Sharpe Ratio'], 2),
                "total_return": round(stats['Total Return [%]'], 2),
                "max_drawdown": round(stats['Max Drawdown [%]'], 2),
                "win_rate": round(stats['Win Rate [%]'], 2),
                "is_valid": True
            }
        except Exception as e:
            # 捕捉任何在回測中可能發生的錯誤
            return {
                "error": str(e),
                "is_valid": False
            }
