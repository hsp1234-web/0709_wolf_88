# -*- coding: utf-8 -*-
"""
每日市場分析儀 CLI 接口邏輯。

此模組包含從舊有 run.py 遷移過來的核心執行邏輯，
以便被新的 Click CLI (main.py) 調用。
"""
import sys
import os
import shutil
from datetime import datetime
import pandas as pd
import csv
import psutil
import queue
import threading
import duckdb # 為了捕獲 duckdb.ConstraintException
import click # 用於 CLI 特有的錯誤處理和訊息輸出

# 設定專案路徑，確保可以正確匯入其他模組
# 這裡的路徑是相對於 cli_interface.py 檔案本身
# 假設 cli_interface.py 在 apps/daily_market_analyzer/ 下
# 則專案根目錄是 .. / ..
# 這個 setup_project_path 應該在 main.py (CLI 入口) 中統一處理，
# 或者通過 PYTHONPATH 環境變數設定。
# 為了模組的獨立性，暫時保留，但理想情況下應由調用方確保路徑正確。
def setup_project_path_if_needed():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

setup_project_path_if_needed()

try:
    from apps.daily_market_analyzer.yfinance_client import YFinanceClient
    from apps.daily_market_analyzer.db_manager import DBManager
    from apps.daily_market_analyzer.analysis_engine import AnalysisEngine
    from apps.daily_market_analyzer.report_generator import ReportGenerator
except ModuleNotFoundError as e:
    # 如果在 main.py 中調用時發生此錯誤，main.py 的導入錯誤處理會捕獲
    # 但如果此模組被其他方式不當調用，這裡會打印
    print(f"錯誤（cli_interface.py）：導入依賴模組時發生錯誤: {e}")
    raise


# --- 全局共享資源 (與 run.py 中類似，但作用域在此函式調用期間) ---
# 這些資源的生命週期需要仔細管理，特別是線程。
# DATA_QUEUE = queue.Queue() # 移至 run_daily_analysis 內部，確保每次調用時是新的
# DB_WRITE_LOCK = threading.Lock() # 同上

def run_daily_analysis(
    tickers: str | None,
    start_date_str: str | None,
    end_date_str: str | None,
    data_only: bool,
    report_only: bool,
    report_start_date_str: str | None,
    report_end_date_str: str | None,
    db_path: str,
    table_name: str,
    no_data_cooldown_days: int,
    force_refresh: bool,
    enable_local_first: bool,
    gdrive_root: str,
    project_path_local: str,
    max_workers: int,
    # cache_db_path: str | None, # 根據 run.py 註釋，此參數目前影響不大
    # process_uploads: bool, # 根據 run.py 註釋，此功能待實現
    # db_name: str | None, # db_path 已包含檔案名
    ):
    """
    執行每日市場分析的核心邏輯。
    參數直接對應原 run.py 中的 argparse 參數。
    """
    # --- 為此函式調用實例化佇列和鎖 ---
    # 這樣每次 CLI 命令執行時，都會使用獨立的佇列和鎖實例。
    data_queue_instance = queue.Queue()
    db_write_lock_instance = threading.Lock()
    # ---

    # --- Local-First: Path Definitions (與 run.py 相同邏輯) ---
    gdrive_db_path = db_path
    local_db_path_instance = None
    active_local_first_mode = enable_local_first

    if active_local_first_mode:
        if not gdrive_db_path:
            click.echo("錯誤 (Local-First): 啟用 --enable-local-first 時，必須提供 --db-path 作為 Google Drive 上的原始資料庫路徑。", err=True)
            raise click.Abort() # 或者返回一個錯誤狀態

        db_filename = os.path.basename(gdrive_db_path)
        if not db_filename:
            click.echo(f"錯誤 (Local-First): 無法從 --db-path '{gdrive_db_path}' 推斷資料庫檔案名稱。", err=True)
            active_local_first_mode = False
        else:
            local_db_dir = os.path.join(project_path_local, "data_workspace", "databases_local")
            local_db_path_instance = os.path.join(local_db_dir, db_filename)
            click.echo(f"INFO (Local-First): Configured for local processing. Local DB will be: {local_db_path_instance}")

    overall_start_time = datetime.now()
    click.echo("--- 每日市場洞察報告引擎 v3.0 (CLI整合版) ---")
    click.echo(f"任務開始時間: {overall_start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    db_manager = None
    final_db_path_used_by_dbmanager = gdrive_db_path
    if active_local_first_mode and local_db_path_instance:
        final_db_path_used_by_dbmanager = local_db_path_instance

    hardware_stats_list = []
    def log_hardware_stats(stage_name: str):
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            ram_percent = psutil.virtual_memory().percent
            hardware_stats_list.append({
                "timestamp": datetime.now().isoformat(),
                "stage": stage_name,
                "cpu_percent": cpu_percent,
                "ram_percent": ram_percent
            })
            # click.echo(f"DEBUG (Hardware Stats): Logged for stage '{stage_name}'. CPU: {cpu_percent}%, RAM: {ram_percent}%")
        except Exception as e:
            click.echo(f"警告: 記錄硬體狀態失敗: {e}", err=True)

    log_hardware_stats("main_start")

    try:
        # --- Parameter Validation (與 run.py 相同邏輯) ---
        # Click 本身會處理一些類型驗證和必要性，但複雜的互斥邏輯需在此處理
        if data_only and report_only:
            click.echo("錯誤：--data-only 和 --report-only 選項不能同時指定。", err=True)
            raise click.Abort()
        if report_only:
            if not report_start_date_str or not report_end_date_str:
                click.echo("錯誤：當使用 --report-only 時，必須提供 --report-start-date 和 --report-end-date。", err=True)
                raise click.Abort()
            if not tickers: # 在 report_only 模式下，tickers 也是必需的
                click.echo("錯誤：當使用 --report-only 時，必須提供 --tickers。", err=True)
                raise click.Abort()
        elif not data_only: # Full flow
            if not tickers or not start_date_str or not end_date_str:
                click.echo("錯誤：在完整流程模式下，必須提供 --tickers, --start-date, 和 --end-date。", err=True)
                raise click.Abort()
        elif data_only: # Data only
             if not tickers or not start_date_str or not end_date_str:
                click.echo("錯誤：當使用 --data-only 時，必須提供 --tickers, --start-date, 和 --end-date。", err=True)
                raise click.Abort()

        # 將日期字串轉換為 Click 的 DateTime 類型已處理，這裡假設傳入的是有效字串或 None
        # 如果 Click 未做轉換，則需在此處解析日期字串

        # --- Dynamic DuckDB Memory Configuration (與 run.py 相同邏輯) ---
        db_config = {}
        try:
            available_bytes = psutil.virtual_memory().available
            available_gb = available_bytes / (1024**3)
            mem_limit_gb = min(available_gb * 0.7, 12.0) # 限制最大為12GB
            mem_limit_gb = max(mem_limit_gb, 0.25) # 確保至少有250MB
            memory_limit_mb = int(mem_limit_gb * 1024)
            memory_limit_setting_str = f"{memory_limit_mb}MB"
            db_config = {'memory_limit': memory_limit_setting_str}
            click.echo(f"INFO: 動態設定 DuckDB memory_limit 為: {memory_limit_setting_str} (基於 {available_gb:.2f} GB 可用記憶體)")
        except Exception as e:
            click.echo(f"警告: 偵測系統可用記憶體或設定 DuckDB 組態時發生錯誤: {e}。將使用 DuckDB 預設記憶體配置。", err=True)


        # --- Local-First: On Startup Copy (與 run.py 相同邏輯) ---
        if active_local_first_mode and local_db_path_instance and gdrive_db_path:
            click.echo(f"INFO (Local-First): '本地優先' 模式已啟用。")
            click.echo(f"INFO (Local-First): 原始資料庫 (GDRIVE): {gdrive_db_path}")
            click.echo(f"INFO (Local-First): 本地目標資料庫: {local_db_path_instance}")

            local_db_dir_for_copy = os.path.dirname(local_db_path_instance)
            if not os.path.exists(local_db_dir_for_copy):
                try:
                    os.makedirs(local_db_dir_for_copy, exist_ok=True)
                    click.echo(f"INFO (Local-First): 已建立本地資料庫目錄: {local_db_dir_for_copy}")
                except Exception as e:
                    click.echo(f"錯誤 (Local-First): 建立本地資料庫目錄 '{local_db_dir_for_copy}' 失敗: {e}。停用本地優先模式。", err=True)
                    active_local_first_mode = False

            if active_local_first_mode: # 再次檢查，因為上面可能設定為 False
                if os.path.exists(gdrive_db_path):
                    try:
                        copy_start_time = datetime.now()
                        click.echo(f"INFO (Local-First) [{copy_start_time.strftime('%H:%M:%S')}]: 開始複製資料庫從 GDrive '{gdrive_db_path}' 到本地 '{local_db_path_instance}'...")
                        total_size = os.path.getsize(gdrive_db_path)
                        click.echo(f"INFO (Local-First): 待複製檔案大小: {total_size / (1024*1024):.2f} MB.")

                        shutil.copy2(gdrive_db_path, local_db_path_instance)

                        copy_end_time = datetime.now()
                        copied_size = os.path.getsize(local_db_path_instance)
                        duration_seconds = (copy_end_time - copy_start_time).total_seconds()
                        click.echo(f"INFO (Local-First) [{copy_end_time.strftime('%H:%M:%S')}]: 資料庫複製到本地完成。耗時: {duration_seconds:.2f} 秒。本地檔案大小: {copied_size / (1024*1024):.2f} MB.")
                        final_db_path_used_by_dbmanager = local_db_path_instance
                    except Exception as e:
                        copy_fail_time = datetime.now()
                        click.echo(f"錯誤 (Local-First) [{copy_fail_time.strftime('%H:%M:%S')}]: 從 GDrive 複製資料庫失敗: {e}。停用本地優先模式。", err=True)
                        active_local_first_mode = False
                else:
                    click.echo(f"警告 (Local-First): GDrive 上的原始資料庫檔案 '{gdrive_db_path}' 不存在。將嘗試在本地路徑 '{local_db_path_instance}' 建立新資料庫。", err=True)
                    final_db_path_used_by_dbmanager = local_db_path_instance

        if not active_local_first_mode: # 如果 Local-First 被停用或失敗
            final_db_path_used_by_dbmanager = gdrive_db_path # 使用原始 gdrive_db_path
            click.echo(f"INFO (Local-First Fallback): 本地優先模式已停用或初始化失敗。將使用資料庫: {final_db_path_used_by_dbmanager}")

        click.echo(f"INFO: 初始化 DBManager，資料庫路徑: {final_db_path_used_by_dbmanager}, 目標資料表: {table_name}")
        db_manager = DBManager(
            db_path=final_db_path_used_by_dbmanager,
            target_ohlcv_table_name=table_name,
            duckdb_config=db_config
        )
        analysis_engine = AnalysisEngine(db_manager_instance=db_manager)

        overall_execution_log = {}
        tickers_list = []
        if tickers:
            tickers_list = [ticker.strip().upper() for ticker in tickers.split(',')]

        task_duration_seconds = 0
        writer_thread = None
        stop_writer_event = threading.Event()

        if not report_only:
            click.echo("INFO (Main Logic): 準備啟動資料庫寫入消費者線程...")
            writer_thread = threading.Thread(
                target=database_writer_worker, # 需要將此函式也遷移或在此定義
                args=(db_manager, db_write_lock_instance, data_queue_instance, stop_writer_event),
                name="DBWriterThread"
            )
            writer_thread.start()
            click.echo("INFO (Main Logic): 資料庫寫入消費者線程已啟動。")

        # 根據模式選擇執行的日期範圍
        current_start_date = start_date_str
        current_end_date = end_date_str
        if report_only:
            current_start_date = report_start_date_str
            current_end_date = report_end_date_str
            # 確保 tickers_list 在 report_only 模式下有值 (已在參數驗證中處理)

        if data_only:
            click.echo(f"執行模式：僅數據處理。資料庫: {final_db_path_used_by_dbmanager}")
            log_hardware_stats("data_pipeline_start")
            yf_client = YFinanceClient(db_manager=db_manager, data_queue=data_queue_instance, no_data_cooldown_days=no_data_cooldown_days)
            overall_execution_log, _ = _run_data_pipeline_logic(
                db_manager, yf_client, tickers_list,
                current_start_date, current_end_date, # 使用 current_start_date, current_end_date
                table_name, force_refresh, max_workers
            )
            log_hardware_stats("data_pipeline_end")
        elif report_only:
            click.echo(f"執行模式：僅報告生成。資料庫: {final_db_path_used_by_dbmanager}")
            log_hardware_stats("report_generation_start")
            _run_report_generation_logic(
                db_manager, analysis_engine, {}, tickers_list,
                current_start_date, current_end_date, # 使用 current_start_date, current_end_date
                overall_start_time, 0, hardware_stats_list, table_name,
                project_path_local, # 傳遞 project_path_local 給報告函式
                gdrive_db_path, # 傳遞原始 gdrive_db_path (或等效的 base_gdrive_path_ref)
                data_only=False, report_only_mode=True # 新增參數以區分模式
            )
            log_hardware_stats("report_generation_end")
        else: # Full flow
            click.echo(f"執行模式：完整流程。資料庫: {final_db_path_used_by_dbmanager}")
            log_hardware_stats("data_pipeline_start")
            yf_client = YFinanceClient(db_manager=db_manager, data_queue=data_queue_instance, no_data_cooldown_days=no_data_cooldown_days)

            data_pipeline_start_time = datetime.now()
            overall_execution_log, _ = _run_data_pipeline_logic(
                db_manager, yf_client, tickers_list,
                current_start_date, current_end_date,
                table_name, force_refresh, max_workers
            )
            data_pipeline_end_time = datetime.now()
            task_duration_seconds = (data_pipeline_end_time - data_pipeline_start_time).total_seconds()
            log_hardware_stats("data_pipeline_end")

            log_hardware_stats("report_generation_start")
            _run_report_generation_logic(
                db_manager, analysis_engine, overall_execution_log, tickers_list,
                current_start_date, current_end_date,
                overall_start_time, task_duration_seconds, hardware_stats_list, table_name,
                project_path_local,
                gdrive_db_path,
                data_only=False, report_only_mode=False
            )
            log_hardware_stats("report_generation_end")

        if writer_thread is not None and writer_thread.is_alive():
            click.echo("INFO (Main Logic): 所有主要任務完成，準備關閉資料庫寫入消費者線程。")
            click.echo("INFO (Main Logic): 等待數據佇列中所有項目被處理 (data_queue_instance.join())...")
            data_queue_instance.join()
            click.echo("INFO (Main Logic): 數據佇列中所有項目均已處理 (task_done)。")
            click.echo("INFO (Main Logic): 向消費者線程發送停止事件信號 (stop_writer_event.set())。")
            stop_writer_event.set()
            click.echo("INFO (Main Logic): 等待消費者線程結束 (writer_thread.join())...")
            writer_thread.join(timeout=10) # 給予10秒超時
            if writer_thread.is_alive():
                click.echo("WARN (Main Logic): 消費者線程在10秒超時後仍未結束。可能存在問題。", err=True)
            else:
                click.echo("INFO (Main Logic): 資料庫寫入消費者線程已成功結束。")
        elif writer_thread is not None: # 線程已創建但未運行 (不太可能到這裡)
             click.echo(f"INFO (Main Logic): 資料庫寫入消費者線程存在但非運行狀態 (is_alive: {writer_thread.is_alive()})。")
        else: # report_only 模式，未啟動線程
            click.echo("INFO (Main Logic): 處於僅報告模式，未啟動資料庫寫入消費者線程。")

        log_hardware_stats("main_end")
        final_overall_end_time = datetime.now()
        total_script_duration = (final_overall_end_time - overall_start_time).total_seconds()
        click.echo(f"\n--- 總任務執行完畢 ---")
        click.echo(f"總體結束時間: {final_overall_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"腳本總執行時長: {total_script_duration:.2f} 秒")

    finally:
        # --- Local-First: On Exit Copy Back (與 run.py 相同邏輯) ---
        # click.echo(f"DEBUG (Finally): active_local_first_mode={active_local_first_mode}, local_db_path_instance={local_db_path_instance}")
        if active_local_first_mode and local_db_path_instance and gdrive_db_path:
            if db_manager and hasattr(db_manager, '_conn') and getattr(db_manager, '_conn', None) is not None:
                click.echo(f"INFO (Local-First): 嘗試關閉 DBManager 連線以釋放檔案鎖...")
                try:
                    del db_manager # 嘗試觸發 __del__ 來關閉連接
                    click.echo(f"INFO (Local-First): DBManager 實例已刪除。")
                except Exception as e:
                    click.echo(f"警告 (Local-First): 關閉/刪除 DBManager 時發生錯誤: {e}", err=True)

            if os.path.exists(local_db_path_instance):
                try:
                    writeback_start_time = datetime.now()
                    click.echo(f"INFO (Local-First) [{writeback_start_time.strftime('%H:%M:%S')}]: 開始將本地資料庫 '{local_db_path_instance}' 回寫到 GDrive '{gdrive_db_path}'...")

                    gdrive_db_dir_for_writeback = os.path.dirname(gdrive_db_path)
                    if gdrive_db_dir_for_writeback and not os.path.exists(gdrive_db_dir_for_writeback):
                        os.makedirs(gdrive_db_dir_for_writeback, exist_ok=True)
                        click.echo(f"INFO (Local-First): 已建立 GDrive 上的目標目錄 (回寫時): {gdrive_db_dir_for_writeback}")

                    local_size_for_wb = os.path.getsize(local_db_path_instance)
                    click.echo(f"INFO (Local-First): 待回寫本地檔案大小: {local_size_for_wb / (1024*1024):.2f} MB.")
                    shutil.copy2(local_db_path_instance, gdrive_db_path)
                    writeback_end_time = datetime.now()
                    duration_seconds_wb = (writeback_end_time - writeback_start_time).total_seconds()
                    click.echo(f"INFO (Local-First) [{writeback_end_time.strftime('%H:%M:%S')}]: 資料庫成功回寫到 GDrive '{gdrive_db_path}'。耗時: {duration_seconds_wb:.2f} 秒。")
                except Exception as e:
                    writeback_fail_time = datetime.now()
                    click.echo(f"錯誤 (Local-First) [{writeback_fail_time.strftime('%H:%M:%S')}]: 回寫資料庫到 GDrive 失敗: {e}", err=True)
            else:
                click.echo(f"警告 (Local-First): 本地資料庫檔案 '{local_db_path_instance}' 不存在於預期路徑，無法回寫。", err=True)
        elif enable_local_first: # 如果最初啟用了 local-first 但後來被禁用
             click.echo(f"INFO (Local-First): 本地優先模式最初啟用，但可能在設置或執行過程中被停用/失敗。跳過回寫。")

        # --- Hardware Stats Archiving (與 run.py 相同邏輯) ---
        if hardware_stats_list:
            # 傳遞 project_path_local 和 gdrive_root 給存檔函式
            # gdrive_db_path 作為 base_gdrive_path_ref
            _archive_hardware_stats_to_csv(
                hardware_stats_list,
                project_path_local,
                gdrive_root,
                overall_start_time.strftime('%Y%m%d_%H%M%S'),
                gdrive_db_path
            )
    # 可以考慮返回一個狀態或結果字典
    return {"status": "success", "message": "每日市場分析流程執行完畢。"}


# --- Helper functions extracted from run.py's main logic ---
# 這些輔助函式需要從 run.py 中對應的 run_data_pipeline 和 run_report_generation 內部邏輯提取和調整
# 並確保它們使用傳入的參數，而不是依賴 argparse 的 args 物件

def _run_data_pipeline_logic(
    db_m: DBManager,
    yf_cli: YFinanceClient,
    tickers_l: list,
    start_d_str: str,
    end_d_str: str,
    table_n: str,
    force_ref: bool,
    max_w: int
    ):
    click.echo("\n--- 開始數據處理流程 (CLI) ---")
    pipeline_start_time = datetime.now()
    db_m.create_ohlcv_table(table_name=table_n) # 使用傳入的 table_n
    current_overall_execution_log = {}

    if not tickers_l:
        click.echo("警告 (Data Pipeline): 標的列表為空，無法執行數據流程。", err=True)
        return {}, []

    from concurrent.futures import ThreadPoolExecutor, as_completed # 保持局部導入
    click.echo(f"INFO (Data Pipeline): 開始並行獲取 {len(tickers_l)} 個標的的市場數據，使用最多 {max_w} 個執行緒。")

    future_to_ticker = {}
    with ThreadPoolExecutor(max_workers=max_w) as executor:
        for ticker_symbol in tickers_l:
            click.echo(f"INFO (Thread Dispatch): 分派標的 {ticker_symbol} 進行數據處理...")
            future = executor.submit(
                yf_cli.hydrate_data_range,
                ticker_symbol,
                start_d_str, # 使用傳入的 start_d_str
                end_d_str,   # 使用傳入的 end_d_str
                db_table_name=table_n, # 使用傳入的 table_n
                force_refresh=force_ref # 使用傳入的 force_ref
            )
            future_to_ticker[future] = ticker_symbol

        for future in as_completed(future_to_ticker):
            ticker_symbol_for_log = future_to_ticker[future]
            try:
                _, ticker_execution_log = future.result() # 假設 hydrate_data_range 返回 (None, log_dict)
                if ticker_execution_log: # 合併日誌
                    for date_key, daily_log_for_all_tickers_on_date in ticker_execution_log.items():
                        if date_key not in current_overall_execution_log:
                            current_overall_execution_log[date_key] = {}
                        current_overall_execution_log[date_key].update(daily_log_for_all_tickers_on_date)

                if ticker_execution_log:
                    log_status_for_ticker = "未知"
                    final_status_messages = [] # 收集特定 ticker 的所有日誌訊息
                    for date_log in ticker_execution_log.values():
                        if ticker_symbol_for_log in date_log:
                            final_status_messages.append(date_log[ticker_symbol_for_log].get('message', '無訊息'))

                    if any("queued" in msg.lower() or "cached" in msg.lower() for msg in final_status_messages):
                        log_status_for_ticker = "已處理 (數據已入隊或來自快取)"
                    elif final_status_messages: # 如果有任何訊息
                        log_status_for_ticker = f"已處理 (最終日誌: {final_status_messages[-1][:100]})" # 取最後一條訊息的摘要
                    else: # 沒有日誌訊息
                        log_status_for_ticker = "已分派處理，但未找到明確的最終狀態日誌"
                    click.echo(f"INFO (Parallel Result): 標的 {ticker_symbol_for_log} 並行生產者任務完成。狀態: {log_status_for_ticker}。日誌已合併。")
                else:
                    click.echo(f"警告 (Parallel Result): 標的 {ticker_symbol_for_log} 並行處理未返回日誌。", err=True)

            except Exception as exc:
                click.echo(f"錯誤 (Parallel Task): 標的 {ticker_symbol_for_log} 的並行任務執行失敗: {exc}", err=True)
                # 記錄錯誤到執行日誌
                # 需要確保 start_d_str 和 end_d_str 是有效的日期字串
                try:
                    date_range_for_error_log = pd.date_range(start_d_str, end_d_str).strftime('%Y-%m-%d')
                    for date_str_key_for_error in date_range_for_error_log:
                        if date_str_key_for_error not in current_overall_execution_log:
                            current_overall_execution_log[date_str_key_for_error] = {}
                        current_overall_execution_log[date_str_key_for_error][ticker_symbol_for_log] = {
                            'status': 'parallel_task_exception', 'interval': None, 'count': 0,
                            'message': f"並行任務執行失敗: {exc}"}
                except ValueError as ve: # 日期格式或範圍問題
                     click.echo(f"錯誤 (Parallel Task Error Logging): 無法為標的 {ticker_symbol_for_log} 的錯誤創建日期範圍日誌: {ve}", err=True)


    click.echo(f"INFO (Data Pipeline): 所有並行標的數據獲取任務已提交到執行緒池。")
    pipeline_end_time = datetime.now()
    pipeline_duration_seconds = (pipeline_end_time - pipeline_start_time).total_seconds()
    click.echo(f"\n--- 數據處理流程結束 (CLI) ---")
    click.echo(f"數據流程執行時長: {pipeline_duration_seconds:.2f} 秒")
    return current_overall_execution_log, tickers_l


def _run_report_generation_logic(
    db_m: DBManager,
    analysis_eng: AnalysisEngine,
    input_exec_log: dict,
    report_tickers_l: list,
    report_start_d_str: str,
    report_end_d_str: str,
    report_overall_start_t: datetime,
    data_task_dur_sec: float,
    hw_stats: list[dict],
    table_n: str,
    proj_path_local: str, # 新增：本地專案路徑
    base_gdrive_path_ref_for_hw: str | None, # 新增：用於硬體報告的 GDrive DB 路徑參考
    data_only_mode: bool, # 新增
    report_only_mode: bool # 新增
    ):
    click.echo("\n--- 開始報告生成流程 (CLI) ---")
    report_pipeline_start_time = datetime.now()

    if not report_tickers_l:
         click.echo("警告 (Report Generation): 標的列表為空，無法生成報告。", err=True)
         return

    run_timestamp_str_for_hw_report = report_overall_start_t.strftime('%Y%m%d_%H%M%S')
    hw_report_filename = f"hardware_monitor_report_{run_timestamp_str_for_hw_report}.csv"
    # 修正：使用 proj_path_local 構造 hardware_report_csv_path_ref
    local_log_archive_base_for_ref = os.path.join(proj_path_local, "data_workspace", "logs", "archive")
    hardware_report_csv_path_ref = os.path.join(local_log_archive_base_for_ref, hw_report_filename)

    report_gen = ReportGenerator(
        execution_log=input_exec_log,
        analysis_engine_instance=analysis_eng,
        hardware_stats=hw_stats, # 使用傳入的 hw_stats
        hardware_report_csv_path=hardware_report_csv_path_ref # 傳遞修正後的路徑
    )

    report_filename_dt_str = report_overall_start_t.strftime('%Y%m%d_%H%M%S')

    click.echo(f"INFO (Report Generation): Generating report for tickers: {report_tickers_l} over range [{report_start_d_str} to {report_end_d_str}]")
    final_report_str = report_gen.generate_full_report(
        overall_start_date_str=report_start_d_str,
        overall_end_date_str=report_end_d_str,
        report_generation_time=datetime.now(), # 當前時間
        task_duration_seconds=data_task_dur_sec,
        target_tickers=report_tickers_l,
        db_table_name=table_n
    )

    click.echo("\n--- 市場分析報告內容預覽 ---")
    preview_lines = final_report_str.splitlines()[:30]
    for line in preview_lines:
        click.echo(line)
    if len(final_report_str.splitlines()) > 30:
        click.echo("... (報告內容過長，已截斷預覽) ...")

    report_output_dir = os.path.join("data_workspace", "reports") # 相對路徑，假設在專案根目錄執行
    os.makedirs(report_output_dir, exist_ok=True)

    report_filename = f"market_analysis_report_{report_filename_dt_str}.md"
    if data_only_mode: # 使用傳入的 data_only_mode
        report_filename = f"data_pipeline_summary_{report_filename_dt_str}.md"
    elif report_only_mode: # 使用傳入的 report_only_mode
        report_filename = f"on_demand_report_{report_filename_dt_str}.md"

    report_filepath = os.path.join(report_output_dir, report_filename)
    try:
        with open(report_filepath, "w", encoding="utf-8") as f:
            f.write(final_report_str)
        click.echo(f"\n報告已成功儲存至：{report_filepath}")
    except IOError as e:
        click.echo(f"\n錯誤：儲存報告至檔案失敗：{e}", err=True)

    report_pipeline_end_time = datetime.now()
    report_duration_seconds = (report_pipeline_end_time - report_pipeline_start_time).total_seconds()
    click.echo(f"報告生成流程執行時長: {report_duration_seconds:.2f} 秒")
    click.echo("--- 報告生成流程結束 (CLI) ---")


def _archive_hardware_stats_to_csv(
    stats_list: list,
    proj_path_local: str, # project_path_local from args
    gdrive_r: str, # gdrive_root from args
    timestamp_str: str,
    base_gdrive_path_ref: str | None # gdrive_db_path from args, used as reference
    ):
    if not stats_list:
        click.echo("INFO (Hardware Archive): No hardware stats collected to archive.")
        return

    # 本地存檔路徑
    local_log_archive_base = os.path.join(proj_path_local, "data_workspace", "logs", "archive")

    # GDrive 存檔路徑推斷 (與 run.py 邏輯一致)
    gdrive_log_archive_base = None
    if base_gdrive_path_ref: # 如果提供了 GDrive 資料庫路徑作為參考
        # 嘗試從 gdrive_db_path 推斷 GDrive 上的 project data_workspace
        gdrive_project_data_workspace = os.path.dirname(base_gdrive_path_ref) # 預期是 .../data_workspace/databases_local/your.db
        # 如果 basename 是 databases_local，再往上一層到 data_workspace
        if os.path.basename(gdrive_project_data_workspace) == "databases_local" and "data_workspace" in gdrive_project_data_workspace:
             gdrive_project_data_workspace = os.path.dirname(gdrive_project_data_workspace)

        if "data_workspace" in gdrive_project_data_workspace: # 如果成功找到 data_workspace
            gdrive_log_archive_base = os.path.join(gdrive_project_data_workspace, "logs", "archive")
        else: # 如果推斷失敗，使用後備路徑
            gdrive_log_archive_base = os.path.join(gdrive_r, "panoramic_market_analyzer_logs", "archive")
            click.echo(f"WARN (Hardware Archive): Could not determine GDrive project structure from '{base_gdrive_path_ref}'. Using fallback GDrive log path: {gdrive_log_archive_base}", err=True)
    else: # 如果沒有 GDrive DB 路徑參考，直接使用後備路徑
        gdrive_log_archive_base = os.path.join(gdrive_r, "panoramic_market_analyzer_logs", "archive")
        click.echo(f"WARN (Hardware Archive): GDrive DB path not available. Using fallback GDrive log path: {gdrive_log_archive_base}", err=True)

    filename = f"hardware_monitor_report_{timestamp_str}.csv"
    local_filepath = os.path.join(local_log_archive_base, filename)
    gdrive_filepath = os.path.join(gdrive_log_archive_base, filename)
    fieldnames = ["timestamp", "stage", "cpu_percent", "ram_percent"]

    try:
        os.makedirs(local_log_archive_base, exist_ok=True)
        with open(local_filepath, 'w', newline='', encoding='utf-8') as f_local:
            writer = csv.DictWriter(f_local, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(stats_list)
        click.echo(f"INFO (Hardware Archive): Hardware stats successfully saved to local: {local_filepath}")
    except Exception as e:
        click.echo(f"錯誤 (Hardware Archive): 儲存硬體狀態到本地 '{local_filepath}' 失敗: {e}", err=True)

    # 只有當本地路徑和 GDrive 路徑不同時才嘗試寫入 GDrive
    if local_filepath != gdrive_filepath :
        try:
            os.makedirs(gdrive_log_archive_base, exist_ok=True) # 確保 GDrive 目標目錄存在
            with open(gdrive_filepath, 'w', newline='', encoding='utf-8') as f_gdrive:
                writer = csv.DictWriter(f_gdrive, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(stats_list)
            click.echo(f"INFO (Hardware Archive): Hardware stats successfully saved to GDrive: {gdrive_filepath}")
        except Exception as e:
            click.echo(f"錯誤 (Hardware Archive): 儲存硬體狀態到 GDrive '{gdrive_filepath}' 失敗: {e}", err=True)


# --- 消費者線程工作函式 (與 run.py 中相同，但需傳入 lock 和 queue) ---
def database_writer_worker(db_m: DBManager, lock: threading.Lock, data_q: queue.Queue, stop_event: threading.Event):
    thread_name = threading.current_thread().name
    click.echo(f"INFO (DB Writer Thread): 消費者線程 '{thread_name}' 已啟動。")
    while not stop_event.is_set() or not data_q.empty():
        try:
            data_item = data_q.get(timeout=1)
            if data_item is not None:
                df_summary = "None"
                actual_df = None
                if isinstance(data_item, dict): actual_df = data_item.get('data')
                if actual_df is not None and isinstance(actual_df, pd.DataFrame): df_summary = f"DataFrame (shape: {actual_df.shape})"
                elif actual_df is not None: df_summary = f"data is {type(actual_df)}"
                item_ticker = data_item.get('ticker', 'N/A') if isinstance(data_item, dict) else 'N/A (item not dict)'
                item_interval = data_item.get('interval', 'N/A') if isinstance(data_item, dict) else 'N/A (item not dict)'
                # click.echo(f"DEBUG (DB Writer Thread): 從佇列收到項目: Ticker: {item_ticker}, Interval: {item_interval}, Data: {df_summary}")
            # elif data_item is None:
                # click.echo(f"DEBUG (DB Writer Thread): 從佇列收到項目: Termination Signal (None)")
        except queue.Empty:
            if stop_event.is_set():
                # click.echo(f"INFO (DB Writer Thread): 停止信號已收到且佇列為空 '{thread_name}'，準備退出。")
                break
            continue # 繼續等待，直到 stop_event 被設置且佇列為空

        if data_item is None: # 終止信號
            data_q.task_done()
            # click.echo(f"INFO (DB Writer Thread): '{thread_name}' 處理 None 結束信號，準備退出。")
            break

        try:
            with lock: # 使用傳入的鎖
                df_to_write = data_item.get('data')
                table_to_write = data_item.get('table_name')
                ticker_symbol = data_item.get('ticker', 'N/A')
                interval_val = data_item.get('interval', 'N/A')

                if df_to_write is not None and not df_to_write.empty and table_to_write:
                    try:
                        db_m.upsert_data(df_to_write, table_name=table_to_write)
                        click.echo(f"INFO (DB Writer Thread): 成功寫入 {len(df_to_write)} 筆來自 '{ticker_symbol}' (顆粒度: {interval_val}) 的數據到資料表 '{table_to_write}'。")
                    except duckdb.ConstraintException as ce:
                        click.echo(f"INFO (DB Writer Thread): 數據已存在或違反唯一約束，跳過寫入 Ticker: {ticker_symbol} (顆粒度: {interval_val}) 到 {table_to_write}。錯誤: {ce}")
                    except Exception as e_upsert:
                        click.echo(f"ERROR (DB Writer Thread): 寫入數據時發生未預期錯誤 Ticker: {ticker_symbol} (顆粒度: {interval_val}) 到 {table_to_write}。錯誤: {e_upsert}", err=True)
                else:
                    click.echo(f"WARN (DB Writer Thread): 從佇列收到的數據項無效或不完整: Ticker {ticker_symbol}, Table {table_to_write}, DataFrame is None or empty: {df_to_write is None or df_to_write.empty}", err=True)
        except Exception as e:
            click.echo(f"ERROR (DB Writer Thread): 消費者線程 '{thread_name}' 處理項目時發生嚴重錯誤: {e}. Data item (部分): {{'ticker': {data_item.get('ticker','N/A') if data_item else 'N/A'}, 'table': {data_item.get('table_name','N/A') if data_item else 'N/A'}}}", err=True)
        finally:
            data_q.task_done() # 確保 task_done 總是被調用

    click.echo(f"INFO (DB Writer Thread): 消費者線程 '{thread_name}' 已結束。")
