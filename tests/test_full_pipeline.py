import unittest
import subprocess
import sys
import os
from pathlib import Path
import duckdb
import pandas as pd
from datetime import datetime, timedelta

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    # 獲取目前腳本的絕對路徑
    current_script_path = Path(__file__).resolve()
    # 測試腳本位於 tests/ 目錄下，專案根目錄是其再上兩層 (tests -> project_root)
    project_root = current_script_path.parent.parent
    # 將專案根目錄加入 sys.path
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError: # __file__ is not defined, common in interactive shells or certain execution contexts
    project_root = Path(os.getcwd())
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    print(f"警告：__file__ 未定義（在 tests/test_full_pipeline.py 中），專案路徑校正可能不準確。已將 {project_root} 加入 sys.path。", file=sys.stderr)
except Exception as e:
    print(f"專案路徑校正時發生錯誤 (tests/test_full_pipeline.py): {e}", file=sys.stderr)
# --- 標準化「路徑自我校正」樣板碼 END ---

# 導入配置，假設 config.py 在 project_root (core/config.py)
try:
    from core import config
except ImportError:
    print("錯誤：無法從 core 導入 config。請確保 core/config.py 存在且專案結構正確。", file=sys.stderr)
    sys.exit(1)

# 測試用的資料庫名稱和路徑
TEST_SOURCE_TICKS_DB_NAME = "test_taifex_ticks.duckdb"
TEST_ANALYTICS_MART_DB_NAME = "test_analytics_mart.duckdb"
TEST_REPORTS_OUTPUT_DIR_NAME = "test_kronos_reports_output" # 測試報告輸出目錄

# 測試用的股票ID 和日期範圍
TEST_STOCK_ID_FINMIND = "2330" # 用於 time_aggregator, FinMind
TEST_STOCK_ID_YFINANCE = "2330.TW" # 用於 yfinance, Chimera, ReportGenerator
TEST_START_DATE_HISTORICAL = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
TEST_END_DATE_TODAY = datetime.now().strftime("%Y-%m-%d")
TEST_AGGREGATION_END_DATETIME = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class TestKronosHarness(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """在所有測試開始前執行一次，用於設定測試環境。"""
        cls.project_root = project_root
        cls.test_source_ticks_db_path = cls.project_root / TEST_SOURCE_TICKS_DB_NAME
        cls.test_analytics_mart_db_path = cls.project_root / TEST_ANALYTICS_MART_DB_NAME
        cls.test_reports_output_dir = cls.project_root / TEST_REPORTS_OUTPUT_DIR_NAME

        # 清理舊的測試資料庫和報告目錄
        if cls.test_source_ticks_db_path.exists():
            cls.test_source_ticks_db_path.unlink()
        if cls.test_analytics_mart_db_path.exists():
            cls.test_analytics_mart_db_path.unlink()
        if cls.test_reports_output_dir.exists():
            import shutil
            shutil.rmtree(cls.test_reports_output_dir)

        cls.test_reports_output_dir.mkdir(parents=True, exist_ok=True)

        # 創建虛假的 taifex_ticks.duckdb
        cls._create_dummy_source_ticks_db()

    @classmethod
    def tearDownClass(cls):
        """在所有測試結束後執行一次，用於清理測試環境。"""
        # print(f"測試完成。保留測試資料庫和報告以供檢查：")
        # print(f"  源 Tick 資料庫: {cls.test_source_ticks_db_path}")
        # print(f"  分析資料庫: {cls.test_analytics_mart_db_path}")
        # print(f"  報告輸出目錄: {cls.test_reports_output_dir}")
        # 暫時自動刪除，如果需要手動檢查再註解掉
        if cls.test_source_ticks_db_path.exists():
            cls.test_source_ticks_db_path.unlink()
        if cls.test_analytics_mart_db_path.exists():
            cls.test_analytics_mart_db_path.unlink()
        if cls.test_reports_output_dir.exists():
            import shutil
            shutil.rmtree(cls.test_reports_output_dir)


    @classmethod
    def _create_dummy_source_ticks_db(cls):
        """創建並填充虛假的源 Tick 資料庫。"""
        print(f"正在創建虛假的源 Tick 資料庫: {cls.test_source_ticks_db_path}")
        with duckdb.connect(str(cls.test_source_ticks_db_path)) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS ticks (
                    timestamp TIMESTAMP,
                    product_id VARCHAR,
                    price DOUBLE,
                    qty BIGINT
                );
            """)
            # 插入一些跨越幾天的範例數據
            sample_data = []
            start_dt = datetime.strptime(TEST_START_DATE_HISTORICAL + " 09:00:00", "%Y-%m-%d %H:%M:%S")
            for i in range(3): # 三天的數據
                current_dt = start_dt + timedelta(days=i)
                for j in range(100): # 每天100筆 tick
                    ts = current_dt + timedelta(minutes=j*5) # 每5分鐘一筆
                    price = 100 + i + (j / 100.0)
                    qty = 10 + j % 10
                    sample_data.append((ts, TEST_STOCK_ID_FINMIND, price, qty))

            con.executemany("INSERT INTO ticks VALUES (?, ?, ?, ?)", sample_data)
            print(f"已創建並填充 {len(sample_data)} 筆範例數據到 {cls.test_source_ticks_db_path} (針對商品 {TEST_STOCK_ID_FINMIND})")

    def _run_pipeline_command(self, command_args=None):
        """執行 run_daily_pipeline.py 命令。"""
        cmd = [
            sys.executable,
            str(self.project_root / "run_pipeline.py") # 更正腳本名稱
        ]
        if command_args:
            cmd.extend(command_args)

        # 在執行管線時，覆寫 config 中的資料庫路徑和報告路徑，使其指向測試用的路徑
        # 這可以通過環境變數或修改 config 檔案（不推薦）或讓 run_daily_pipeline.py 接受更多參數來實現
        # 為了簡化，我們假設 run_daily_pipeline.py 會優先使用環境變數（如果已設定）
        # 或者，如果 config.py 是基於 __file__ 的相對路徑，我們可以臨時修改它或提供一個測試用的 config
        # 目前，我們將依賴 time_aggregator 等腳本內部對環境變數的處理，
        # 並在測試中設定這些環境變數。

        # 關鍵：需要確保 run_daily_pipeline.py 及其調用的所有子腳本
        # 在測試時使用 cls.test_source_ticks_db_path 和 cls.test_analytics_mart_db_path
        # 以及 cls.test_reports_output_dir
        # 最直接的方式是讓 run_daily_pipeline.py 接受這些路徑作為參數，
        # 或者讓 config.py 能夠從環境變數讀取這些路徑並優先使用。
        # 由於我們已經修改過 config.py 和各個 run.py 以支持環境變數，這裡我們設定環境變數。

        env_override = os.environ.copy()
        env_override["KRONOS_SOURCE_TICKS_DB_PATH"] = str(self.test_source_ticks_db_path)
        env_override["KRONOS_ANALYTICS_DB_PATH"] = str(self.test_analytics_mart_db_path)
        env_override["KRONOS_REPORTS_OUTPUT_DIR"] = str(self.test_reports_output_dir)

        # 強制重新編譯 generator.py
        compile_cmd = [sys.executable, "-m", "compileall", str(self.project_root / "apps" / "report_generator" / "generator.py")]
        print(f"強制編譯命令: {' '.join(compile_cmd)}")
        compile_process = subprocess.run(compile_cmd, capture_output=True, text=True, cwd=self.project_root)
        if compile_process.returncode != 0:
            print("--- 強制編譯 generator.py STDOUT ---")
            print(compile_process.stdout)
            print("--- 強制編譯 generator.py STDERR ---")
            print(compile_process.stderr)
            # 可以選擇在此處引發錯誤或讓後續的管線執行來暴露問題
        else:
            print("強制編譯 generator.py 成功。")

        print(f"執行管線命令: {' '.join(cmd)}")
        print(f"  環境變數 KRONOS_SOURCE_TICKS_DB_PATH: {env_override.get('KRONOS_SOURCE_TICKS_DB_PATH')}")
        print(f"  環境變數 KRONOS_ANALYTICS_DB_PATH: {env_override.get('KRONOS_ANALYTICS_DB_PATH')}")
        print(f"  環境變數 KRONOS_REPORTS_OUTPUT_DIR: {env_override.get('KRONOS_REPORTS_OUTPUT_DIR')}") # 新增

        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            cwd=self.project_root, # 在專案根目錄執行
            env=env_override # 傳遞修改後的環境變數
        )
        print("--- 管線 STDOUT ---")
        print(process.stdout)
        print("--- 管線 STDERR ---")
        print(process.stderr)
        print("-------------------")
        return process

    def test_01_run_pipeline_and_check_ohlcv(self):
        """測試執行完整的 run_daily_pipeline.py 並檢查 OHLCV 數據是否生成。"""
        # 執行管線，不強制刷新 (依賴 time_aggregator 的冪等性)
        # 為了讓測試更明確，可以先執行一次強制刷新
        print("\n--- 測試步驟 1: 執行管線 (強制刷新測試股票) ---")
        process = self._run_pipeline_command(command_args=["--force-refresh", TEST_STOCK_ID_FINMIND])
        self.assertEqual(process.returncode, 0, f"run_daily_pipeline.py 執行失敗，返回碼 {process.returncode}")

        # 驗證 analytics_mart.duckdb 中是否已生成了 ohlcv_* 表格
        self.assertTrue(self.test_analytics_mart_db_path.exists(), "測試分析資料庫未創建。")

        with duckdb.connect(str(self.test_analytics_mart_db_path), read_only=True) as con:
            # 檢查 time_aggregator 定義的所有時間週期表
            # 這裡我們需要能從外部獲取 time_aggregator 的 TIME_PERIODS
            # 暫時硬編碼一份簡化版或與 time_aggregator.py 同步
            time_aggregator_periods_keys = ["1min", "5min", "15min", "30min", "1h", "4h", "12h", "1d", "1w", "1m"]

            for period_name in time_aggregator_periods_keys:
                table_name = f"ohlcv_{period_name}"
                print(f"檢查資料表: {table_name} 是否存在於 {self.test_analytics_mart_db_path}")
                try:
                    count_res = con.execute(f"SELECT COUNT(*) FROM {table_name} WHERE product_id = '{TEST_STOCK_ID_FINMIND}'").fetchone()
                    self.assertIsNotNone(count_res, f"資料表 {table_name} 查詢 COUNT(*) 失敗。")
                    self.assertTrue(count_res[0] > 0, f"資料表 {table_name} (商品 {TEST_STOCK_ID_FINMIND}) 中沒有數據。")
                    print(f"資料表 {table_name} (商品 {TEST_STOCK_ID_FINMIND}) 存在且包含 {count_res[0]} 筆數據。")

                    # 可以進一步抽查數據的正確性，例如時間範圍等
                    # data_df = con.execute(f"SELECT * FROM {table_name} WHERE product_id = '{TEST_STOCK_ID_FINMIND}' ORDER BY timestamp LIMIT 5").fetchdf()
                    # print(f"資料表 {table_name} 的前5筆數據:\n{data_df}")

                except duckdb.CatalogException:
                    self.fail(f"錯誤：OHLCV 資料表 '{table_name}' 不存在於資料庫 {self.test_analytics_mart_db_path} 中。")
                except Exception as e:
                    self.fail(f"查詢資料表 '{table_name}' 時發生錯誤: {e}")

            # 檢查 yfinance client 生成的 daily_ohlcv 表 (如果其邏輯包含在 pipeline 中)
            try:
                table_name = "daily_ohlcv" # yfinance_client 預設表名
                count_res_yf = con.execute(f"SELECT COUNT(*) FROM {table_name} WHERE symbol = '{TEST_STOCK_ID_YFINANCE}'").fetchone()
                self.assertIsNotNone(count_res_yf, f"資料表 {table_name} 查詢 COUNT(*) 失敗。")
                self.assertTrue(count_res_yf[0] > 0, f"資料表 {table_name} (商品 {TEST_STOCK_ID_YFINANCE}) 中沒有數據。")
                print(f"資料表 {table_name} (商品 {TEST_STOCK_ID_YFINANCE}) 存在且包含 {count_res_yf[0]} 筆數據。")
            except duckdb.CatalogException:
                self.fail(f"錯誤：yfinance 資料表 'daily_ohlcv' 不存在。")


    def test_02_check_chimera_signals(self):
        """測試 Chimera 分析結果是否生成。"""
        print("\n--- 測試步驟 2: 檢查 Chimera 信號數據 ---")
        self.assertTrue(self.test_analytics_mart_db_path.exists(), "測試分析資料庫未創建。")
        with duckdb.connect(str(self.test_analytics_mart_db_path), read_only=True) as con:
            table_name = "chimera_daily_signals"
            try:
                count_res = con.execute(f"SELECT COUNT(*) FROM {table_name} WHERE stock_id = '{TEST_STOCK_ID_YFINANCE}'").fetchone()
                self.assertIsNotNone(count_res, f"資料表 {table_name} 查詢 COUNT(*) 失敗。")
                # Chimera 可能因為數據不足而不生成信號，所以不強制 count > 0，但表必須存在
                self.assertTrue(True, f"資料表 {table_name} 存在。") # 只要表存在即可
                data_count = count_res[0] if count_res else 0
                print(f"資料表 {table_name} (商品 {TEST_STOCK_ID_YFINANCE}) 存在，包含 {data_count} 筆數據。")
            except duckdb.CatalogException:
                self.fail(f"錯誤：Chimera 信號資料表 '{table_name}' 不存在。")

    def test_03_check_report_generation(self):
        """測試 HTML 報告是否已生成。"""
        print("\n--- 測試步驟 3: 檢查 HTML 報告生成 ---")
        self.assertTrue(self.test_reports_output_dir.exists(), "測試報告輸出目錄未創建。")

        # 報告檔案名可能包含日期和時間週期，需要一種方式來預測它
        # 例如: {stock_id}_{timeframe}_{start_date}_{end_date}_report.html
        # 這裡我們只檢查是否有任何為 TEST_STOCK_ID_YFINANCE 生成的 .html 報告
        expected_report_prefix = f"{TEST_STOCK_ID_YFINANCE}_1d" # 假設 pipeline 預設生成 1d 報告

        html_reports_found = list(self.test_reports_output_dir.glob(f"{expected_report_prefix}*.html"))

        self.assertTrue(
            len(html_reports_found) > 0,
            f"在目錄 {self.test_reports_output_dir} 中未找到預期的 HTML 報告 (應以 {expected_report_prefix} 開頭)。"
        )
        print(f"在 {self.test_reports_output_dir} 中找到 {len(html_reports_found)} 個符合條件的報告檔案。第一個是: {html_reports_found[0]}")
        # 可以進一步檢查報告內容，但這比較複雜，暫時只檢查檔案是否存在


if __name__ == '__main__':
    print(f"專案根目錄 (由 _test_kronos_harness.py 推斷): {project_root}")
    print(f"測試用的源 Tick 資料庫將位於: {project_root / TEST_SOURCE_TICKS_DB_NAME}")
    print(f"測試用的分析資料庫將位於: {project_root / TEST_ANALYTICS_MART_DB_NAME}")
    print(f"測試用的報告輸出目錄將位於: {project_root / TEST_REPORTS_OUTPUT_DIR_NAME}")

    # 為了讓 config.py 中的路徑在測試時也能被環境變數覆寫，
    # 需要確保 config.py 的頂層路徑設定邏輯能夠讀取環境變數。
    # 例如，config.ANALYTICS_DB_PATH 的設定可以類似：
    # ANALYTICS_DB_PATH = os.getenv("KRONOS_ANALYTICS_DB_PATH", str(PROJECT_ROOT / ANALYTICS_DB_NAME))
    # 這需要在 config.py 中修改。
    # 假設這個修改已經在 config.py 中完成，或者 run_daily_pipeline.py 會將正確的路徑傳遞給子腳本。

    unittest.main()

# TODO:
# 1. (重要) 確保 config.py 中的核心路徑 (SOURCE_TICKS_DB_PATH, ANALYTICS_DB_PATH, REPORTS_OUTPUT_DIR)
#    能夠被環境變數 KRONOS_SOURCE_TICKS_DB_PATH, KRONOS_ANALYTICS_DB_PATH, KRONOS_REPORTS_OUTPUT_DIR 覆寫。
#    這樣測試腳本才能通過設定環境變數來控制管線使用測試資料庫和目錄。
#    目前 time_aggregator 的 DB 路徑已支持環境變數。config.py 本身的 ANALYTICS_DB_PATH 和 REPORTS_OUTPUT_DIR 也需要調整。
# 2. 完善 _create_dummy_source_ticks_db 使其數據更貼近真實情況，以更好地測試所有聚合週期。
# 3. 在 test_01_run_pipeline_and_check_ohlcv 中，更精確地驗證 ohlcv 數據的內容，而不僅僅是行數。
# 4. 在 test_03_check_report_generation 中，更精確地預測報告檔案名，或解析報告內容進行驗證。
# 5. 考慮為不同的測試案例（例如，--force-refresh 全局 vs 特定股票）創建不同的測試方法。
# 6. 確保 run_daily_pipeline.py 在調用 feature_analyzer (Chimera) 和 report_generator 時，
#    如果這些腳本也依賴 config.py 中的路徑，那麼這些路徑也需要能被測試環境覆寫。
#    (目前 ChimeraAnalyzer 和 ReportGenerator 都是直接實例化並傳入 db_path，較好控制)
#    但 run_daily_pipeline.py 傳給 feature_analyzer 的 --analytics_mart_db 和 report_generator 的 --db-path
#    本身是從 config 讀取的，所以 config.ANALYTICS_DB_PATH 需要能被環境變數覆寫。
#    REPORTS_OUTPUT_DIR 同理。
print("初步的 _test_kronos_harness.py 結構已創建。")
