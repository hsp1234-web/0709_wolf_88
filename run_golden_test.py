import subprocess
import sys
import os
from pathlib import Path
import shutil # For removing directory tree if needed for db path

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    project_root = Path(os.getcwd()).resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    print(f"警告：(run_golden_test.py) __file__ 未定義，專案路徑校正可能不準確。已將 {project_root} 加入 sys.path。", file=sys.stderr)
except Exception as e:
    print(f"專案路徑校正時發生錯誤 (run_golden_test.py): {e}", file=sys.stderr)
# --- 標準化「路徑自我校正」樣板碼 END ---

# 現在可以安全地導入 core.config 和 run_pipeline
try:
    from core import config as app_config # 使用別名以避免與此腳本中的變數衝突
    from core.utils import setup_logger # <--- 修正：直接從 core.utils 導入
    from run_pipeline import main_pipeline
    from golden_test_case.populate_mock_ohlcv import populate_ohlcv_1d
except ImportError as e:
    print(f"導入錯誤: {e}。請確保所有必要的模組和路徑都正確。", file=sys.stderr)
    sys.exit(1)

# 設定測試用的日誌
logger = setup_logger(__name__, level="INFO") # setup_logger 現在是直接從 core.utils 導入的

# --- 黃金測試案例配置 ---
GOLDEN_TEST_CASE_DIR = project_root / "golden_test_case"
MOCK_TAIFEX_RAW_DATA_DIR = GOLDEN_TEST_CASE_DIR / "taifex_raw_data"
POPULATE_MOCK_OHLCV_SCRIPT = GOLDEN_TEST_CASE_DIR / "populate_mock_ohlcv.py" # 未直接使用，而是導入函數

# 資料庫檔案將在專案根目錄創建/刪除，與 run_pipeline.py 的行為一致
TEST_ANALYTICS_DB_PATH = project_root / app_config.ANALYTICS_DB_NAME
# 確保源 TICK 資料庫存在 (即使是空的)，因為 time_aggregator 可能會嘗試連接它
# 為了此測試，我們主要關注 TAIFEX 和之後的流程，可以創建一個空的 mock tick db
MOCK_SOURCE_TICKS_DB_PATH = project_root / "mock_taifex_ticks.duckdb"

def prepare_environment():
    """準備測試環境"""
    logger.info("====== [黃金測試] 階段：準備環境 ======")

    # 1. 淨化作戰環境：刪除舊的 analytics_mart.duckdb
    if TEST_ANALYTICS_DB_PATH.exists():
        logger.info(f"正在刪除舊的測試資料庫: {TEST_ANALYTICS_DB_PATH}")
        try:
            TEST_ANALYTICS_DB_PATH.unlink()
        except OSError as e:
            logger.error(f"刪除資料庫 {TEST_ANALYTICS_DB_PATH} 失敗: {e}. 請檢查檔案權限或是否有其他程序正在使用它。")
            # 如果是目錄，嘗試用 shutil.rmtree (雖然 duckdb 通常是單一檔案)
            if TEST_ANALYTICS_DB_PATH.is_dir():
                try:
                    shutil.rmtree(TEST_ANALYTICS_DB_PATH)
                    logger.info(f"已成功刪除目錄: {TEST_ANALYTICS_DB_PATH}")
                except Exception as e_dir:
                    logger.error(f"嘗試刪除目錄 {TEST_ANALYTICS_DB_PATH} 失敗: {e_dir}")
                    sys.exit(1) # 無法清理，中止測試
            else:
                sys.exit(1) # 無法清理，中止測試


    logger.info(f"已確認測試資料庫 {TEST_ANALYTICS_DB_PATH} 不存在或已被刪除。")

    # 2. 準備目標股價數據：運行 populate_mock_ohlcv.py 中的函數
    logger.info(f"正在填充 0050.TW 的模擬 OHLCV 數據到 {TEST_ANALYTICS_DB_PATH}...")
    try:
        populate_ohlcv_1d(str(TEST_ANALYTICS_DB_PATH))
        logger.info("模擬 OHLCV 數據填充成功。")
    except Exception as e:
        logger.error(f"填充模擬 OHLCV 數據時發生錯誤: {e}")
        sys.exit(1)

    # 3. 創建一個空的 mock tick db，以避免 time_aggregator 出錯 (雖然此測試不依賴其產出)
    if not MOCK_SOURCE_TICKS_DB_PATH.exists():
        try:
            import duckdb
            with duckdb.connect(str(MOCK_SOURCE_TICKS_DB_PATH)) as con:
                con.execute("CREATE TABLE IF NOT EXISTS ticks (timestamp TIMESTAMP, product_id VARCHAR, price DOUBLE, volume BIGINT);")
            logger.info(f"已創建空的模擬源 Tick 資料庫: {MOCK_SOURCE_TICKS_DB_PATH}")
        except Exception as e:
            logger.warning(f"創建模擬源 Tick 資料庫失敗: {e}")

    # 4. 覆蓋 config 中的 TAIFEX_RAW_DATA_DIR 路徑
    #    最好的方法是通過修改 app_config 物件 (如果允許) 或設置環境變數
    #    這裡我們直接修改導入的 app_config 物件的屬性
    logger.info(f"將 TAIFEX_RAW_DATA_DIR 設置為: {MOCK_TAIFEX_RAW_DATA_DIR}")
    app_config.TAIFEX_RAW_DATA_DIR = str(MOCK_TAIFEX_RAW_DATA_DIR)
    # 同樣，確保 source_ticks_db_path 指向 mock 的，避免 time_aggregator 讀取真實數據或報錯
    app_config.SOURCE_TICKS_DB_PATH = str(MOCK_SOURCE_TICKS_DB_PATH)

    # 淨化 TAIFEX 原始數據庫
    # TAIFEX_RAW_DB_DIR 由 config 文件定義，通常是 project_root / "data" / "raw_taifex"
    # TAIFEX_RAW_DB_FILENAME 也是
    raw_taifex_db_path = Path(app_config.TAIFEX_RAW_DB_DIR) / app_config.TAIFEX_RAW_DB_FILENAME
    if raw_taifex_db_path.exists():
        logger.info(f"正在刪除舊的 TAIFEX 原始數據庫: {raw_taifex_db_path}")
        try:
            raw_taifex_db_path.unlink()
        except OSError as e:
            logger.error(f"刪除 TAIFEX 原始數據庫 {raw_taifex_db_path} 失敗: {e}.")
            # 可以考慮是否中止測試，取決於其重要性
            # sys.exit(1)
    else:
        logger.info(f"TAIFEX 原始數據庫 {raw_taifex_db_path} 不存在，無需刪除。")

    # 確保 TAIFEX 原始數據庫的目錄存在，因為 taifex_data_pipeline 會在那裡寫入
    Path(app_config.TAIFEX_RAW_DB_DIR).mkdir(parents=True, exist_ok=True)


    # 確保報告輸出目錄存在
    Path(app_config.REPORTS_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    logger.info(f"已確認報告輸出目錄存在: {app_config.REPORTS_OUTPUT_DIR}")
    logger.info("====== [黃金測試] 環境準備完畢 ======")

def run_test_pipeline():
    """運行修改後的管線進行測試"""
    logger.info("====== [黃金測試] 階段：執行管線 ======")

    # 構建傳遞給 main_pipeline 的參數
    # 我們需要確保 feature_analyzer 會運行以計算 P/C ratio
    # 並且 report_generator 會為 0050.TW 生成報告
    # run_pipeline.py 中的 argparse 參數：
    # --force-refresh (可選, 此處不需要特別強制，因為DB是新的)
    # --run_chimera_analysis_flag (觸發 Chimera price/volume/institutional flow)
    # --run_taifex_pc_ratio (觸發 P/C Ratio 計算)
    # --pc_ratio_products (P/C Ratio 的目標產品)

    # 模擬命令行參數
    # 注意：argparse 會將 '-' 轉換為 '_'。
    # run_pipeline.py 的 main_pipeline(args, main_logger)
    # run_pipeline.py 中的 parser.add_argument("--run_chimera_analysis_flag", action="store_true")
    # run_pipeline.py 中的 parser.add_argument("--run_taifex_pc_ratio", action="store_true")
    class Args:
        def __init__(self):
            self.force_refresh = False # 不需要強制刷新，因為是乾淨的DB
            self.run_chimera_analysis_flag = True # 需要運行 Chimera 才能讓 feature_analyzer 處理
            self.run_taifex_pc_ratio = True # 關鍵：確保 P/C Ratio 被計算
            self.pc_ratio_products = ['TXO'] # 測試目標是 TXO

    test_args = Args()

    # 執行主管線
    # main_pipeline 函數在 run_pipeline.py 中定義為 main_pipeline(args)
    pipeline_success = main_pipeline(test_args) # <--- 修正：只傳遞 test_args

    if pipeline_success:
        logger.info("====== [黃金測試] 管線執行成功 ======")
    else:
        logger.error("====== [黃金測試] 管線執行失敗 ======")
        sys.exit(1) # 管線失敗，測試不通過

def verify_results():
    """驗證測試結果"""
    logger.info("====== [黃金測試] 階段：驗證結果 ======")

    # 1. 檢查 HTML 報告是否生成
    # 報告檔名格式: {stock_id.replace('.','_')}_{timeframe}_{start_date}_{end_date}_report.html
    # 我們的模擬數據是 2023-01-01 到 2023-01-05 (OHLCV)
    # 報告的 start_date 由 config.REPORT_START_DATE_OFFSET_MONTHS 決定，
    # end_date 是當前日期。為了穩定測試，我們應該找到一個與模擬數據匹配的報告。
    # 由於 main_pipeline 使用 today_date_str 作為 end_date，
    # 且 REPORT_START_DATE_OFFSET_MONTHS 為 36，
    # 這意味著報告的日期範圍會很大。我們需要確保我們的模擬數據落在這個範圍內。

    # 我們的 OHLCV 數據是 2023-01-01 到 2023-01-05
    # 我們的 TAIFEX 數據是 2023-01-01 到 2023-01-05 (根據 CSV 檔案 OptionsDaily_TXO_20230101_20230105.csv)
    # ReportGenerator._fetch_data 會使用傳入的 start/end date
    # run_pipeline 傳給 ReportGenerator 的日期是：
    # report_start_date_argus = (current_run_datetime - timedelta(days=app_config.REPORT_START_DATE_OFFSET_MONTHS * 30)).strftime("%Y-%m-%d")
    # today_date_str

    report_dir = Path(app_config.REPORTS_OUTPUT_DIR)
    generated_report_path = None
    target_stock_id_fn_part = "0050_TW_1d" # ReportGenerator 產生的檔案名包含 '0050_TW_1d'

    if not report_dir.exists():
        logger.error(f"報告目錄 {report_dir} 不存在！測試失敗。")
        sys.exit(1)

    # 查找最新的 0050.TW 1d 報告
    latest_report_mtime = 0
    for item in report_dir.iterdir():
        if item.is_file() and target_stock_id_fn_part in item.name and item.name.endswith("_report.html"):
            try:
                mtime = item.stat().st_mtime
                if mtime > latest_report_mtime:
                    latest_report_mtime = mtime
                    generated_report_path = item
            except FileNotFoundError:
                logger.warning(f"檢查檔案 {item} 時發生 FileNotFoundError，可能檔案在迭代過程中被刪除。")
                continue # 跳過此檔案

    if generated_report_path:
        logger.info(f"找到最新的 0050.TW 1d HTML 報告: {generated_report_path}")
    else:
        logger.error(f"未能在 {report_dir} 中找到符合 '{target_stock_id_fn_part}' 的 HTML 報告。測試失敗。")
        logger.error("目錄內容:")
        for item in report_dir.iterdir(): logger.error(f" - {item.name}")
        sys.exit(1)

    # 2. 手動視覺確認提示
    logger.info("====== 【視覺確認任務】 ======")
    logger.info(f"請手動打開以下 HTML 報告檔案：")
    logger.info(f"檔案路徑: {generated_report_path.resolve()}")
    logger.info("請檢查以下內容：")
    logger.info("  1. 報告中是否包含一個標題為 \"Put/Call Ratio (TXO)\" 的子圖表。")
    logger.info("  2. 該圖表中是否顯示了基於模擬數據 (2023-01-01 至 2023-01-03) 計算出的 Put/Call Ratio 時間序列線圖。")
    logger.info("     應有 P/C Ratio (Volume) 和 P/C Ratio (OI) 的線條。")
    logger.info("  3. K線圖和成交量圖是否也正確顯示了 2023-01-01 至 2023-01-05 的模擬 0050.TW 數據。")
    logger.info("如果以上所有條件均滿足，則【視覺確認】行動成功。")
    logger.info("==============================")

if __name__ == "__main__":
    logger.info("##### 【行動代號：視覺確認】測試腳本啟動 #####")

    # 檢查必要的原始數據是否存在
    if not MOCK_TAIFEX_RAW_DATA_DIR.exists():
        logger.error(f"錯誤：模擬 TAIFEX 原始數據目錄 {MOCK_TAIFEX_RAW_DATA_DIR} 不存在！")
        logger.error("請確保已執行完畢作戰計畫的第一階段，並已創建相關的模擬 CSV 檔案。")
        sys.exit(1)
    if not POPULATE_MOCK_OHLCV_SCRIPT.exists(): # 雖然是導入函數，但原始腳本也應存在
         logger.error(f"錯誤：用於填充 OHLCV 數據的腳本 {POPULATE_MOCK_OHLCV_SCRIPT} 不存在！")
         sys.exit(1)

    prepare_environment()
    run_test_pipeline()
    verify_results()

    logger.info("##### 【行動代號：視覺確認】測試腳本執行完畢 #####")
    logger.info("請根據以上提示進行手動視覺確認。")
