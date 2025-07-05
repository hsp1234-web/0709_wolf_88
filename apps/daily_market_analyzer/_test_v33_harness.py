# -*- coding: utf-8 -*-
"""
整合測試腳本 for v33.0 "智能獵犬" 引擎升級。
此腳本必須包含並依次通過所有指定的測試案例。
"""
import subprocess
import os
import sys
import time
from datetime import datetime, timedelta, timezone # 新增 timezone
import pandas as pd
import duckdb
import shutil

# --- 配置 ---
PYTHON_EXE = sys.executable
SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'run.py'))
BASE_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data_workspace', 'test_v33_analyzer.duckdb'))
REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data_workspace', 'reports'))
TABLE_NAME = "market_ohlcv_data_test_v33"
LOG_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data_workspace', '_test_v33_harness.log'))

# 測試股票和日期
TICKER_INVALID_HISTORICAL = "GOOG"
START_DATE_INVALID_HISTORICAL = "2000-01-01"
END_DATE_INVALID_HISTORICAL = "2000-02-15" # 擴大日期範圍以觸發 >30 天的預檢邏輯

TICKER_DATA_ONLY = "MSFT"
END_DATE_DATA_ONLY_REPORT_ONLY = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
START_DATE_DATA_ONLY_REPORT_ONLY = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")

TICKER_FULL_FLOW = "NVDA"
END_DATE_FULL_FLOW = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
START_DATE_FULL_FLOW = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

TICKER_PREFLIGHT_FALLBACK = "AMC"
START_DATE_PREFLIGHT_FALLBACK = "2014-01-01"
END_DATE_PREFLIGHT_FALLBACK = "2014-03-30"

# --- 輔助函數 ---
def print_header(message):
    print(f"\n{'='*60}\n{message}\n{'='*60}")

def print_subheader(message):
    print(f"\n--- {message} ---")

def log_message(message, to_console=True):
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    if to_console:
        print(message)

def run_command(command: list[str]) -> tuple[int, str, str]:
    log_message(f"執行命令: {' '.join(command)}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
    stdout, stderr = process.communicate()
    log_message(f"命令返回碼: {process.returncode}")
    if stdout:
        log_message(f"標準輸出:\n{stdout[-1000:]}{'... (輸出過長，已截斷)' if len(stdout)>1000 else ''}", to_console=False)
    if stderr:
        log_message(f"標準錯誤:\n{stderr}", to_console=False)
    return process.returncode, stdout, stderr

def check_log_contains(log_content: str, expected_strings: list[str], case_sensitive=True) -> bool:
    all_found = True
    for s in expected_strings:
        if case_sensitive:
            if s not in log_content:
                log_message(f"檢查日誌: 未找到預期字串 '{s}'")
                all_found = False
        else:
            if s.lower() not in log_content.lower():
                log_message(f"檢查日誌 (不區分大小寫): 未找到預期字串 '{s}'")
                all_found = False
    return all_found

def check_log_not_contains(log_content: str, unexpected_strings: list[str], case_sensitive=True) -> bool:
    none_found = True
    for s in unexpected_strings:
        if case_sensitive:
            if s in log_content:
                log_message(f"檢查日誌: 找到非預期字串 '{s}'")
                none_found = False
        else:
            if s.lower() in log_content.lower():
                log_message(f"檢查日誌 (不區分大小寫): 找到非預期字串 '{s}'")
                none_found = False
    return none_found

def query_duckdb(db_path: str, query: str, params=None) -> pd.DataFrame:
    try:
        with duckdb.connect(db_path, read_only=True) as con:
            if params:
                result = con.execute(query, params).fetchdf()
            else:
                result = con.execute(query).fetchdf()
            log_message(f"DuckDB 查詢: {query} (參數: {params}) -> 返回 {len(result)} 行", to_console=False)
            return result
    except Exception as e:
        log_message(f"DuckDB 查詢失敗: {e}")
        return pd.DataFrame()

def file_exists(filepath: str) -> bool:
    exists = os.path.exists(filepath)
    log_message(f"檢查檔案存在性: {filepath} -> {'存在' if exists else '不存在'}")
    return exists

def cleanup_files(db_to_clean_path: str, report_dir_to_clean: str):
    print_subheader("開始清理...")
    if os.path.exists(db_to_clean_path):
        try:
            os.remove(db_to_clean_path)
            log_message(f"已刪除測試資料庫: {db_to_clean_path}")
        except Exception as e:
            log_message(f"刪除測試資料庫失敗 {db_to_clean_path}: {e}")

    if os.path.exists(report_dir_to_clean):
        for item in os.listdir(report_dir_to_clean):
            if item.endswith(".md") and ("market_analysis_report_" in item or "on_demand_report_" in item or "data_pipeline_summary_" in item):
                item_path = os.path.join(report_dir_to_clean, item)
                try:
                    os.remove(item_path)
                    log_message(f"已刪除測試報告檔案: {item_path}")
                except Exception as e:
                    log_message(f"刪除測試報告檔案失敗 {item_path}: {e}")
    log_message("清理完成。")

def get_report_files(directory: str) -> list[str]:
    if not os.path.exists(directory):
        return []
    return [f for f in os.listdir(directory) if f.endswith(".md") and ("market_analysis_report_" in f or "on_demand_report_" in f or "data_pipeline_summary_" in f)]

# --- 測試案例 ---

def test_1_invalid_historical_data():
    print_header("測試 1: 無效歷史數據測試 (`--data-only`)")
    cleanup_files(BASE_DB_PATH, REPORTS_DIR)

    cmd = [
        PYTHON_EXE, SCRIPT_PATH,
        "--tickers", TICKER_INVALID_HISTORICAL,
        "--start-date", START_DATE_INVALID_HISTORICAL,
        "--end-date", END_DATE_INVALID_HISTORICAL,
        "--db-path", BASE_DB_PATH,
        "--table-name", TABLE_NAME,
        "--data-only"
    ]
    returncode, stdout, stderr = run_command(cmd)

    assert returncode == 0, f"測試 1 失敗: 命令執行失敗 (返回碼 {returncode})"
    log_message("測試 1: 命令執行成功。")

    expected_in_log_actual = [
        f"Performing existence pre-flight check for historical range [{START_DATE_INVALID_HISTORICAL} to {END_DATE_INVALID_HISTORICAL}]",
        f"INFO: Pre-flight check for {TICKER_INVALID_HISTORICAL} from {START_DATE_INVALID_HISTORICAL} to {END_DATE_INVALID_HISTORICAL} (1mo) failed. Attempting secondary pre-flight with '1d'.",
        f"INFO: Secondary pre-flight check for {TICKER_INVALID_HISTORICAL} from {START_DATE_INVALID_HISTORICAL} to {END_DATE_INVALID_HISTORICAL} (1d) also failed. Skipping all intervals.",
        f"===== 數據回填任務結束 (預檢 '1mo' 及 '1d' 均失敗): Ticker={TICKER_INVALID_HISTORICAL} ====="
    ]

    assert check_log_contains(stdout, expected_in_log_actual, case_sensitive=False), "測試 1 失敗: 日誌未包含預檢失敗的關鍵訊息。"
    log_message("測試 1: 日誌包含預檢失敗訊息。")

    pre_flight_failed_marker = f"INFO: Secondary pre-flight check for {TICKER_INVALID_HISTORICAL} from {START_DATE_INVALID_HISTORICAL} to {END_DATE_INVALID_HISTORICAL} (1d) also failed. Skipping all intervals."
    marker_index = stdout.find(pre_flight_failed_marker)

    assert marker_index != -1, f"測試 1 失敗: 未在日誌中找到預檢失敗標記 '{pre_flight_failed_marker}' (這表示1mo和1d預檢都失敗的日誌)。"
    log_message(f"測試 1: 在日誌中找到預檢失敗標記 (1d also failed): '{pre_flight_failed_marker}'")

    stdout_after_marker = stdout[marker_index + len(pre_flight_failed_marker):]

    unexpected_strings_after_preflight_failure = [
        f"INFO: hydrate_data_range: Ticker={TICKER_INVALID_HISTORICAL}. 正在評估顆粒度 '1d'",
        f"INFO: hydrate_data_range: Ticker={TICKER_INVALID_HISTORICAL}. 正在評估顆粒度 '1h'",
        f"INFO: hydrate_data_range: Ticker={TICKER_INVALID_HISTORICAL}. 正在評估顆粒度 '1m'",
        f"fetch_single_chunk: Ticker={TICKER_INVALID_HISTORICAL}, Interval=1d",
        f"fetch_single_chunk: Ticker={TICKER_INVALID_HISTORICAL}, Interval=1h",
        f"fetch_single_chunk: Ticker={TICKER_INVALID_HISTORICAL}, Interval=1m",
    ]

    assert check_log_not_contains(stdout_after_marker, unexpected_strings_after_preflight_failure, case_sensitive=False), \
        "測試 1 失敗: 在預檢失敗標記之後的日誌中發現了多餘的 interval 嘗試記錄。"
    log_message("測試 1: 預檢失敗後未進行多餘的 interval 嘗試。")

    db_data = query_duckdb(BASE_DB_PATH, f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE ticker = '{TICKER_INVALID_HISTORICAL}' AND datetime >= '{START_DATE_INVALID_HISTORICAL}' AND datetime <= '{END_DATE_INVALID_HISTORICAL} 23:59:59'")
    assert db_data['count_star()'].iloc[0] == 0, f"測試 1 失敗: 資料庫中不應存在 {TICKER_INVALID_HISTORICAL} 的數據，但找到了 {db_data['count_star()'].iloc[0]} 筆。"
    log_message(f"測試 1: 資料庫中沒有 {TICKER_INVALID_HISTORICAL} 在無效日期的數據。測試通過！")
    return True


def test_2_data_only_mode():
    print_header("測試 2: 純數據處理測試 (`--data-only`)")
    cleanup_files(BASE_DB_PATH, REPORTS_DIR)
    initial_reports = get_report_files(REPORTS_DIR)

    cmd = [
        PYTHON_EXE, SCRIPT_PATH,
        "--tickers", TICKER_DATA_ONLY,
        "--start-date", START_DATE_DATA_ONLY_REPORT_ONLY,
        "--end-date", END_DATE_DATA_ONLY_REPORT_ONLY,
        "--db-path", BASE_DB_PATH,
        "--table-name", TABLE_NAME,
        "--data-only"
    ]
    returncode, stdout, stderr = run_command(cmd)

    assert returncode == 0, f"測試 2 失敗: 命令執行失敗 (返回碼 {returncode})"
    log_message("測試 2: 命令執行成功。")

    expected_in_log = [
        f"執行模式：僅數據處理 (--data-only)",
        f"開始處理標的 (數據流程): {TICKER_DATA_ONLY}",
        f"資訊：標的 {TICKER_DATA_ONLY} 數據成功寫入資料庫",
        "數據處理流程結束"
    ]
    assert check_log_contains(stdout, expected_in_log, case_sensitive=False), "測試 2 失敗: 日誌未包含數據處理成功的關鍵訊息。"
    log_message("測試 2: 日誌包含數據處理成功訊息。")

    db_data = query_duckdb(BASE_DB_PATH, f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE ticker = '{TICKER_DATA_ONLY}' AND datetime >= '{START_DATE_DATA_ONLY_REPORT_ONLY}' AND datetime <= '{END_DATE_DATA_ONLY_REPORT_ONLY} 23:59:59'")
    assert db_data['count_star()'].iloc[0] > 0, f"測試 2 失敗: 資料庫中應存在 {TICKER_DATA_ONLY} 的數據，但未找到。"
    log_message(f"測試 2: 資料庫中已寫入 {TICKER_DATA_ONLY} 的數據 ({db_data['count_star()'].iloc[0]} 筆)。")

    final_reports = get_report_files(REPORTS_DIR)
    new_reports = [r for r in final_reports if r not in initial_reports]
    assert not new_reports, f"測試 2 失敗: --data-only 模式不應生成報告，但生成了: {new_reports}"
    log_message("測試 2: 未生成報告檔案。測試通過！")
    return True


def test_3_report_only_mode():
    print_header("測試 3: 純報告生成測試 (`--report-only`)")
    initial_reports = get_report_files(REPORTS_DIR)

    cmd = [
        PYTHON_EXE, SCRIPT_PATH,
        "--tickers", TICKER_DATA_ONLY,
        "--report-start-date", START_DATE_DATA_ONLY_REPORT_ONLY,
        "--report-end-date", END_DATE_DATA_ONLY_REPORT_ONLY,
        "--db-path", BASE_DB_PATH,
        "--table-name", TABLE_NAME,
        "--report-only"
    ]
    returncode, stdout, stderr = run_command(cmd)

    assert returncode == 0, f"測試 3 失敗: 命令執行失敗 (返回碼 {returncode})"
    log_message("測試 3: 命令執行成功。")

    expected_in_log = [
        "執行模式：僅報告生成 (--report-only)",
        f"INFO (run_report_generation): Generating report for tickers: ['{TICKER_DATA_ONLY}'] over range [{START_DATE_DATA_ONLY_REPORT_ONLY} to {END_DATE_DATA_ONLY_REPORT_ONLY}]",
        "報告已成功儲存至"
    ]
    assert check_log_contains(stdout, expected_in_log, case_sensitive=False), "測試 3 失敗: 日誌未包含報告生成成功的關鍵訊息。"
    log_message("測試 3: 日誌包含報告生成成功訊息。")

    unexpected_in_log_actual = [
        "--- 開始數據處理流程 ---",
        "hydrate_data_range",
        "YFinanceClient (Data Hydrator v33.0) 初始化完畢"
    ]
    assert check_log_not_contains(stdout, unexpected_in_log_actual, case_sensitive=False), "測試 3 失敗: 日誌中包含數據獲取相關的多餘訊息。"
    log_message("測試 3: 日誌未包含數據獲取相關訊息。")

    final_reports = get_report_files(REPORTS_DIR)
    found_on_demand_report = any("on_demand_report_" in r for r in final_reports)

    assert found_on_demand_report, f"測試 3 失敗: 未能找到預期的 'on_demand_report_*.md' 報告檔案。"
    log_message("測試 3: 成功生成報告檔案。測試通過！")
    return True


def test_4_full_flow():
    print_header("測試 4: 完整流程測試")
    cleanup_files(BASE_DB_PATH, REPORTS_DIR)
    initial_reports = get_report_files(REPORTS_DIR)

    cmd = [
        PYTHON_EXE, SCRIPT_PATH,
        "--tickers", TICKER_FULL_FLOW,
        "--start-date", START_DATE_FULL_FLOW,
        "--end-date", END_DATE_FULL_FLOW,
        "--db-path", BASE_DB_PATH,
        "--table-name", TABLE_NAME
    ]
    returncode, stdout, stderr = run_command(cmd)

    assert returncode == 0, f"測試 4 失敗: 命令執行失敗 (返回碼 {returncode})"
    log_message("測試 4: 命令執行成功。")

    expected_in_log = [
        "執行模式：完整流程 (數據處理與報告生成)",
        f"開始處理標的 (數據流程): {TICKER_FULL_FLOW}",
        f"資訊：標的 {TICKER_FULL_FLOW} 數據成功寫入資料庫",
        "數據處理流程結束",
        "開始報告生成流程",
        f"INFO (run_report_generation): Generating report for tickers: ['{TICKER_FULL_FLOW}'] over range [{START_DATE_FULL_FLOW} to {END_DATE_FULL_FLOW}]",
        "報告已成功儲存至"
    ]
    assert check_log_contains(stdout, expected_in_log, case_sensitive=False), "測試 4 失敗: 日誌未包含完整流程成功的關鍵訊息。"
    log_message("測試 4: 日誌包含完整流程成功訊息。")

    db_data = query_duckdb(BASE_DB_PATH, f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE ticker = '{TICKER_FULL_FLOW}' AND datetime >= '{START_DATE_FULL_FLOW}' AND datetime <= '{END_DATE_FULL_FLOW} 23:59:59'")
    assert db_data['count_star()'].iloc[0] > 0, f"測試 4 失敗: 資料庫中應存在 {TICKER_FULL_FLOW} 的數據，但未找到。"
    log_message(f"測試 4: 資料庫中已寫入 {TICKER_FULL_FLOW} 的數據 ({db_data['count_star()'].iloc[0]} 筆)。")

    final_reports = get_report_files(REPORTS_DIR)
    found_full_flow_report = any("market_analysis_report_" in r for r in final_reports)

    assert found_full_flow_report, f"測試 4 失敗: 未能找到預期的 'market_analysis_report_*.md' 報告檔案。"
    log_message("測試 4: 成功生成報告檔案。測試通過！")
    return True

def test_5_preflight_fallback():
    print_header("測試 5: 預檢回退邏輯測試 (`--data-only`)")
    cleanup_files(BASE_DB_PATH, REPORTS_DIR)

    cmd = [
        PYTHON_EXE, SCRIPT_PATH,
        "--tickers", TICKER_PREFLIGHT_FALLBACK,
        "--start-date", START_DATE_PREFLIGHT_FALLBACK,
        "--end-date", END_DATE_PREFLIGHT_FALLBACK,
        "--db-path", BASE_DB_PATH,
        "--table-name", TABLE_NAME,
        "--data-only",
        "--force-refresh"
    ]
    returncode, stdout, stderr = run_command(cmd)

    assert returncode == 0, f"測試 5 失敗: 命令執行失敗 (返回碼 {returncode})"
    log_message("測試 5: 命令執行成功。")

    preflight_trigger_log = f"Performing existence pre-flight check for historical range [{START_DATE_PREFLIGHT_FALLBACK} to {END_DATE_PREFLIGHT_FALLBACK}]"
    assert preflight_trigger_log.lower() in stdout.lower(), \
        f"測試 5 失敗: 未觸發預檢邏輯 (沒有 '{preflight_trigger_log}' 日誌)。實際日誌片段: {stdout[:1000]}"
    log_message("測試 5: 日誌包含 'Performing existence pre-flight check'。")

    log_1mo_failed = f"INFO: Pre-flight check for {TICKER_PREFLIGHT_FALLBACK} from {START_DATE_PREFLIGHT_FALLBACK} to {END_DATE_PREFLIGHT_FALLBACK} (1mo) failed. Attempting secondary pre-flight with '1d'."
    log_1mo_success = f"INFO: Pre-flight check for {TICKER_PREFLIGHT_FALLBACK} from {START_DATE_PREFLIGHT_FALLBACK} to {END_DATE_PREFLIGHT_FALLBACK} (1mo) successful. Proceeding with detailed fetch."

    if log_1mo_failed.lower() in stdout.lower():
        log_message("測試 5: 觀察到 '1mo' 預檢失敗路徑。")
        secondary_1d_successful_log = f"INFO: Secondary pre-flight check for {TICKER_PREFLIGHT_FALLBACK} from {START_DATE_PREFLIGHT_FALLBACK} to {END_DATE_PREFLIGHT_FALLBACK} (1d) successful."
        secondary_1d_also_failed_log = f"INFO: Secondary pre-flight check for {TICKER_PREFLIGHT_FALLBACK} from {START_DATE_PREFLIGHT_FALLBACK} to {END_DATE_PREFLIGHT_FALLBACK} (1d) also failed."

        if secondary_1d_successful_log.lower() in stdout.lower():
            log_message("測試 5: '1mo' 預檢失敗後，'1d' 二次預檢成功。")
            expected_logs = [
                log_1mo_failed,
                secondary_1d_successful_log,
                f"Using HISTORICAL_FALLBACK: {['1d', '1wk', '1mo']}",
                f"INFO: hydrate_data_range: Ticker={TICKER_PREFLIGHT_FALLBACK}. 正在評估顆粒度 '1d'",
                f"fetch_single_chunk: Ticker={TICKER_PREFLIGHT_FALLBACK}, Interval=1d",
                f"資訊：標的 {TICKER_PREFLIGHT_FALLBACK} 數據成功寫入資料庫"
            ]
            assert check_log_contains(stdout, expected_logs, case_sensitive=False), "測試 5 失敗: ('1mo' 失敗, '1d' 成功) 路徑的日誌不匹配。"
            db_data = query_duckdb(BASE_DB_PATH, f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE ticker = '{TICKER_PREFLIGHT_FALLBACK}'")
            assert db_data['count_star()'].iloc[0] > 0, "測試 5 失敗: ('1mo' 失敗, '1d' 成功) 路徑下，資料庫應有數據。"
            log_message(f"測試 5: ('1mo' 失敗, '1d' 成功) 路徑下，資料庫已寫入 {db_data['count_star()'].iloc[0]} 筆數據。")
        elif secondary_1d_also_failed_log.lower() in stdout.lower():
            log_message("測試 5: '1mo' 預檢失敗後，'1d' 二次預檢也失敗。")
            expected_logs = [
                 log_1mo_failed,
                 secondary_1d_also_failed_log,
                 f"===== 數據回填任務結束 (預檢 '1mo' 及 '1d' 均失敗): Ticker={TICKER_PREFLIGHT_FALLBACK} ====="
            ]
            assert check_log_contains(stdout, expected_logs, case_sensitive=False), "測試 5 失敗: ('1mo' 失敗, '1d' 失敗) 路徑的日誌不匹配。"
            db_data = query_duckdb(BASE_DB_PATH, f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE ticker = '{TICKER_PREFLIGHT_FALLBACK}'")
            assert db_data['count_star()'].iloc[0] == 0, "測試 5 失敗: ('1mo' 失敗, '1d' 失敗) 路徑下，資料庫不應有數據。"
            log_message(f"測試 5: ('1mo' 失敗, '1d' 失敗) 路徑下，資料庫中沒有 {TICKER_PREFLIGHT_FALLBACK} 的數據。")
        else:
            assert False, "測試 5 失敗: '1mo' 預檢失敗後，未明確找到 '1d' 二次預檢成功或失敗的日誌。"

    elif log_1mo_success.lower() in stdout.lower():
        log_message("測試 5: 觀察到 '1mo' 預檢成功路徑。")
        expected_logs = [
            log_1mo_success,
            f"Using HISTORICAL_FALLBACK: {['1d', '1wk', '1mo']}",
            f"INFO: hydrate_data_range: Ticker={TICKER_PREFLIGHT_FALLBACK}. 正在評估顆粒度 '1d'",
            f"fetch_single_chunk: Ticker={TICKER_PREFLIGHT_FALLBACK}, Interval=1d",
        ]
        assert check_log_contains(stdout, expected_logs, case_sensitive=False), "測試 5 失敗: '1mo' 預檢成功路徑的日誌不匹配。"
        db_data = query_duckdb(BASE_DB_PATH, f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE ticker = '{TICKER_PREFLIGHT_FALLBACK}'")
        assert db_data['count_star()'].iloc[0] > 0, "測試 5 失敗: '1mo' 預檢成功且後續1d獲取數據後，資料庫應有數據。"
        log_message(f"測試 5: '1mo' 預檢成功路徑下，資料庫已寫入 {db_data['count_star()'].iloc[0]} 筆數據。")
        assert f"資訊：標的 {TICKER_PREFLIGHT_FALLBACK} 數據成功寫入資料庫".lower() in stdout.lower(), "測試 5 失敗: '1mo' 預檢成功路徑下，未找到數據成功寫入資料庫的日誌。"
    else:
        assert False, f"測試 5 失敗: 日誌中既未找到 '1mo' 預檢成功 ('{log_1mo_success}') 也未找到失敗 ('{log_1mo_failed}') 的明確標記。Stdout: {stdout[:1500]}"

    log_message("測試 5: 預檢回退邏輯測試通過！")
    return True


def test_6_no_data_skip_logic():
    print_header("測試 6: 無數據區塊記錄與跳過邏輯測試")
    cleanup_files(BASE_DB_PATH, REPORTS_DIR)

    ticker_no_data = "NOEXISTS.TICKER"
    start_date_no_data = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    end_date_no_data = (datetime.now() - timedelta(days=9)).strftime("%Y-%m-%d")
    cooldown_param = "1"

    print_subheader("測試 6.1: 首次執行 - 記錄無數據區塊")
    cmd1 = [
        PYTHON_EXE, SCRIPT_PATH,
        "--tickers", ticker_no_data,
        "--start-date", start_date_no_data,
        "--end-date", end_date_no_data,
        "--db-path", BASE_DB_PATH,
        "--table-name", TABLE_NAME,
        "--data-only",
        "--no_data_cooldown_days", cooldown_param
    ]
    returncode1, stdout1, stderr1 = run_command(cmd1)
    assert returncode1 == 0, f"測試 6.1 失敗: 命令執行失敗 (返回碼 {returncode1})"

    expected_in_log1 = [
        f"fetch_single_chunk: Ticker={ticker_no_data}",
        f"INFO: fetch_single_chunk: [情報] {ticker_no_data}",
        f"此區塊已被記錄為無數據",
        f"INFO: 已記錄/更新無數據區塊: Ticker={ticker_no_data}",
    ]
    assert check_log_contains(stdout1, expected_in_log1), "測試 6.1 失敗: 首次執行的日誌未包含預期訊息。"
    log_message("測試 6.1: 首次執行日誌驗證通過。")

    no_data_entry_query_any_for_ticker = f"SELECT COUNT(*) FROM no_data_records WHERE ticker = '{ticker_no_data}'"
    db_record_check = query_duckdb(BASE_DB_PATH, no_data_entry_query_any_for_ticker)
    assert db_record_check['count_star()'].iloc[0] > 0, f"測試 6.1 失敗: 資料庫 no_data_records 中未找到 {ticker_no_data} 的記錄。"
    log_message(f"測試 6.1: 資料庫 no_data_records 中已為 {ticker_no_data} 寫入記錄。")

    print_subheader("測試 6.2: 第二次執行 - 跳過 API 呼叫")
    time.sleep(1)
    cmd2 = cmd1
    returncode2, stdout2, stderr2 = run_command(cmd2)
    assert returncode2 == 0, f"測試 6.2 失敗: 命令執行失敗 (返回碼 {returncode2})"

    expected_in_log2 = [
        f"DEBUG: 發現有效的無數據記錄: Ticker={ticker_no_data}",
        f"[數據偵查] Ticker={ticker_no_data}",
        f"已跳過",
        f"因在最近 {cooldown_param} 天內曾記錄為無數據區塊"
    ]
    assert check_log_contains(stdout2, expected_in_log2), "測試 6.2 失敗: 第二次執行的日誌未包含預期跳過訊息。"

    unexpected_in_log2 = [
        f"fetch_single_chunk: Ticker={ticker_no_data}",
        f"INFO: 已記錄/更新無數據區塊: Ticker={ticker_no_data}"
    ]
    assert check_log_not_contains(stdout2, unexpected_in_log2), "測試 6.2 失敗: 第二次執行的日誌中包含不應出現的 fetch 或記錄訊息。"
    log_message("測試 6.2: 第二次執行日誌驗證通過，API 呼叫已跳過。")

    print_subheader("測試 6.3: 第三次執行 - 冷卻期過後，重新嘗試")
    two_days_ago_iso = (datetime.now(timezone.utc) - timedelta(days=int(cooldown_param) + 1)).isoformat()
    try:
        with duckdb.connect(BASE_DB_PATH) as con:
            update_query = f"UPDATE no_data_records SET recorded_at = '{two_days_ago_iso}' WHERE ticker = '{ticker_no_data}'"
            con.execute(update_query)
            log_message(f"測試 6.3: 已手動將 {ticker_no_data} 在 no_data_records 中的 recorded_at 更新為 {two_days_ago_iso}")
    except Exception as e:
        log_message(f"測試 6.3 錯誤: 更新 no_data_records 失敗: {e}")
        assert False, f"測試 6.3 準備失敗: 無法更新資料庫記錄: {e}"

    cmd3 = cmd1
    returncode3, stdout3, stderr3 = run_command(cmd3)
    assert returncode3 == 0, f"測試 6.3 失敗: 命令執行失敗 (返回碼 {returncode3})"

    unexpected_in_log3_after_cooldown = [
        f"DEBUG: 發現有效的無數據記錄: Ticker={ticker_no_data}",
        f"[數據偵查] Ticker={ticker_no_data}.*已跳過"
    ]
    assert check_log_not_contains(stdout3, [unexpected_in_log3_after_cooldown[0]]), "測試 6.3 失敗: 冷卻期過後，仍將記錄視為有效。"
    assert check_log_not_contains(stdout3, [f"[數據偵查] Ticker={ticker_no_data}","已跳過"], case_sensitive=False), "測試 6.3 失敗: 冷卻期過後，仍在日誌中發現跳過訊息。"

    expected_in_log3_after_cooldown = [
        f"fetch_single_chunk: Ticker={ticker_no_data}",
        f"INFO: 已記錄/更新無數據區塊: Ticker={ticker_no_data}",
    ]
    assert check_log_contains(stdout3, expected_in_log3_after_cooldown), "測試 6.3 失敗: 冷卻期過後的日誌未包含預期的 fetch 和記錄訊息。"
    log_message("測試 6.3: 第三次執行日誌驗證通過，冷卻期過後重新嘗試 API 並記錄。")

    log_message("測試 6: 無數據區塊記錄與跳過邏輯測試通過！")
    return True


# --- 主執行邏輯 ---
if __name__ == "__main__":
    log_dir = os.path.dirname(LOG_FILE_PATH)
    print(f"DEBUG: Determined log directory: {log_dir}")
    if not os.path.exists(log_dir):
        print(f"DEBUG: Log directory {log_dir} does not exist. Attempting to create.")
        try:
            os.makedirs(log_dir, exist_ok=True)
            if os.path.exists(log_dir):
                print(f"INFO: Test harness created log directory: {log_dir}")
            else:
                print(f"CRITICAL_ERROR: os.makedirs was called for {log_dir}, but it still does not exist!")
                sys.exit(f"CRITICAL_FAILURE: Could not create log directory: {log_dir}")
        except Exception as e:
            print(f"CRITICAL_ERROR: Failed to create log directory {log_dir}: {e}")
            sys.exit(f"CRITICAL_FAILURE: Exception while creating log directory: {log_dir} - {e}")
    else:
        print(f"DEBUG: Log directory {log_dir} already exists.")

    if os.path.exists(LOG_FILE_PATH):
        try:
            os.remove(LOG_FILE_PATH)
        except Exception as e:
            print(f"WARNING: Failed to remove existing log file {LOG_FILE_PATH}: {e}. Log output may be mixed.")

    log_message(f"測試腳本 _test_v33_harness.py 開始執行。日誌將記錄於: {LOG_FILE_PATH}", to_console=True)
    log_message(f"Python 解譯器: {PYTHON_EXE}", to_console=False)
    log_message(f"待測腳本: {SCRIPT_PATH}", to_console=False)
    log_message(f"測試資料庫: {BASE_DB_PATH}", to_console=False)
    log_message(f"報告目錄: {REPORTS_DIR}", to_console=False)
    log_message(f"測試表格: {TABLE_NAME}", to_console=False)

    tests_passed = 0
    total_tests = 0

    all_tests = [
        test_1_invalid_historical_data,
        test_2_data_only_mode,
        test_3_report_only_mode,
        test_4_full_flow,
        test_5_preflight_fallback,
        test_6_no_data_skip_logic
    ]
    total_tests = len(all_tests)

    for i, test_func in enumerate(all_tests):
        test_name = test_func.__name__
        log_message(f"開始執行測試 ({i+1}/{total_tests}): {test_name}", to_console=True)
        try:
            if test_func():
                tests_passed += 1
                log_message(f"測試 ({i+1}/{total_tests}): {test_name} 通過。", to_console=True)
            else:
                log_message(f"測試 ({i+1}/{total_tests}): {test_name} 失敗 (斷言觸發)。", to_console=True)
        except AssertionError as ae:
            log_message(f"測試 ({i+1}/{total_tests}): {test_name} 失敗 (斷言錯誤): {ae}", to_console=True)
            import traceback
            log_message(traceback.format_exc(), to_console=False)
        except Exception as e:
            log_message(f"測試 ({i+1}/{total_tests}): {test_name} 執行時發生意外錯誤: {e}", to_console=True)
            import traceback
            log_message(traceback.format_exc(), to_console=False)

        time.sleep(0.5)


    print_header("測試總結")
    log_message(f"總共規劃測試: {total_tests}", to_console=True)
    log_message(f"通過測試數: {tests_passed}", to_console=True)

    if tests_passed == total_tests and total_tests > 0 :
        log_message("所有 v33.0 整合測試案例均已通過！", to_console=True)
        sys.exit(0)
    else:
        log_message(f"v33.0 整合測試未完全通過 ({tests_passed}/{total_tests})。請檢查日誌 '{LOG_FILE_PATH}'。", to_console=True)
        sys.exit(1)

print("INFO: _test_v33_harness.py 腳本定義完畢。")
