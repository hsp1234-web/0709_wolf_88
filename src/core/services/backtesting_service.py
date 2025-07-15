import pandas as pd
import pandas_ta as ta
import vectorbt as vbt
from typing import Dict, Any
from src.core.context import AppContext
import random

def create_mock_price_data() -> pd.DataFrame:
    """創建一個模擬的、有趨勢性的價格數據，以便夏普比率不是 NaN。"""
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=200))
    # 加上一個小趨勢以避免零標準差
    price_data = [100 + i * 0.1 + (random.random() - 0.5) * 10 for i in range(200)]
    return pd.DataFrame({'Close': price_data}, index=dates)

class BacktestingService:
    def __init__(self, context: AppContext):
        self.context = context
        # 模擬價格數據在服務實例化時創建一次
        self.price_df = create_mock_price_data()

    async def run_backtest(self, genome: Dict[str, Any]) -> float:
        """
        根據給定的基因體（策略參數）運行回測。
        注意：此函數現在是同步的，因為 vectorbt 是同步庫。
        我們會在非同步的 worker 中調用它。
        """
        price = self.price_df['Close']

        # 從基因體中安全地提取參數
        rsi_period = int(genome.get("params", {}).get("rsi_period", 14))
        buy_threshold = float(genome.get("params", {}).get("buy_threshold", 30))
        # 增加一個賣出門檻以形成有效策略
        sell_threshold = float(genome.get("params", {}).get("sell_threshold", 70))

        # 計算指標
        rsi = self.price_df.ta.rsi(length=rsi_period)

        # 產生交易信號
        entries = rsi < buy_threshold
        exits = rsi > sell_threshold

        # 執行回測
        if entries.any() and exits.any():
            portfolio = vbt.Portfolio.from_signals(price, entries, exits, init_cash=100000, freq="D")
            sharpe_ratio = portfolio.sharpe_ratio()
        else:
            sharpe_ratio = 0.0 # 如果沒有交易，則夏普比率為 0

        # 返回一個浮點數，處理 NaN 的情況
        return float(sharpe_ratio) if pd.notna(sharpe_ratio) else 0.0
