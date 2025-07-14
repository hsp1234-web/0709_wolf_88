# 檔案: src/core/services/backtesting_service.py
import pandas as pd
import vectorbt as vbt
from typing import Tuple

from src.core.clients.yfinance import YFinanceClient
from src.core.db.results_saver import ResultsSaver
from src.core.logger import LogManager

class BacktestingService:
    """
    回測服務 v2.0 (真實數據版)
    負責執行單次回測任務，計算策略的適應度分數。
    """
    def __init__(self, results_saver: ResultsSaver, log_manager: LogManager):
        self.results_saver = results_saver
        self.log_manager = log_manager
        # 初始化真實數據客戶端
        self.yf_client = YFinanceClient()
        self.log_manager.log("INFO", "回測服務已初始化，使用 YFinanceClient 獲取真實數據。")

    def run_backtest(self, individual: Tuple[int, int], backtest_id: str) -> float:
        """
        執行一次完整的、基於真實數據的回測。

        Args:
            individual: 一個包含 (快線週期, 慢線週期) 的元組。
            backtest_id: 本次獨立回測的唯一識別碼。

        Returns:
            該策略的夏普比率 (Sharpe Ratio) 作為適應度分數。
        """
        fast_window, slow_window = individual

        # 策略驗證：慢線必須長於快線
        if slow_window <= fast_window:
            self.log_manager.log("WARNING", f"無效策略參數: 慢線({slow_window}) <= 快線({fast_window})。適應度設為-1。")
            return -1.0

        try:
            # 1. 獲取真實數據
            self.log_manager.log("INFO", f"[{backtest_id}] 正在為 SPY 獲取 2020-2023 年的歷史日線數據...")
            price = self.yf_client.get_daily_data(
                ticker="SPY",
                start_date="2020-01-01",
                end_date="2023-12-31"
            )
            if price.empty:
                self.log_manager.log("ERROR", f"[{backtest_id}] 無法獲取 SPY 數據。")
                return 0.0

            # 2. 計算移動平均線
            fast_ma = vbt.MA.run(price, window=fast_window, short_name="fast")
            slow_ma = vbt.MA.run(price, window=slow_window, short_name="slow")

            # 3. 生成交易信號
            entries = fast_ma.ma_crossed_above(slow_ma)
            exits = fast_ma.ma_crossed_below(slow_ma)

            # 4. 執行回測
            portfolio = vbt.Portfolio.from_signals(price, entries, exits, init_cash=100000)

            # 5. 計算表現指標 (夏普比率)
            sharpe_ratio = portfolio.sharpe_ratio()

            # 儲存回測結果 (此處僅為範例，可擴充)
            self.results_saver.save_result(
                backtest_id=backtest_id,
                strategy_name="SMACrossover",
                parameters={"fast": fast_window, "slow": slow_window},
                # 將 portfolio.stats() 轉換為字典以便儲存
                metrics=portfolio.stats().to_dict()
            )

            self.log_manager.log("SUCCESS", f"[{backtest_id}] 策略 ({fast_window}, {slow_window}) 回測完成。夏普比率: {sharpe_ratio:.4f}")

            # 返回適應度分數
            return float(sharpe_ratio)

        except Exception as e:
            self.log_manager.log("CRITICAL", f"[{backtest_id}] 在回測過程中發生嚴重錯誤: {e}")
            return 0.0
