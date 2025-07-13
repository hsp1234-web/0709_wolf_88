import pandas as pd
import numpy as np

def calculate_sma_crossover(symbol: str, fast: int = 5, slow: int = 10) -> dict:
    """
    一個簡單的 SMA 交叉策略計算函數。
    為求簡化，此處使用隨機數據模擬股價。

    Args:
        symbol (str): 標的代碼 (僅用於日誌記錄)。
        fast (int): 短週期移動平均線。
        slow (int): 長週期移動平均線。

    Returns:
        dict: 包含計算結果的字典。
    """
    # 模擬生成 30 天的收盤價數據
    np.random.seed(sum(map(ord, symbol))) # 確保不同 symbol 生成不同數據
    prices = pd.Series(100 + np.random.randn(30).cumsum(), name="close")

    # 計算快慢移動平均線
    fast_sma = prices.rolling(window=fast).mean()
    slow_sma = prices.rolling(window=slow).mean()

    # 找出交叉點
    crossovers = np.where(np.diff(np.sign(fast_sma - slow_sma)))[0]

    return {
        "symbol": symbol,
        "crossover_points": len(crossovers),
        "last_price": round(prices.iloc[-1], 2)
    }
