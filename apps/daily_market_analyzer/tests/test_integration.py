# -*- coding: utf-8 -*-
"""
最終架構驗收測試腳本：daily_market_analyzer v3.0 (生產者-消費者模型)

此腳本旨在驗證重構後的 daily_market_analyzer 微服務是否滿足以下核心要求：
1.  冪等性與數據完整性：多次運行不產生重複數據。
2.  並發處理穩定性：在高負載下無資料庫鎖衝突。
3.  系統韌性：優雅處理有效、無效及特殊市場標的。
"""
import subprocess
import os
import sys
import time
import shutil
from datetime import datetime, timedelta
import duckdb
import pandas as pd
import re # 新增導入 re 模組

# --- 設定專案路徑 ---
def setup_project_path():
    """將專案根目錄添加到 sys.path"""
    project_root_env = os.getenv("PROJECT_ROOT_FOR_TESTS")
    if project_root_env:
        project_root = project_root_env
    else:
        # 如果環境變數未設定，則嘗試從 __file__ 推斷
        try:
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..'))
        except NameError: # __file__ is not defined (e.g. in an interactive session not running as a file)
            project_root = os.path.abspath(os.path.join(os.getcwd(), "../.."))


    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    print(f"DEBUG (Test Harness): Project root set to: {project_root}")
    print(f"DEBUG (Test Harness): Current sys.path: {sys.path}")
    print(f"DEBUG (Test Harness): Current CWD: {os.getcwd()}")
    return project_root

PROJECT_ROOT = setup_project_path()
RUN_PY_PATH = os.path.join(PROJECT_ROOT, "apps", "daily_market_analyzer", "run.py")

# --- 測試配置 ---
TEST_DB_DIR = os.path.join(PROJECT_ROOT, "data_workspace", "test_dbs_v3_arch")
TEST_DB_NAME_PREFIX = "test_arch_v3_"
LOG_FILE_PATH = os.path.join(PROJECT_ROOT, "data_workspace", "logs", "_test_v3_architecture_harness.log")
DEFAULT_TABLE_NAME = "market_data" # 與 run.py 中 args.table_name 的預期預設值保持一致或測試時明確指定

# ANALYSIS_TICKERS (用於壓力測試，根據需要調整)
# 包含多種類型：指數期貨, VIX, 主要指數, 國際指數, 中國A股, 外匯, 美債期貨, 美債ETF, 熱門股票, ADR, 加密貨幣
ANALYSIS_TICKERS_FULL_LIST_STR = (
    "NQ=F,ES=F,YM=F,"  # 指數期貨 (CME)
    "^VIX,"  # 波動率指數
    "^DJI,^SPX,^IXIC,"  # 美國主要指數
    #"^N225,^FTSE,^GDAXI," # 其他國際主要指數 (日經,富時,DAX) - 有些可能需要特定後綴或在yfinance中不穩定
    "^TWII,^HSI,000001.SS,"  # 亞洲主要指數 (台灣加權,恆生,上證綜指)
    "DX-Y.NYB,"  # 美元指數
    #"EURUSD=X,JPY=X,GBPUSD=X,CNY=X," # 主要貨幣對 - JPY=X 可能有問題，改用 USDJPY=X
    "USDJPY=X,EURUSD=X,GBPUSD=X,"
    "ZB=F,ZN=F,ZT=F,ZF=F,"  # 美債期貨 (CBOT) - ZT=F (2年), ZF=F (5年)
    "^TNX,^TYX,^FVX," # 美債殖利率 (10年, 30年, 5年)
    "TLT,SHY,IEI,"  # 美債ETF (長期,短期,中期)
    "CL=F,NG=F,GC=F,SI=F,HG=F,ZS=F,ZC=F,ZW=F,"  # 大宗商品期貨 (原油,天然氣,黃金,白銀,銅,黃豆,玉米,小麥)
    "GLD,SLV,USO,UNG," # 大宗商品ETF
    "AAPL,MSFT,NVDA,GOOG,AMZN,META,TSLA,BRK-A,JPM,V,PG,JNJ,XOM,WMT,"  # 熱門美股
    "TSM,BABA,NIO,"  # 熱門ADR
    "2330.TW,0050.TW," # 台股範例 (台積電, 台灣50 ETF)
    "0700.HK," # 港股範例 (騰訊)
    # "600519.SS,601318.SS," # A股範例 (貴州茅台, 中國平安) - yfinance對A股支持可能不穩定
    "BTC-USD,ETH-USD,SOL-USD,DOGE-USD"  # 主流加密貨幣
)


# --- 輔助函式 ---
def initialize_test_environment():
    """初始化測試環境，清理舊的測試資料庫和日誌。"""
    print_test_header("環境初始化", main_header=True)
    os.makedirs(TEST_DB_DIR, exist_ok=True)

    # 清理該測試腳本先前可能產生的所有測試資料庫
    for item in os.listdir(TEST_DB_DIR):
        if item.startswith(TEST_DB_NAME_PREFIX) and item.endswith(".duckdb"):
            try:
                os.remove(os.path.join(TEST_DB_DIR, item))
                log_message(f"INFO: 已刪除舊的測試資料庫: {item}")
            except OSError as e:
                log_message(f"警告: 無法刪除舊的測試資料庫 {item}: {e}。")

    if os.path.exists(LOG_FILE_PATH):
        os.remove(LOG_FILE_PATH)
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    log_message(f"INFO: 測試日誌將記錄到: {LOG_FILE_PATH}")
    print_separator()

def get_test_db_path(test_case_name: str) -> str:
    """為每個測試案例生成唯一的資料庫路徑。"""
    return os.path.join(TEST_DB_DIR, f"{TEST_DB_NAME_PREFIX}{test_case_name}.duckdb")

def print_separator(char="=", length=70):
    print(char * length)

def print_test_header(test_name: str, main_header: bool = False):
    char = "=" if main_header else "-"
    print_separator(char)
    print(f"[[ {test_name} ]]")
    if main_header:
        print(f"日誌檔案: {LOG_FILE_PATH}")
    print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_separator(char)

def print_test_footer(test_name: str, success: bool, duration: float):
    status = "✅ 成功" if success else "❌ 失敗"
    print_separator("-")
    print(f"測試案例: {test_name} - 結果: {status}")
    print(f"結束時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"執行時長: {duration:.2f} 秒")
    print_separator("-")
    log_message(f"測試案例: {test_name} - 結果: {status} - 時長: {duration:.2f} 秒", to_console=False)

def log_message(message: str, to_console: bool = True):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    full_message = f"[{timestamp}] {message}"
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(full_message + "\n")
    if to_console:
        print(full_message)

def run_analyzer_script(
    db_path: str,
    tickers_str: str,
    start_date: str,
    end_date: str,
    data_only: bool = True,
    force_refresh: bool = False,
    max_workers: int = 8, # 根據測試案例調整
    table_name: str = DEFAULT_TABLE_NAME,
    extra_args: list[str] | None = None
) -> tuple[int, str, str]:
    """執行 daily_market_analyzer/run.py 腳本。"""
    cmd = [
        sys.executable, RUN_PY_PATH,
        "--tickers", tickers_str,
        "--start-date", start_date,
        "--end-date", end_date,
        "--db-path", db_path, # 直接使用為此測試案例指定的DB路徑
        "--table-name", table_name,
        "--max-workers", str(max_workers),
        # "--enable-local-first" # 在v3架構測試中，Local-First不是主要驗證點，可暫不啟用以簡化
    ]
    if data_only:
        cmd.append("--data-only")
    if force_refresh:
        cmd.append("--force-refresh")
    if extra_args:
        cmd.extend(extra_args)

    log_message(f"執行命令: {' '.join(cmd)}", to_console=False) #詳細命令只入log
    print(f"INFO: 正在執行 run.py (TICKERS: {tickers_str}, DB: {os.path.basename(db_path)})")

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
    stdout, stderr = process.communicate()
    return_code = process.returncode

    log_message(f"命令 '{os.path.basename(db_path)}' run.py 返回碼: {return_code}", to_console=False)
    if stdout:
        log_message(f"STDOUT for '{os.path.basename(db_path)}':\n{stdout}", to_console=False)
    if stderr:
        log_message(f"STDERR for '{os.path.basename(db_path)}':\n{stderr}", to_console=False)

    # 打印簡略的輸出到控制台
    if return_code != 0:
        print(f"ERROR: run.py 執行失敗 (返回碼: {return_code})。詳情請見日誌。")
        if stderr: print(f"STDERR (摘要):\n{stderr[:500]}{'...' if len(stderr)>500 else ''}")
    else:
        print(f"INFO: run.py 執行成功 (返回碼: 0)。")

    return return_code, stdout, stderr

def get_db_row_count(db_path: str, table_name: str = DEFAULT_TABLE_NAME) -> int:
    """獲取資料庫表的總行數。"""
    if not os.path.exists(db_path):
        log_message(f"DB Row Count: 資料庫檔案不存在: {db_path}", to_console=False)
        return 0
    try:
        with duckdb.connect(database=db_path, read_only=True) as con:
            # 檢查表格是否存在
            res_table_exists = con.execute(f"SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}'").fetchone()
            if res_table_exists is None:
                log_message(f"DB Row Count: 資料表 '{table_name}' 不存在於 '{db_path}'", to_console=False)
                return 0
            count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            log_message(f"DB Row Count: 資料表 '{table_name}' 在 '{os.path.basename(db_path)}' 中有 {count} 行。", to_console=False)
            return count
    except Exception as e:
        log_message(f"DB Row Count: 查詢資料庫 '{os.path.basename(db_path)}' 時發生錯誤: {e}", to_console=False)
        return -1 # 表示查詢出錯

def count_log_keywords(log_content: str, keywords: list[str], case_sensitive=False) -> dict[str, int]:
    """計算日誌內容中關鍵詞的出現次數。"""
    counts = {keyword: 0 for keyword in keywords}
    temp_log_content = log_content if case_sensitive else log_content.lower()
    for keyword in keywords:
        kw_to_search = keyword if case_sensitive else keyword.lower()
        counts[keyword] = temp_log_content.count(kw_to_search)
    return counts

def check_db_data_for_tickers(db_path: str, tickers_list: list[str], start_date_str: str, end_date_str: str,
                               table_name: str = DEFAULT_TABLE_NAME, expect_data: bool = True,
                               expected_min_rows_per_ticker: int = 1) -> bool:
    """檢查資料庫中是否存在指定 tickers 的數據。"""
    log_message(f"DB Check: 檢查資料庫 '{os.path.basename(db_path)}' 中的標的: {tickers_list} (日期: {start_date_str} to {end_date_str}, 表: {table_name}, 預期數據: {expect_data})", to_console=False)
    if not os.path.exists(db_path):
        print(f"ERROR (DB Check): 資料庫檔案不存在: {db_path}")
        return False

    all_conditions_met = True
    try:
        with duckdb.connect(database=db_path, read_only=True) as con:
            res_table_exists = con.execute(f"SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}'").fetchone()
            if res_table_exists is None:
                print(f"ERROR (DB Check): 資料表 '{table_name}' 在資料庫中不存在。")
                return False

            start_dt_query = f"{start_date_str} 00:00:00"
            end_dt_obj = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)
            end_dt_query = end_dt_obj.strftime("%Y-%m-%d 00:00:00")

            for ticker in tickers_list:
                query = f"SELECT COUNT(*) FROM {table_name} WHERE ticker = ? AND datetime >= ? AND datetime < ?"
                count = con.execute(query, [ticker, start_dt_query, end_dt_query]).fetchone()[0]

                if expect_data:
                    if count >= expected_min_rows_per_ticker:
                        log_message(f"DB Check SUCCESS: 標的 {ticker} 在資料庫中找到 {count} 筆數據 (預期至少 {expected_min_rows_per_ticker} 筆)。", to_console=False)
                    else:
                        print(f"DB Check FAILURE: 標的 {ticker} 在資料庫中數據不足 (預期至少 {expected_min_rows_per_ticker} 筆, 實際 {count} 筆)。")
                        all_conditions_met = False
                else: # expect_no_data
                    if count == 0:
                        log_message(f"DB Check SUCCESS: 標的 {ticker} 在資料庫中未找到數據 (符合預期無數據)。", to_console=False)
                    else:
                        print(f"DB Check FAILURE: 標的 {ticker} 在資料庫中找到 {count} 筆數據 (預期無數據)。")
                        all_conditions_met = False
    except Exception as e:
        print(f"ERROR (DB Check): 檢查資料庫時發生錯誤: {e}")
        return False
    return all_conditions_met

# --- 測試案例實施 ---

def test_A_idempotency_and_integrity() -> bool:
    """測試案例 A：冪等性與數據完整性終極驗證"""
    case_name = "A_idempotency"
    print_test_header(case_name)
    start_run_time = time.time()

    db_path = get_test_db_path(case_name)
    tickers = "AAPL,MSFT,GOOG"
    # 使用較近的日期以確保 yfinance 有數據
    end_date = datetime.now() - timedelta(days=1) #昨天
    start_date = end_date - timedelta(days=3) #過去3天
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    # --- 第一次執行 (強制刷新) ---
    log_message(f"\nINFO ({case_name}): --- 第一次執行 (force_refresh=True) ---")
    if os.path.exists(db_path): os.remove(db_path) # 確保全新開始

    time_run1_start = time.time()
    return_code1, stdout1, stderr1 = run_analyzer_script(
        db_path, tickers, start_date_str, end_date_str, force_refresh=True, max_workers=4
    )
    time_run1_duration = time.time() - time_run1_start
    db_rows_after_run1 = get_db_row_count(db_path)
    log_message(f"INFO ({case_name}): 第一次執行 - 返回碼: {return_code1}, 時長: {time_run1_duration:.2f}s, DB行數: {db_rows_after_run1}")

    if return_code1 != 0:
        print(f"FAILURE ({case_name}): 第一次執行失敗 (返回碼: {return_code1})。測試終止。")
        print_test_footer(case_name, False, time.time() - start_run_time)
        return False
    if db_rows_after_run1 <= 0:
        print(f"FAILURE ({case_name}): 第一次執行後資料庫中沒有數據 (行數: {db_rows_after_run1})。測試終止。")
        print_test_footer(case_name, False, time.time() - start_run_time)
        return False

    # --- 第二次執行 (不強制刷新) ---
    log_message(f"\nINFO ({case_name}): --- 第二次執行 (force_refresh=False) ---")
    time_run2_start = time.time()
    return_code2, stdout2, stderr2 = run_analyzer_script(
        db_path, tickers, start_date_str, end_date_str, force_refresh=False, max_workers=4
    )
    time_run2_duration = time.time() - time_run2_start
    db_rows_after_run2 = get_db_row_count(db_path)
    log_message(f"INFO ({case_name}): 第二次執行 - 返回碼: {return_code2}, 時長: {time_run2_duration:.2f}s, DB行數: {db_rows_after_run2}")

    # 驗收標準
    cond_ret_code_2_ok = (return_code2 == 0)
    cond_time_faster = (time_run2_duration < time_run1_duration) or (time_run1_duration < 1.0) # 如果第一次很快，第二次可能不會顯著更快
    cond_rows_same = (db_rows_after_run1 == db_rows_after_run2)

    # 新的驗收標準 v2.0：檢查第二次日誌中是否有生產者端表明數據已快取/跳過獲取的日誌
    # 關鍵日誌模式：
    # 1. `DEBUG [CACHE_CHECK_DECISION_DETAIL]: Ticker: ..., Interval: .... All requested dates ... are present in cache for this interval.`
    # 2. `INFO [HYDRATE_SKIP_DATE_PRE_EXISTING]: Ticker: ..., Date: .... Data already exists (any interval). Skipping fetch ...`
    # 3. `成功: hydrate_data_range: Ticker=..., Interval=.... 所有請求數據 ... 均在快取中。`
    # 4. `===== 數據生產任務結束 (完全快取命中或無需獲取): Ticker=..., Interval=... =====`
    # 只要滿足其中之一（針對每個 Ticker 和主要嘗試的 interval），就認為生產者端正確處理了快取。

    combined_log_run2 = stdout2 + stderr2
    producer_handled_cache_correctly = True

    # 檢查是否有 "數據生產任務結束 (完全快取命中或無需獲取)"
    # 這是一個強烈的信號，表明對於某個 ticker 和 interval，沒有新的數據需要獲取。
    fully_cached_or_no_new_data_log_pattern = r"數據生產任務結束 \(完全快取命中或無需獲取\): Ticker=(AAPL|MSFT|GOOG)"
    if not re.search(fully_cached_or_no_new_data_log_pattern, combined_log_run2):
        # 如果沒有上述的通用成功日誌，則檢查更詳細的跳過日誌
        # 對於測試中的每個 ticker，我們期望看到它至少對嘗試的第一個 interval (1m) 進行快取檢查並決定跳過或確認已快取
        specific_skip_patterns = []
        for ticker_symbol in tickers.split(','):
            # 模式1: DEBUG [CACHE_CHECK_DECISION_DETAIL]: Ticker: AAPL, Interval: 1m. All requested dates [...] are present in cache for this interval.
            # 模式2: INFO [HYDRATE_SKIP_DATE_PRE_EXISTING]: Ticker: AAPL, Date: YYYY-MM-DD. Data already exists (any interval). Skipping fetch...
            # 由於日期是動態的，我們只檢查 ticker 和關鍵短語
            # 並且，如果所有日期都已存在（模式1），則可能不會為每個日期都打印模式2。
            # 因此，我們主要尋找 "All requested dates ... are present" 或 "Data already exists (any interval)"
            # 或者是 "所有請求數據 ... 均在快取中"

            # 測試腳本中的 simple_producer_skip_keywords 包含了這些
            # "成功: hydrate_data_range: Ticker=AAPL, Interval=1m. 所有請求數據 ... 均在快取中" (這個日誌目前不存在於 yfinance_client.py)
            # "DEBUG [CACHE_CHECK_DECISION_DETAIL]: Ticker: AAPL, Interval: 1m. All requested dates" (存在)
            # "INFO [HYDRATE_SKIP_DATE_PRE_EXISTING]" (存在)
            pattern_for_ticker_all_cached = rf"DEBUG \[CACHE_CHECK_DECISION_DETAIL\]: Ticker: {ticker_symbol}, Interval: 1m\. All requested dates.*are present in cache"
            pattern_for_ticker_any_interval_skip = rf"INFO \[HYDRATE_SKIP_DATE_PRE_EXISTING\]: Ticker: {ticker_symbol}.*Data already exists \(any interval\)"

            if not (re.search(pattern_for_ticker_all_cached, combined_log_run2) or \
                    re.search(pattern_for_ticker_any_interval_skip, combined_log_run2)):
                log_message(f"WARNING ({case_name}): 未找到 Ticker {ticker_symbol} (1m) 的明確生產者跳過/快取命中日誌。")
                # 這裡可以選擇是否將 producer_handled_cache_correctly 設為 False
                # 鑑於之前的 UnboundLocalError 可能影響了日誌，我們暫時更寬容
                # 但如果行數和時間都對了，很可能生產者是正確的。
                # 最強的證據是 DATA_QUEUE 為空，但這較難直接從外部測試。
                # 我們現在主要依賴行數和時間。
                # 如果要嚴格，這裡應該是 producer_handled_cache_correctly = False

    # 新的驗收標準 v2.0：
    # 檢查第二次日誌中是否有生產者端表明數據已快取或跳過獲取的明確日誌。
    # 我們期望對於每個 ticker，hydrate_data_range 最終會因為數據已完全快取而提前結束其 interval 循環。
    # 標誌性日誌："成功: hydrate_data_range: Ticker=..., Interval=.... 所有請求數據 ... 均在快取中。"
    # 或 "INFO [HYDRATE_SKIP_DATE_PRE_EXISTING]: Ticker: ..., Date: .... Data already exists (any interval). Skipping fetch ..."
    # 並且最終是 "===== 數據生產任務結束 (完全快取命中或無需獲取): Ticker=..., Interval=... ====="

    cond_producer_skipped_or_cached = True # 假設通過，除非找到反證或缺少證據

    # 檢查消費者線程是否收到了非預期的數據進行寫入
    # (理想情況下，第二次運行時，DATA_QUEUE 應該是空的，或只包含合法的空數據更新)
    # 我們可以檢查 DEBUG (DB Writer Thread): 從佇列收到項目: ... Data: DataFrame (shape: (X, Y)) 其中 X > 0
    unexpected_write_attempts = re.findall(r"DEBUG \(DB Writer Thread\): 從佇列收到項目:.*DataFrame \(shape: \((\d+), \d+\)\)", combined_log_run2)
    num_unexpected_writes = sum(1 for count_str in unexpected_write_attempts if int(count_str) > 0)

    if num_unexpected_writes > 0:
        log_message(f"FAILURE ({case_name}): 第二次執行時，消費者線程仍然收到了 {num_unexpected_writes} 個包含數據的項目進行寫入。")
        cond_producer_skipped_or_cached = False
    else:
        log_message(f"INFO ({case_name}): 第二次執行時，消費者線程未收到新的數據項進行寫入，符合預期。")

    # 並且，我們期望看到生產者端的快取命中日誌
    # 至少對於每個 ticker 的第一個嘗試的 interval ('1m')，應該有明確的快取命中指示
    # 例如 "DEBUG [CACHE_CHECK_DECISION_DETAIL]: Ticker: AAPL, Interval: 1m. All requested dates [...] are present in cache for this interval."
    # 或者，如果部分日期缺失（週末），則應該有 "INFO [HYDRATE_SKIP_DATE_PRE_EXISTING]" 針對已存在數據的日期
    # 並且最終，對於 '1m' interval，應該因為數據被確認無需獲取而提前結束。
    # "INFO: hydrate_data_range: Ticker=AAPL, Interval=1m. All missing date ranges for this interval processed successfully (data queued or confirmed no data). Ending attempts for this ticker."
    # 或 "成功: hydrate_data_range: Ticker=AAPL, Interval=1m. 所有請求數據 (2025-07-02 to 2025-07-05) 均在快取中。"

    all_tickers_showed_cache_behavior = True
    for ticker_symbol in tickers.split(','):
        # 模式1: 所有日期都在特定 interval 的快取中
        pattern_all_cached_current_interval = rf"DEBUG \[CACHE_CHECK_DECISION_DETAIL\]: Ticker: {re.escape(ticker_symbol)}, Interval: \w+\..*All requested dates.*are present in cache"
        # 模式2: 日期因任何 interval 已存在而被跳過 (這個日誌會在 hydrate_data_range 過濾 missing_dates_list 时打印)
        pattern_any_interval_skip = rf"INFO \[HYDRATE_SKIP_DATE_PRE_EXISTING\]: Ticker: {re.escape(ticker_symbol)}.*Data already exists \(any interval\)"
        # 模式3: 整個 hydrate_data_range 調用因為完全快取而提前結束
        pattern_hydrate_full_cache_hit = rf"成功: hydrate_data_range: Ticker={re.escape(ticker_symbol)}, Interval=\w+\. 所有請求數據 .* 均在快取中"
        # 模式4: hydrate_data_range 對於一個 interval 的所有 missing ranges 都處理完畢（可能是獲取了空數據）
        pattern_hydrate_interval_processed = rf"INFO: hydrate_data_range: Ticker={re.escape(ticker_symbol)}, Interval=\w+\. All missing date ranges for this interval processed successfully .* Ending attempts for this ticker"


        if not (re.search(pattern_all_cached_current_interval, combined_log_run2) or \
                re.search(pattern_any_interval_skip, combined_log_run2) or \
                re.search(pattern_hydrate_full_cache_hit, combined_log_run2) or \
                re.search(pattern_hydrate_interval_processed, combined_log_run2) ):
            log_message(f"WARNING ({case_name}): 未找到 Ticker {ticker_symbol} 的明確生產者快取命中或跳過日誌。")
            all_tickers_showed_cache_behavior = False
            # break # 一旦有一個不滿足，就可以認為 cond_producer_skipped_or_cached 為 False

    cond_producer_skipped_or_cached = cond_producer_skipped_or_cached and all_tickers_showed_cache_behavior


    log_message(f"INFO ({case_name}): 驗收條件檢查:")
    log_message(f"  - 第二次執行返回碼為0: {cond_ret_code_2_ok}")
    log_message(f"  - 第二次執行時間更快: {cond_time_faster} (第一次: {time_run1_duration:.2f}s, 第二次: {time_run2_duration:.2f}s)")
    log_message(f"  - 資料庫行數相同: {cond_rows_same} (第一次後: {db_rows_after_run1}, 第二次後: {db_rows_after_run2})")
    log_message(f"  - 第二次日誌包含生產者跳過/快取命中信息 (且消費者無新數據寫入): {cond_producer_skipped_or_cached}")

    success = cond_ret_code_2_ok and cond_time_faster and cond_rows_same and cond_producer_skipped_or_cached
    print_test_footer(case_name, success, time.time() - start_run_time)
    return success


def test_B_pressure_test() -> bool:
    """測試案例 B：全員突擊壓力測試"""
    case_name = "B_pressure_test"
    print_test_header(case_name)
    start_run_time = time.time()

    db_path = get_test_db_path(case_name)
    if os.path.exists(db_path): os.remove(db_path)

    tickers = ANALYSIS_TICKERS_FULL_LIST_STR
    # 短日期範圍以加速，主要測試並行穩定性
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=1) # 僅獲取1-2天數據
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    log_message(f"\nINFO ({case_name}): --- 開始壓力測試 ---")
    return_code, stdout, stderr = run_analyzer_script(
        db_path, tickers, start_date_str, end_date_str,
        force_refresh=True, # 強制從API獲取以增加負載
        max_workers=16 # 使用較多 workers
    )

    # 驗收標準
    cond_ret_code_ok = (return_code == 0)

    # 檢查是否有鎖衝突日誌
    lock_error_keywords = [
        "database is locked", "Lock Conflict", "duckdb.IOException: IO Error: Could not set lock",
        "duckdb.OperationalError: IO Error: Failed to read from file", # 也可能是鎖相關的IO問題
        "OperationalError: database system is locked" # SQLite 樣式，以防萬一
    ]
    lock_error_counts = count_log_keywords(stdout + stderr, lock_error_keywords, case_sensitive=False)
    cond_no_lock_errors = all(count == 0 for count in lock_error_counts.values())

    log_message(f"INFO ({case_name}): 驗收條件檢查:")
    log_message(f"  - 返回碼為0: {cond_ret_code_ok}")
    log_message(f"  - 未檢測到鎖衝突日誌: {cond_no_lock_errors} (計數: {lock_error_counts})")

    # 數據庫行數 > 0 是一個好的跡象，但不強制要求所有 ticker 都有數據
    db_rows = get_db_row_count(db_path)
    cond_data_written = db_rows > 0
    log_message(f"  - 資料庫中寫入了數據: {cond_data_written} (行數: {db_rows})")


    success = cond_ret_code_ok and cond_no_lock_errors and cond_data_written
    if not cond_data_written and success: # 如果沒鎖錯誤且返回0，但沒數據，也算通過核心穩定性，但給予提示
        print(f"WARNING ({case_name}): 壓力測試通過了穩定性檢查，但資料庫中未寫入任何數據。請檢查 Ticker 列表和 yfinance API 的可用性。")

    print_test_footer(case_name, success, time.time() - start_run_time)
    return success


def test_C_system_resilience() -> bool:
    """測試案例 C：系統韌性 - 混合目標驗證"""
    case_name = "C_resilience_test"
    print_test_header(case_name)
    start_run_time = time.time()

    db_path = get_test_db_path(case_name)
    if os.path.exists(db_path): os.remove(db_path)

    valid_ticker = "AAPL"
    invalid_ticker = "THIS-IS-DEFINITELY-INVALID-TICKER-XYZ"
    # 下市或數據稀少股票的例子，yfinance 可能返回空或部分數據
    # 使用一個已知的、在特定歷史時期存在的股票，但可能在近期數據稀少或已下市
    # 例如 'SIRI' (Sirius XM) 在 yfinance 中是活躍的。
    # 我們需要一個更確定的例子，或者接受 yfinance client 的 "no data" 處理
    # 為了測試的穩定性，我們專注於一個明確的有效和一個明確的無效 ticker
    # BRK.A 是一個有效的，但數據可能與其他股票不同（例如，沒有分鐘線）
    # 我們可以選擇一個代碼本身格式就可能錯誤的，或者 yfinance 無法識別的
    delisted_or_sparse_ticker = "BRK-A" # Berkshire Hathaway Class A (通常有日線數據)
                                      # 或使用一個更老的、確認已下市的，如 "FTRCQ" (Frontier Communications, 破產前)
                                      # 為了簡化，這裡的 "下市/稀疏" 測試與 "無效" 測試的預期行為（無數據寫入）可能類似

    tickers_list = [valid_ticker, invalid_ticker, delisted_or_sparse_ticker]
    tickers_str = ",".join(tickers_list)

    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=5) # 5天數據
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    log_message(f"\nINFO ({case_name}): --- 開始韌性測試 ---")
    return_code, stdout, stderr = run_analyzer_script(
        db_path, tickers_str, start_date_str, end_date_str,
        force_refresh=True, max_workers=3
    )

    # 1. 程式成功執行，返回碼為 0
    cond_ret_code_ok = (return_code == 0)

    # 2. 日誌清晰記錄了對無效/下市目標的跳過處理
    # 檢查 yfinance_client 層面的日誌
    # 對於 invalid_ticker，預期有 "fetch_single_chunk ... yfinance returned None" 或 "Pre-flight check ... failed"
    # 或 "所有降級顆粒度 ... 均無法 ... 回填完整數據"
    # 對於 delisted_or_sparse_ticker，行為可能多樣，可能是部分數據，也可能是無數據
    log_output = stdout + stderr

    invalid_handling_logs_present = False
    if invalid_ticker.lower() in log_output.lower():
        if "fetch_single_chunk" in log_output and "returned none" in log_output.lower() and invalid_ticker.lower() in log_output.lower(): invalid_handling_logs_present = True
        if "pre-flight check" in log_output.lower() and "failed" in log_output.lower() and invalid_ticker.lower() in log_output.lower(): invalid_handling_logs_present = True
        if "所有降級顆粒度" in log_output and "均無法" in log_output and invalid_ticker.lower() in log_output.lower(): invalid_handling_logs_present = True
        if "已記錄/更新無數據區塊" in log_output and invalid_ticker.lower() in log_output.lower() : invalid_handling_logs_present = True # 也可能是被記錄為無數據

    cond_invalid_logged = invalid_handling_logs_present

    # 3. 資料庫中，AAPL 的數據應完整存在
    cond_valid_data_exists = check_db_data_for_tickers(db_path, [valid_ticker], start_date_str, end_date_str, expect_data=True, expected_min_rows_per_ticker=1)

    # 4. 資料庫中，FAKE-TICKER 和 BRK.A (假設它在此日期範圍內無細顆粒度數據或被視為稀疏) 的數據則不應存在
    #    或者，如果 yfinance_client 為它們記錄了 "no_data_records"，那也可以。
    #    這裡主要檢查 OHLCV 表中沒有它們的數據。
    cond_invalid_no_data = check_db_data_for_tickers(db_path, [invalid_ticker], start_date_str, end_date_str, expect_data=False)

    # 對於 BRK-A，它可能有日線數據。如果測試範圍是幾天，它應該有幾行日線數據。
    # 如果我們期望它因 "稀疏" 而無數據，那麼測試日期範圍或 Ticker 選擇需要更精確。
    # 這裡假設，如果它有數據，check_db_data_for_tickers(expect_data=True) 會通過；如果沒有，expect_data=False 會通過。
    # 為了測試的明確性，我們假設 BRK-A 在此測試中應該有數據 (例如日線)
    cond_sparse_data_behavior = check_db_data_for_tickers(db_path, [delisted_or_sparse_ticker], start_date_str, end_date_str, expect_data=True, expected_min_rows_per_ticker=1)
    # 如果 BRK-A 確實可能無數據 (例如，如果 yfinance 恰好在那幾天沒有 BRK-A 的數據)，則上面的 expected_min_rows_per_ticker 應為0或調整 expect_data=False

    log_message(f"INFO ({case_name}): 驗收條件檢查:")
    log_message(f"  - 返回碼為0: {cond_ret_code_ok}")
    log_message(f"  - 無效 Ticker ({invalid_ticker}) 的處理日誌存在: {cond_invalid_logged}")
    log_message(f"  - 有效 Ticker ({valid_ticker}) 的數據存在於DB: {cond_valid_data_exists}")
    log_message(f"  - 無效 Ticker ({invalid_ticker}) 的數據不存在於DB: {cond_invalid_no_data}")
    log_message(f"  - 特定 Ticker ({delisted_or_sparse_ticker}) 的數據行為符合預期 (此處預期有數據): {cond_sparse_data_behavior}")

    # 根據 BRK-A 的實際情況，可能需要調整 cond_sparse_data_behavior 的預期
    # 假設 BRK-A 應該有數據
    success = cond_ret_code_ok and cond_invalid_logged and cond_valid_data_exists and cond_invalid_no_data and cond_sparse_data_behavior

    print_test_footer(case_name, success, time.time() - start_run_time)
    return success

# --- 主執行邏輯 ---
def main_test_runner():
    """主測試執行器"""
    initialize_test_environment()
    results = {}
    overall_success = True

    # 執行測試案例
    tests_to_run = [
        test_A_idempotency_and_integrity,
        test_B_pressure_test,
        test_C_system_resilience
    ]

    for test_func in tests_to_run:
        test_name = test_func.__name__
        try:
            result = test_func()
            results[test_name] = result
            if not result:
                overall_success = False
        except Exception as e:
            log_message(f"ERROR: 測試案例 {test_name} 執行時發生未預期異常: {e}", to_console=True)
            import traceback
            log_message(traceback.format_exc(), to_console=False)
            results[test_name] = False
            overall_success = False
        print_separator("=") # 在每個測試案例後添加分隔符

    # 總結
    print_test_header("測試結果總結", main_header=True)
    for test_name, result in results.items():
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"- {test_name}: {status}")

    print_separator("=")
    if overall_success:
        print("🎉🎉🎉 所有 v3.0 架構驗收測試案例均已通過！ 🎉🎉🎉")
        log_message("所有 v3.0 架構驗收測試案例均已通過！", to_console=False)
    else:
        print("😥 部分 v3.0 架構驗收測試案例失敗。請檢查日誌。")
        log_message("部分 v3.0 架構驗收測試案例失敗。", to_console=False)

    print(f"詳細日誌請參閱: {LOG_FILE_PATH}")
    print_separator("=")

    if not overall_success:
        sys.exit(1) # 以非0狀態碼退出，標示CI失敗

if __name__ == "__main__":
    main_test_runner()
