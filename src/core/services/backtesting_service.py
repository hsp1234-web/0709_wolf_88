import pandas as pd
import pandas_ta as ta
import vectorbt as vbt
from typing import Dict, Any

from src.core.clients.yfinance import YFinanceClient
from src.core.db.results_saver import ResultsSaver
from src.core.logger import LogManager

def create_mock_price_data() -> pd.DataFrame:
    """生成一個結構正確的、用於測試的模擬價格數據 DataFrame。"""
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=200))
    price_data = [100 + (i % 20) * (1 if (i // 20) % 2 == 0 else -1) for i in range(200)]
    # 根據《🔬Pandas-ta 相容性修復計畫》，返回 DataFrame 以確保 .ta 擴展穩定
    return pd.DataFrame({'Close': price_data}, index=dates)

class BacktestingService:
    """ 回測服務 v3.3 (模式感知穩定版) """
    def __init__(self, results_saver: ResultsSaver, log_manager: LogManager, mode: str = 'prod'):
        self.results_saver = results_saver
        self.log_manager = log_manager
        self.mode = mode

        if self.mode == 'prod':
            self.yf_client = YFinanceClient()

        self.log_manager.log("INFO", f"回測服務 v3.3 在 '{self.mode}' 模式下初始化。")

    def _get_price_data(self) -> pd.DataFrame:
        """根據運行模式獲取價格數據。"""
        if self.mode == 'test':
            self.log_manager.log("INFO", "偵測到測試模式，使用確定性模擬數據。")
            return create_mock_price_data()

        # 生產模式下的真實數據獲取邏輯
        try:
            # 假設 yfinance 客戶端有一個返回 DataFrame 的方法
            price_df = self.yf_client.get_daily_data_df("SPY", "2020-01-01", "2023-12-31")
            if price_df is None or price_df.empty:
                raise ValueError("真實數據獲取失敗或為空。")
            return price_df
        except Exception as e:
            self.log_manager.log("ERROR", f"生產模式數據獲取失敗: {e}")
            raise

    def _interpret_genome_and_run(self, price_df: pd.DataFrame, genome: Dict[str, Any]) -> float:
        price = price_df['Close'] # 提取 Series 進行回測
        strategy_name = genome.get("strategy_name")
        if strategy_name == "RSI_MeanReversion":
            rsi_params = genome["indicators"][0]["params"]
            # 在 DataFrame 上安全地使用 .ta
            rsi = price_df.ta.rsi(length=rsi_params["window"])
            entry_rule = genome["entry_rules"][0]
            exit_rule = genome["exit_rules"][0]
            entries = rsi < entry_rule["value"]
            exits = rsi > exit_rule["value"]
            portfolio = vbt.Portfolio.from_signals(price, entries, exits, init_cash=100000, freq="D")
            return float(portfolio.sharpe_ratio())
        return 0.0

    def run_backtest(self, genome: Dict[str, Any], backtest_id: str) -> float:
        try:
            price_df = self._get_price_data()
            sharpe_ratio = self._interpret_genome_and_run(price_df, genome)
            self.results_saver.save_result(
                backtest_id=backtest_id,
                strategy_name=genome.get("strategy_name", "Unknown"),
                parameters=genome,
                metrics={"sharpe_ratio": sharpe_ratio}
            )
            self.log_manager.log("SUCCESS", f"[{backtest_id}] 回測完成。夏普比率: {sharpe_ratio:.4f}")
            return sharpe_ratio
        except Exception as e:
            self.log_manager.log("CRITICAL", f"[{backtest_id}] 回測過程中發生嚴重錯誤: {e}", exc_info=True)
            return 0.0
