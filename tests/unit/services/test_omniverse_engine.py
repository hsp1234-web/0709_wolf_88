import unittest
import pandas as pd
import numpy as np
import yaml
import os

from prometheus.services.evolution_chamber import EvolutionChamber
from prometheus.services.backtesting_service import BacktestingService

# 建立一個假的設定檔，用於測試
FAKE_CONFIG_CONTENT = """
factor_universe:
  - name: "RSI"
    params:
      window: [14, 28]
    operators: ["less_than", "greater_than"]
    value_range: [20, 80]
  - name: "SMA_cross"
    params:
      fast_window: [5, 10]
      slow_window: [20, 40]
    operators: ["cross_above", "cross_below"]
"""
FAKE_CONFIG_PATH = "tests/unit/services/fake_config.yml"

class TestEvolutionChamber(unittest.TestCase):
    """測試萬象引擎的演化室"""

    @classmethod
    def setUpClass(cls):
        # 創建假的設定檔
        with open(FAKE_CONFIG_PATH, "w") as f:
            f.write(FAKE_CONFIG_CONTENT)
        cls.chamber = EvolutionChamber(config_path=FAKE_CONFIG_PATH)

    @classmethod
    def tearDownClass(cls):
        # 清理假的設定檔
        os.remove(FAKE_CONFIG_PATH)

    def test_initialization(self):
        """測試演化室是否能成功初始化"""
        self.assertIsNotNone(self.chamber)
        self.assertTrue(len(self.chamber.factor_universe) == 2)

    def test_create_random_condition(self):
        """測試是否能生成一個隨機但有效的條件"""
        condition = self.chamber.create_random_condition()
        self.assertIn("factor", condition)
        self.assertIn("params", condition)
        self.assertIn("operator", condition)

        # 檢查參數是否在定義的範圍內
        if condition["factor"] == "RSI":
            self.assertIn(condition["operator"], ["less_than", "greater_than"])
            self.assertTrue(14 <= condition["params"]["window"] <= 28)
            self.assertTrue(20 <= condition["value"] <= 80)
        elif condition["factor"] == "SMA_cross":
            self.assertIn(condition["operator"], ["cross_above", "cross_below"])
            self.assertTrue(5 <= condition["params"]["fast_window"] <= 10)
            self.assertTrue(20 <= condition["params"]["slow_window"] <= 40)

    def test_create_individual(self):
        """測試是否能生成一個完整的基因體 (個體)"""
        individual = self.chamber.toolbox.individual()
        self.assertIsInstance(individual, list)
        self.assertTrue(1 <= len(individual) <= self.chamber.max_conditions)
        # 檢查列表中的每個元素都是一個有效的條件字典
        for condition in individual:
            self.assertIn("factor", condition)

    def test_mutation_and_crossover(self):
        """測試突變和交叉操作是否能正常執行"""
        pop = self.chamber.create_population(n=2)
        ind1, ind2 = pop[0], pop[1]

        # 突變
        mutated_ind, = self.chamber.mutate_individual(ind1)
        self.assertIsInstance(mutated_ind, list)

        # 交叉
        crossed_ind1, crossed_ind2 = self.chamber.crossover_individuals(ind1, ind2)
        self.assertIsInstance(crossed_ind1, list)
        self.assertIsInstance(crossed_ind2, list)


class TestBacktestingService(unittest.TestCase):
    """測試萬象引擎的回測服務"""

    @classmethod
    def setUpClass(cls):
        # 建立假的價格數據
        dates = pd.date_range(start="2023-01-01", periods=100)
        price = np.random.rand(100).cumsum() + 50
        cls.price_data = pd.DataFrame({"close": price}, index=dates)
        cls.backtester = BacktestingService(cls.price_data)

    def test_run_valid_rsi_strategy(self):
        """測試一個有效的單一 RSI 策略"""
        genome = [
            {"factor": "RSI", "params": {"window": 14}, "operator": "less_than", "value": 30}
        ]
        result = self.backtester.run_backtest(genome)
        self.assertTrue(result["is_valid"])
        self.assertIn("sharpe_ratio", result)

    def test_run_valid_sma_cross_strategy(self):
        """測試一個有效的均線交叉策略"""
        genome = [
            {"factor": "SMA_cross", "params": {"fast_window": 10, "slow_window": 20}, "operator": "cross_above"}
        ]
        result = self.backtester.run_backtest(genome)
        self.assertTrue(result["is_valid"])
        self.assertIn("total_return", result)

    def test_run_combined_strategy(self):
        """測試一個組合策略"""
        genome = [
            {"factor": "RSI", "params": {"window": 14}, "operator": "greater_than", "value": 70},
            {"factor": "SMA_cross", "params": {"fast_window": 5, "slow_window": 20}, "operator": "cross_below"}
        ]
        result = self.backtester.run_backtest(genome)
        # 即使組合策略可能不賺錢或沒有信號，它也應該被視為有效的
        self.assertIn("is_valid", result)
        self.assertIn("sharpe_ratio", result)

    def test_run_invalid_genome(self):
        """測試無效的基因體 (例如空的)"""
        genome = []
        result = self.backtester.run_backtest(genome)
        self.assertFalse(result["is_valid"])
        self.assertIn("error", result)

    def test_invalid_price_data(self):
        """測試初始化時傳入無效的價格數據"""
        with self.assertRaises(ValueError):
            BacktestingService(pd.DataFrame({"not_close": [1, 2, 3]}))

if __name__ == "__main__":
    unittest.main()
