# 檔案: src/core/services/backtesting_service.py
import pandas as pd
import pandas_ta as ta
import vectorbt as vbt
from typing import Dict, Any

from src.core.db.results_saver import ResultsSaver
# 暫時移除 LogManager 和 YFinanceClient 依賴，專注於流程打通

def create_mock_price_data() -> pd.DataFrame:
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=200))
    price_data = [100 + (i % 20) * (1 if (i // 20) % 2 == 0 else -1) for i in range(200)]
    return pd.DataFrame({'Close': price_data}, index=dates)

class BacktestingService:
    def __init__(self, results_saver: ResultsSaver):
        self.results_saver = results_saver

    async def run_backtest(self, genome: Dict[str, Any], backtest_id: str) -> float:
        # 在非同步函數中運行同步的 CPU 密集型代碼是安全的
        price_df = create_mock_price_data()
        price = price_df['Close']

        rsi_params = genome["indicators"][0]["params"]
        rsi = price_df.ta.rsi(length=rsi_params["window"])

        entry_rule = genome["entry_rules"][0]
        exit_rule = genome["exit_rules"][0]
        entries = rsi < entry_rule["value"]
        exits = rsi > exit_rule["value"]

        portfolio = vbt.Portfolio.from_signals(price, entries, exits, init_cash=100000, freq="D")
        sharpe_ratio = float(portfolio.sharpe_ratio())

        await self.results_saver.save_result(
            backtest_id=backtest_id,
            strategy_name=genome.get("strategy_name", "Unknown"),
            parameters=genome,
            metrics={"sharpe_ratio": sharpe_ratio}
        )
        return sharpe_ratio
