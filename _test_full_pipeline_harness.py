# _test_full_pipeline_harness.py
import unittest
import subprocess
import sys
import os
from pathlib import Path
import shutil # 用於刪除目錄樹
import duckdb
from datetime import datetime, date, timedelta

# --- 測試配置 ---
# 假設此測試腳本位於專案根目錄
PROJECT_ROOT_FOR_TEST = Path(__file__).resolve().parent
TEST_CONFIG_FILENAME = "config_test_pipeline.py"
TEST_DB_NAME = "temp_pipeline_test_analytics_mart.duckdb"
TEST_REPORTS_DIR_NAME = "temp_pipeline_test_reports"

# 被測腳本
PIPELINE_SCRIPT_PATH = PROJECT_ROOT_FOR_TEST / "run_daily_pipeline.py"

class TestFullPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """在所有測試開始前，準備測試環境。"""
        cls.test_project_root = PROJECT_ROOT_FOR_TEST
        cls.test_db_path = cls.test_project_root / TEST_DB_NAME
        cls.test_reports_output_dir = cls.test_project_root / TEST_REPORTS_DIR_NAME

        # 1. 創建臨時的測試配置文件 (config_test_pipeline.py)
        cls.test_config_path = cls.test_project_root / TEST_CONFIG_FILENAME
        cls.mock_target_stocks_yfinance = ['MOCK.TW', 'TEST.TW']
        cls.mock_target_stocks_finmind = ['MOCK', 'TEST']

        # 確保測試時 FinMind API Token 為空，以測試跳過邏輯或模擬失敗
        # 如果需要測試真實 API 調用，則應在測試環境中設定 FINMIND_API_TOKEN
        # os.environ["FINMIND_API_TOKEN"] = "YOUR_TEST_TOKEN" # 如果需要
        original_finmind_token = os.environ.pop("FINMIND_API_TOKEN", None) # 暫時移除，測試後恢復
        cls.original_finmind_token = original_finmind_token

        # 從測試配置中讀取 REPORT_START_DATE_OFFSET_MONTHS 以供測試方法使用
        # 這裡我們硬編碼一個值，因為直接從字串解析 config_content 較麻煩
        # 理想情況下，config_test_pipeline.py 可以被導入並讀取其變數
        cls.test_report_offset_months = 1 # 必須與下面 config_content 中的值一致

        config_content = f"""
# Test config for full pipeline harness
import os
from pathlib import Path
import logging

PROJECT_ROOT = Path("{cls.test_project_root.as_posix()}") # 使用 as_posix() 確保路徑格式正確

TARGET_STOCK_IDS_YFINANCE = {cls.mock_target_stocks_yfinance}
TARGET_STOCK_IDS_FINMIND = {cls.mock_target_stocks_finmind}
CHIMERA_ANALYSIS_STOCK_IDS = TARGET_STOCK_IDS_YFINANCE # 確保測試配置中也定義此項

ANALYTICS_DB_NAME = "{TEST_DB_NAME}"
ANALYTICS_DB_PATH = str(PROJECT_ROOT / ANALYTICS_DB_NAME)

REPORTS_OUTPUT_DIR_NAME = "{TEST_REPORTS_DIR_NAME}"
REPORTS_OUTPUT_DIR = str(PROJECT_ROOT / REPORTS_OUTPUT_DIR_NAME)

LOG_LEVEL_STR = "DEBUG" # 測試時使用 DEBUG 級別
LOG_LEVEL = logging.DEBUG

FINMIND_API_TOKEN = os.getenv("FINMIND_API_TOKEN") # 測試時應為 None 或 mock token

# Paths to micro-app run scripts (use absolute paths based on test_project_root)
YFINANCE_CLIENT_RUN_PATH = str(PROJECT_ROOT / "apps" / "yfinance_client" / "run.py")
INSTITUTIONAL_ANALYZER_RUN_PATH = str(PROJECT_ROOT / "apps" / "institutional_analyzer" / "run.py")
FEATURE_ANALYZER_RUN_PATH = str(PROJECT_ROOT / "apps" / "feature_analyzer" / "run.py")
REPORT_GENERATOR_RUN_PATH = str(PROJECT_ROOT / "apps" / "report_generator" / "run.py")

YFINANCE_START_DATE_OFFSET_YEARS = 1 # 縮短測試數據範圍
INSTITUTIONAL_START_DATE_OFFSET_MONTHS = 2
REPORT_START_DATE_OFFSET_MONTHS = 1
SUBPROCESS_TIMEOUT = 60 # 縮短超時以利測試
"""
        with open(cls.test_config_path, "w", encoding="utf-8") as f:
            f.write(config_content)
        print(f"測試配置文件已創建: {cls.test_config_path}")

        # 2. 清理並創建臨時資料庫和報告目錄
        if cls.test_db_path.exists():
            cls.test_db_path.unlink()
        if cls.test_reports_output_dir.exists():
            shutil.rmtree(cls.test_reports_output_dir)
        cls.test_reports_output_dir.mkdir(parents=True, exist_ok=True)

        # 3. (可選) 預填充一些基礎數據到測試資料庫，模擬部分客戶端已運行
        # 這裡我們讓 yfinance_client 實際運行 (但用 mock ID，所以不會真的下載)
        # institutional_analyzer 會因為 FINMIND_API_TOKEN 未設定而跳過 (或失敗)
        # 這樣可以測試 pipeline 在某些步驟可能無數據或失敗時的行為
        # 我們需要確保 ohlcv_1d 和 chimera_daily_signals 表格的結構存在，即使是空的
        # 以便 feature_analyzer 和 report_generator 不會因為表不存在而失敗
        # 或者，我們可以在 setUp 中手動創建這些表結構
        try:
            with duckdb.connect(str(cls.test_db_path)) as con:
                # 創建 ohlcv_1d 表並插入少量 mock 數據
                # 數據的日期應該落在 report_generator 的查詢範圍內
                # report_generator 的 start_date 是 today - (REPORT_START_DATE_OFFSET_MONTHS * 30 天)
                # 測試配置中 REPORT_START_DATE_OFFSET_MONTHS = 1
                # 所以數據日期應該在 (今天 - 30天) 到 今天 之間
                con.execute("CREATE TABLE IF NOT EXISTS ohlcv_1d (timestamp TIMESTAMP, product_id VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT);")

                today = datetime.now()
                # 創建幾天內的數據，確保能被 report_generator 捕捉到
                mock_ohlcv_data = [
                    (today - timedelta(days=5), 'MOCK.TW', 100.0, 102.0, 99.0, 101.0, 1000),
                    (today - timedelta(days=4), 'MOCK.TW', 101.0, 103.0, 100.0, 102.0, 1200),
                    (today - timedelta(days=3), 'MOCK.TW', 102.0, 104.0, 101.0, 103.0, 1100),
                    (today - timedelta(days=2), 'MOCK.TW', 103.0, 105.0, 102.0, 104.0, 1300),
                    (today - timedelta(days=1), 'MOCK.TW', 104.0, 106.0, 103.0, 105.0, 1400),

                    (today - timedelta(days=5), 'TEST.TW', 50.0, 51.0, 49.5, 50.5, 500),
                    (today - timedelta(days=4), 'TEST.TW', 50.5, 52.0, 50.0, 51.5, 600),
                    (today - timedelta(days=3), 'TEST.TW', 51.5, 53.0, 51.0, 52.5, 550),
                    (today - timedelta(days=2), 'TEST.TW', 52.5, 54.0, 52.0, 53.5, 650),
                    (today - timedelta(days=1), 'TEST.TW', 53.5, 55.0, 53.0, 54.5, 700),
                ]
                con.executemany("INSERT INTO ohlcv_1d VALUES (?, ?, ?, ?, ?, ?, ?)", mock_ohlcv_data)
                print(f"已為 MOCK.TW 和 TEST.TW 插入最近幾日的 mock OHLCV 數據到 {cls.test_db_path}。")

                # 確保 institutional_trades 表存在 (institutional_analyzer 會創建，但這裡確保其存在以防萬一)
                # 由於 FinMind API token 未設，此表在 pipeline 運行中應該不會有 MOCK/TEST 的數據寫入
                con.execute("CREATE TABLE IF NOT EXISTS institutional_trades (date DATE, stock_id VARCHAR, investor_type VARCHAR, buy_shares BIGINT, sell_shares BIGINT, net_shares BIGINT, PRIMARY KEY (date, stock_id, investor_type));")

                # 確保 chimera_daily_signals 表存在 (feature_analyzer 會創建)
                # 我們也可以為 chimera_daily_signals 預填充一些與 ohlcv_1d 日期對應的數據，以確保 report_generator 有信號可畫
                con.execute("CREATE TABLE IF NOT EXISTS chimera_daily_signals (date DATE, stock_id VARCHAR, price_change_pct DOUBLE, volume_change_pct DOUBLE, price_volume_quadrant INTEGER, price_volume_label VARCHAR, total_net_shares BIGINT, institutional_flow_label VARCHAR, composite_signal VARCHAR, PRIMARY KEY (date, stock_id));")
                mock_chimera_data = [
                    ((today - timedelta(days=4)).date(), 'MOCK.TW', 1.0, 20.0, 1, "價漲量增", None, "籌碼未知", "價漲量增_籌碼未知"),
                    ((today - timedelta(days=3)).date(), 'MOCK.TW', 1.0, -10.0, 4, "價漲量縮", None, "籌碼未知", "價漲量縮_籌碼未知"),
                    ((today - timedelta(days=4)).date(), 'TEST.TW', 1.98, 20.0, 1, "價漲量增", None, "籌碼未知", "價漲量增_籌碼未知"),
                ]
                con.executemany("INSERT INTO chimera_daily_signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", mock_chimera_data)
                print(f"已為 MOCK.TW 和 TEST.TW 插入 mock Chimera 信號數據。")

            print(f"已準備測試資料庫 {cls.test_db_path} 並預填充了 ohlcv_1d 和 chimera_daily_signals 數據。")
        except Exception as e:
            print(f"準備測試資料庫及預填充數據時出錯: {e}")
            # 不在此處 sys.exit，讓測試框架處理

    @classmethod
    def tearDownClass(cls):
        """在所有測試結束後，清理測試環境。"""
        if cls.test_config_path.exists():
            cls.test_config_path.unlink()
            print(f"測試配置文件已刪除: {cls.test_config_path}")
        if cls.test_db_path.exists():
            cls.test_db_path.unlink()
            print(f"測試資料庫已刪除: {cls.test_db_path}")
        if cls.test_reports_output_dir.exists():
            shutil.rmtree(cls.test_reports_output_dir)
            print(f"測試報告目錄已刪除: {cls.test_reports_output_dir}")

        # 恢復原始的 FINMIND_API_TOKEN (如果有的話)
        if cls.original_finmind_token is not None:
            os.environ["FINMIND_API_TOKEN"] = cls.original_finmind_token
        elif "FINMIND_API_TOKEN" in os.environ: # 如果 setUp 時它不存在，但測試過程中被意外設定
            del os.environ["FINMIND_API_TOKEN"]


    def test_run_full_pipeline(self):
        """測試執行完整的 run_daily_pipeline.py 腳本。"""
        # 修改 run_daily_pipeline.py，使其能夠接受 --config 參數
        # 這裡我們假設 run_daily_pipeline.py 會自動尋找同目錄的 config.py
        # 或者，我們可以在執行時通過環境變數或其他方式指定要使用的配置文件
        # 為了簡單，測試時 run_daily_pipeline.py 將會導入 config_test_pipeline.py
        # 這需要在 run_daily_pipeline.py 中加入邏輯來處理這種情況，例如：
        # if os.getenv("TEST_MODE") == "PIPELINE_HARNESS":
        #     import config_test_pipeline as config
        # else:
        #     import config
        #
        # 一個更簡單的方法是，讓主控腳本接受一個配置文件路徑作為命令行參數。
        # 假設 run_daily_pipeline.py 現在支持 `--config` 參數 (需要在 run_daily_pipeline.py 中實現)
        # 如果 run_daily_pipeline.py 不支持，則此測試需要調整。
        #
        # 目前 run_daily_pipeline.py 是直接 `import config`。
        # 我們在 setUpClass 中創建了 config_test_pipeline.py，
        # 為了讓 run_daily_pipeline.py 加載它，我們需要臨時將其重命名為 config.py
        # 或者修改 run_daily_pipeline.py 使其可配置。
        #
        # 為了不修改 run_daily_pipeline.py 的導入邏輯，我們在測試時
        # 將 config_test_pipeline.py 複製/重命名為 config.py，測試結束後恢復/刪除。

        original_config_py_path = self.test_project_root / "config.py"
        temp_backup_config_py_path = self.test_project_root / "config.py.backup_harness"

        had_original_config = False
        if original_config_py_path.exists():
            had_original_config = True
            original_config_py_path.rename(temp_backup_config_py_path)
            print(f"已備份原始 config.py 至 {temp_backup_config_py_path}")

        try:
            shutil.copy(self.test_config_path, original_config_py_path)
            print(f"已將測試配置文件複製為 config.py")

            cmd = [sys.executable, str(PIPELINE_SCRIPT_PATH)]
            print(f"執行主控調度腳本: {' '.join(cmd)}")

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False, # 我們會檢查返回碼和日誌
                cwd=self.test_project_root, # 在專案根目錄下執行
                encoding='utf-8'
            )

            print("\n--- run_daily_pipeline.py STDOUT ---")
            print(process.stdout)
            print("\n--- run_daily_pipeline.py STDERR ---")
            print(process.stderr)

            # 基本驗證：主控腳本應成功退出 (返回碼 0)
            self.assertEqual(process.returncode, 0, "主控調度腳本執行失敗。")

            # 驗證報告是否已生成
            for stock_id in self.mock_target_stocks_yfinance:
                # 報告的日期範圍取決於 config_test_pipeline.py 中的 REPORT_START_DATE_OFFSET_MONTHS
                # 和當前日期。為了使測試穩定，我們需要一個固定的日期或更精確的日期計算。
                # 這裡簡化，只檢查檔案是否存在。
                # 檔案名格式：STOCKID_YYYYMMDD_YYYYMMDD_report.html
                # 我們需要知道 run_daily_pipeline.py 中如何計算報告的 start_date 和 end_date
                # 假設 end_date 是 today_str, start_date 是 today - offset
                today_for_report = datetime.now()
                # 使用 setUpClass 中設定的 TestFullPipeline.test_report_offset_months
                report_start_for_report = today_for_report - timedelta(days=TestFullPipeline.test_report_offset_months * 30)

                # 由於 run_daily_pipeline.py 內部使用 datetime.now()，測試時的日期會變化。
                # 為了穩定驗證檔案名，我們應該讓 run_daily_pipeline.py 能接受一個固定的“今日日期”作為參數，
                # 或者在測試中模擬/固定 datetime.now()。
                # 目前，我們先檢查是否有任何符合模式的報告檔案生成。

                report_found = False
                for item in self.test_reports_output_dir.iterdir():
                    if item.is_file() and item.name.startswith(stock_id) and item.name.endswith("_report.html"):
                        report_found = True
                        print(f"找到為 {stock_id} 生成的報告: {item.name}")
                        # 可以進一步驗證 HTML 內容，例如是否包含 Plotly 特徵
                        with open(item, 'r', encoding='utf-8') as f_report:
                            content = f_report.read()
                            self.assertTrue("plotly.js" in content or "Plotly.newPlot" in content,
                                            f"報告 {item.name} 未包含 Plotly 特徵字串。")
                        break
                self.assertTrue(report_found, f"未找到為股票 {stock_id} 生成的報告。")

            # （可選）驗證資料庫中 chimera_daily_signals 是否有數據
            # 這取決於 yfinance_client 是否能為 MOCK.TW, TEST.TW 獲取到數據
            # 由於 yfinance client 對無效股票代碼的處理方式（可能會報錯或返回空），
            # chimera 表中可能沒有數據。測試重點是流程能跑通。
            with duckdb.connect(str(self.test_db_path)) as con:
                for stock_id_yf in self.mock_target_stocks_yfinance:
                    count_result = con.execute(f"SELECT COUNT(*) FROM chimera_daily_signals WHERE stock_id = '{stock_id_yf}'").fetchone()
                    # 我們不強制要求一定有數據，因為 yfinance client 可能對 mock id 無法獲取數據
                    print(f"股票 {stock_id_yf} 在 chimera_daily_signals 中的記錄數: {count_result[0] if count_result else 0}")


        finally:
            # 恢復/清理 config.py
            if original_config_py_path.exists(): # 刪除測試用的 config.py
                original_config_py_path.unlink()
            if had_original_config and temp_backup_config_py_path.exists(): # 恢復原始的 config.py
                temp_backup_config_py_path.rename(original_config_py_path)
                print(f"已恢復原始 config.py")


if __name__ == "__main__":
    # 確保能找到 apps 目錄下的模組
    # (如果 _test_full_pipeline_harness.py 在根目錄，且 run_daily_pipeline.py 中的導入依賴於此)
    # 這段路徑校正通常放在被測腳本或測試腳本的頂部
    if str(PROJECT_ROOT_FOR_TEST) not in sys.path:
       sys.path.insert(0, str(PROJECT_ROOT_FOR_TEST))

    unittest.main()
