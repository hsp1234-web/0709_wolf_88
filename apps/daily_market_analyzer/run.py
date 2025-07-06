# -*- coding: utf-8 -*-
"""
每日市場分析儀 主執行入口。

接收命令列參數，協調 YFinanceClient 進行數據擷取與考古，
使用 DBManager 將數據存入資料庫，透過 AnalysisEngine 分析數據，
最後使用 ReportGenerator 生成每日市場洞察報告。
"""
import argparse
import sys
import os
import shutil # Added for Local-First
from datetime import datetime
import pandas as pd
import csv # For hardware stats CSV
# import statistics # For hardware stats summary - will add to ReportGenerator instead

import psutil # 新增：用於偵測系統資源

# 設定專案路徑，確保可以正確匯入其他模組
def setup_project_path():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        # print(f"DEBUG: Project root added to sys.path: {project_root}") # 移除調試信息

setup_project_path()

try:
    from apps.daily_market_analyzer.yfinance_client import YFinanceClient
    from apps.daily_market_analyzer.db_manager import DBManager
    from apps.daily_market_analyzer.analysis_engine import AnalysisEngine
    from apps.daily_market_analyzer.report_generator import ReportGenerator
    # print("DEBUG: Successfully imported YFinanceClient, DBManager, AnalysisEngine, ReportGenerator") # 移除調試信息
except ModuleNotFoundError as e:
    print(f"錯誤：導入模組時發生錯誤 (ModuleNotFoundError): {e}") # 中文化
    # print(f"DEBUG: Current sys.path: {sys.path}") # 保留或移除調試信息
    # try:
    #     print(f"DEBUG: Contents of 'apps/': {os.listdir('apps')}")
    #     print(f"DEBUG: Contents of 'apps/daily_market_analyzer/': {os.listdir('apps/daily_market_analyzer')}")
    # except FileNotFoundError:
    #     print("DEBUG: 'apps/' or 'apps/daily_market_analyzer/' directory not found from current working directory.")
    raise

def main():
    """
    主執行函數 for Daily Market Analyzer。
    """
    parser = argparse.ArgumentParser(description="每日市場洞察報告與智能數據考古引擎。")
    # 核心參數
    parser.add_argument("--tickers", help="要分析的標的列表，以逗號分隔 (例如: AAPL,MSFT)。在純報告模式下非必需，但若提供則用於報告。")
    parser.add_argument("--start-date", help="數據分析/獲取的起始日期 (格式: YYYY-MM-DD)。")
    parser.add_argument("--end-date", help="數據分析/獲取的結束日期 (格式: YYYY-MM-DD)。")

    # 流程控制參數
    parser.add_argument("--data-only", action="store_true", help="僅執行數據獲取和存儲流程。")
    parser.add_argument("--report-only", action="store_true", help="僅執行報告生成流程 (需要已存在的數據)。")
    parser.add_argument("--report-start-date", help="報告生成的起始日期 (格式: YYYY-MM-DD)，配合 --report-only 使用。")
    parser.add_argument("--report-end-date", help="報告生成的結束日期 (格式: YYYY-MM-DD)，配合 --report-only 使用。")

    # 資料庫與表格參數
    parser.add_argument("--db-path", default="data_workspace/daily_market_analyzer.duckdb",
                        help="主分析資料庫的完整路徑 (例如: data_workspace/daily_market_analysis.duckdb)。")
    parser.add_argument("--db-name", default="daily_market_analysis.duckdb", # 實際已較少直接使用，db_path 更為主要
                        help="主分析資料庫的檔案名稱 (參考用，主要以 db_path 為準)。")
    parser.add_argument("--cache-db-path",
                        help="DuckDB 快取資料庫的最終存檔路徑 (目前 yfinance_client 直接使用主DB進行快取檢查)。") # 說明其當前用途
    parser.add_argument("--table-name", default="market_ohlcv_data",
                        help="資料庫中儲存 OHLCV 數據的表格名稱。")
    parser.add_argument("--process-uploads", action="store_true",
                        help="若指定，則處理 'uploads' 資料夾 (此功能待實現)。")
    parser.add_argument("--no_data_cooldown_days", type=int, default=7,
                        help="「無數據區塊」記錄的有效冷卻天數。預設為 7 天。")
    parser.add_argument("--force-refresh", action="store_true",
                        help="強制刷新數據，忽略快取 (針對 yfinance_client)。")
    # --- Local-First Workflow ---
    parser.add_argument("--enable-local-first", action="store_true",
                        help="啟用本地優先工作流程，將資料庫複製到本地處理。")
    parser.add_argument("--gdrive-root", default="/content/drive/MyDrive/", # Typical Colab GDrive mount
                        help="Google Drive 的根路徑。")
    parser.add_argument("--project-path-local", default="/content/panoramic_market_analyzer/", # As per plan
                        help="專案在本地 Colab 儲存的根路徑。")
    # --- Parallel YFinance ---
    parser.add_argument("--max-workers", type=int, default=16, # Default from plan
                        help="YFinance 並行數據抓取的最大工作進程數。")

    args = parser.parse_args()

    # --- Local-First: Path Definitions ---
    # args.db_path is the source of truth from GDrive if local-first is enabled.
    gdrive_db_path = args.db_path  # This is the original path, assumed to be on GDrive
    local_db_path_instance = None  # Full path to the local copy of the DB

    # This flag will be dynamically updated if local-first setup fails
    # We use a local copy of the arg to allow modification inside main()
    active_local_first_mode = args.enable_local_first

    if active_local_first_mode:
        if not gdrive_db_path: # Check if original db_path was provided
            print("錯誤 (Local-First): 啟用 --enable-local-first 時，必須提供 --db-path 作為 Google Drive 上的原始資料庫路徑。")
            sys.exit(1)

        db_filename = os.path.basename(gdrive_db_path)
        if not db_filename:
            print(f"錯誤 (Local-First): 無法從 --db-path '{gdrive_db_path}' 推斷資料庫檔案名稱。")
            active_local_first_mode = False # Fallback
        else:
            # Construct local path as per plan: <PROJECT_PATH_LOCAL>/data_workspace/databases_local/<db_filename>
            local_db_dir = os.path.join(args.project_path_local, "data_workspace", "databases_local")
            local_db_path_instance = os.path.join(local_db_dir, db_filename)
            print(f"INFO (Local-First): Configured for local processing. Local DB will be: {local_db_path_instance}")

    # Determine the path to be used for DBManager initialization *before* the try block
    # This path might change inside the try block if initial copy fails.
    # So, final_db_manager_path is better determined *inside* the try, before DBManager init.

    # Overall script timer
    overall_start_time = datetime.now()
    print("--- 每日市場洞察報告引擎 v33.0 ---")
    print(f"任務開始時間: {overall_start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Initialize db_manager to None for the finally block
    db_manager = None
    # This will hold the path DBManager was actually initialized with
    # Needs to be defined before try block for access in finally, even if try fails early.
    final_db_path_used_by_dbmanager = gdrive_db_path
    if active_local_first_mode and local_db_path_instance:
        final_db_path_used_by_dbmanager = local_db_path_instance # Tentative, might change if copy fails

    # --- Hardware Stats Collection ---
    hardware_stats_list = []
    def log_hardware_stats(stage_name: str):
        try:
            cpu_percent = psutil.cpu_percent(interval=None) # Non-blocking
            ram_percent = psutil.virtual_memory().percent
            hardware_stats_list.append({
                "timestamp": datetime.now().isoformat(),
                "stage": stage_name,
                "cpu_percent": cpu_percent,
                "ram_percent": ram_percent
            })
            print(f"DEBUG (Hardware Stats): Logged for stage '{stage_name}'. CPU: {cpu_percent}%, RAM: {ram_percent}%")
        except Exception as e:
            print(f"警告: 記錄硬體狀態失敗: {e}")

    log_hardware_stats("main_start")

    try:
        # --- Parameter Validation (moved after path setup, before main logic) ---
        if args.data_only and args.report_only:
            print("錯誤：--data-only 和 --report-only 選項不能同時指定。")
            sys.exit(1)
        if args.report_only:
            if not args.report_start_date or not args.report_end_date:
                print("錯誤：當使用 --report-only 時，必須提供 --report-start-date 和 --report-end-date。")
                sys.exit(1)
            if not args.tickers:
                print("錯誤：當使用 --report-only 時，必須提供 --tickers。")
                sys.exit(1)
        elif not args.data_only: # Full flow
            if not args.tickers or not args.start_date or not args.end_date:
                print("錯誤：在完整流程模式下，必須提供 --tickers, --start-date, 和 --end-date。")
                sys.exit(1)
        elif args.data_only: # Data only
             if not args.tickers or not args.start_date or not args.end_date:
                print("錯誤：當使用 --data-only 時，必須提供 --tickers, --start-date, 和 --end-date。")
                sys.exit(1)

        # --- Dynamic DuckDB Memory Configuration ---
        db_config = {}
        try:
            available_bytes = psutil.virtual_memory().available
            available_gb = available_bytes / (1024**3)
            mem_limit_gb = min(available_gb * 0.7, 12.0)
            mem_limit_gb = max(mem_limit_gb, 0.25)
            memory_limit_mb = int(mem_limit_gb * 1024)
            memory_limit_setting_str = f"{memory_limit_mb}MB"
            db_config = {'memory_limit': memory_limit_setting_str}
            print(f"INFO: 動態設定 DuckDB memory_limit 為: {memory_limit_setting_str} (基於 {available_gb:.2f} GB 可用記憶體)")
        except Exception as e:
            print(f"警告: 偵測系統可用記憶體或設定 DuckDB 組態時發生錯誤: {e}。將使用 DuckDB 預設記憶體配置。")

        # --- Local-First: On Startup Copy (if active_local_first_mode is true) ---
        if active_local_first_mode and local_db_path_instance and gdrive_db_path:
            print(f"INFO (Local-First): '本地優先' 模式已啟用。")
            print(f"INFO (Local-First): 原始資料庫 (GDRIVE): {gdrive_db_path}")
            print(f"INFO (Local-First): 本地目標資料庫: {local_db_path_instance}")

            local_db_dir_for_copy = os.path.dirname(local_db_path_instance) # Renamed to avoid conflict
            if not os.path.exists(local_db_dir_for_copy):
                try:
                    os.makedirs(local_db_dir_for_copy, exist_ok=True)
                    print(f"INFO (Local-First): 已建立本地資料庫目錄: {local_db_dir_for_copy}")
                except Exception as e:
                    print(f"錯誤 (Local-First): 建立本地資料庫目錄 '{local_db_dir_for_copy}' 失敗: {e}。停用本地優先模式。")
                    active_local_first_mode = False

            if active_local_first_mode: # Re-check if directory creation was successful
                if os.path.exists(gdrive_db_path):
                    try:
                        copy_start_time = datetime.now()
                        print(f"INFO (Local-First) [{copy_start_time.strftime('%H:%M:%S')}]: 開始複製資料庫從 GDrive '{gdrive_db_path}' 到本地 '{local_db_path_instance}'...")
                        total_size = os.path.getsize(gdrive_db_path)
                        print(f"INFO (Local-First): 待複製檔案大小: {total_size / (1024*1024):.2f} MB.")

                        shutil.copy2(gdrive_db_path, local_db_path_instance)

                        copy_end_time = datetime.now()
                        copied_size = os.path.getsize(local_db_path_instance)
                        duration_seconds = (copy_end_time - copy_start_time).total_seconds()
                        print(f"INFO (Local-First) [{copy_end_time.strftime('%H:%M:%S')}]: 資料庫複製到本地完成。耗時: {duration_seconds:.2f} 秒。本地檔案大小: {copied_size / (1024*1024):.2f} MB.")
                        final_db_path_used_by_dbmanager = local_db_path_instance # Success, confirm local path
                    except Exception as e:
                        copy_fail_time = datetime.now()
                        print(f"錯誤 (Local-First) [{copy_fail_time.strftime('%H:%M:%S')}]: 從 GDrive 複製資料庫失敗: {e}。停用本地優先模式。")
                        active_local_first_mode = False
                else:
                    print(f"警告 (Local-First): GDrive 上的原始資料庫檔案 '{gdrive_db_path}' 不存在。將嘗試在本地路徑 '{local_db_path_instance}' 建立新資料庫。")
                    final_db_path_used_by_dbmanager = local_db_path_instance # New DB will be local

        # If local_first_mode was disabled due to an error, fall back to gdrive_db_path
        if not active_local_first_mode:
            final_db_path_used_by_dbmanager = gdrive_db_path
            print(f"INFO (Local-First Fallback): 本地優先模式已停用或初始化失敗。將使用資料庫: {final_db_path_used_by_dbmanager}")

        # --- Initialize Core Components ---
        print(f"INFO: 初始化 DBManager，資料庫路徑: {final_db_path_used_by_dbmanager}")
        db_manager = DBManager(db_path=final_db_path_used_by_dbmanager, duckdb_config=db_config)
        analysis_engine = AnalysisEngine(db_manager_instance=db_manager)

        overall_execution_log = {}
        tickers_list = []
        if args.tickers:
            tickers_list = [ticker.strip().upper() for ticker in args.tickers.split(',')]
        task_duration_seconds = 0

        # --- Main Execution Logic ---
        if args.data_only:
            print(f"執行模式：僅數據處理。資料庫: {final_db_path_used_by_dbmanager}")
            log_hardware_stats("data_pipeline_start")
            yf_client = YFinanceClient(db_manager=db_manager, no_data_cooldown_days=args.no_data_cooldown_days)
            overall_execution_log, _ = run_data_pipeline(args, db_manager, yf_client, tickers_list)
            log_hardware_stats("data_pipeline_end")
        elif args.report_only:
            print(f"執行模式：僅報告生成。資料庫: {final_db_path_used_by_dbmanager}")
            args.start_date = args.report_start_date
            args.end_date = args.report_end_date
            log_hardware_stats("report_generation_start")
            run_report_generation(args, db_manager, analysis_engine, {}, tickers_list, overall_start_time, 0, hardware_stats_list)
            log_hardware_stats("report_generation_end")
        else: # Full flow
            print(f"執行模式：完整流程。資料庫: {final_db_path_used_by_dbmanager}")
            log_hardware_stats("data_pipeline_start")
            yf_client = YFinanceClient(db_manager=db_manager, no_data_cooldown_days=args.no_data_cooldown_days)
            data_pipeline_start_time = datetime.now()
            overall_execution_log, _ = run_data_pipeline(args, db_manager, yf_client, tickers_list)
            data_pipeline_end_time = datetime.now()
            task_duration_seconds = (data_pipeline_end_time - data_pipeline_start_time).total_seconds()
            log_hardware_stats("data_pipeline_end")

            log_hardware_stats("report_generation_start")
            run_report_generation(args, db_manager, analysis_engine, overall_execution_log, tickers_list, overall_start_time, task_duration_seconds, hardware_stats_list)
            log_hardware_stats("report_generation_end")

        log_hardware_stats("main_end")
        final_overall_end_time = datetime.now()
        total_script_duration = (final_overall_end_time - overall_start_time).total_seconds()
        print(f"\n--- 總任務執行完畢 ---")
        print(f"總體結束時間: {final_overall_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"腳本總執行時長: {total_script_duration:.2f} 秒")

    finally:
        # --- Local-First: On Shutdown Writeback ---
        # active_local_first_mode reflects if the local DB *should* have been used and *was* successfully set up.
        # local_db_path_instance is the path to the local DB if it was configured.
        # gdrive_db_path is the original GDrive path.
        print(f"DEBUG (Finally): active_local_first_mode={active_local_first_mode}, local_db_path_instance={local_db_path_instance}")

        if active_local_first_mode and local_db_path_instance and gdrive_db_path:
            # Explicitly release DB connection if DBManager has one
            if db_manager and hasattr(db_manager, '_conn') and getattr(db_manager, '_conn', None) is not None:
                print(f"INFO (Local-First): 嘗試關閉 DBManager 連線以釋放檔案鎖...")
                try:
                    # DuckDB connections are often managed by 'with' or closed on garbage collection.
                    # Explicitly deleting the manager might help ensure the file is released.
                    del db_manager
                    print(f"INFO (Local-First): DBManager 實例已刪除。")
                except Exception as e:
                    print(f"警告 (Local-First): 關閉/刪除 DBManager 時發生錯誤: {e}")

            if os.path.exists(local_db_path_instance):
                try:
                    writeback_start_time = datetime.now()
                    print(f"INFO (Local-First) [{writeback_start_time.strftime('%H:%M:%S')}]: 開始將本地資料庫 '{local_db_path_instance}' 回寫到 GDrive '{gdrive_db_path}'...")

                    gdrive_db_dir_for_writeback = os.path.dirname(gdrive_db_path)
                    if gdrive_db_dir_for_writeback and not os.path.exists(gdrive_db_dir_for_writeback):
                        os.makedirs(gdrive_db_dir_for_writeback, exist_ok=True)
                        print(f"INFO (Local-First): 已建立 GDrive 上的目標目錄 (回寫時): {gdrive_db_dir_for_writeback}")

                    local_size_for_wb = os.path.getsize(local_db_path_instance)
                    print(f"INFO (Local-First): 待回寫本地檔案大小: {local_size_for_wb / (1024*1024):.2f} MB.")

                    shutil.copy2(local_db_path_instance, gdrive_db_path)

                    writeback_end_time = datetime.now()
                    duration_seconds_wb = (writeback_end_time - writeback_start_time).total_seconds()
                    # Verifying GDrive file size might be slow/unreliable immediately
                    print(f"INFO (Local-First) [{writeback_end_time.strftime('%H:%M:%S')}]: 資料庫成功回寫到 GDrive '{gdrive_db_path}'。耗時: {duration_seconds_wb:.2f} 秒。")
                except Exception as e:
                    writeback_fail_time = datetime.now()
                    print(f"錯誤 (Local-First) [{writeback_fail_time.strftime('%H:%M:%S')}]: 回寫資料庫到 GDrive 失敗: {e}")
            else:
                print(f"警告 (Local-First): 本地資料庫檔案 '{local_db_path_instance}' 不存在於預期路徑，無法回寫。")
        elif args.enable_local_first: # Original intent was local, but it might have failed
             print(f"INFO (Local-First): 本地優先模式最初啟用，但可能在設置或執行過程中被停用/失敗。跳過回寫。")

        # --- Archive Hardware Stats ---
        if hardware_stats_list:
            run_timestamp_str = overall_start_time.strftime('%Y%m%d_%H%M%S')
            archive_hardware_stats_to_csv(
                hardware_stats_list,
                args, # Pass args to derive paths
                run_timestamp_str,
                gdrive_db_path # Pass gdrive_db_path to help determine GDrive project root
            )


# --- Helper function for archiving hardware stats ---
def archive_hardware_stats_to_csv(stats_list: list, cli_args: argparse.Namespace, timestamp_str: str, base_gdrive_path_ref: str | None):
    if not stats_list:
        print("INFO (Hardware Archive): No hardware stats collected to archive.")
        return

    # Define archive paths
    local_log_archive_base = os.path.join(cli_args.project_path_local, "data_workspace", "logs", "archive")

    # Try to make GDrive archive path relative to the project on GDrive
    # If gdrive_db_path was "foo/bar/data_workspace/db.duckdb", then log archive would be "foo/bar/data_workspace/logs/archive"
    gdrive_log_archive_base = None
    if base_gdrive_path_ref:
        # Navigate up from data_workspace/db_file.duckdb to data_workspace, then add /logs/archive
        gdrive_project_data_workspace = os.path.dirname(base_gdrive_path_ref) # data_workspace
        if os.path.basename(gdrive_project_data_workspace) == "databases_local" and "data_workspace" in gdrive_project_data_workspace : # if path is like .../data_workspace/databases_local
             gdrive_project_data_workspace = os.path.dirname(gdrive_project_data_workspace) # Get .../data_workspace

        if "data_workspace" in gdrive_project_data_workspace: # Check if "data_workspace" is in the path
            gdrive_log_archive_base = os.path.join(gdrive_project_data_workspace, "logs", "archive")
        else: # Fallback if path structure is unexpected
            gdrive_log_archive_base = os.path.join(cli_args.gdrive_root, "panoramic_market_analyzer_logs", "archive")
            print(f"WARN (Hardware Archive): Could not determine GDrive project structure from '{base_gdrive_path_ref}'. Using fallback GDrive log path: {gdrive_log_archive_base}")
    else: # Fallback if gdrive_db_path was not available
        gdrive_log_archive_base = os.path.join(cli_args.gdrive_root, "panoramic_market_analyzer_logs", "archive")
        print(f"WARN (Hardware Archive): GDrive DB path not available. Using fallback GDrive log path: {gdrive_log_archive_base}")

    filename = f"hardware_monitor_report_{timestamp_str}.csv"
    local_filepath = os.path.join(local_log_archive_base, filename)
    gdrive_filepath = os.path.join(gdrive_log_archive_base, filename)

    fieldnames = ["timestamp", "stage", "cpu_percent", "ram_percent"]

    # Write to local file
    try:
        os.makedirs(local_log_archive_base, exist_ok=True)
        with open(local_filepath, 'w', newline='', encoding='utf-8') as f_local:
            writer = csv.DictWriter(f_local, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(stats_list)
        print(f"INFO (Hardware Archive): Hardware stats successfully saved to local: {local_filepath}")
    except Exception as e:
        print(f"錯誤 (Hardware Archive): 儲存硬體狀態到本地 '{local_filepath}' 失敗: {e}")

    # Write to GDrive file (if different from local, e.g. not a local-only run)
    # This assumes GDrive path is writable.
    if local_filepath != gdrive_filepath : # Avoid writing twice to same location if project_path_local is on GDrive
        try:
            os.makedirs(gdrive_log_archive_base, exist_ok=True) # Ensure GDrive archive dir exists
            with open(gdrive_filepath, 'w', newline='', encoding='utf-8') as f_gdrive:
                writer = csv.DictWriter(f_gdrive, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(stats_list)
            print(f"INFO (Hardware Archive): Hardware stats successfully saved to GDrive: {gdrive_filepath}")
        except Exception as e:
            print(f"錯誤 (Hardware Archive): 儲存硬體狀態到 GDrive '{gdrive_filepath}' 失敗: {e}")


def run_data_pipeline(args, db_manager: DBManager, yf_client: YFinanceClient, tickers_list: list):
    """
    執行數據獲取、處理和存儲的流程。
    """
    print("\n--- 開始數據處理流程 ---")
    pipeline_start_time = datetime.now()

    # 確保資料表存在
    db_manager.create_ohlcv_table(table_name=args.table_name) # Called once before parallel processing

    current_overall_execution_log = {}

    if not tickers_list:
        print("警告 (run_data_pipeline): 標的列表為空，無法執行數據流程。")
        return {}, []

    from concurrent.futures import ProcessPoolExecutor, as_completed

    print(f"INFO (run_data_pipeline): 開始並行獲取 {len(tickers_list)} 個標的的市場數據，使用最多 {args.max_workers} 個工作進程。")

    # To map futures back to ticker symbols for logging results
    future_to_ticker = {}

    with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        for ticker_symbol in tickers_list:
            print(f"INFO (Parallel Dispatch): 分派標的 {ticker_symbol} 進行數據處理...")
            # yf_client.hydrate_data_range is a synchronous method that handles its own DB operations.
            # It's crucial that DBManager's methods (like connect) are process-safe.
            # DuckDB connections via `with duckdb.connect(...)` are generally safe as they are opened and closed per call.
            future = executor.submit(
                yf_client.hydrate_data_range,
                ticker_symbol,
                args.start_date,
                args.end_date,
                db_table_name=args.table_name,
                force_refresh=args.force_refresh
            )
            future_to_ticker[future] = ticker_symbol

        for future in as_completed(future_to_ticker):
            ticker_symbol_for_log = future_to_ticker[future]
            try:
                hydrated_df, ticker_execution_log = future.result() # Returns tuple (DataFrame | None, dict)

                if ticker_execution_log:
                    # Merge logs: ticker_execution_log is dict[date_str, dict[ticker_sym, log_detail]]
                    for date_key, daily_log_for_all_tickers_on_date in ticker_execution_log.items():
                        if date_key not in current_overall_execution_log:
                            current_overall_execution_log[date_key] = {}
                        current_overall_execution_log[date_key].update(daily_log_for_all_tickers_on_date)

                # Logging based on the outcome for this specific ticker
                if hydrated_df is not None and not hydrated_df.empty:
                    print(f"INFO (Parallel Result): 標的 {ticker_symbol_for_log} 並行處理成功。擷取 {len(hydrated_df)} 筆數據。日誌已合併。")
                elif hydrated_df is not None and hydrated_df.empty : # No error, but no data (e.g. fully cached, or truly no data for range)
                    print(f"INFO (Parallel Result): 標的 {ticker_symbol_for_log} 並行處理完成。未獲取到新數據。日誌已合併。")
                else: # hydrated_df is None, which implies an error or complete failure for this ticker in hydrate_data_range
                    print(f"警告 (Parallel Result): 標的 {ticker_symbol_for_log} 並行處理返回 None DataFrame。請檢查合併後的日誌以了解詳情。")

            except Exception as exc:
                print(f"錯誤 (Parallel Task): 標的 {ticker_symbol_for_log} 的並行任務執行失敗: {exc}")
                # Create a generic error log entry for this ticker for all relevant dates
                # This indicates an unexpected error not handled within hydrate_data_range's return log.
                for date_str_key_for_error in pd.date_range(args.start_date, args.end_date).strftime('%Y-%m-%d'):
                    if date_str_key_for_error not in current_overall_execution_log:
                        current_overall_execution_log[date_str_key_for_error] = {}
                    current_overall_execution_log[date_str_key_for_error][ticker_symbol_for_log] = {
                        'status': 'parallel_task_exception',
                        'interval': None,
                        'count': 0,
                        'message': f"並行任務執行失敗: {exc}"
                    }
        print(f"INFO (run_data_pipeline): 所有並行標的數據獲取任務已完成處理。")

    pipeline_end_time = datetime.now()
    pipeline_duration_seconds = (pipeline_end_time - pipeline_start_time).total_seconds()
    print(f"\n--- 數據處理流程結束 ---")
    print(f"數據流程執行時長: {pipeline_duration_seconds:.2f} 秒")

    return current_overall_execution_log, tickers_list


def run_report_generation(args, db_manager: DBManager, analysis_engine: AnalysisEngine,
                          input_execution_log: dict, report_tickers_list: list,
                          report_overall_start_time: datetime, data_task_duration_seconds: float,
                          hardware_stats: list[dict]): # Added hardware_stats
    """
    執行報告生成的流程。
    """
    print("\n--- 開始報告生成流程 ---")
    report_pipeline_start_time = datetime.now()

    # 如果是 report-only 模式，tickers_list 可能需要從 args 重新獲取
    # 但已在 main 函數中將 args.tickers 賦予 tickers_list，並傳遞給 report_tickers_list
    if not report_tickers_list:
         print("警告 (run_report_generation): 標的列表為空，無法生成報告。")
         return

    # ReportGenerator 初始化時可以傳入空的 execution_log，它主要用於記錄數據獲取過程。
    # 在 report-only 模式下，這個 log 可能不包含數據獲取的詳細信息。
    # AnalysisEngine 則直接從 DB 讀取數據。

    # Determine hardware report CSV path to reference in the main report
    # Use the local path as the primary reference.
    run_timestamp_str_for_hw_report = report_overall_start_time.strftime('%Y%m%d_%H%M%S')
    hw_report_filename = f"hardware_monitor_report_{run_timestamp_str_for_hw_report}.csv"
    # Consistent with archive_hardware_stats_to_csv:
    local_log_archive_base_for_ref = os.path.join(args.project_path_local, "data_workspace", "logs", "archive")
    hardware_report_csv_path_ref = os.path.join(local_log_archive_base_for_ref, hw_report_filename)
    # If GDrive path is different and relevant, could also pass that. For now, local path is clear.

    report_gen = ReportGenerator(
        execution_log=input_execution_log,
        analysis_engine_instance=analysis_engine,
        hardware_stats=hardware_stats, # Pass hardware stats
        hardware_report_csv_path=hardware_report_csv_path_ref # Pass path to CSV
    )

    # 報告的時間戳使用傳入的 overall_start_time (即腳本開始運行的時間或特定模式的開始時間)
    # 而不是重新生成一個 report_generation_time_for_filename，以保持一致性
    report_filename_dt_str = report_overall_start_time.strftime('%Y%m%d_%H%M%S')

    # 報告的日期範圍應使用 args.start_date 和 args.end_date
    # 在 report-only 模式下，這兩個值已在 main 中被 report_start_date 和 report_end_date 覆蓋
    report_start_d = args.start_date
    report_end_d = args.end_date
    if args.report_only: # 再次確認，以防萬一
        report_start_d = args.report_start_date
        report_end_d = args.report_end_date

    print(f"INFO (run_report_generation): Generating report for tickers: {report_tickers_list} over range [{report_start_d} to {report_end_d}]")

    final_report_str = report_gen.generate_full_report(
        overall_start_date_str=report_start_d,
        overall_end_date_str=report_end_d,
        report_generation_time=datetime.now(), # 使用當前時間作為報告生成時間點
        task_duration_seconds=data_task_duration_seconds, # 這是數據處理時長，或在純報告模式下為0
        target_tickers=report_tickers_list,
        db_table_name=args.table_name
    )

    print("\n--- 市場分析報告內容預覽 ---")
    preview_lines = final_report_str.splitlines()[:30]
    for line in preview_lines:
        print(line)
    if len(final_report_str.splitlines()) > 30:
        print("... (報告內容過長，已截斷預覽) ...")

    report_output_dir = os.path.join("data_workspace", "reports")
    os.makedirs(report_output_dir, exist_ok=True)

    report_filename = f"market_analysis_report_{report_filename_dt_str}.md"
    if args.data_only:
        report_filename = f"data_pipeline_summary_{report_filename_dt_str}.md" # 若未來要為 data-only 生成摘要
    elif args.report_only:
        report_filename = f"on_demand_report_{report_filename_dt_str}.md"

    report_filepath = os.path.join(report_output_dir, report_filename)

    try:
        with open(report_filepath, "w", encoding="utf-8") as f:
            f.write(final_report_str)
        print(f"\n報告已成功儲存至：{report_filepath}")
    except IOError as e:
        print(f"\n錯誤：儲存報告至檔案失敗：{e}")

    report_pipeline_end_time = datetime.now()
    report_duration_seconds = (report_pipeline_end_time - report_pipeline_start_time).total_seconds()
    print(f"報告生成流程執行時長: {report_duration_seconds:.2f} 秒")
    print("--- 報告生成流程結束 ---")


if __name__ == "__main__":
    # print(f"DEBUG: Current CWD for __main__ in daily_market_analyzer/run.py: {os.getcwd()}") # 移除調試信息
    # print(f"DEBUG: Current sys.path for __main__ in daily_market_analyzer/run.py: {sys.path}") # 移除調試信息

    # 移除 __main__ 中的延遲導入，因為已在頂部導入
    # if 'YFinanceClient' not in globals() or 'AnalysisEngine' not in globals(): # 檢查新加入的 AnalysisEngine
    #     try:
    #         # 更新導入路徑以匹配新的應用名稱
    #         from apps.daily_market_analyzer.yfinance_client import YFinanceClient
    #         from apps.daily_market_analyzer.db_manager import DBManager
    #         from apps.daily_market_analyzer.analysis_engine import AnalysisEngine
    #         from apps.daily_market_analyzer.report_generator import ReportGenerator
    #         # print("DEBUG: Late imports in daily_market_analyzer __main__ successful.") # 移除調試信息
    #     except ModuleNotFoundError as e:
    #         print(f"ERROR: Late ModuleNotFoundError in daily_market_analyzer __main__: {e}") # 中文化

    # Wrap main() call in a try/finally to ensure Local-First writeback
    # Need to access args from main, so the finally block should be inside main() or args passed around.
    # Revisiting main() structure for the finally block.

    # The main() function already has a structure. The finally block should be at the end of its try-catch.
    # Let's adjust the end of the main() function.

    # It appears main() doesn't have an explicit try/finally for its entire body.
    # It's better to add the write-back logic before the final print statements in main().
    # This is because the script might exit normally without an exception.
    # A full try/finally around the whole main() body is also an option.
    # For now, let's place it before the "總任務執行完畢" print.

    # Re-locating the finally logic to be directly within main() before it concludes.
    # The provided snippet is for if __name__ == "__main__". The actual main() function needs modification.

    # Correct approach: Add the finally block to the main() function structure.
    # Since main() doesn't have its own try/finally, I will add one.

    # This modification needs to be inside the main() function.
    # Let's find the end of the main() function and add the logic there.
    # The current search block is outside main().

    # I will create a new diff for the main() function's end.
    # This current diff is for the __main__ block, which is not the right place.
    # I will apply this change, then make another targeted change to main().
    main()
