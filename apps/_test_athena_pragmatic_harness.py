# apps/_test_athena_pragmatic_harness.py
# 整合測試腳本，用於驗證雅典娜計畫 - 務實推進階段的服務協同工作。

import unittest
import subprocess
import duckdb
import pandas as pd
import os
from pathlib import Path
from datetime import datetime, timedelta

# --- 全局測試設定 ---
# 使用獨立的測試資料庫檔案，避免與開發/生產數據衝突
TEST_MARKET_DATA_DB = "test_market_data.duckdb"
TEST_ANALYTICS_MART_DB = "test_analytics_mart.duckdb"

# 測試用的小型樣本數據參數
YFINANCE_TEST_SYMBOLS = ['AAPL', '^GSPC'] # 少量代碼以加快測試
YFINANCE_TEST_START_DATE = (datetime.today() - timedelta(days=90)).strftime('%Y-%m-%d') # 過去約3個月的數據
YFINANCE_TEST_END_DATE = datetime.today().strftime('%Y-%m-%d')

# NYFED client 不需要特定符號或日期，它會抓取所有設定的數據
# Feature Analyzer 相關測試參數
CORRELATION_TEST_ASSETS = YFINANCE_TEST_SYMBOLS # 確保與 yfinance client 抓取的資產一致
CORRELATION_WINDOW = 20 # 使用較小的窗口以確保有足夠數據生成結果

class TestAthenaPragmaticHarness(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """在所有測試開始前執行一次，用於清理舊的測試資料庫。"""
        print("\n--- 初始化整合測試環境 ---")
        if os.path.exists(TEST_MARKET_DATA_DB):
            os.remove(TEST_MARKET_DATA_DB)
            print(f"已刪除舊的測試資料庫: {TEST_MARKET_DATA_DB}")
        if os.path.exists(TEST_ANALYTICS_MART_DB):
            os.remove(TEST_ANALYTICS_MART_DB)
            print(f"已刪除舊的測試資料庫: {TEST_ANALYTICS_MART_DB}")
        print("測試資料庫清理完畢。")

    def _run_subprocess(self, command: list[str]):
        """輔助函數：執行子進程並檢查返回碼。"""
        print(f"\n執行命令: {' '.join(command)}")
        process = subprocess.run(command, capture_output=True, text=True)
        print("STDOUT:")
        print(process.stdout)
        if process.stderr:
            print("STDERR:")
            print(process.stderr)
        self.assertEqual(process.returncode, 0, f"命令 {' '.join(command)} 執行失敗。")
        return process

    def test_1_run_yfinance_client(self):
        """步驟一（部分）：觸發 yfinance_client。"""
        print("\n--- 測試階段 1: 執行 yfinance_client ---")
        command = [
            "python", "-m", "apps.yfinance_client.run",
            "--symbols", *YFINANCE_TEST_SYMBOLS,
            "--start_date", YFINANCE_TEST_START_DATE,
            "--end_date", YFINANCE_TEST_END_DATE,
            "--db_file", TEST_MARKET_DATA_DB # 指向測試資料庫
        ]
        self._run_subprocess(command)
        self.assertTrue(os.path.exists(TEST_MARKET_DATA_DB), f"{TEST_MARKET_DATA_DB} 未被創建。")

        # 驗證數據抓取
        with duckdb.connect(TEST_MARKET_DATA_DB, read_only=True) as con:
            table_exists = con.execute("SELECT table_name FROM information_schema.tables WHERE table_name='daily_ohlcv';").fetchone()
            self.assertIsNotNone(table_exists, "'daily_ohlcv' 表未在測試資料庫中創建。")

            count_df = con.execute("SELECT COUNT(*) FROM daily_ohlcv;").fetchdf()
            self.assertGreater(count_df.iloc[0,0], 0, "'daily_ohlcv' 表中沒有數據。")

            symbols_in_db = con.execute("SELECT DISTINCT symbol FROM daily_ohlcv;").fetchdf()['symbol'].tolist()
            for sym in YFINANCE_TEST_SYMBOLS:
                self.assertIn(sym, symbols_in_db, f"商品 {sym} 未在 'daily_ohlcv' 表中找到。")
        print("yfinance_client 執行及數據驗證成功。")

    def test_2_run_nyfed_client(self):
        """步驟一（部分）：觸發 nyfed_client。"""
        print("\n--- 測試階段 2: 執行 nyfed_client ---")
        command = [
            "python", "-m", "apps.nyfed_client.run",
            "--db_file", TEST_MARKET_DATA_DB # 指向同一個測試 market_data 資料庫
        ]
        self._run_subprocess(command)
        self.assertTrue(os.path.exists(TEST_MARKET_DATA_DB), f"{TEST_MARKET_DATA_DB} 未被 nyfed_client 找到或創建。")

        # 驗證數據抓取
        with duckdb.connect(TEST_MARKET_DATA_DB, read_only=True) as con:
            table_exists = con.execute("SELECT table_name FROM information_schema.tables WHERE table_name='primary_dealer_positions';").fetchone()
            self.assertIsNotNone(table_exists, "'primary_dealer_positions' 表未在測試資料庫中創建。")

            count_df = con.execute("SELECT COUNT(*) FROM primary_dealer_positions;").fetchdf()
            self.assertGreater(count_df.iloc[0,0], 0, "'primary_dealer_positions' 表中沒有數據。")
        print("nyfed_client 執行及數據驗證成功。")

    def test_3_run_feature_analyzer_correlation(self):
        """步驟二和三（部分）：觸發 feature_analyzer 進行跨市場相關性分析並驗證結果。"""
        print("\n--- 測試階段 3: 執行 feature_analyzer (跨市場相關性分析) ---")

        # 在調用 feature_analyzer 之前，確保其引用的 DB 名稱與測試用 DB 名稱一致
        # 這需要修改 cross_market_analyzer.py 使其能夠接受 DB 路徑作為參數，或者在這裡臨時修改其全局變量
        # 為了簡化整合測試，我們假設 cross_market_analyzer.py 內部會被調整為可配置，
        # 或者我們確保它的預設輸入輸出與這裡的測試DB名匹配。
        # 目前 cross_market_analyzer.py 內部硬編碼了 MARKET_DATA_DB 和 ANALYTICS_MART_DB
        # 我們需要讓 feature_analyzer.run 能將測試DB路徑傳遞下去，或者修改 cross_market_analyzer.py
        # 暫時的解決方案：我們將在 feature_analyzer.run 中確保它能正確找到測試DB
        # (這通常意味著 cross_market_analyzer.py 需要從其調用者那裡獲取DB路徑)
        # 為了這個測試腳本，我們將依賴 cross_market_analyzer.py 使用它內部定義的常量名，
        # 但它會讀取由 yfinance_client 創建的 TEST_MARKET_DATA_DB，並寫入 TEST_ANALYTICS_MART_DB
        # 這需要 cross_market_analyzer.py 內部在被 feature_analyzer.run 調用時，
        # 能夠使用傳遞過來的或修改過的 DB 路徑。

        # 這裡的作戰命令是調用 feature_analyzer 的 run.py
        # 我們需要確保 feature_analyzer.cross_market_analyzer 內部的 DB 常量指向測試DB
        # 這是一個常見的整合測試挑戰。理想情況下，所有DB路徑都應可配置。
        # 為了推進，我們將先創建一個指向 TEST_ANALYTICS_MART_DB 的符號連結或複製，
        # 如果 feature_analyzer 硬編碼了 "analytics_mart.duckdb"。
        # 但更好的方式是修改 feature_analyzer.run 和其子模組，使其接受 db 路徑。

        # 假設 feature_analyzer.run 能夠正確地將 DB 操作導向測試DB
        # cross_market_analyzer.py 內部常量:
        # MARKET_DATA_DB = "market_data.duckdb" -> 應讀取 TEST_MARKET_DATA_DB
        # ANALYTICS_MART_DB = "analytics_mart.duckdb" -> 應寫入 TEST_ANALYTICS_MART_DB
        # 由於 feature_analyzer.run 還沒有相關參數，我們需要修改 cross_market_analyzer.py 的DB常量
        # 或者，更簡單的是，我們在這個測試腳本中臨時修改環境變數或 monkeypatch

        # 移除了 monkeypatching，現在通過命令列參數傳遞DB路徑
        command = [
            "python", "-m", "apps.feature_analyzer.run",
            "--run_correlation",
            "--market_data_db", TEST_MARKET_DATA_DB,
            "--analytics_mart_db", TEST_ANALYTICS_MART_DB
            # 注意：assets_to_analyze 和 window 參數需要傳遞給 feature_analyzer.run，
            # 然後由 run.py 再傳遞給 run_cross_market_correlation_analysis。
            # 目前 feature_analyzer.run 不支持這些參數。
            # 為了讓測試通過，我們需要確保 feature_analyzer.run 在調用時，
            # cross_market_analyzer.run_cross_market_correlation_analysis 使用了 YFINANCE_TEST_SYMBOLS
            # 和 CORRELATION_WINDOW。
            # 最直接的方法是修改 feature_analyzer.run 以接受這些參數，
            # 或者在測試中再次 monkeypatch cross_market_analyzer.CORE_ASSETS 和修改窗口。
            # 鑑於之前的重構是讓 run.py 傳遞 db 路徑，我們應該擴展它以傳遞分析特定參數。
            # 為了快速修復此測試，我將暫時在 cross_market_analyzer 中使用較小的資產列表
            # 或在 run.py 中修改傳給 run_cross_market_correlation_analysis 的 assets_to_analyze。
            # 這裡，我將修改測試，讓 feature_analyzer.run 的 correlation 分析部分使用 YFINANCE_TEST_SYMBOLS。
            # 這需要 feature_analyzer.run 能夠將 assets_to_analyze 和 window 參數傳下去。
            # 由於 run.py 尚未修改以接受這些，我將 monkeypatch cross_analyzer 的 CORE_ASSETS
            # 並在 run_cross_market_correlation_analysis 中修改 window 的預設值（或傳參）
            # 為了簡化，這裡先假設 feature_analyzer.run 內部會使用 YFINANCE_TEST_SYMBOLS。
            # (實際上，我們在 test_3 中直接調用 feature_analyzer.run，它內部會用 cma.CORE_ASSETS)
            # 我們需要的是 cma.CORE_ASSETS 在被 run.py 導入時就是 YFINANCE_TEST_SYMBOLS。
        ]

        # Monkeypatching CORE_ASSETS in cross_market_analyzer for this test
        import apps.feature_analyzer.cross_market_analyzer as cma
        original_core_assets = cma.CORE_ASSETS
        cma.CORE_ASSETS = YFINANCE_TEST_SYMBOLS # 使用 yfinance 下載的資產

        # Monkeypatching the window size in run_cross_market_correlation_analysis
        # This is more invasive. A better way is to allow run.py to pass it.
        # For now, we rely on CORRELATION_WINDOW being used if passed.
        # The run_cross_market_correlation_analysis needs to accept window.
        # Let's assume run.py's call to run_cross_market_correlation_analysis
        # will be updated to pass a window.
        # For this test, we will ensure the assets are correct. The window is 30 by default in cma.
        # The test uses CORRELATION_WINDOW = 20. We need to make sure this is used.

        # The best approach is to modify feature_analyzer.run to accept these.
        # Given current structure, the easiest fix is to ensure yfinance_client downloads data for cma.CORE_ASSETS
        # OR to ensure cma.run_cross_market_correlation_analysis is called with YFINANCE_TEST_SYMBOLS.
        # The latter is cleaner for the test.
        # The command already calls feature_analyzer.run.
        # The call inside run.py to run_cross_market_correlation_analysis uses cma.CORE_ASSETS.
        # So, monkeypatching cma.CORE_ASSETS before the subprocess run is the way here.
        # 更新：不再使用 monkeypatching，而是通過命令列參數傳遞

        # 準備命令，包含新的資產和窗口參數
        command_corr = [
            "python", "-m", "apps.feature_analyzer.run",
            "--run_correlation",
            "--market_data_db", TEST_MARKET_DATA_DB,
            "--analytics_mart_db", TEST_ANALYTICS_MART_DB,
            "--correlation_assets", *YFINANCE_TEST_SYMBOLS, # 使用測試定義的資產
            "--correlation_window", str(CORRELATION_WINDOW) # 使用測試定義的窗口
        ]
        self._run_subprocess(command_corr)

        self.assertTrue(os.path.exists(TEST_ANALYTICS_MART_DB), f"{TEST_ANALYTICS_MART_DB} 未被創建 (相關性分析)。")

        with duckdb.connect(TEST_ANALYTICS_MART_DB, read_only=True) as con:
            table_exists = con.execute("SELECT table_name FROM information_schema.tables WHERE table_name='cross_market_correlation';").fetchone()
            self.assertIsNotNone(table_exists, "'cross_market_correlation' 表未在測試分析資料庫中創建。")

            count_df = con.execute("SELECT COUNT(*) FROM cross_market_correlation;").fetchdf()
            self.assertGreater(count_df.iloc[0,0], 0, "'cross_market_correlation' 表中沒有數據。")
        print("feature_analyzer (跨市場相關性分析) 執行及數據驗證成功。")


    def test_4_run_feature_analyzer_dealer_analysis(self):
        """步驟二和三（部分）：觸發 feature_analyzer 進行一級交易商分析並驗證結果。"""
        print("\n--- 測試階段 4: 執行 feature_analyzer (一級交易商分析) ---")

        # 移除了 monkeypatching
        command = [
            "python", "-m", "apps.feature_analyzer.run",
            "--run_dealer_analysis",
            "--market_data_db", TEST_MARKET_DATA_DB,
            "--analytics_mart_db", TEST_ANALYTICS_MART_DB
        ]
        self._run_subprocess(command)
        self.assertTrue(os.path.exists(TEST_ANALYTICS_MART_DB), f"{TEST_ANALYTICS_MART_DB} 未被創建 (交易商分析)。")

        with duckdb.connect(TEST_ANALYTICS_MART_DB, read_only=True) as con:
            table_exists = con.execute("SELECT table_name FROM information_schema.tables WHERE table_name='primary_dealer_analysis';").fetchone()
            self.assertIsNotNone(table_exists, "'primary_dealer_analysis' 表未在測試分析資料庫中創建。")

            count_df = con.execute("SELECT COUNT(*) FROM primary_dealer_analysis;").fetchdf()
            self.assertGreater(count_df.iloc[0,0], 0, "'primary_dealer_analysis' 表中沒有數據。")
        print("feature_analyzer (一級交易商分析) 執行及數據驗證成功。")

    @classmethod
    def tearDownClass(cls):
        """在所有測試結束後執行一次，用於清理測試資料庫。"""
        print("\n--- 清理整合測試環境 ---")
        # 為了方便調試，可以選擇性地保留測試資料庫
        # if os.path.exists(TEST_MARKET_DATA_DB):
        #     os.remove(TEST_MARKET_DATA_DB)
        #     print(f"已刪除測試資料庫: {TEST_MARKET_DATA_DB}")
        # if os.path.exists(TEST_ANALYTICS_MART_DB):
        #     os.remove(TEST_ANALYTICS_MART_DB)
        #     print(f"已刪除測試資料庫: {TEST_ANALYTICS_MART_DB}")
        print(f"測試資料庫 {TEST_MARKET_DATA_DB} 和 {TEST_ANALYTICS_MART_DB} 已保留供檢查。")


if __name__ == '__main__':
    # 確保 PYTHONPATH 包含 apps 目錄的父目錄，以便模組能被正確找到
    # 在命令行中運行時，通常是從專案根目錄運行 python -m unittest apps._test_athena_pragmatic_harness
    # 或者直接運行 python apps/_test_athena_pragmatic_harness.py (如果 apps 在 PYTHONPATH 中)

    # 為了讓這個腳本可以直接 python apps/_test_athena_pragmatic_harness.py 運行
    # 我們需要將專案根目錄 (apps 的父目錄) 加入 sys.path
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent
    if str(project_root) not in os.sys.path:
         os.sys.path.insert(0, str(project_root))
         print(f"已將 {project_root} 加入 sys.path")

    unittest.main()
