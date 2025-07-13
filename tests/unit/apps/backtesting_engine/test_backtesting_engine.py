# tests/unit/apps/backtesting_engine/test_backtesting_engine.py
import unittest

import pandas as pd

from apps.backtesting_engine.engine import BacktestingEngine


class TestBacktestingEngine(unittest.TestCase):
    def setUp(self):
        """設定測試所需的初始條件。"""
        self.engine = BacktestingEngine()
        # 建立一個簡單的、可預測的價格序列
        self.price_data = pd.Series(
            [100, 102, 105, 103, 106, 108, 110, 107],
            index=pd.to_datetime(
                [
                    "2023-01-01 09:00",
                    "2023-01-01 10:00",
                    "2023-01-01 11:00",
                    "2023-01-01 12:00",
                    "2023-01-01 13:00",
                    "2023-01-01 14:00",
                    "2023-01-01 15:00",
                    "2023-01-01 16:00",
                ]
            ),
            dtype=float,
        )
        # 建立一個對應的信號序列
        self.signals = pd.Series(
            [0, 1, 0, -1, 1, 0, -1, 0],
            index=self.price_data.index,
            dtype=float,
        )

    def test_run_backtest_successfully(self):
        """測試 run 方法能否在有效的輸入下成功執行並返回績效報告。"""
        report = self.engine.run(self.price_data, self.signals)

        self.assertIsNotNone(report)
        self.assertIsInstance(report, dict)

        # 驗證報告中是否包含所有預期的關鍵指標
        expected_keys = [
            "total_return_pct",
            "sharpe_ratio",
            "max_drawdown_pct",
            "win_rate_pct",
            "total_trades",
            "profit_factor",
            "avg_winning_trade_pct",
            "avg_losing_trade_pct",
        ]
        for key in expected_keys:
            self.assertIn(key, report)

        # 驗證返回值的類型是否正確
        self.assertIsInstance(report["total_return_pct"], float)
        self.assertIsInstance(report["total_trades"], int)

        # 根據我們的假數據，我們可以做一些基本的邏輯斷言
        # 交易 1: 買入@102, 賣出@103 -> 獲利
        # 交易 2: 買入@106, 賣出@107 -> 獲利
        # 因此，勝率應該是 100%
        self.assertEqual(report["win_rate_pct"], 100.0)
        self.assertEqual(report["total_trades"], 2)
        # 總回報應該是正數
        self.assertGreater(report["total_return_pct"], 0)

    def test_run_with_mismatched_indices(self):
        """測試當價格和信號的索引不匹配時，run 方法是否返回 None。"""
        invalid_signals = self.signals.copy()
        invalid_signals.index = pd.to_datetime(
            [
                "2023-01-02 09:00",
                "2023-01-02 10:00",
                "2023-01-02 11:00",
                "2023-01-02 12:00",
                "2023-01-02 13:00",
                "2023-01-02 14:00",
                "2023-01-02 15:00",
                "2023-01-02 16:00",
            ]
        )

        report = self.engine.run(self.price_data, invalid_signals)
        self.assertIsNone(report)

    def test_run_with_invalid_input_types(self):
        """測試當輸入不是 Pandas Series 時，run 方法是否返回 None。"""
        report_with_list = self.engine.run(self.price_data.tolist(), self.signals)
        self.assertIsNone(report_with_list)

        report_with_numpy = self.engine.run(
            self.price_data, self.signals.to_numpy()
        )
        self.assertIsNone(report_with_numpy)

    def test_run_with_no_trades(self):
        """測試當沒有任何交易信號時，回測是否能正常處理。"""
        no_trade_signals = pd.Series(
            0, index=self.price_data.index, dtype=float
        )
        report = self.engine.run(self.price_data, no_trade_signals)

        self.assertIsNotNone(report)
        self.assertEqual(report["total_trades"], 0)
        # 在沒有交易的情況下，總回報應為 0
        self.assertEqual(report["total_return_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
