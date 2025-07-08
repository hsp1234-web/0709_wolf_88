# run_daily_pipeline.py
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
import sys
import time # 用於測量每個步驟的耗時
import os # 新增導入 os 模組

# 嘗試從 core 模組導入 config
try:
    from core import config
except ImportError:
    print("錯誤：無法從 core 導入 config。請確保 core/config.py 存在且專案結構正確。")
    sys.exit(1)

# --- 日誌設定 ---
# 使用 core.config 中定義的日誌級別
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
    # 確保 cmd_list 中的所有元素都是字串，以兼容 subprocess.run 和 str.join
    cmd_list_str = [str(item) for item in cmd_list]

    logger.info(f"開始執行 [{log_label}]: {' '.join(cmd_list_str)}")
    start_time = time.time()
    try:
        process = subprocess.run(
            cmd_list_str, # 使用轉換後的字串列表
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
        logger.error(f"[{log_label}] 命令未找到，請檢查路徑: {cmd_list_str[0]}") # 使用 cmd_list_str
        return False
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"[{log_label}] 執行時發生未預期錯誤 (耗時: {elapsed_time:.2f} 秒): {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

# --- 主流程函數 ---
def main_pipeline(args): # 添加 args 參數
    logger.info("開始執行每日自動化分析與報告生成流程...")
    if args.force_refresh:
        if isinstance(args.force_refresh, str):
            logger.warning(f"##### 強制刷新已啟用 (特定股票): {args.force_refresh} #####")
        else:
            logger.warning("##### 全局強制刷新已啟用! #####")

    # 讀取配置
    logger.info(f"統一目標列表 (TARGETS):")
    for target_info in config.TARGETS:
        logger.info(f"  - {target_info}")
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
    current_run_datetime = datetime.now()
    today_date_str = current_run_datetime.strftime("%Y-%m-%d")
    # 對於 time_aggregator，end_date 可以是更精確的時間戳
    aggregation_end_datetime_str = current_run_datetime.strftime("%Y-%m-%d %H:%M:%S")


    # --- [階段 1/5] 時間序列聚合 (Time Aggregator) ---
    # (此階段將變為 [階段 1/7])
    logger.info("====== [階段 1/7] 開始時間序列聚合 (Time Aggregator) ======")

    # 預設聚合起始偏移年數，優先使用專門為聚合配置的值
    agg_offset_years = getattr(config, 'DEFAULT_AGGREGATION_START_OFFSET_YEARS', config.YFINANCE_START_DATE_OFFSET_YEARS)
    default_agg_start_date = (current_run_datetime - timedelta(days=agg_offset_years * 365))

    # 根據是否有 force_refresh_stock_id 決定聚合哪些股票及起始日期
    targets_to_aggregate = []

    if args.force_refresh: # args 將從 main 函數傳入
        if isinstance(args.force_refresh, str): # 特定股票強制刷新
            # force_refresh 可能帶 .TW 也可能不帶，需要同時檢查 'id' 和 'yfinance_id'
            forced_stock_yfin_id = args.force_refresh if '.TW' in args.force_refresh else args.force_refresh + '.TW'
            forced_stock_plain_id = args.force_refresh.replace('.TW', '')

            found_target = None
            for target in config.TARGETS:
                if target['id'] == forced_stock_plain_id or target['yfinance_id'] == forced_stock_yfin_id:
                    found_target = target
                    break

            if found_target:
                targets_to_aggregate = [found_target]
                logger.info(f"強制刷新股票 {found_target['name']} ({found_target['id']})，將從 {default_agg_start_date.strftime('%Y-%m-%d %H:%M:%S')} 開始聚合。")
            else:
                logger.error(f"錯誤：--force-refresh 指定的股票ID '{args.force_refresh}' 不在 config.TARGETS 中。")
                pipeline_success = False
        else: # 全局強制刷新
            targets_to_aggregate = config.TARGETS
            logger.info(f"全局強制刷新，所有目標股票將從 {default_agg_start_date.strftime('%Y-%m-%d %H:%M:%S')} 開始聚合。")
    else: # 非強制刷新，也處理所有股票，time_aggregator 內部冪等性會處理
        targets_to_aggregate = config.TARGETS
        logger.info(f"標準執行，所有目標股票將從 {default_agg_start_date.strftime('%Y-%m-%d %H:%M:%S')} 開始聚合（由 time_aggregator 內部冪等性確保更新）。")

    if not pipeline_success:
        logger.warning("由於股票ID配置錯誤，跳過時間聚合階段。")
    else:
        for target in targets_to_aggregate:
            stock_id_for_agg = target['id'] # 使用不帶後綴的 ID for time_aggregator
            agg_start_date_str_for_cmd = default_agg_start_date.strftime("%Y-%m-%d %H:%M:%S")
            cmd_time_aggregator = [
                sys.executable, config.TIME_AGGREGATOR_RUN_PATH,
                stock_id_for_agg, # 傳遞 'id'
                agg_start_date_str_for_cmd,
                aggregation_end_datetime_str,
                "--source_db", config.SOURCE_TICKS_DB_PATH,
                "--analytics_db", config.ANALYTICS_DB_PATH
            ]
            if not run_subprocess_command(cmd_time_aggregator, f"time_aggregator ({stock_id_for_agg})"): # 修正變數名稱
                pipeline_success = False
                logger.error(f"time_aggregator ({stock_id_for_agg}) 執行失敗。後續分析可能受影響。") # 修正變數名稱
                # 考慮是否中止整個流程
    logger.info("====== [階段 1/7] 時間序列聚合完成 ======")


    # --- [階段 2/7] TAIFEX 原始數據載入 (TAIFEX Data Loader) ---
    logger.info("====== [階段 2/7] 開始 TAIFEX 原始數據載入 (TAIFEX Data Loader) ======")
    if not pipeline_success:
        logger.warning("由於前序階段失敗，可能影響 TAIFEX 原始數據載入。")
    else:
        # 確保 TAIFEX_RAW_DATA_DIR 存在
        if not Path(config.TAIFEX_RAW_DATA_DIR).is_dir():
            logger.warning(f"TAIFEX 原始數據目錄 {config.TAIFEX_RAW_DATA_DIR} 不存在或不是一個目錄。跳過 TAIFEX 數據載入。")
        else:
            ALLOWED_EXTENSIONS = {".zip", ".csv", ".txt", ".json", ".html"} # 參考指揮官工具
            taifex_files_to_process = []
            for root, _, files in os.walk(config.TAIFEX_RAW_DATA_DIR):
                for file in files:
                    if Path(file).suffix.lower() in ALLOWED_EXTENSIONS:
                        taifex_files_to_process.append(str(Path(root) / file))

            if not taifex_files_to_process:
                logger.info("在 TAIFEX_RAW_DATA_DIR 中沒有找到符合條件的檔案。")
            else:
                logger.info(f"找到 {len(taifex_files_to_process)} 個 TAIFEX 相關檔案進行處理。")
                # 確保 TAIFEX_RAW_DB_DIR 存在
                Path(config.TAIFEX_RAW_DB_DIR).mkdir(parents=True, exist_ok=True)

                for file_path in taifex_files_to_process:
                    cmd_taifex_loader = [
                        sys.executable, config.TAIFEX_DATA_PIPELINE_RUN_PATH,
                        "--input-files", file_path,
                        "--db-output-dir", config.TAIFEX_RAW_DB_DIR,
                        "--metadata-db-path", config.ANALYTICS_DB_PATH # 根據計畫書
                    ]
                    if not run_subprocess_command(cmd_taifex_loader, f"taifex_data_pipeline ({Path(file_path).name})"):
                        pipeline_success = False
                        logger.error(f"taifex_data_pipeline ({Path(file_path).name}) 執行失敗。")
                        # 決定是否中止，或允許部分失敗

    logger.info("====== [階段 2/7] TAIFEX 原始數據載入完成 ======")


    # --- [階段 3/7] TAIFEX 數據轉換 (TAIFEX Data Transformer) ---
    logger.info("====== [階段 3/7] 開始 TAIFEX 數據轉換 (TAIFEX Data Transformer) ======")
    if not pipeline_success:
        logger.warning("由於前序階段失敗，可能影響 TAIFEX 數據轉換。")
    else:
        raw_taifex_db_full_path = str(Path(config.TAIFEX_RAW_DB_DIR) / config.TAIFEX_RAW_DB_FILENAME)

        # 檢查原始 TAIFEX 資料庫檔案是否存在
        if not Path(raw_taifex_db_full_path).is_file():
            logger.warning(f"TAIFEX 原始資料庫檔案 {raw_taifex_db_full_path} 不存在。可能是因為 TAIFEX 數據載入階段沒有成功生成該檔案，或者沒有處理任何檔案。跳過 TAIFEX 數據轉換。")
        else:
            cmd_taifex_transformer = [
                sys.executable, config.TAIFEX_DATA_TRANSFORMER_RUN_PATH,
                "--raw-db-path", raw_taifex_db_full_path,
                "--analytics-db-path", config.ANALYTICS_DB_PATH
            ]
            if not run_subprocess_command(cmd_taifex_transformer, "taifex_data_transformer"):
                pipeline_success = False
                logger.error("taifex_data_transformer 執行失敗。")
    logger.info("====== [階段 3/7] TAIFEX 數據轉換完成 ======")


    # --- [階段 4/7] (原階段 2/5) 其他數據源獲取 (yfinance, FinMind) ---
    logger.info("====== [階段 4/7] 開始其他數據源獲取 (yfinance, FinMind) ======") # 更新階段編號
    if not pipeline_success:
        logger.warning("由於前序階段失敗或配置錯誤，可能影響其他數據源獲取。")

    # 1. yfinance_client (日線OHLCV)
    # 計算 yfinance 的起始日期
    yf_start_date = (current_run_datetime - timedelta(days=config.YFINANCE_START_DATE_OFFSET_YEARS * 365)).strftime("%Y-%m-%d")

    # 從 config.TARGETS 提取所有 yfinance_id
    yfinance_ids_for_client = [target['yfinance_id'] for target in config.TARGETS]

    cmd_yfinance = [
        sys.executable, config.YFINANCE_CLIENT_RUN_PATH,
        "--symbols", *yfinance_ids_for_client, # 傳遞 yfinance_id 列表
        "--start_date", yf_start_date,
        "--end_date", today_date_str, # 使用 today_date_str
        "--db_file", config.ANALYTICS_DB_PATH
    ]
    if not run_subprocess_command(cmd_yfinance, "yfinance_client"):
        pipeline_success = False
        logger.error("yfinance_client 執行失敗，後續分析可能受影響。")
        # 可以選擇在此處中止流程，或繼續執行其他步驟
        # return # 如果希望失敗時中止

    # 2. institutional_analyzer (法人籌碼)
    if config.FINMIND_API_TOKEN: # 只有在 Token 存在時才執行
        # 計算法人籌碼的起始日期
        inst_start_date = (current_run_datetime - timedelta(days=config.INSTITUTIONAL_START_DATE_OFFSET_MONTHS * 30)).strftime("%Y-%m-%d")
        for target in config.TARGETS: # 遍歷 TARGETS
            stock_id_for_fm = target['id'] # 使用 'id' (不帶 .TW)
            cmd_institutional = [
                sys.executable, config.INSTITUTIONAL_ANALYZER_RUN_PATH,
                "--stock-id", stock_id_for_fm,
                "--start-date", inst_start_date,
                "--end-date", today_date_str, # 使用 today_date_str
                "--api-token", config.FINMIND_API_TOKEN,
                "--db-path", config.ANALYTICS_DB_PATH
            ]
            if not run_subprocess_command(cmd_institutional, f"institutional_analyzer ({stock_id_fm})"):
                pipeline_success = False
                logger.warning(f"institutional_analyzer ({stock_id_fm}) 執行失敗。")
    else:
        logger.warning("未設定 FINMIND_API_TOKEN，跳過法人籌碼數據更新。")
    logger.info("====== [階段 4/7] 其他數據源獲取完成 ======") # 更新階段編號和日誌

    # --- [階段 5/7] (原階段 3/5) 核心分析 (Chimera) ---
    logger.info("====== [階段 5/7] 開始核心分析 (Chimera) ======") # 更新階段編號
    if pipeline_success: # 僅在前序階段成功或未被中止時執行
        # Chimera 分析的日期範圍可以不指定，讓它處理資料庫中所有可用數據
        # 或者指定一個與報告期相關的範圍
        chimera_start_date = (current_run_datetime - timedelta(days=config.REPORT_START_DATE_OFFSET_MONTHS * 30)).strftime("%Y-%m-%d") # 與報告期一致

        # config.CHIMERA_ANALYSIS_STOCK_IDS 已經在 config.py 中從 TARGETS 更新，所以這裡保持不變
        # 它會是 yfinance_id 的列表: [target['yfinance_id'] for target in TARGETS]
        cmd_feature_analyzer = [
            sys.executable, config.FEATURE_ANALYZER_RUN_PATH,
            "--run_chimera_analysis",
            "--analytics_mart_db", config.ANALYTICS_DB_PATH,
            "--stock_ids", *config.CHIMERA_ANALYSIS_STOCK_IDS, # 應已是 yfinance_id 列表
            "--start_date", chimera_start_date, # 新增 start_date
            "--end_date", today_date_str        # 新增 end_date (使用 today_date_str)
        ]
        if args.run_taifex_pc_ratio:
            cmd_feature_analyzer.append("--run_taifex_pc_ratio")
            if args.pc_ratio_products:
                cmd_feature_analyzer.extend(["--pc_ratio_products", *args.pc_ratio_products])

        if not run_subprocess_command(cmd_feature_analyzer, "feature_analyzer (Chimera & P/C Ratio)"):
            pipeline_success = False
            logger.error("feature_analyzer (Chimera) 執行失敗，報告生成可能受影響。")
    else:
        logger.warning("由於前序階段失敗，跳過核心分析 (Chimera)。")
    logger.info("====== [階段 5/7] 核心分析完成 ======") # 更新階段編號


    # --- [階段 6/7] (原階段 4/5) 報告生成 (Argus) ---
    logger.info("====== [階段 6/7] 開始報告生成 (Argus) ======") # 更新階段編號
    if pipeline_success:
        report_start_date = (current_run_datetime - timedelta(days=config.REPORT_START_DATE_OFFSET_MONTHS * 30)).strftime("%Y-%m-%d")
        default_report_timeframe = "1d" # 可配置或遍歷
        for target in config.TARGETS: # 遍歷 TARGETS
            stock_id_for_report = target['yfinance_id'] # 使用 'yfinance_id'
            cmd_report_generator = [
                sys.executable, config.REPORT_GENERATOR_RUN_PATH,
                "--stock-id", stock_id_for_report,
                "--start-date", report_start_date,
                "--end-date", today_date_str, # 使用 today_date_str
                "--db-path", config.ANALYTICS_DB_PATH,
                "--output-dir", config.REPORTS_OUTPUT_DIR,
                "--timeframe", default_report_timeframe # 已存在，很好
            ]
            if not run_subprocess_command(cmd_report_generator, f"report_generator ({stock_id_for_report}, {default_report_timeframe})"): # 修正變數名稱
                pipeline_success = False
                logger.warning(f"report_generator ({stock_id_for_report}, {default_report_timeframe}) 執行失敗。") # 修正變數名稱
    else:
        logger.warning("由於前序階段失敗，跳過報告生成。")
    logger.info(f"====== [階段 6/7] 報告生成完成 ======") # 更新階段編號


    # --- [階段 7/7] (原階段 5/5) 清理與總結 ---
    logger.info("====== [階段 7/7] 清理與總結 ======") # 更新階段編號
    if pipeline_success:
        logger.info("每日自動化分析與報告生成流程成功執行完畢。")
        return True
    else:
        logger.error("每日自動化分析與報告生成流程部分或全部執行失敗。請檢查以上日誌獲取詳細信息。")
        return False
    # 不再需要 final_message，因為函數會返回狀態


import argparse # 導入 argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="【克洛諾斯計畫】每日自動化分析與報告生成管線。")
    parser.add_argument(
        "--force-refresh",
        nargs='?', # 0 或 1 個參數
        const=True, # 如果沒有參數，則為 True (刷新全部)
        default=False, # 預設不刷新
        metavar="STOCK_ID", # 提示用戶可以指定股票ID
        help="強制重新聚合時間序列數據。若不指定 STOCK_ID，則刷新所有目標股票。若指定 STOCK_ID (例如 '2330' 或 '2330.TW')，則僅刷新該股票。"
    )
    # 新增參數給 feature_analyzer
    parser.add_argument(
        "--run_taifex_pc_ratio",
        action="store_true",
        help="執行 TAIFEX Put/Call Ratio 分析 (由 feature_analyzer 執行)。"
    )
    parser.add_argument(
        "--pc_ratio_products",
        nargs="+",
        default=['TXO'], # 預設計算 TXO
        help="要計算 P/C Ratio 的期交所選擇權商品代號列表 (例如 TXO TEO)。"
    )
    # 注意：run_pipeline.py 自身的 --stock_ids 控制 yfinance 和 institutional_analyzer 的目標
    # 而 feature_analyzer 的 --stock_ids 目前是從 config.CHIMERA_ANALYSIS_STOCK_IDS 獲取
    # 如果需要命令行完全控制，則 run_pipeline.py 也需要一個 --stock_ids_for_feature_analysis 參數

    args = parser.parse_args()

    # 檢查 config.py 是否能被正確加載和使用
    if 'PROJECT_ROOT' not in dir(config):
        logger.critical("config.py 未能正確加載或缺少必要配置。請檢查 config.py 的內容和位置。")
        sys.exit(1)

    logger.info(f"主控調度腳本啟動，使用配置文件: {config.__file__}")

    pipeline_status_ok = main_pipeline(args) # 將 args 傳遞給 main_pipeline

    if pipeline_status_ok:
        logger.info("主控調度腳本執行成功。")
        sys.exit(0)
    else:
        logger.error("主控調度腳本執行失敗。")
        sys.exit(1)
