# 檔案: src/core/services/backtesting_service.py
import pandas as pd
import pandas_ta as ta
import vectorbt as vbt
from typing import Dict, Any

from src.core.clients.yfinance import YFinanceClient
from src.core.db.results_saver import ResultsSaver
from src.core.logger import LogManager

class BacktestingService:
    """
    回測服務 v3.0 (基因體解讀版)
    負責接收一個標準化的「策略基因體」，並執行回測。
    """
    def __init__(self, results_saver: ResultsSaver, log_manager: LogManager):
        self.results_saver = results_saver
        self.log_manager = log_manager
        self.yf_client = YFinanceClient()
        self.log_manager.log("INFO", "回測服務 v3.0 初始化，具備策略基因體解讀能力。")

    def _interpret_genome_and_run(self, price: pd.Series, genome: Dict[str, Any]) -> float:
        """
        內部核心：解讀基因體並執行回測。
        (目前僅實作 RSI 均值回歸策略作為原型)
        """
        strategy_name = genome.get("strategy_name")

        if strategy_name == "RSI_MeanReversion":
            # 1. 解析指標
            rsi_params = genome["indicators"][0]["params"]
            rsi = ta.rsi(price, length=rsi_params["window"])

            # 2. 解析交易規則
            entry_rule = genome["entry_rules"][0]
            exit_rule = genome["exit_rules"][0]

            entries = rsi < entry_rule["value"]
            exits = rsi > exit_rule["value"]

            # 3. 執行回測
            portfolio = vbt.Portfolio.from_signals(price, entries, exits, init_cash=100000, freq="D")

            # 4. 返回適應度分數
            return float(portfolio.sharpe_ratio())

        # 未來可在此處添加對其他策略名稱 (如 SMACrossover) 的解讀邏輯
        # elif strategy_name == "SMACrossover":
        #     ...

        else:
            self.log_manager.log("ERROR", f"未知的策略名稱: {strategy_name}")
            return 0.0


    def run_backtest(self, genome: Dict[str, Any], backtest_id: str) -> float:
        """
        執行一次基於策略基因體的回測。

        Args:
            genome: 描述完整策略的字典。
            backtest_id: 本次獨立回測的唯一識別碼。

        Returns:
            該策略的夏普比率 (Sharpe Ratio)。
        """
        try:
            # 獲取真實數據 (此處暫時硬編碼，未來可由基因體定義)
            price_close = self.yf_client.get_daily_data("SPY", "2020-01-01", "2023-12-31")
            if price_close.empty:
                self.log_manager.log("ERROR", f"[{backtest_id}] 無法獲取 SPY 數據。")
                return 0.0

            # 調用內部核心來執行
            sharpe_ratio = self._interpret_genome_and_run(price_close, genome)

            # 儲存結果
            self.results_saver.save_result(
                backtest_id=backtest_id,
                strategy_name=genome.get("strategy_name", "Unknown"),
                parameters=genome, # 將整個基因體存為參數
                metrics={"sharpe_ratio": sharpe_ratio}
            )

            self.log_manager.log("SUCCESS", f"[{backtest_id}] 基因體 {genome.get('strategy_name')} 回測完成。夏普比率: {sharpe_ratio:.4f}")
            return sharpe_ratio

        except Exception as e:
            self.log_manager.log("CRITICAL", f"[{backtest_id}] 在基因體回測過程中發生嚴重錯誤: {e}")
            return 0.0
