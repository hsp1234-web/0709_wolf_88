# -*- coding: utf-8 -*-
"""
對 EvolutionChamber 的單元測試。
"""
import unittest
from unittest.mock import MagicMock

# 將 src 目錄添加到 PYTHONPATH
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from prometheus.services.evolution_chamber import EvolutionChamber
from prometheus.models.strategy_models import PerformanceReport, Strategy

class TestEvolutionChamber(unittest.TestCase):

    def setUp(self):
        """
        設置模擬的依賴項和測試數據。
        """
        self.mock_backtester = MagicMock()
        self.available_factors = ['T10Y2Y', 'VIXCLS', 'DXY', 'SOFR', 'MOVE', 'USDOLLAR']

        self.chamber = EvolutionChamber(
            backtesting_service=self.mock_backtester,
            available_factors=self.available_factors
        )

    def test_toolbox_can_create_individual(self):
        """
        測試：驗證 toolbox 是否能成功創建一個有效的「個體」。
        """
        individual = self.chamber.toolbox.individual()
        self.assertIsInstance(individual, list)
        self.assertEqual(len(individual), self.chamber.num_factors_to_select)
        # 驗證所有基因（索引）都是唯一的
        self.assertEqual(len(set(individual)), len(individual))
        print("\n[PASS] EvolutionChamber 的個體創建測試成功。")

    def test_evaluate_strategy_calls_backtester(self):
        """
        測試：驗證評估函數能正確調用回測服務並返回適應度分數。
        """
        # 1. 準備 (Arrange)
        # 模擬一個個體（基因組），代表選擇了前5個因子
        test_individual = [0, 1, 2, 3, 4]

        # 設定模擬的回測服務的回傳值
        mock_report = PerformanceReport(sharpe_ratio=1.5)
        self.mock_backtester.run.return_value = mock_report

        # 2. 執行 (Act)
        fitness = self.chamber.toolbox.evaluate(test_individual)

        # 3. 斷言 (Assert)
        # 驗證回測服務的 run 方法被呼叫了一次
        self.mock_backtester.run.assert_called_once()

        # 驗證傳遞給 run 方法的 strategy 物件內容是否正確
        called_strategy = self.mock_backtester.run.call_args[0][0]
        expected_factors = ['T10Y2Y', 'VIXCLS', 'DXY', 'SOFR', 'MOVE']
        self.assertCountEqual(called_strategy.factors, expected_factors)

        # 驗證返回的適應度分數是否正確
        self.assertEqual(fitness, (1.5,))
        print("[PASS] EvolutionChamber 的適應度函數整合測試成功。")

    def test_run_evolution_returns_best_individual(self):
        """
        測試：驗證演化主迴圈能夠運行並返回名人堂物件。
        """
        # 1. 準備 (Arrange)
        # 讓模擬的回測器根據個體的基因（索引）返回一個可預測的分數
        def mock_evaluate_logic(strategy: Strategy) -> PerformanceReport:
            # 假設基因（此處為因子名稱）的字母長度總和越大，分數越高
            # 這提供了一個簡單、確定性的方式來預測哪個“個體”會是最好的
            score = sum(len(factor) for factor in strategy.factors)
            return PerformanceReport(sharpe_ratio=float(score))

        self.mock_backtester.run.side_effect = mock_evaluate_logic

        # 2. 執行 (Act)
        # 執行一個小規模的演化
        hof = self.chamber.run_evolution(n_pop=10, n_gen=3, cxpb=0.5, mutpb=0.2)

        # 3. 斷言 (Assert)
        self.assertGreater(self.mock_backtester.run.call_count, 0)
        self.assertEqual(len(hof), 1) # 驗證名人堂中有一個最優個體
        self.assertTrue(hasattr(hof[0], 'fitness')) # 驗證最優個體有適應度屬性
        self.assertTrue(hof[0].fitness.valid) # 驗證適應度是有效的
        self.assertGreater(hof[0].fitness.values[0], 0) # 驗證適應度分數大於0

        print("\n[PASS] EvolutionChamber 的演化主迴圈測試成功。")

if __name__ == '__main__':
    unittest.main()
