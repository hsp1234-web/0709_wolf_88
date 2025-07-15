import pandas as pd
import vectorbt as vbt
import numpy as np

class BacktestingService:
    """
    一個動態的、基於規則的回測引擎。
    本服務能夠解釋由 EvolutionChamber 產生的複雜基因體 (Genome)，
    將其轉換為交易信號，並使用 vectorbt 執行高效的向量化回測。
    """

    def __init__(self, price_data: pd.DataFrame):
        if not isinstance(price_data, pd.DataFrame) or "close" not in price_data.columns:
            raise ValueError("必須提供包含 'close' 欄位的 Pandas DataFrame。")

        # 為了使用 .ta 擴展，我們需要匯入 pandas_ta
        try:
            import pandas_ta
        except ImportError:
            raise ImportError("請安裝 pandas_ta 套件: pip install pandas_ta")

        self.price_data = price_data


    def run_backtest(self, genome: list) -> dict:
        """
        根據給定的基因體 (一系列條件) 執行回測。

        :param genome: 一個包含多個條件字典的列表。
                       例如: [
                           { "factor": "RSI", "params": { "window": 14 }, "operator": "less_than", "value": 30 },
                           { "factor": "SMA_cross", "params": { "fast_window": 10, "slow_window": 20 }, "operator": "cross_above" }
                       ]
        :return: 一個包含關鍵績效指標 (KPIs) 的字典。
        """
        if not isinstance(genome, list) or not genome:
            return self._invalid_strategy_results("基因體為空或格式不正確。")

        try:
            # 產生進場和出場信號
            entries, exits = self._generate_signals(genome)

            # 如果沒有產生任何交易信號，這是一個有效的、但不活躍的策略。
            # 直接返回零績效，而不是將其視為錯誤。
            if entries.sum() == 0 and exits.sum() == 0:
                return self._zero_performance_results()

            # 執行向量化回測
            portfolio = vbt.Portfolio.from_signals(
                self.price_data["close"],
                entries=entries,
                exits=exits,
                freq="D",
                init_cash=100000,
            )

            stats = portfolio.stats()
            return {
                "sharpe_ratio": round(stats.get("Sharpe Ratio", np.nan), 2),
                "total_return": round(stats.get("Total Return [%]", np.nan), 2),
                "max_drawdown": round(stats.get("Max Drawdown [%]", np.nan), 2),
                "win_rate": round(stats.get("Win Rate [%]", np.nan), 2),
                "is_valid": True,
            }
        except Exception as e:
            # 捕捉任何在回測中可能發生的錯誤
            return self._invalid_strategy_results(f"回測時發生錯誤: {e}")

    def _generate_signals(self, genome: list) -> (pd.Series, pd.Series):
        """
        根據基因體中的所有條件，動態生成組合的進出場信號。
        """
        all_entry_signals = pd.DataFrame(index=self.price_data.index)
        all_exit_signals = pd.DataFrame(index=self.price_data.index)

        for i, condition in enumerate(genome):
            entry_signal, exit_signal = self._evaluate_condition(condition)
            all_entry_signals[f'condition_{i}'] = entry_signal
            all_exit_signals[f'condition_{i}'] = exit_signal

        # 核心邏輯：所有條件的進場信號必須同時滿足 (AND)
        final_entries = all_entry_signals.all(axis=1)
        # 核心邏輯：任何一個條件的出場信號被觸發即可 (OR)
        final_exits = all_exit_signals.any(axis=1)

        return final_entries, final_exits

    def _evaluate_condition(self, condition: dict) -> (pd.Series, pd.Series):
        """
        評估單一條件，並返回對應的進出場布林序列。
        """
        factor_name = condition["factor"]
        params = condition.get("params", {})
        operator = condition["operator"]
        value = condition.get("value")

        # 初始化信號序列
        entries = pd.Series(False, index=self.price_data.index)
        exits = pd.Series(False, index=self.price_data.index)

        # --- 處理特殊因子 ---
        if factor_name == "SMA_cross":
            fast_window = params["fast_window"]
            slow_window = params["slow_window"]

            # 【保護機制】如果快線大於或等於慢線，這是一個無效條件，直接返回空信號
            if fast_window >= slow_window:
                return entries, exits # 返回全為 False 的序列

            fast_sma = self.price_data.ta.sma(length=fast_window)
            slow_sma = self.price_data.ta.sma(length=slow_window)

            if operator == "cross_above":
                entries = fast_sma.vbt.crossed_above(slow_sma)
                exits = fast_sma.vbt.crossed_below(slow_sma)
            elif operator == "cross_below":
                entries = fast_sma.vbt.crossed_below(slow_sma)
                exits = fast_sma.vbt.crossed_above(slow_sma)

        # --- 處理一般因子 (例如 RSI, MACD 等) ---
        else:
            # 動態計算指標
            indicator = getattr(self.price_data.ta, factor_name.lower())(**params)

            if operator == "less_than":
                entries = indicator < value
                exits = indicator > value # 假設出場條件是反向的
            elif operator == "greater_than":
                entries = indicator > value
                exits = indicator < value # 假設出場條件是反向的

        return entries, exits

    def _zero_performance_results(self) -> dict:
        """返回一個代表有效但無交易活動的策略的標準字典。"""
        return {
            "sharpe_ratio": 0.0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "is_valid": True,
            "error": "No signals generated",
        }

    def _invalid_strategy_results(self, error_message: str) -> dict:
        """返回一個代表無效或失敗策略的標準字典。"""
        return {
            "sharpe_ratio": -1.0,
            "total_return": -100.0,
            "max_drawdown": 100.0,
            "win_rate": 0.0,
            "is_valid": False,
            "error": error_message,
        }
