# -*- coding: utf-8 -*-
"""
對 BacktestingService 的單元測試。
"""
import unittest
from unittest.mock import MagicMock
import pandas as pd
import numpy as np

# 將 src 目錄添加到 PYTHONPATH
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from prometheus.services.backtesting_service import BacktestingService
from prometheus.models.strategy_models import Strategy, PerformanceReport

class TestBacktestingService(unittest.TestCase):

    def setUp(self):
        """
        在每個測試前執行，設置模擬的依賴項和測試數據。
        """
        self.mock_db_manager = MagicMock()

        # 建立一個模擬的 DataFrame 作為 db_manager.fetch_table 的回傳值
        dates = pd.to_datetime(pd.date_range(start='2023-01-01', periods=100, freq='D'))
        self.mock_data = pd.DataFrame({
            'date': dates,
            'symbol': 'SPY',
            'T10Y2Y': np.linspace(2.5, 2.0, 100), # 模擬一個因子
            'VIXCLS': np.linspace(20, 30, 100),   # 模擬另一個因子
            'close': np.linspace(400, 450, 100)  # 模擬資產價格
        })
        # 讓 mock 物件在被呼叫時返回此 DataFrame
        self.mock_db_manager.fetch_table.return_value = self.mock_data

        self.backtesting_service = BacktestingService(self.mock_db_manager)

    def test_run_backtest_calculates_performance_correctly(self):
        """
        測試：驗證 run 方法能夠基於模擬數據，正確計算績效指標。
        """
        # 1. 準備 (Arrange)
        test_strategy = Strategy(
            factors=['T10Y2Y', 'VIXCLS'],
            weights={'T10Y2Y': 0.7, 'VIXCLS': -0.3}, # 假設一個策略
            target_asset='SPY'
        )

        # 2. 執行 (Act)
        report = self.backtesting_service.run(test_strategy)

        # 3. 斷言 (Assert)
        self.assertIsInstance(report, PerformanceReport)

        # 驗證 DBManager 的方法被正確呼叫
        self.mock_db_manager.fetch_table.assert_called_with('factors')

        # 驗證計算結果是否為合理的數值 (不為 0 或 NaN)
        self.assertNotEqual(report.sharpe_ratio, 0.0)
        self.assertNotEqual(report.annualized_return, 0.0)
        self.assertLess(report.max_drawdown, 0.0) # 最大回撤應為負數
        self.assertGreater(report.total_trades, 0)

        # 驗證返回值的類型
        self.assertIsInstance(report.sharpe_ratio, float)
        self.assertIsInstance(report.annualized_return, float)

        print("\n[PASS] BacktestingService 的核心演算法測試成功。")

if __name__ == '__main__':
    unittest.main()
