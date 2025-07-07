# run_daily_pipeline.py
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
import sys
import time # 用於測量每個步驟的耗時

# 嘗試從同級目錄的 config.py 導入配置
# 如果此腳本不在專案根目錄，或者 config.py 不在，則此導入會失敗
# 更好的做法是確保 config.py 能被 Python 解釋器找到
try:
    import config
except ImportError:
    print("錯誤：無法導入 config.py。請確保 config.py 與 run_daily_pipeline.py 在同一目錄，或者已正確設定 PYTHONPATH。")
    sys.exit(1)

# --- 日誌設定 ---
# 使用 config 中定義的日誌級別
logging.basicConfig(
    level=config.LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout) # 輸出到控制台
        # 可以考慮添加 FileHandler 以輸出到日誌檔案
        # logging.FileHandler(config.PROJECT_ROOT / "pipeline.log")
    ]
)
logger = logging.getLogger(__name__)

# --- 輔助函數：執行子進程命令 ---
def run_subprocess_command(cmd_list: list[str], log_label: str, timeout: int = config.SUBPROCESS_TIMEOUT) -> bool:
    """
    執行一個子進程命令，記錄其輸出，並返回成功與否。
    :param cmd_list: 命令及其參數列表。
    :param log_label: 用於日誌記錄的標籤。
    :param timeout: 命令超時時間 (秒)。
    :return: True 如果命令成功執行 (返回碼為0)，否則 False。
    """
    logger.info(f"開始執行 [{log_label}]: {' '.join(cmd_list)}")
    start_time = time.time()
    try:
        process = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            check=False, # 設置為 False，手動檢查返回碼
            timeout=timeout,
            encoding='utf-8' # 確保正確解碼中文輸出
        )
        elapsed_time = time.time() - start_time

        if process.stdout:
            logger.debug(f"[{log_label}] 標準輸出:\n{process.stdout}")
        if process.stderr:
            # 將 stderr 視為警告級別，除非返回碼不為0
            if process.returncode == 0:
                logger.warning(f"[{log_label}] 標準錯誤 (但成功執行):\n{process.stderr}")
            else:
                logger.error(f"[{log_label}] 標準錯誤:\n{process.stderr}")

        if process.returncode == 0:
            logger.info(f"[{log_label}] 成功完成 (耗時: {elapsed_time:.2f} 秒)。")
            return True
        else:
            logger.error(f"[{log_label}] 執行失敗，返回碼: {process.returncode} (耗時: {elapsed_time:.2f} 秒)。")
            return False

    except subprocess.TimeoutExpired:
        elapsed_time = time.time() - start_time
        logger.error(f"[{log_label}] 執行超時 (超過 {timeout} 秒，實際耗時: {elapsed_time:.2f} 秒)。")
        return False
    except FileNotFoundError:
        logger.error(f"[{log_label}] 命令未找到，請檢查路徑: {cmd_list[0]}")
        return False
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"[{log_label}] 執行時發生未預期錯誤 (耗時: {elapsed_time:.2f} 秒): {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

# --- 主流程函數 (稍後實現) ---
def main_pipeline():
    logger.info("開始執行每日自動化分析與報告生成流程...")

    # 步驟 c: 讀取配置 (部分已在頂層完成，這裡可以再次確認或加載特定於流程的)
    logger.info(f"目標股票 (yfinance): {config.TARGET_STOCK_IDS_YFINANCE}")
    logger.info(f"目標股票 (FinMind): {config.TARGET_STOCK_IDS_FINMIND}")
    logger.info(f"分析資料庫: {config.ANALYTICS_DB_PATH}")
    logger.info(f"報告輸出目錄: {config.REPORTS_OUTPUT_DIR}")
    if not config.FINMIND_API_TOKEN:
        logger.warning("FINMIND_API_TOKEN 未在環境變數中設定，法人籌碼分析可能失敗或使用限制數據。")

    # 確保報告輸出目錄存在
    Path(config.REPORTS_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    logger.info(f"已確認報告輸出目錄存在: {config.REPORTS_OUTPUT_DIR}")

    # 新增：檢查 yfinance 是否可導入
    try:
        import yfinance
        logger.debug(f"yfinance 套件已安裝 (版本: {yfinance.__version__ if hasattr(yfinance, '__version__') else '未知'})。")
    except ImportError:
        logger.critical("錯誤：必要的 'yfinance' 套件未安裝。請運行 'pip install yfinance' 來安裝它。")
        logger.critical("無法繼續執行 yfinance_client，流程中止。")
        sys.exit(1) # 中止流程

    pipeline_success = True
    today_str = datetime.now().strftime("%Y-%m-%d")

    # --- 步驟 e.i: 數據更新階段 ---
    logger.info("====== [階段 1/4] 開始數據更新 ======")

    # 1. yfinance_client (日線OHLCV)
    # 計算 yfinance 的起始日期
    yf_start_date = (datetime.now() - timedelta(days=config.YFINANCE_START_DATE_OFFSET_YEARS * 365)).strftime("%Y-%m-%d")
    cmd_yfinance = [
        sys.executable, config.YFINANCE_CLIENT_RUN_PATH,
        "--symbols", *config.TARGET_STOCK_IDS_YFINANCE,
        "--start_date", yf_start_date,
        "--end_date", today_str,
        "--db_file", config.ANALYTICS_DB_PATH # 修正: 參數名從 --db_path 改為 --db_file
    ]
    if not run_subprocess_command(cmd_yfinance, "yfinance_client"):
        pipeline_success = False
        logger.error("yfinance_client 執行失敗，後續分析可能受影響。")
        # 可以選擇在此處中止流程，或繼續執行其他步驟
        # return # 如果希望失敗時中止

    # 2. institutional_analyzer (法人籌碼)
    if config.FINMIND_API_TOKEN: # 只有在 Token 存在時才執行
        # 計算法人籌碼的起始日期
        inst_start_date = (datetime.now() - timedelta(days=config.INSTITUTIONAL_START_DATE_OFFSET_MONTHS * 30)).strftime("%Y-%m-%d")
        for stock_id_fm in config.TARGET_STOCK_IDS_FINMIND:
            cmd_institutional = [
                sys.executable, config.INSTITUTIONAL_ANALYZER_RUN_PATH,
                "--stock-id", stock_id_fm,
                "--start-date", inst_start_date,
                "--end-date", today_str,
                "--api-token", config.FINMIND_API_TOKEN,
                # institutional_analyzer 的 --analytics_mart_db 參數可能與 config.py 中的 ANALYTICS_DB_PATH 名稱不同
                # 假設其內部也使用 --db-path 或類似，或直接寫入 ANALYTICS_DB_PATH
                # 這裡我們假設它會使用 ANALYTICS_DB_PATH (需要確認其 run.py 參數)
                # 如果 institutional_analyzer 的 run.py 中 db path 參數是 --analytics_mart_db
                # 則用 "--analytics_mart_db", config.ANALYTICS_DB_PATH
                "--db-path", config.ANALYTICS_DB_PATH # 假設與 yfinance client 一致
            ]
            if not run_subprocess_command(cmd_institutional, f"institutional_analyzer ({stock_id_fm})"):
                pipeline_success = False # 記錄失敗，但繼續處理其他股票
                logger.warning(f"institutional_analyzer ({stock_id_fm}) 執行失敗。")
    else:
        logger.warning("未設定 FINMIND_API_TOKEN，跳過法人籌碼數據更新。")
    logger.info("====== [階段 1/4] 數據更新完成 ======")

    # --- 步驟 e.ii: 核心分析階段 (feature_analyzer - Chimera) ---
    logger.info("====== [階段 2/4] 開始核心分析 (Chimera) ======")
    # Chimera 分析的日期範圍可以不指定，讓它處理資料庫中所有可用數據
    # 或者指定一個與報告期相關的範圍
    # Chimera 的 stock_ids 參數是 --stock_ids (複數)
    cmd_feature_analyzer = [
        sys.executable, config.FEATURE_ANALYZER_RUN_PATH,
        "--run_chimera_analysis",
        "--analytics_mart_db", config.ANALYTICS_DB_PATH,
        "--stock_ids", *config.CHIMERA_ANALYSIS_STOCK_IDS # 使用 yfinance ID 列表
        # 可選: --start_date 和 --end_date，如果需要限定分析範圍
    ]
    if not run_subprocess_command(cmd_feature_analyzer, "feature_analyzer (Chimera)"):
        pipeline_success = False
        logger.error("feature_analyzer (Chimera) 執行失敗，報告生成可能受影響。")
        # return # 如果希望失敗時中止
    logger.info("====== [階段 2/4] 核心分析完成 ======")

    # --- 步驟 e.iii: 報告生成階段 (report_generator) ---
    logger.info("====== [階段 3/4] 開始報告生成 ======")
    # 計算報告的起始日期
    report_start_date = (datetime.now() - timedelta(days=config.REPORT_START_DATE_OFFSET_MONTHS * 30)).strftime("%Y-%m-%d")
    for stock_id_yf in config.TARGET_STOCK_IDS_YFINANCE: # 報告通常基於 yfinance 的 ID
        cmd_report_generator = [
            sys.executable, config.REPORT_GENERATOR_RUN_PATH,
            "--stock-id", stock_id_yf, # report_generator 使用的 stock_id
            "--start-date", report_start_date,
            "--end-date", today_str,
            "--db-path", config.ANALYTICS_DB_PATH,
            "--output-dir", config.REPORTS_OUTPUT_DIR
        ]
        if not run_subprocess_command(cmd_report_generator, f"report_generator ({stock_id_yf})"):
            pipeline_success = False # 記錄失敗，但繼續處理其他股票的報告
            logger.warning(f"report_generator ({stock_id_yf}) 執行失敗。")
    logger.info("====== [階段 3/4] 報告生成完成 ======")

    logger.info("====== [階段 4/4] 清理與總結 ======")
    if pipeline_success:
        logger.info("每日自動化分析與報告生成流程成功執行完畢。")
    else:
        logger.error("每日自動化分析與報告生成流程部分或全部執行失敗。請檢查以上日誌獲取詳細信息。")

    final_message = "所有流程已執行。"
    logger.info(final_message)
    # print(final_message) # 如果也想在 stdout 無視 logger 等級看到


if __name__ == "__main__":
    # 檢查 config.py 是否能被正確加載和使用
    if 'PROJECT_ROOT' not in dir(config):
        logger.critical("config.py 未能正確加載或缺少必要配置。請檢查 config.py 的內容和位置。")
        sys.exit(1)

    logger.info(f"主控調度腳本啟動，使用配置文件: {config.__file__}")

    main_pipeline() # 實際執行完整流程

    # 初步測試 run_subprocess_command (示例)
    # logger.info("--- 測試 run_subprocess_command ---")
    # test_cmd_success = run_subprocess_command(["echo", "subprocess測試成功"], "Echo測試(成功)")
    # logger.info(f"Echo測試(成功) 結果: {test_cmd_success}")
    # test_cmd_fail = run_subprocess_command(["ls", "/non_existent_path_for_testing_failure"], "ls測試(失敗)")
    # logger.info(f"ls測試(失敗) 結果: {test_cmd_fail}")
    # test_cmd_timeout = run_subprocess_command(["sleep", "5"], "Sleep測試(超時)", timeout=2)
    # logger.info(f"Sleep測試(超時) 結果: {test_cmd_timeout}")
    logger.info("--- run_subprocess_command 測試完畢 (已註解掉實際執行) ---")

    print("\n(主控調度腳本初步框架已設定，完整流程待 main_pipeline 函數實現)")
