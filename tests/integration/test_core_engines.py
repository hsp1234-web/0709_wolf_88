# tests/integration/test_core_engines.py
import unittest

import pandas as pd

from apps.backtesting_engine.engine import BacktestingEngine
from apps.factor_engine.engine import FactorEngine
from core.analysis.data_engine import DataEngine
from core.clients.yfinance import YFinanceClient


class TestCoreEnginesIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        在所有測試開始前執行一次，用於設定共享資源，例如數據。
        """
        # 為了使整合測試穩定且可重複，我們不依賴外部 API
        # 我們將建立一個真實但固定的數據集
        print("--- [Integration Test] Setting up test data ---")
        client = YFinanceClient()
        # 我們使用一個已知的、有數據的股票和時間範圍
        cls.ticker = "tqqq"
        cls.start_date = "2024-06-01"
        cls.end_date = "2024-07-10"

        # 使用 DataEngine 獲取真實數據
        # 注意：這會讓測試依賴於 DataEngine 和 YFinanceClient 的正確性
        # 這正是整合測試的目的
        data_engine = DataEngine(yf_client=client)
        cls.price_data = data_engine.get_hourly_series(
            cls.ticker, "close", cls.start_date, cls.end_date
        )
        data_engine.close()

        # 確保我們真的獲取到了數據
        if cls.price_data is None or cls.price_data.empty:
            raise ValueError(
                "Failed to fetch test data. "
                "Integration test cannot proceed."
            )
        print(f"--- Successfully fetched {len(cls.price_data)} data points for {cls.ticker.upper()} ---")

    def test_end_to_end_workflow(self):
        """
        測試從因子計算到回測的完整端到端流程。
        """
        # --- 步驟 1: 實例化引擎 ---
        factor_engine = FactorEngine()
        backtesting_engine = BacktestingEngine()

        # --- 步驟 2: 計算因子信號 ---
        # 定義我們要使用的因子和其參數
        factor_config = {
            "name": "sma_crossover",
            "params": {
                "ticker": self.ticker,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "short_window": 10,  # 使用較短的窗口以在測試數據中產生信號
                "long_window": 30,
            },
        }

        # 執行因子計算
        # 我們傳入一個空的 DataFrame，因為因子函數會自行獲取數據
        factor_result_df = factor_engine.compute(pd.DataFrame(), factor_config)

        # 驗證因子計算是否成功
        self.assertIsNotNone(factor_result_df)
        self.assertIsInstance(factor_result_df, pd.DataFrame)
        self.assertIn("signal", factor_result_df.columns)
        self.assertIn(f"{self.ticker}_close", factor_result_df.columns)

        # --- 步驟 3: 準備回測數據 ---
        # 從因子結果中提取價格和信號序列
        # 確保它們的索引是對齊的
        price_for_backtest = factor_result_df[f"{self.ticker}_close"]
        signals_for_backtest = factor_result_df["signal"]

        # --- 步驟 4: 執行回測 ---
        performance_report = backtesting_engine.run(
            price_for_backtest, signals_for_backtest
        )

        # --- 步驟 5: 斷言結果 ---
        # 驗證回測是否成功並返回了報告
        self.assertIsNotNone(performance_report)
        self.assertIsInstance(performance_report, dict)

        # 驗證報告的結構和數據類型
        expected_keys = [
            "total_return_pct",
            "sharpe_ratio",
            "max_drawdown_pct",
            "win_rate_pct",
            "total_trades",
            "profit_factor",
        ]
        for key in expected_keys:
            self.assertIn(key, performance_report)
            self.assertIsInstance(
                performance_report[key], (float, int)
            )

        print("\n--- [Integration Test] End-to-End Workflow Report ---")
        for key, value in performance_report.items():
            print(f"{key}: {value}")
        print("----------------------------------------------------")

        # 斷言至少發生了一筆交易，證明信號被正確處理
        self.assertGreater(performance_report["total_trades"], 0, "回測中沒有發生任何交易，請檢查因子參數或數據。")


if __name__ == "__main__":
    # 這使得我們可以從命令行直接運行這個整合測試
    unittest.main()
