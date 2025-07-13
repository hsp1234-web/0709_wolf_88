# apps/backtesting_engine/engine.py
from typing import Dict

import numpy as np
import pandas as pd
import vectorbt as vbt


class BacktestingEngine:
    """
    回測引擎，專門負責執行交易策略的回測並產出標準化的績效報告。
    它封裝了 vectorbt 的核心邏輯，提供一個簡潔的接口。
    """

    def run(
        self, price_data: pd.Series, signals: pd.Series
    ) -> Dict[str, float | int] | None:
        """
        執行回測並返回一個標準化的績效報告。

        :param price_data: 包含價格時間序列的 Pandas Series，索引為日期時間。
        :param signals: 包含交易信號的 Pandas Series (1: 進場, -1: 出場)，
                        索引必須與 price_data 對齊。
        :return: 一個包含關鍵績效指標 (KPIs) 的字典，如果回測失敗則返回 None。
        """
        if not isinstance(price_data, pd.Series) or not isinstance(
            signals, pd.Series
        ):
            print("錯誤：price_data 和 signals 必須是 Pandas Series。")
            return None

        if not price_data.index.equals(signals.index):
            print("錯誤：價格數據和信號的索引必須完全匹配。")
            # 在更複雜的系統中，可以嘗試重新對齊索引
            # signals = signals.reindex(price_data.index, method='ffill').fillna(0)
            return None

        try:
            # 將進出場信號轉換為 vbt 所需的布林值格式
            # 這裡我們假設 1 是進場信號，-1 是出場信號
            entries = signals == 1
            exits = signals == -1

            # 使用 vectorbt 的 Portfolio.from_signals 執行回測
            # 我們設定一些基本參數，例如初始資本和手續費
            portfolio = vbt.Portfolio.from_signals(
                close=price_data,
                entries=entries,
                exits=exits,
                init_cash=100_000,  # 初始資金
                freq="H",  # 假設數據頻率為小時
                fees=0.001,  # 交易手續費 0.1%
            )

            # 從回測結果中提取關鍵績效指標 (KPIs)
            stats = portfolio.stats()

            # 將結果格式化為一個標準化的字典
            # 我們使用 .get() 方法以避免因缺少某些指標而導致的錯誤
            performance_report = {
                "total_return_pct": stats.get("Total Return [%]", 0.0),
                "sharpe_ratio": stats.get("Sharpe Ratio", 0.0),
                "max_drawdown_pct": stats.get("Max Drawdown [%]", 0.0),
                "win_rate_pct": stats.get("Win Rate [%]", 0.0),
                "total_trades": int(stats.get("Total Trades", 0)),
                "profit_factor": stats.get("Profit Factor", 0.0),
                "avg_winning_trade_pct": stats.get("Avg Winning Trade [%]", 0.0),
                "avg_losing_trade_pct": stats.get("Avg Losing Trade [%]", 0.0),
            }

            # 將 numpy 類型轉換為 Python 原生類型，以確保兼容性
            for key, value in performance_report.items():
                if isinstance(value, (np.floating, float)):
                    performance_report[key] = float(value)
                elif isinstance(value, (np.integer, int)):
                    performance_report[key] = int(value)

            print("--- 回測引擎：計算完成 ---")
            return performance_report

        except Exception as e:
            print(f"執行回測時發生錯誤：{e}")
            # 在實際應用中，這裡應該有更詳細的日誌記錄
            return None
