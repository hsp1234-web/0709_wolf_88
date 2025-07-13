# tests/unit/apps/factor_engine/test_factor_engine.py
import unittest
from unittest.mock import patch

import pandas as pd

from apps.factor_engine.engine import FactorEngine


# 建立一個假的因子計算函數用於測試
def dummy_factor_calculator(**kwargs):
    """一個簡單的假因子函數，返回一個包含傳入參數的DataFrame。"""
    df = pd.DataFrame([kwargs])
    # 加上一個 signal 列，模擬真實因子函數的輸出
    df["signal"] = 1
    return df


class TestFactorEngine(unittest.TestCase):
    def setUp(self):
        """在每個測試前執行，初始化 FactorEngine。"""
        self.engine = FactorEngine()
        # 為了測試的獨立性，我們註冊一個已知的假因子
        self.engine._register_factor("dummy_factor", dummy_factor_calculator)

    def test_list_factors(self):
        """測試 list_factors 方法是否能返回所有註冊的因子。"""
        factors = self.engine.list_factors()
        self.assertIn("sma_crossover", factors)
        self.assertIn("dummy_factor", factors)

    def test_compute_existing_factor(self):
        """測試 compute 方法能否成功調用一個已註冊的因子。"""
        factor_config = {
            "name": "dummy_factor",
            "params": {"param1": 10, "param2": "test"},
        }
        # 我們傳入一個空的 DataFrame，因為當前設計下因子函數不使用它
        result = self.engine.compute(pd.DataFrame(), factor_config)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, pd.DataFrame)
        # 驗證 dummy_factor_calculator 是否被正確的參數調用
        self.assertEqual(result.iloc[0]["param1"], 10)
        self.assertEqual(result.iloc[0]["param2"], "test")
        self.assertIn("signal", result.columns)

    def test_compute_non_existing_factor(self):
        """測試當請求一個不存在的因子時，compute 方法是否返回 None。"""
        factor_config = {"name": "non_existent_factor"}
        result = self.engine.compute(pd.DataFrame(), factor_config)
        self.assertIsNone(result)

    def test_compute_missing_name_in_config(self):
        """測試當因子設定中缺少 'name' 時，compute 方法是否返回 None。"""
        factor_config = {"params": {"param1": 10}}
        result = self.engine.compute(pd.DataFrame(), factor_config)
        self.assertIsNone(result)

    @patch("apps.factor_engine.engine.calculate_sma_crossover")
    def test_compute_sma_crossover_integration(self, mock_calculate_sma):
        """
        測試 FactorEngine 是否能正確地調用真實的 sma_crossover 因子。
        我們使用 @patch 來模擬 `calculate_sma_crossover` 函數，
        以避免實際的數據獲取和計算，使測試更快、更獨立。
        """
        # 設定 mock 函數的返回值
        mock_calculate_sma.return_value = pd.DataFrame({"signal": [-1, 1]})

        factor_config = {
            "name": "sma_crossover",
            "params": {
                "ticker": "test_ticker",
                "short_window": 5,
                "long_window": 10,
            },
        }

        result = self.engine.compute(pd.DataFrame(), factor_config)

        # 驗證 calculate_sma_crossover 是否被以正確的參數調用
        mock_calculate_sma.assert_called_once_with(
            ticker="test_ticker", short_window=5, long_window=10
        )

        # 驗證 compute 的返回結果是否就是 mock 函數的返回結果
        self.assertIsNotNone(result)
        pd.testing.assert_frame_equal(result, mock_calculate_sma.return_value)


if __name__ == "__main__":
    unittest.main()
