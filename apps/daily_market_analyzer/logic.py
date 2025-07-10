# -*- coding: utf-8 -*-
"""
每日市場分析儀的核心邏輯。
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
from typing import Optional, List

try:
    from apps.daily_market_analyzer.yfinance_client import YFinanceClient
    from apps.daily_market_analyzer.db_manager import DBManager
    from apps.daily_market_analyzer.analysis_engine import AnalysisEngine
    from apps.daily_market_analyzer.report_generator import ReportGenerator
except ModuleNotFoundError:
    project_root_logic = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root_logic not in sys.path:
        sys.path.insert(0, project_root_logic)
    # Retry imports
    from apps.daily_market_analyzer.yfinance_client import YFinanceClient
    from apps.daily_market_analyzer.db_manager import DBManager
    from apps.daily_market_analyzer.analysis_engine import AnalysisEngine
    from apps.daily_market_analyzer.report_generator import ReportGenerator

DATA_QUEUE = queue.Queue()
DB_WRITE_LOCK = threading.Lock()
hardware_stats_list_global = []

def log_hardware_stats(stage_name: str):
    try:
        cpu_percent = psutil.cpu_percent(interval=None)
        ram_percent = psutil.virtual_memory().percent
        hardware_stats_list_global.append({
            "timestamp": datetime.now().isoformat(),
            "stage": stage_name,
            "cpu_percent": cpu_percent,
            "ram_percent": ram_percent
        })
    except Exception as e:
        print(f"警告: 記錄硬體狀態失敗: {e}")

def archive_hardware_stats_to_csv(stats_list: list, project_path_local: str, gdrive_root: str, timestamp_str: str, base_gdrive_path_ref: Optional[str]):
    if not stats_list:
        print("INFO (Hardware Archive): 無硬體狀態數據可供歸檔。")
        return
    local_log_archive_base = os.path.join(project_path_local, "data_workspace", "logs", "archive")
    gdrive_log_archive_base = None
    if base_gdrive_path_ref:
        gdrive_project_data_workspace = os.path.dirname(base_gdrive_path_ref)
        if os.path.basename(gdrive_project_data_workspace) == "databases_local" and "data_workspace" in gdrive_project_data_workspace.split(os.sep):
             gdrive_project_data_workspace = os.path.dirname(gdrive_project_data_workspace)
        if "data_workspace" in gdrive_project_data_workspace.split(os.sep):
            dw_parts = gdrive_project_data_workspace.split(os.sep)
            try:
                dw_index = dw_parts.index("data_workspace")
                gdrive_data_workspace_proper = os.sep.join(dw_parts[:dw_index+1])
                gdrive_log_archive_base = os.path.join(gdrive_data_workspace_proper, "logs", "archive")
            except ValueError:
                 gdrive_log_archive_base = os.path.join(gdrive_root, "panoramic_market_analyzer_logs", "archive")
                 print(f"警告 (Hardware Archive): 無法從 '{base_gdrive_path_ref}' 的路徑中正確推斷 'data_workspace'。使用備用 GDrive 日誌路徑: {gdrive_log_archive_base}")
        else:
            gdrive_log_archive_base = os.path.join(gdrive_root, "panoramic_market_analyzer_logs", "archive")
            print(f"警告 (Hardware Archive): 'data_workspace' 未在 '{base_gdrive_path_ref}' 的路徑中找到。使用備用 GDrive 日誌路徑: {gdrive_log_archive_base}")
    else:
        gdrive_log_archive_base = os.path.join(gdrive_root, "panoramic_market_analyzer_logs", "archive")
        print(f"警告 (Hardware Archive): GDrive 資料庫路徑未提供。使用備用 GDrive 日誌路徑: {gdrive_log_archive_base}")

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
        print(f"INFO (Hardware Archive): 硬體狀態已成功儲存至本地: {local_filepath}")
    except Exception as e:
        print(f"錯誤 (Hardware Archive): 儲存硬體狀態到本地 '{local_filepath}' 失敗: {e}")
    if local_filepath != gdrive_filepath :
        try:
            os.makedirs(gdrive_log_archive_base, exist_ok=True)
            shutil.copy2(local_filepath, gdrive_filepath)
            print(f"INFO (Hardware Archive): 硬體狀態已成功複製到 GDrive: {gdrive_filepath}")
        except Exception as e:
            print(f"錯誤 (Hardware Archive): 複製硬體狀態到 GDrive '{gdrive_filepath}' 失敗: {e}")

def run_data_pipeline_logic(
    tickers: List[str], start_date: str, end_date: str, db_manager: DBManager,
    yf_client: YFinanceClient, table_name: str, max_workers: int, force_refresh: bool
):
    print("\n--- 開始數據處理流程 ---")
    pipeline_start_time = datetime.now()
    db_manager.create_ohlcv_table(table_name=table_name)
    current_overall_execution_log = {}
    if not tickers:
        print("警告 (run_data_pipeline_logic): 標的列表為空，無法執行數據流程。")
        return {}, []
    from concurrent.futures import ThreadPoolExecutor, as_completed
    print(f"INFO (run_data_pipeline_logic): 開始並行獲取 {len(tickers)} 個標的的市場數據，使用最多 {max_workers} 個執行緒。")
    future_to_ticker = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for ticker_symbol in tickers:
            print(f"INFO (Thread Dispatch): 分派標的 {ticker_symbol} 進行數據處理...")
            future = executor.submit(
                yf_client.hydrate_data_range, ticker_symbol, start_date, end_date,
                db_table_name=table_name, force_refresh=force_refresh
            )
            future_to_ticker[future] = ticker_symbol
        for future in as_completed(future_to_ticker):
            ticker_symbol_for_log = future_to_ticker[future]
            try:
                _, ticker_execution_log = future.result()
                if ticker_execution_log:
                    for date_key, daily_log in ticker_execution_log.items():
                        current_overall_execution_log.setdefault(date_key, {}).update(daily_log)
                    # Simplified logging status based on the presence of logs
                    print(f"INFO (Parallel Result): 標的 {ticker_symbol_for_log} 並行生產者任務完成。日誌已合併。")
                else:
                    print(f"警告 (Parallel Result): 標的 {ticker_symbol_for_log} 並行處理未返回日誌。")
            except Exception as exc:
                print(f"錯誤 (Parallel Task): 標的 {ticker_symbol_for_log} 的並行任務執行失敗: {exc}")
                for date_str_key in pd.date_range(start_date, end_date).strftime('%Y-%m-%d'):
                    current_overall_execution_log.setdefault(date_str_key, {})[ticker_symbol_for_log] = {
                        'status': 'parallel_task_exception', 'interval': None, 'count': 0,
                        'message': f"並行任務執行失敗: {str(exc)[:200]}"}
    pipeline_end_time = datetime.now()
    print(f"\n--- 數據處理流程結束 --- 時長: {(pipeline_end_time - pipeline_start_time).total_seconds():.2f} 秒")
    return current_overall_execution_log, tickers

def run_report_generation_logic(
    tickers: List[str], start_date: str, end_date: str, db_manager: DBManager,
    analysis_engine: AnalysisEngine, input_execution_log: dict, report_overall_start_time: datetime,
    data_task_duration_seconds: float, project_path_local: str, table_name: str
):
    print("\n--- 開始報告生成流程 ---")
    report_pipeline_start_time = datetime.now()
    if not tickers:
         print("警告 (run_report_generation_logic): 標的列表為空，無法生成報告。")
         return
    global hardware_stats_list_global
    hw_report_filename = f"hardware_monitor_report_{report_overall_start_time.strftime('%Y%m%d_%H%M%S')}.csv"
    hardware_report_csv_path = os.path.join(project_path_local, "data_workspace", "logs", "archive", hw_report_filename)
    report_gen = ReportGenerator(
        execution_log=input_execution_log, analysis_engine_instance=analysis_engine,
        hardware_stats=hardware_stats_list_global, hardware_report_csv_path=hardware_report_csv_path
    )
    final_report_str = report_gen.generate_full_report(
        overall_start_date_str=start_date, overall_end_date_str=end_date,
        report_generation_time=datetime.now(), task_duration_seconds=data_task_duration_seconds,
        target_tickers=tickers, db_table_name=table_name
    )
    print("\n--- 市場分析報告內容預覽 ---\n" + "\n".join(final_report_str.splitlines()[:15]) + "\n...")
    report_output_dir = os.path.join(project_path_local, "data_workspace", "reports")
    os.makedirs(report_output_dir, exist_ok=True)
    report_filename_prefix = "market_analysis_report"
    if not input_execution_log and data_task_duration_seconds == 0: report_filename_prefix = "on_demand_report"
    elif not final_report_str or "無可分析數據" in final_report_str: report_filename_prefix = "data_pipeline_summary"
    report_filename = f"{report_filename_prefix}_{report_overall_start_time.strftime('%Y%m%d_%H%M%S')}.md"
    report_filepath = os.path.join(report_output_dir, report_filename)
    try:
        with open(report_filepath, "w", encoding="utf-8") as f: f.write(final_report_str)
        print(f"\n報告已成功儲存至：{report_filepath}")
    except IOError as e:
        print(f"\n錯誤：儲存報告至檔案失敗：{e}")
    print(f"--- 報告生成流程結束 --- 時長: {(datetime.now() - report_pipeline_start_time).total_seconds():.2f} 秒")

def database_writer_worker(db_m: DBManager, lock: threading.Lock, data_q: queue.Queue, stop_event: threading.Event):
    print(f"INFO (DB Writer Thread): 消費者線程 '{threading.current_thread().name}' 已啟動。")
    while not stop_event.is_set() or not data_q.empty():
        try:
            data_item = data_q.get(timeout=1)
            if data_item is None:
                 data_q.task_done(); break
            df_to_write = data_item.get('data')
            table_to_write = data_item.get('table_name')
            ticker = data_item.get('ticker', 'N/A')
            interval = data_item.get('interval', 'N/A')
            if df_to_write is not None and not df_to_write.empty and table_to_write:
                with lock:
                    try:
                        db_m.upsert_data(df_to_write, table_name=table_to_write)
                        print(f"INFO (DB Writer): 寫入 {len(df_to_write)} 筆 {ticker} ({interval}) 到 {table_to_write}")
                    except duckdb.ConstraintException as ce:
                        print(f"INFO (DB Writer): 跳過已存在數據 {ticker} ({interval}) for {table_to_write}. {ce}")
                    except Exception as e_upsert:
                        print(f"ERROR (DB Writer): 寫入錯誤 {ticker} ({interval}) for {table_to_write}. {e_upsert}")
            else:
                print(f"WARN (DB Writer): 無效數據項: Ticker {ticker}, Table {table_to_write}")
        except queue.Empty:
            if stop_event.is_set() and data_q.empty(): break
            continue
        except Exception as e:
            print(f"ERROR (DB Writer Thread): 嚴重錯誤: {e}")
        finally:
            if data_item is not None: data_q.task_done() # Avoid task_done on None if already done
    print(f"INFO (DB Writer Thread): 消費者線程 '{threading.current_thread().name}' 已結束。")

def daily_market_analyzer_main_logic(
    tickers: Optional[str], start_date: Optional[str], end_date: Optional[str],
    data_only: bool, report_only: bool, report_start_date: Optional[str], report_end_date: Optional[str],
    db_path: str, cache_db_path: Optional[str], table_name: str, no_data_cooldown_days: int,
    force_refresh: bool, enable_local_first: bool, gdrive_root: str, project_path_local: str, max_workers: int
):
    global hardware_stats_list_global
    hardware_stats_list_global.clear()
    overall_start_time = datetime.now()
    print(f"--- 每日市場洞察報告引擎 v3.0 (CLI模式) @ {overall_start_time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    log_hardware_stats("main_start")

    if data_only and report_only: raise ValueError("錯誤：--data-only 和 --report-only 不能同時指定。")

    effective_tickers_list = [t.strip().upper() for t in tickers.split(',')] if tickers else []
    current_start_date, current_end_date = start_date, end_date

    if report_only:
        if not report_start_date or not report_end_date: raise ValueError("錯誤：純報告模式需指定 --report-start-date 和 --report-end-date。")
        if not effective_tickers_list: raise ValueError("錯誤：純報告模式需指定 --tickers。")
        current_start_date, current_end_date = report_start_date, report_end_date
    elif not (effective_tickers_list and current_start_date and current_end_date):
        if not data_only: # Full flow needs all
             raise ValueError("錯誤：完整流程或僅數據模式需指定 --tickers, --start-date, --end-date。")

    active_local_first = enable_local_first
    final_db_path = db_path
    local_db_instance_path = None

    if active_local_first:
        if not db_path: active_local_first = False; print("警告: 本地優先模式啟用但 --db-path 未提供，已停用。")
        else:
            db_fname = os.path.basename(db_path)
            if not db_fname: active_local_first = False; print(f"警告: 無法從 --db-path '{db_path}' 推斷檔案名，本地優先已停用。")
            else:
                local_db_dir = os.path.join(project_path_local, "data_workspace", "databases_local")
                local_db_instance_path = os.path.join(local_db_dir, db_fname)
                final_db_path = local_db_instance_path
                print(f"INFO (Local-First): 本地資料庫設為: {final_db_path}")
                if not os.path.exists(local_db_dir): os.makedirs(local_db_dir, exist_ok=True)
                if os.path.exists(db_path): # gdrive_db_path is original db_path
                    print(f"INFO (Local-First): 從 GDrive '{db_path}' 複製到本地 '{final_db_path}'...")
                    shutil.copy2(db_path, final_db_path)
                else: print(f"警告 (Local-First): GDrive 原始檔 '{db_path}' 不存在，將在本地創建。")

    if not active_local_first and final_db_path != db_path : # Fallback if local_first was disabled mid-setup
        final_db_path = db_path
        print(f"INFO (Local-First Fallback): 使用資料庫: {final_db_path}")

    db_cfg = {}
    try:
        available_gb = psutil.virtual_memory().available / (1024**3)
        mem_limit_gb = f"{int(min(available_gb * 0.7, 12.0) * 1024)}MB"
        db_cfg = {'memory_limit': mem_limit_gb}
        print(f"INFO: DuckDB memory_limit: {mem_limit_gb}")
    except Exception as e_mem: print(f"警告: 設定DuckDB記憶體失敗: {e_mem}")

    db_man = DBManager(db_path=final_db_path, target_ohlcv_table_name=table_name, duckdb_config=db_cfg)
    analysis_eng = AnalysisEngine(db_manager_instance=db_man)
    exec_log_data = {}
    data_duration_sec = 0.0
    writer_thr, stop_evt = None, threading.Event()

    try:
        if not report_only:
            writer_thr = threading.Thread(target=database_writer_worker, args=(db_man, DB_WRITE_LOCK, DATA_QUEUE, stop_evt), name="DBWriter")
            writer_thr.start()
            log_hardware_stats("data_pipeline_start")
            yf_cli = YFinanceClient(db_manager=db_man, data_queue=DATA_QUEUE, no_data_cooldown_days=no_data_cooldown_days)
            ds_time = datetime.now()
            exec_log_data, _ = run_data_pipeline_logic(
                effective_tickers_list, current_start_date, current_end_date, db_man, yf_cli, table_name, max_workers, force_refresh
            )
            data_duration_sec = (datetime.now() - ds_time).total_seconds()
            log_hardware_stats("data_pipeline_end")

        if not data_only:
            log_hardware_stats("report_generation_start")
            run_report_generation_logic(
                effective_tickers_list, current_start_date, current_end_date, db_man, analysis_eng,
                exec_log_data, overall_start_time, data_duration_sec, project_path_local, table_name
            )
            log_hardware_stats("report_generation_end")
    finally:
        if writer_thr and writer_thr.is_alive():
            print("INFO (Logic): 等待數據佇列清空...")
            DATA_QUEUE.join()
            print("INFO (Logic): 佇列已清空，發送停止信號給寫入線程...")
            stop_evt.set()
            DATA_QUEUE.put(None) # Ensure writer wakes up
            writer_thr.join(timeout=15)
            if writer_thr.is_alive(): print("警告: DB寫入線程超時未結束。")
            else: print("INFO: DB寫入線程已結束。")

        log_hardware_stats("main_end")
        if active_local_first and local_db_instance_path and db_path and os.path.exists(local_db_instance_path):
            del db_man # Release lock on local DB
            print(f"INFO (Local-First): 回寫本地資料庫 '{local_db_instance_path}' 到 GDrive '{db_path}'...")
            try:
                gdrive_db_dir = os.path.dirname(db_path)
                if gdrive_db_dir and not os.path.exists(gdrive_db_dir): os.makedirs(gdrive_db_dir, exist_ok=True)
                shutil.copy2(local_db_instance_path, db_path)
                print(f"INFO (Local-First): 資料庫成功回寫。")
            except Exception as e_wb: print(f"錯誤 (Local-First): 回寫失敗: {e_wb}")

        if hardware_stats_list_global:
            archive_hardware_stats_to_csv(
                hardware_stats_list_global, project_path_local, gdrive_root,
                overall_start_time.strftime('%Y%m%d_%H%M%S'),
                db_path if active_local_first else final_db_path
            )
    print(f"--- 總任務執行完畢 --- 總時長: {(datetime.now() - overall_start_time).total_seconds():.2f} 秒")
