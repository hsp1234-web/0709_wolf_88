import unittest
import subprocess
import duckdb
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import shutil
import os
import sys

# 確保專案根目錄在 sys.path 中，以便導入 config 和其他模組
# (與 run.py 類似的路徑校正邏輯，但更適用於測試腳本的上下文)
try:
    current_script_path = Path(__file__).resolve()
    # 假設此腳本在 apps/time_aggregator/ 下，根目錄是上三層
    project_root = current_script_path.parent.parent.parent
except NameError: # __file__ is not defined
    project_root = Path(os.getcwd()) # Fallback for some execution contexts

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 現在可以嘗試導入 config
try:
    import config
except ImportError:
    print("錯誤：無法導入 config.py。請確保 _test_time_aggregator_harness.py 的路徑設置正確，並且 config.py 位於專案根目錄。", file=sys.stderr)
    # 根據情況，可能需要 sys.exit(1) 或讓測試因導入失敗而失敗

# 從 time_aggregator/run.py 獲取支持的時間週期
# 這樣如果 run.py 中的定義改變，測試也能自動適應
try:
    from apps.time_aggregator.run import TIME_PERIODS
except ImportError:
    print("錯誤: 無法從 apps.time_aggregator.run 導入 TIME_PERIODS。請檢查路徑和檔案。", file=sys.stderr)
    # 如果無法導入，測試將無法正確運行，提供一個備用列表以允許框架繼續，但測試會失敗
    TIME_PERIODS = {
        "1min": "1T", "5min": "5T", "15min": "15T", "30min": "30T",
        "1h": "1H", "4h": "4H", "12h": "12H", "1d": "1D",
        "1w": "W-MON", "1m": "MS"
    }
    print("警告: 使用了備用的 TIME_PERIODS 定義。", file=sys.stderr)


class TestTimeAggregatorHarness(unittest.TestCase):
    TEST_SOURCE_DB_NAME = "test_harness_source_ticks.duckdb"
    TEST_ANALYTICS_DB_NAME = "test_harness_analytics_mart.duckdb"
    TEST_STOCK_ID = "TESTSTOCK001"
    TEMP_TEST_DIR_NAME = "temp_time_aggregator_test_output"

    @classmethod
    def setUpClass(cls):
        """在所有測試開始前執行一次，創建臨時測試目錄。"""
        cls.base_dir = Path(__file__).resolve().parent
        cls.temp_test_dir = cls.base_dir / cls.TEMP_TEST_DIR_NAME
        if cls.temp_test_dir.exists():
            shutil.rmtree(cls.temp_test_dir)
        cls.temp_test_dir.mkdir(parents=True, exist_ok=True)

        cls.source_db_path = cls.temp_test_dir / cls.TEST_SOURCE_DB_NAME
        cls.analytics_db_path = cls.temp_test_dir / cls.TEST_ANALYTICS_DB_NAME

        # 獲取 time_aggregator/run.py 的路徑
        # 假設 config.py 中的 TIME_AGGREGATOR_RUN_PATH 是正確的
        # 如果 config 無法導入，這一步會失敗
        if 'config' in sys.modules:
            cls.time_aggregator_run_script_path = config.TIME_AGGREGATOR_RUN_PATH
        else:
            # 備用路徑，如果 config 無法導入
            cls.time_aggregator_run_script_path = str(project_root / "apps" / "time_aggregator" / "run.py")
            print(f"警告: config 未能導入，TIME_AGGREGATOR_RUN_PATH 使用備用路徑: {cls.time_aggregator_run_script_path}", file=sys.stderr)


    @classmethod
    def tearDownClass(cls):
        """在所有測試結束後執行一次，清理臨時測試目錄。"""
        if cls.temp_test_dir.exists():
            print(f"清理臨時測試目錄: {cls.temp_test_dir}")
            shutil.rmtree(cls.temp_test_dir)
            pass

    def setUp(self):
        """每個測試方法執行前調用。"""
        # 確保每次測試開始時，資料庫是乾淨的
        if self.source_db_path.exists():
            self.source_db_path.unlink()
        if self.analytics_db_path.exists():
            self.analytics_db_path.unlink()

    def tearDown(self):
        """每個測試方法執行後調用。"""
        # 可以在此處添加額外的清理，如果需要的話
        pass

    def _create_dummy_source_db(self, stock_id: str, tick_data: list[tuple]):
        """
        創建包含虛擬 Tick 數據的源資料庫。
        tick_data: list of (timestamp_str, price, qty)
        """
        with duckdb.connect(str(self.source_db_path)) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS ticks (
                    timestamp TIMESTAMP,
                    product_id VARCHAR,
                    price DOUBLE,
                    qty BIGINT
                );
            """)
            # 準備插入數據，將 stock_id 添加到每條記錄中
            data_to_insert = [(row[0], stock_id, row[1], row[2]) for row in tick_data]
            con.executemany("INSERT INTO ticks VALUES (?, ?, ?, ?)", data_to_insert)
        print(f"已創建虛擬源資料庫 {self.source_db_path} 並為 {stock_id} 插入 {len(tick_data)} 筆 Tick 數據。")

    def _run_time_aggregator(self, stock_id: str, start_dt_str: str, end_dt_str: str) -> bool:
        """
        通過 subprocess 調用 time_aggregator/run.py。
        返回 True 表示成功 (exit code 0)，否則 False。
        """
        cmd = [
            sys.executable,  # 使用當前 Python 解釋器
            self.time_aggregator_run_script_path,
            stock_id,
            start_dt_str,
            end_dt_str,
            "--source_db", str(self.source_db_path),
            "--analytics_db", str(self.analytics_db_path)
        ]
        print(f"執行命令: {' '.join(cmd)}")
        try:
            process = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60, encoding='utf-8')
            if process.stdout:
                print(f"Time Aggregator STDOUT:\n{process.stdout}")
            if process.stderr:
                # 如果 stderr 有內容但返回碼為0，視為警告
                if process.returncode == 0:
                    print(f"Time Aggregator STDERR (但成功執行):\n{process.stderr}")
                else:
                    print(f"Time Aggregator STDERR:\n{process.stderr}")

            if process.returncode == 0:
                print("Time Aggregator 執行成功。")
                return True
            else:
                print(f"Time Aggregator 執行失敗，返回碼: {process.returncode}")
                return False
        except subprocess.TimeoutExpired:
            print("Time Aggregator 執行超時。")
            return False
        except Exception as e:
            print(f"執行 Time Aggregator 時發生未預期錯誤: {e}")
            return False

    # 後續將在此處添加測試用例，如 test_aggregation_various_timeframes

    def test_aggregation_various_timeframes(self):
        """
        測試核心聚合邏輯，包括表格創建和對 1min, 1d 週期的抽樣數據驗證。
        """
        tick_data = [
            ('2023-03-15 09:00:05', 100.0, 10), # T1
            ('2023-03-15 09:00:15', 102.0, 5),  # T2 (High)
            ('2023-03-15 09:00:25', 101.0, 8),  # T3
            ('2023-03-15 09:00:55', 99.0, 12),  # T4 (Low, Close for 09:00)
            ('2023-03-15 09:01:05', 99.5, 15),  # T5 (Open for 09:01)
            ('2023-03-15 09:01:35', 100.5, 20), # T6 (High, Close for 09:01)
            ('2023-03-15 10:30:00', 105.0, 30), # T7 (Different hour, contributes to day high/close)
            ('2023-03-16 13:00:00', 110.0, 25)  # T8 (Different day)
        ]
        start_datetime_str = "2023-03-15 00:00:00"
        # 結束時間需要包含 T8，所以設到 2023-03-16 之後，或 2023-03-17 00:00:00
        # run.py 的 end_date 是不包含的 (timestamp < end_date)
        end_datetime_str = "2023-03-17 00:00:00"

        self._create_dummy_source_db(self.TEST_STOCK_ID, tick_data)

        # 執行聚合
        run_success = self._run_time_aggregator(self.TEST_STOCK_ID, start_datetime_str, end_datetime_str)
        self.assertTrue(run_success, "Time Aggregator 腳本執行失敗。")

        # 連接到分析資料庫進行驗證
        self.assertTrue(self.analytics_db_path.exists(), f"分析資料庫 {self.analytics_db_path} 未創建。")
        with duckdb.connect(str(self.analytics_db_path), read_only=True) as con:
            # 1. 驗證所有預期的 OHLCV 表格是否已創建
            all_tables_in_db = con.execute("SHOW TABLES;").fetchdf()['name'].tolist()
            expected_ohlcv_tables = [f"ohlcv_{period_name}" for period_name in TIME_PERIODS.keys()]

            for table_name in expected_ohlcv_tables:
                self.assertIn(table_name, all_tables_in_db, f"預期表格 {table_name} 未在分析資料庫中找到。")
            print(f"成功驗證所有 {len(expected_ohlcv_tables)} 個 OHLCV 表格均已創建。")

            # 2. 抽樣驗證 ohlcv_1min 的數據
            try:
                ohlcv_1min_df = con.execute(f"SELECT * FROM ohlcv_1min WHERE product_id = '{self.TEST_STOCK_ID}' ORDER BY timestamp").fetchdf()
            except duckdb.CatalogException:
                self.fail("ohlcv_1min 表格不存在或查詢失敗。")

            self.assertFalse(ohlcv_1min_df.empty, "ohlcv_1min 表格中沒有 TESTSTOCK001 的數據。")

            # 預期 ohlcv_1min 結果
            expected_1min_data = [
                # Timestamp (as datetime), Open, High, Low, Close, Volume
                (pd.Timestamp('2023-03-15 09:00:00'), 100.0, 102.0, 99.0, 99.0, 35),
                (pd.Timestamp('2023-03-15 09:01:00'), 99.5, 100.5, 99.5, 100.5, 35),
                (pd.Timestamp('2023-03-15 10:30:00'), 105.0, 105.0, 105.0, 105.0, 30),
                (pd.Timestamp('2023-03-16 13:00:00'), 110.0, 110.0, 110.0, 110.0, 25),
            ]

            self.assertEqual(len(ohlcv_1min_df), len(expected_1min_data), "ohlcv_1min 數據筆數不匹配。")

            for i, expected_row in enumerate(expected_1min_data):
                actual_row = ohlcv_1min_df.iloc[i]
                self.assertEqual(pd.Timestamp(actual_row['timestamp']), expected_row[0], f"1min - Row {i} Timestamp 不匹配")
                self.assertAlmostEqual(actual_row['open'], expected_row[1], places=2, msg=f"1min - Row {i} Open 不匹配")
                self.assertAlmostEqual(actual_row['high'], expected_row[2], places=2, msg=f"1min - Row {i} High 不匹配")
                self.assertAlmostEqual(actual_row['low'], expected_row[3], places=2, msg=f"1min - Row {i} Low 不匹配")
                self.assertAlmostEqual(actual_row['close'], expected_row[4], places=2, msg=f"1min - Row {i} Close 不匹配")
                self.assertEqual(actual_row['volume'], expected_row[5], f"1min - Row {i} Volume 不匹配")
            print("成功驗證 ohlcv_1min 數據。")

            # 3. 抽樣驗證 ohlcv_1d 的數據
            try:
                ohlcv_1d_df = con.execute(f"SELECT * FROM ohlcv_1d WHERE product_id = '{self.TEST_STOCK_ID}' ORDER BY timestamp").fetchdf()
            except duckdb.CatalogException:
                self.fail("ohlcv_1d 表格不存在或查詢失敗。")

            self.assertFalse(ohlcv_1d_df.empty, "ohlcv_1d 表格中沒有 TESTSTOCK001 的數據。")

            expected_1d_data = [
                (pd.Timestamp('2023-03-15 00:00:00'), 100.0, 105.0, 99.0, 105.0, 100), # T1-T7
                (pd.Timestamp('2023-03-16 00:00:00'), 110.0, 110.0, 110.0, 110.0, 25),  # T8
            ]
            self.assertEqual(len(ohlcv_1d_df), len(expected_1d_data), "ohlcv_1d 數據筆數不匹配。")

            for i, expected_row in enumerate(expected_1d_data):
                actual_row = ohlcv_1d_df.iloc[i]
                self.assertEqual(pd.Timestamp(actual_row['timestamp']), expected_row[0], f"1d - Row {i} Timestamp 不匹配")
                self.assertAlmostEqual(actual_row['open'], expected_row[1], places=2, msg=f"1d - Row {i} Open 不匹配")
                self.assertAlmostEqual(actual_row['high'], expected_row[2], places=2, msg=f"1d - Row {i} High 不匹配")
                self.assertAlmostEqual(actual_row['low'], expected_row[3], places=2, msg=f"1d - Row {i} Low 不匹配")
                self.assertAlmostEqual(actual_row['close'], expected_row[4], places=2, msg=f"1d - Row {i} Close 不匹配")
                self.assertEqual(actual_row['volume'], expected_row[5], f"1d - Row {i} Volume 不匹配")
            print("成功驗證 ohlcv_1d 數據。")


if __name__ == '__main__':
    unittest.main()
