# -*- coding: utf-8 -*-
"""
整合測試腳本 for v33.0 "智能獵犬" 引擎升級。
此腳本必須包含並依次通過所有指定的測試案例。
"""
import subprocess
import os
import sys
import time
from datetime import datetime, timedelta
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

# 針對測試 5: 預檢回退
# 我們需要一個在 yfinance 上近期沒有月線數據，但有日線數據的標的。
# 這通常發生在非常新的 IPO，或者某些特定市場的股票。
# 為了測試的穩定性，我們可能需要一個更可控的方式，或者接受這個測試可能因數據源變化而不穩定。
# 假設 "FAKEAPPL.US" 是一個符合條件的虛構代碼，或者我們可以找到一個真實但不常用的代碼。
# 為了使測試更具確定性，我們將使用一個已知的、在特定歷史時期只有日線的標的。
# 例如，一個在2023年才IPO的股票，在2022年查詢月線會失敗，但日線可能也失敗。
# 這裡我們用一個代號，並期望 yfinance 對此代號的 '1mo' 請求失敗，對 '1d' 請求成功。
# 注意：這個測試的可靠性高度依賴 yfinance 返回的數據。
TICKER_PREFLIGHT_FALLBACK = "AMC" # AMC 在某些早期歷史區間可能更稀疏
# 選擇一個較早的日期，增加 '1mo' 數據缺失的可能性，但 '1d' 數據可能存在
START_DATE_PREFLIGHT_FALLBACK = "2014-01-01"
END_DATE_PREFLIGHT_FALLBACK = "2014-03-30" # 查詢一個季度左右的數據，超過30天觸發預檢

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
        log_message(f"標準輸出:\n{stdout[-1000:]}{'... (輸出過長，已截斷)' if len(stdout)>1000 else ''}", to_console=False) # Log last 1000 chars
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

    # 清理報告目錄下的 md 檔案 (避免刪除其他可能的非測試報告)
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
    cleanup_files(BASE_DB_PATH, REPORTS_DIR) # 清理舊數據

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

    expected_in_log = [
        f"Pre-flight check for {TICKER_INVALID_HISTORICAL} from {START_DATE_INVALID_HISTORICAL} to {END_DATE_INVALID_HISTORICAL} (1mo) failed",
        "Skipping all intervals",
        "INFO: Pre-flight check for TICKER failed. Skipping all intervals." # 這是指令中要求的日誌格式，但 yfinance_client.py 中實際日誌可能不同
    ]
    # yfinance_client.py 實際日誌是 "INFO: Pre-flight check for {ticker} from {start_date_str} to {end_date_str} (1mo) failed. Skipping all intervals."
    # 和 "status": "preflight_failed_empty"
    # 我們需要根據實際輸出來調整 expected_in_log

    # 更新為更精確的預期日誌 (基於 yfinance_client.py 的實現)
    # overall_execution_log 的內部狀態不會直接打印到 stdout，所以不檢查 status 和 message JSON 片段
    expected_in_log_actual = [
        f"Performing existence pre-flight check for historical range [{START_DATE_INVALID_HISTORICAL} to {END_DATE_INVALID_HISTORICAL}]",
        f"INFO: Pre-flight check for {TICKER_INVALID_HISTORICAL} from {START_DATE_INVALID_HISTORICAL} to {END_DATE_INVALID_HISTORICAL} (1mo) failed. Skipping all intervals.",
        f"===== 數據回填任務結束 (預檢失敗): Ticker={TICKER_INVALID_HISTORICAL} =====" # 修正為匹配 yfinance_client.py 的中文輸出
    ]

    assert check_log_contains(stdout, expected_in_log_actual, case_sensitive=False), "測試 1 失敗: 日誌未包含預檢失敗的關鍵訊息。"
    log_message("測試 1: 日誌包含預檢失敗訊息。")

    unexpected_in_log = [
        f"正在評估顆粒度 '1d'", # 不應嘗試 1d
        f"正在評估顆粒度 '1h'", # 不應嘗試 1h
        f"正在評估顆粒度 '1m'", # 不應嘗試 1m
        f"fetch_single_chunk: Ticker={TICKER_INVALID_HISTORICAL}, Interval=1d",
        f"fetch_single_chunk: Ticker={TICKER_INVALID_HISTORICAL}, Interval=1h",
        f"fetch_single_chunk: Ticker={TICKER_INVALID_HISTORICAL}, Interval=1m",
    ]
    # 預檢後，不應該有對 '1mo' 以外的 interval 的 fetch_single_chunk 嘗試 (除了預檢本身的 '1mo')
    # 也不應該有 "正在評估顆粒度" 除了可能的 '1mo' (如果預檢邏輯在那裡)
    # 由於預檢是在 hydrate_data_range 的開頭，如果失敗則直接返回，因此不應看到後續 interval 的評估日誌。

    # 調整 unexpected_in_log 以反映 yfinance_client 的實際日誌輸出
    # 如果預檢失敗，hydrate_data_range 會提前退出，不會進入 fallback interval 循環。
    # 所以，不應該看到 "正在評估顆粒度" for '1d', '1h', '1m' for the main hydration loop.
    # unexpected_in_log_actual = [ # 舊的檢查，會檢查整個 stdout
    #     f"INFO: hydrate_data_range: Ticker={TICKER_INVALID_HISTORICAL}. 正在評估顆粒度 '1d'",
    #     f"INFO: hydrate_data_range: Ticker={TICKER_INVALID_HISTORICAL}. 正在評估顆粒度 '1h'",
    #     f"INFO: hydrate_data_range: Ticker={TICKER_INVALID_HISTORICAL}. 正在評估顆粒度 '1m'",
    #     f"fetch_single_chunk: Ticker={TICKER_INVALID_HISTORICAL}, Interval=1d",
    #     f"fetch_single_chunk: Ticker={TICKER_INVALID_HISTORICAL}, Interval=1h",
    #     f"fetch_single_chunk: Ticker={TICKER_INVALID_HISTORICAL}, Interval=1m",
    # ]
    # assert check_log_not_contains(stdout, unexpected_in_log_actual, case_sensitive=False), "測試 1 失敗: 日誌中包含多餘的 interval 嘗試記錄。"
    # log_message("測試 1: 日誌未包含多餘的 interval 嘗試。")

    # --- 新增的更精確的檢查 ---
    pre_flight_failed_marker = f"INFO: Pre-flight check for {TICKER_INVALID_HISTORICAL} from {START_DATE_INVALID_HISTORICAL} to {END_DATE_INVALID_HISTORICAL} (1mo) failed. Skipping all intervals."
    marker_index = stdout.find(pre_flight_failed_marker)

    assert marker_index != -1, f"測試 1 失敗: 未在日誌中找到預檢失敗標記 '{pre_flight_failed_marker}'"
    log_message(f"測試 1: 在日誌中找到預檢失敗標記: '{pre_flight_failed_marker}'")

    # 只檢查標記之後的日誌內容
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
    # --- 結束新增的檢查 ---

    db_data = query_duckdb(BASE_DB_PATH, f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE ticker = '{TICKER_INVALID_HISTORICAL}' AND datetime >= '{START_DATE_INVALID_HISTORICAL}' AND datetime <= '{END_DATE_INVALID_HISTORICAL} 23:59:59'")
    assert db_data['count_star()'].iloc[0] == 0, f"測試 1 失敗: 資料庫中不應存在 {TICKER_INVALID_HISTORICAL} 的數據，但找到了 {db_data['count_star()'].iloc[0]} 筆。"
    log_message(f"測試 1: 資料庫中沒有 {TICKER_INVALID_HISTORICAL} 在無效日期的數據。測試通過！")
    return True


def test_2_data_only_mode():
    print_header("測試 2: 純數據處理測試 (`--data-only`)")
    # 清理應確保不影響後續測試，如果後續測試依賴此處生成的數據
    # test_3 依賴 test_2 的數據，所以這裡不應該完全清理 DB，或者 test_3 自己準備數據
    # 根據指令 "緊接著上一步"，我們在這裡生成數據，test_3 使用它。
    # 所以，在 test_2 執行 *前* 清理，執行 *後* 不清理 DB。
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

    # 驗證數據庫
    db_data = query_duckdb(BASE_DB_PATH, f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE ticker = '{TICKER_DATA_ONLY}' AND datetime >= '{START_DATE_DATA_ONLY_REPORT_ONLY}' AND datetime <= '{END_DATE_DATA_ONLY_REPORT_ONLY} 23:59:59'")
    assert db_data['count_star()'].iloc[0] > 0, f"測試 2 失敗: 資料庫中應存在 {TICKER_DATA_ONLY} 的數據，但未找到。"
    log_message(f"測試 2: 資料庫中已寫入 {TICKER_DATA_ONLY} 的數據 ({db_data['count_star()'].iloc[0]} 筆)。")

    # 驗證未生成報告
    final_reports = get_report_files(REPORTS_DIR)
    new_reports = [r for r in final_reports if r not in initial_reports]
    assert not new_reports, f"測試 2 失敗: --data-only 模式不應生成報告，但生成了: {new_reports}"
    log_message("測試 2: 未生成報告檔案。測試通過！")
    return True


def test_3_report_only_mode():
    print_header("測試 3: 純報告生成測試 (`--report-only`)")
    # 此測試依賴 test_2 生成的數據，所以不在此處清理 DB。
    # 但需要清理舊報告，以驗證新報告是否生成。

    # 先記錄當前報告目錄中的檔案，以便後續比較
    # 注意：REPORTS_DIR 的清理應該在 test_1 或 test_2 開始時進行，以確保一個乾淨的起點。
    # test_2 執行前已清理 REPORTS_DIR。
    initial_reports = get_report_files(REPORTS_DIR)

    cmd = [
        PYTHON_EXE, SCRIPT_PATH,
        "--tickers", TICKER_DATA_ONLY, # 使用與 test_2 相同的 Ticker
        "--report-start-date", START_DATE_DATA_ONLY_REPORT_ONLY, # 使用 test_2 的日期範圍
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

    unexpected_in_log = [
        "run_data_pipeline", # 不應執行數據流程
        "hydrate_data_range", # 不應調用數據回填
        "YFinanceClient", # YFinanceClient 可能會初始化，但其 hydrate_data_range 不應被調用
                           # run.py 中，如果 report_only, yf_client 不會被實例化。所以不該有 YFinanceClient 相關日誌
        "YFinanceClient 初始化完畢" # 確認 yf_client 是否真的未初始化
    ]
    # 根據 run.py 的邏輯，在 --report-only 模式下，yf_client 不會被初始化。
    # 所以 "YFinanceClient 初始化完畢" 也不應該出現。
    unexpected_in_log_actual = [
        "--- 開始數據處理流程 ---", # from run_data_pipeline
        "hydrate_data_range", # from yf_client
        "YFinanceClient (Data Hydrator v33.0) 初始化完畢" # from yf_client constructor
    ]
    assert check_log_not_contains(stdout, unexpected_in_log_actual, case_sensitive=False), "測試 3 失敗: 日誌中包含數據獲取相關的多餘訊息。"
    log_message("測試 3: 日誌未包含數據獲取相關訊息。")

    # 驗證報告是否生成
    final_reports = get_report_files(REPORTS_DIR)
    new_reports = [r for r in final_reports if r not in initial_reports] # 比較的是 test_2 運行後的狀態

    generated_report_for_current_test = False
    expected_report_name_part = "on_demand_report_" # run.py 中 --report-only 生成的檔案名

    for r_name in new_reports: # new_reports 可能為空，如果 test_2 執行後沒有清理 reports 目錄且 test_2 未產生報告
        if expected_report_name_part in r_name:
             generated_report_for_current_test = True
             break

    # 更可靠的檢查：直接檢查是否有 on_demand_report_*.md 檔案生成
    found_on_demand_report = any(expected_report_name_part in r for r in final_reports)

    assert found_on_demand_report, f"測試 3 失敗: 未能找到預期的 '{expected_report_name_part}*.md' 報告檔案。"
    log_message("測試 3: 成功生成報告檔案。測試通過！")
    return True


def test_4_full_flow():
    print_header("測試 4: 完整流程測試")
    cleanup_files(BASE_DB_PATH, REPORTS_DIR) # 清理舊數據和報告
    initial_reports = get_report_files(REPORTS_DIR)

    cmd = [
        PYTHON_EXE, SCRIPT_PATH,
        "--tickers", TICKER_FULL_FLOW,
        "--start-date", START_DATE_FULL_FLOW,
        "--end-date", END_DATE_FULL_FLOW,
        "--db-path", BASE_DB_PATH,
        "--table-name", TABLE_NAME
        # 無 --data-only 或 --report-only
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

    # 驗證數據庫
    db_data = query_duckdb(BASE_DB_PATH, f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE ticker = '{TICKER_FULL_FLOW}' AND datetime >= '{START_DATE_FULL_FLOW}' AND datetime <= '{END_DATE_FULL_FLOW} 23:59:59'")
    assert db_data['count_star()'].iloc[0] > 0, f"測試 4 失敗: 資料庫中應存在 {TICKER_FULL_FLOW} 的數據，但未找到。"
    log_message(f"測試 4: 資料庫中已寫入 {TICKER_FULL_FLOW} 的數據 ({db_data['count_star()'].iloc[0]} 筆)。")

    # 驗證報告是否生成
    final_reports = get_report_files(REPORTS_DIR)
    new_reports = [r for r in final_reports if r not in initial_reports]

    generated_report_for_current_test = False
    expected_report_name_part = "market_analysis_report_" # run.py 中完整流程生成的檔案名

    for r_name in new_reports: # new_reports 應該只包含當前測試生成的報告
        if expected_report_name_part in r_name:
             generated_report_for_current_test = True
             break
    # 或者更直接的檢查
    found_full_flow_report = any(expected_report_name_part in r for r in final_reports)

    assert found_full_flow_report, f"測試 4 失敗: 未能找到預期的 '{expected_report_name_part}*.md' 報告檔案。"
    log_message("測試 4: 成功生成報告檔案。測試通過！")
    return True

def test_5_preflight_fallback():
    print_header("測試 5: 預檢回退邏輯測試 (`--data-only`)")
    cleanup_files(BASE_DB_PATH, REPORTS_DIR) # 清理舊數據

    cmd = [
        PYTHON_EXE, SCRIPT_PATH,
        "--tickers", TICKER_PREFLIGHT_FALLBACK,
        "--start-date", START_DATE_PREFLIGHT_FALLBACK,
        "--end-date", END_DATE_PREFLIGHT_FALLBACK,
        "--db-path", BASE_DB_PATH,
        "--table-name", TABLE_NAME,
        "--data-only",
        "--force-refresh" # 強制刷新以確保每次都觸發 API 調用
    ]
    returncode, stdout, stderr = run_command(cmd)

    assert returncode == 0, f"測試 5 失敗: 命令執行失敗 (返回碼 {returncode})"
    log_message("測試 5: 命令執行成功。")

    # 驗證日誌中 '1mo' 預檢失敗，然後 '1d' 預檢成功 (或失敗，取決於 TICKER_PREFLIGHT_FALLBACK 的實際情況)
    # 並接著嘗試使用 HISTORICAL_FALLBACK (其中包含 '1d') 獲取數據
    expected_in_log = [
        f"Performing existence pre-flight check for historical range [{START_DATE_PREFLIGHT_FALLBACK} to {END_DATE_PREFLIGHT_FALLBACK}]",
        f"INFO: Pre-flight check for {TICKER_PREFLIGHT_FALLBACK} from {START_DATE_PREFLIGHT_FALLBACK} to {END_DATE_PREFLIGHT_FALLBACK} (1mo) failed. Attempting secondary pre-flight with '1d'.",
    ]
    assert check_log_contains(stdout, expected_in_log, case_sensitive=False), "測試 5 失敗: 日誌未包含 '1mo' 預檢失敗和嘗試 '1d' 預檢的訊息。"
    log_message("測試 5: 日誌包含 '1mo' 預檢失敗和嘗試 '1d' 預檢的訊息。")

    # 接下來，我們需要判斷 '1d' 預檢是否成功
    # 情況 A: '1d' 預檢成功
    secondary_preflight_success_log = f"INFO: Secondary pre-flight check for {TICKER_PREFLIGHT_FALLBACK} from {START_DATE_PREFLIGHT_FALLBACK} to {END_DATE_PREFLIGHT_FALLBACK} (1d) successful."
    # 情況 B: '1d' 預檢也失敗
    secondary_preflight_fail_log = f"INFO: Secondary pre-flight check for {TICKER_PREFLIGHT_FALLBACK} from {START_DATE_PREFLIGHT_FALLBACK} to {END_DATE_PREFLIGHT_FALLBACK} (1d) also failed."

    if secondary_preflight_success_log.lower() in stdout.lower():
        log_message("測試 5: '1d' 二次預檢成功。")
        # 驗證是否繼續使用 HISTORICAL_FALLBACK (包含 '1d') 進行數據獲取
        expected_after_1d_success = [
            f"Using HISTORICAL_FALLBACK: {['1d', '1wk', '1mo']}", # yfinance_client.py 中的日誌
            f"INFO: hydrate_data_range: Ticker={TICKER_PREFLIGHT_FALLBACK}. 正在評估顆粒度 '1d'", # 應首先嘗試 '1d'
            f"fetch_single_chunk: Ticker={TICKER_PREFLIGHT_FALLBACK}, Interval=1d",
            f"資訊：標的 {TICKER_PREFLIGHT_FALLBACK} 數據成功寫入資料庫" # run.py 中的日誌
        ]
        assert check_log_contains(stdout, expected_after_1d_success, case_sensitive=False), "測試 5 失敗: '1d' 預檢成功後，未按預期流程獲取 '1d' 數據。"
        log_message("測試 5: '1d' 預檢成功後，按預期流程獲取 '1d' 數據。")

        db_data = query_duckdb(BASE_DB_PATH, f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE ticker = '{TICKER_PREFLIGHT_FALLBACK}' AND datetime >= '{START_DATE_PREFLIGHT_FALLBACK}' AND datetime <= '{END_DATE_PREFLIGHT_FALLBACK} 23:59:59'")
        assert db_data['count_star()'].iloc[0] > 0, f"測試 5 失敗: '1d' 預檢成功後，資料庫中應存在 {TICKER_PREFLIGHT_FALLBACK} 的數據，但未找到。"
        log_message(f"測試 5: '1d' 預檢成功後，資料庫中已寫入 {TICKER_PREFLIGHT_FALLBACK} 的數據 ({db_data['count_star()'].iloc[0]} 筆)。")

    elif secondary_preflight_fail_log.lower() in stdout.lower():
        log_message("測試 5: '1d' 二次預檢失敗。")
        # 驗證是否正確終止流程
        expected_after_1d_fail = [
            f"===== 數據回填任務結束 (預檢 '1mo' 及 '1d' 均失敗): Ticker={TICKER_PREFLIGHT_FALLBACK} =====",
            f"總結：標的 {TICKER_PREFLIGHT_FALLBACK} 在請求的歷史範圍內未找到任何數據。" # run.py 中的日誌
        ]
        assert check_log_contains(stdout, expected_after_1d_fail, case_sensitive=False), "測試 5 失敗: '1d' 預檢失敗後，未按預期終止流程並記錄日誌。"
        log_message("測試 5: '1d' 預檢失敗後，按預期終止流程。")

        db_data = query_duckdb(BASE_DB_PATH, f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE ticker = '{TICKER_PREFLIGHT_FALLBACK}' AND datetime >= '{START_DATE_PREFLIGHT_FALLBACK}' AND datetime <= '{END_DATE_PREFLIGHT_FALLBACK} 23:59:59'")
        assert db_data['count_star()'].iloc[0] == 0, f"測試 5 失敗: '1d' 預檢失敗後，資料庫中不應存在 {TICKER_PREFLIGHT_FALLBACK} 的數據，但找到了 {db_data['count_star()'].iloc[0]} 筆。"
        log_message(f"測試 5: '1d' 預檢失敗後，資料庫中沒有 {TICKER_PREFLIGHT_FALLBACK} 的數據。")
    else:
        assert False, "測試 5 失敗: 日誌中既未找到 '1d' 預檢成功也未找到失敗的明確標記。"

    log_message("測試 5: 預檢回退邏輯測試通過！")
    return True


def test_6_no_data_skip_logic():
    print_header("測試 6: 無數據區塊記錄與跳過邏輯測試")
    cleanup_files(BASE_DB_PATH, REPORTS_DIR)

    ticker_no_data = "NOEXISTS.TICKER" # 一個預期 yfinance 無法找到數據的代號
    start_date_no_data = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    end_date_no_data = (datetime.now() - timedelta(days=9)).strftime("%Y-%m-%d")
    cooldown_param = "1" # 1 天的冷卻期

    # --- 首次執行 ---
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

    # 驗證 fetch_single_chunk 被呼叫 (yfinance_client 日誌)
    # 驗證 record_no_data_range 被呼叫 (db_manager 日誌)
    expected_in_log1 = [
        f"fetch_single_chunk: Ticker={ticker_no_data}", # 至少會嘗試一次
        f"INFO: fetch_single_chunk: [情報] {ticker_no_data}", # yfinance_client.py 中的無數據日誌
        f"此區塊已被記錄為無數據", # yfinance_client.py 中記錄後的日誌片段
        f"INFO: 已記錄/更新無數據區塊: Ticker={ticker_no_data}", # db_manager.py 中的日誌
    ]
    assert check_log_contains(stdout1, expected_in_log1), "測試 6.1 失敗: 首次執行的日誌未包含預期訊息。"
    log_message("測試 6.1: 首次執行日誌驗證通過。")

    # 驗證資料庫中 no_data_records 表
    # 由於 yfinance_client 會嘗試多個 interval，我們需要找到對應的記錄
    # 假設它至少會為某個 interval (如 '1m' 或 '1d') 記錄
    # 我們可以檢查是否存在任何 ticker_no_data 的記錄
    # 注意：yfinance_client 的 hydrate_data_range 會為請求的整個日期範圍（start_date_no_data 到 end_date_no_data）
    # 在 fetch_single_chunk 失敗時，記錄的是 chunk 的範圍。
    # 如果 hydrate_data_range 的請求範圍就是一個 chunk，那麼 start_date 和 end_date 會匹配。
    # 我們需要找到一個被記錄的 interval。
    # 為了簡化，我們檢查是否存在任何 ticker_no_data 的記錄，並且其 start/end date 與請求範圍一致。
    # 這假設 yf_client 中的 chunking 邏輯對於短日期範圍會產生一個與請求範圍相同的 chunk。
    # 或者，更準確地，我們應該檢查是否有任何 ticker_no_data 的記錄。

    no_data_entry_query = f"SELECT COUNT(*) FROM no_data_records WHERE ticker = '{ticker_no_data}' AND start_date = '{start_date_no_data}' AND end_date = '{end_date_no_data}'"
    # 可能因為 interval 不同而導致 start_date/end_date 略有不同，或者 yf_client 的 chunking 策略
    # 更穩健的查詢是只查 ticker
    no_data_entry_query_any_for_ticker = f"SELECT COUNT(*) FROM no_data_records WHERE ticker = '{ticker_no_data}'"
    db_record_check = query_duckdb(BASE_DB_PATH, no_data_entry_query_any_for_ticker)
    assert db_record_check['count_star()'].iloc[0] > 0, f"測試 6.1 失敗: 資料庫 no_data_records 中未找到 {ticker_no_data} 的記錄。"
    log_message(f"測試 6.1: 資料庫 no_data_records 中已為 {ticker_no_data} 寫入記錄。")

    # --- 第二次執行 (冷卻期內) ---
    print_subheader("測試 6.2: 第二次執行 - 跳過 API 呼叫")
    # 為確保仍在冷卻期，可以稍微等待一下，但對於1天的冷卻期，立即執行通常是安全的
    time.sleep(1) # 短暫等待，確保時間戳不會完全相同（雖然影響不大）
    cmd2 = cmd1 # 使用相同的命令
    returncode2, stdout2, stderr2 = run_command(cmd2)
    assert returncode2 == 0, f"測試 6.2 失敗: 命令執行失敗 (返回碼 {returncode2})"

    # 驗證 check_no_data_record_exists 被呼叫且返回 True (db_manager 日誌)
    # 驗證跳過訊息 (yfinance_client 日誌)
    # 驗證 fetch_single_chunk 沒有被呼叫
    expected_in_log2 = [
        f"DEBUG: 發現有效的無數據記錄: Ticker={ticker_no_data}", # db_manager.py
        f"[數據偵查] Ticker={ticker_no_data}", # yfinance_client.py
        f"已跳過", # yfinance_client.py
        f"因在最近 {cooldown_param} 天內曾記錄為無數據區塊" # yfinance_client.py
    ]
    assert check_log_contains(stdout2, expected_in_log2), "測試 6.2 失敗: 第二次執行的日誌未包含預期跳過訊息。"

    unexpected_in_log2 = [
        f"fetch_single_chunk: Ticker={ticker_no_data}", # 不應該再呼叫 fetch
        f"INFO: 已記錄/更新無數據區塊: Ticker={ticker_no_data}" # 不應該再次記錄
    ]
    assert check_log_not_contains(stdout2, unexpected_in_log2), "測試 6.2 失敗: 第二次執行的日誌中包含不應出現的 fetch 或記錄訊息。"
    log_message("測試 6.2: 第二次執行日誌驗證通過，API 呼叫已跳過。")

    # --- 第三次執行 (模擬冷卻期過後) ---
    print_subheader("測試 6.3: 第三次執行 - 冷卻期過後，重新嘗試")
    # 手動修改資料庫中記錄的 recorded_at，使其早於冷卻期
    # cooldown_param 是 1 天，所以我們將 recorded_at 設置為 2 天前
    two_days_ago_iso = (datetime.now(timezone.utc) - timedelta(days=int(cooldown_param) + 1)).isoformat()
    try:
        with duckdb.connect(BASE_DB_PATH) as con:
            # 更新所有 ticker_no_data 的記錄，以防有多個 interval 被記錄
            update_query = f"UPDATE no_data_records SET recorded_at = '{two_days_ago_iso}' WHERE ticker = '{ticker_no_data}'"
            con.execute(update_query)
            log_message(f"測試 6.3: 已手動將 {ticker_no_data} 在 no_data_records 中的 recorded_at 更新為 {two_days_ago_iso}")
    except Exception as e:
        log_message(f"測試 6.3 錯誤: 更新 no_data_records 失敗: {e}")
        assert False, f"測試 6.3 準備失敗: 無法更新資料庫記錄: {e}"

    cmd3 = cmd1 # 使用相同的命令
    returncode3, stdout3, stderr3 = run_command(cmd3)
    assert returncode3 == 0, f"測試 6.3 失敗: 命令執行失敗 (返回碼 {returncode3})"

    # 驗證 check_no_data_record_exists 被呼叫但返回 False (沒有 "發現有效的無數據記錄" 的 DEBUG 日誌)
    # 驗證 fetch_single_chunk 再次被呼叫
    # 驗證無數據區塊再次被記錄 (因為 API 仍然返回無數據)

    # 期望 check_no_data_record_exists 執行，但不會找到有效的記錄 (即不會打印 "發現有效的無數據記錄")
    # 因此，我們檢查 "發現有效的無數據記錄" 是否 *不* 存在於 stdout3 中 (針對此 ticker 和相關 interval)
    # 但 check_no_data_record_exists 本身還是會被呼叫的，所以它查詢資料庫的日誌可能在
    # 更簡單的是檢查跳過訊息是否 *不* 存在

    unexpected_in_log3_after_cooldown = [
        f"DEBUG: 發現有效的無數據記錄: Ticker={ticker_no_data}", # 不應該再是有效記錄
        f"[數據偵查] Ticker={ticker_no_data}.*已跳過" # 不應該再跳過
    ]
    # 使用正則表達式來匹配跳過訊息會更準確，但 check_log_not_contains 不支持
    # 我們可以分開檢查
    assert check_log_not_contains(stdout3, [unexpected_in_log3_after_cooldown[0]]), "測試 6.3 失敗: 冷卻期過後，仍將記錄視為有效。"
    assert check_log_not_contains(stdout3, [f"[數據偵查] Ticker={ticker_no_data}","已跳過"], case_sensitive=False), "測試 6.3 失敗: 冷卻期過後，仍在日誌中發現跳過訊息。"


    expected_in_log3_after_cooldown = [
        f"fetch_single_chunk: Ticker={ticker_no_data}", # 應該再次嘗試 fetch
        f"INFO: 已記錄/更新無數據區塊: Ticker={ticker_no_data}", # 應該再次記錄，因為 API 還是無數據
    ]
    assert check_log_contains(stdout3, expected_in_log3_after_cooldown), "測試 6.3 失敗: 冷卻期過後的日誌未包含預期的 fetch 和記錄訊息。"
    log_message("測試 6.3: 第三次執行日誌驗證通過，冷卻期過後重新嘗試 API 並記錄。")

    log_message("測試 6: 無數據區塊記錄與跳過邏輯測試通過！")
    return True


# --- 主執行邏輯 ---
if __name__ == "__main__":
    log_dir = os.path.dirname(LOG_FILE_PATH)
    # 使用 print 進行初始調試，因為 log_message 依賴於此目錄的成功創建
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

    # 初始化日誌檔案 (確保目錄已成功創建或已存在)
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
    total_tests = 0 # 將在後面增加

    # 執行測試
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

        # 短暫停頓，確保日誌寫入和檔案操作完成
        time.sleep(0.5)


    print_header("測試總結")
    log_message(f"總共規劃測試: {total_tests}", to_console=True)
    log_message(f"通過測試數: {tests_passed}", to_console=True)

    if tests_passed == total_tests and total_tests > 0 : # 確保至少跑了一個測試
        log_message("所有 v33.0 整合測試案例均已通過！", to_console=True)
        sys.exit(0)
    else:
        log_message(f"v33.0 整合測試未完全通過 ({tests_passed}/{total_tests})。請檢查日誌 '{LOG_FILE_PATH}'。", to_console=True)
        sys.exit(1)

print("INFO: _test_v33_harness.py 腳本定義完畢。")
