# -*- coding: utf-8 -*-
"""
YFinanceHydrator 端到端實彈測試工具 (Live Test Harness)
======================================================
此腳本用於在真實網路環境下測試 YFinanceHydrator 的完整流程。
警告：執行此腳本會產生實際的 yfinance API 網路請求。請注意請求頻率限制。

使用方式：
1. 確保環境中已安裝所有必要套件 (pandas, yfinance, duckdb)。
2. 可選：設定環境變數 TEST_DB_PATH 指定測試資料庫路徑，否則使用預設路徑。
3. 從項目根目錄執行: python tests/_test_harness_hydrator_live.py
"""
import pandas as pd
from datetime import datetime, date, timedelta, timezone
import os
import time
import shutil # 用於可選的資料庫清理
import argparse # 用於命令行參數

# 假設模組路徑配置正確
from apps.daily_market_analyzer.db_manager import DBManager
from apps.yfinance_hydrator.hydrator import YFinanceHydrator

# --- 配置 ---
DEFAULT_TEST_DB_PATH = "data_workspace/temp/test_hydrator_live.duckdb"
TEST_DB_PATH = os.environ.get("TEST_DB_PATH", DEFAULT_TEST_DB_PATH)

TEST_TICKERS = {
    "regular_day": "AAPL",
    "holiday_check": "SPY",
    "non_existent": "THIS_TICKER_DOES_NOT_EXIST_XYZ123ABC"
}

# 動態獲取日期
today_date = date.today()
# RECENT_TRADE_DATE: 嘗試獲取一個較近的、數據可能完整的交易日。使用固定的過去日期可能更穩定。
# 為了演示，我們用一個固定的過去日期，確保數據的穩定性。
# 如果需要動態，可以取消註釋下面的部分，但要注意API數據可能延遲。
# if today_date.weekday() == 5: # 週六 -> 前一天是週五
#     RECENT_TRADE_DATE = (today_date - timedelta(days=1)).strftime("%Y-%m-%d")
# elif today_date.weekday() == 6: # 週日 -> 前兩天是週五
#     RECENT_TRADE_DATE = (today_date - timedelta(days=2)).strftime("%Y-%m-%d")
# else: # 工作日
#     RECENT_TRADE_DATE = (today_date - timedelta(days=1)).strftime("%Y-%m-%d")
RECENT_TRADE_DATE = "2024-03-01" # 固定日期 (週五)，假設數據穩定
KNOWN_US_MARKET_HOLIDAY = "2024-01-01" # 新年元旦

# --- 輔助函數 ---
def setup_test_environment(db_path, clean_db_first=False):
    print(f"\n--- 設定測試環境 ---")
    print(f"測試資料庫路徑: {db_path}")

    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        print(f"已創建目錄: {db_dir}")

    if clean_db_first and os.path.exists(db_path):
        try:
            os.remove(db_path)
            print(f"已清理舊的測試資料庫: {db_path}")
        except Exception as e:
            print(f"清理測試資料庫 {db_path} 失敗: {e}")

    # 確保 DBManager 使用 MarketPrices_Daily (或計畫書指定的表名)
    db_manager = DBManager(db_path=db_path, target_ohlcv_table_name="MarketPrices_Daily")
    hydrator = YFinanceHydrator(db_manager=db_manager)
    print("DBManager 和 YFinanceHydrator 初始化完畢。")
    return db_manager, hydrator

def print_cache_status(db_manager, ticker, date_str, hydrator_instance):
    request_hash = hydrator_instance._create_request_hash(ticker)
    status_info = db_manager.check_request_status(request_hash, date_str)
    print(f"  CacheIndex 狀態 for {ticker} @ {date_str}:")
    if status_info:
        print(f"    Status: {status_info['status']}")
        print(f"    Final Interval: {status_info.get('final_interval', 'N/A')}")
        print(f"    Last Attempt: {status_info['last_attempt']}")
        print(f"    Message: {status_info['message']}")
    else:
        print(f"    未找到記錄。")

def check_data_in_db(db_manager, ticker, date_str, expected_interval=None):
    target_d = datetime.strptime(date_str, "%Y-%m-%d").date()
    start_utc = datetime(target_d.year, target_d.month, target_d.day, tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(days=1)
    query = f"SELECT COUNT(*) FROM {db_manager.ohlcv_table_name} WHERE ticker = ? AND datetime >= ? AND datetime < ?"
    params = [ticker, start_utc, end_utc]
    if expected_interval:
        query += " AND interval = ?"
        params.append(expected_interval)
    count = db_manager.execute_query(query, params=params).iloc[0,0]
    result = count > 0
    interval_info = f" (Interval: {expected_interval})" if expected_interval else ""
    print(f"  DB CHECK: {'找到' if result else '未找到'} {count if result else ''} 筆記錄 for {ticker} @ {date_str}{interval_info}.")
    return result

# --- 測試場景 ---
def scene_a_first_run_success(hydrator, db_manager, ticker, date_str):
    print(f"\n--- 場景 A: 首次運行 - 成功 ({ticker} @ {date_str}) ---")
    # 確保此特定 ticker/date 的快取是空的，以模擬首次運行
    request_hash = hydrator._create_request_hash(ticker)
    db_manager.execute_query(f"DELETE FROM CacheIndex WHERE request_hash = '{request_hash}' AND date = '{date_str}'")
    print(f"  (為確保首次運行，已清理 {ticker} @ {date_str} 的 CacheIndex)")

    start_time = time.time()
    hydrator.hydrate_day(ticker, date_str, force_refresh=False)
    duration = time.time() - start_time
    print(f"  操作完成，耗時: {duration:.2f} 秒。")
    print_cache_status(db_manager, ticker, date_str, hydrator)
    check_data_in_db(db_manager, ticker, date_str)

def scene_b_cache_hit(hydrator, db_manager, ticker, date_str):
    print(f"\n--- 場景 B: 快取命中 ({ticker} @ {date_str}) ---")
    start_time = time.time()
    hydrator.hydrate_day(ticker, date_str, force_refresh=False)
    duration = time.time() - start_time
    print(f"  操作完成，耗時: {duration:.2f} 秒 (預期非常快)。")
    print_cache_status(db_manager, ticker, date_str, hydrator)
    assert duration < 0.5, f"場景 B 快取命中執行時間過長: {duration:.4f}s"


def scene_c_intelligent_fallback_holiday(hydrator, db_manager, ticker, holiday_date_str):
    print(f"\n--- 場景 C: 智能降級 - 市場假日 ({ticker} @ {holiday_date_str}) ---")
    request_hash = hydrator._create_request_hash(ticker)
    db_manager.execute_query(f"DELETE FROM CacheIndex WHERE request_hash = '{request_hash}' AND date = '{holiday_date_str}'")
    print(f"  (為確保首次處理假日，已清理 {ticker} @ {holiday_date_str} 的 CacheIndex)")

    start_time = time.time()
    hydrator.hydrate_day(ticker, holiday_date_str, force_refresh=False)
    duration = time.time() - start_time
    print(f"  操作完成，耗時: {duration:.2f} 秒。")
    print_cache_status(db_manager, ticker, holiday_date_str, hydrator)
    assert not check_data_in_db(db_manager, ticker, holiday_date_str), "假日不應有數據存入DB"

def scene_d_failure_memory_holiday(hydrator, db_manager, ticker, holiday_date_str):
    print(f"\n--- 場景 D: 失敗記憶 - 市場假日 ({ticker} @ {holiday_date_str}) ---")
    start_time = time.time()
    hydrator.hydrate_day(ticker, holiday_date_str, force_refresh=False)
    duration = time.time() - start_time
    print(f"  操作完成，耗時: {duration:.2f} 秒 (預期非常快)。")
    print_cache_status(db_manager, ticker, holiday_date_str, hydrator)
    assert duration < 0.5, f"場景 D 失敗記憶命中執行時間過長: {duration:.4f}s"
    assert not check_data_in_db(db_manager, ticker, holiday_date_str), "假日不應有數據存入DB"


def scene_e_non_existent_ticker(hydrator, db_manager, ticker, date_str):
    print(f"\n--- 場景 E: 不存在的 Ticker ({ticker} @ {date_str}) ---")
    request_hash = hydrator._create_request_hash(ticker)
    db_manager.execute_query(f"DELETE FROM CacheIndex WHERE request_hash = '{request_hash}' AND date = '{date_str}'")
    print(f"  (為確保首次處理不存在的Ticker，已清理 {ticker} @ {date_str} 的 CacheIndex)")

    start_time = time.time()
    hydrator.hydrate_day(ticker, date_str, force_refresh=False)
    duration = time.time() - start_time
    print(f"  操作完成，耗時: {duration:.2f} 秒。")
    print_cache_status(db_manager, ticker, date_str, hydrator)
    assert not check_data_in_db(db_manager, ticker, date_str), "不存在的Ticker不應有數據存入DB"
    # 驗證 CacheIndex 狀態是否為 NO_DATA 或 API_FAILURE
    status_info = db_manager.check_request_status(request_hash, date_str)
    assert status_info and status_info['status'] in ["NO_DATA", "API_FAILURE"], \
        f"不存在的 Ticker 快取狀態應為 NO_DATA 或 API_FAILURE，實際為: {status_info['status'] if status_info else 'None'}"


# --- 主執行邏輯 ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YFinanceHydrator 實彈測試工具。")
    parser.add_argument(
        "--clean_db", action="store_true",
        help="在開始所有測試前，完全清理並重建測試資料庫。"
    )
    args = parser.parse_args()

    print("===== YFinanceHydrator 實彈測試開始 =====")

    db_manager_main, hydrator_main = setup_test_environment(TEST_DB_PATH, clean_db_first=args.clean_db)

    # --- 執行場景 ---
    active_ticker = TEST_TICKERS["regular_day"]
    test_date_scene_ab = RECENT_TRADE_DATE
    print(f"\n\n========== 測試常規股票: {active_ticker}, 日期: {test_date_scene_ab} ==========")
    scene_a_first_run_success(hydrator_main, db_manager_main, active_ticker, test_date_scene_ab)
    time.sleep(1)
    scene_b_cache_hit(hydrator_main, db_manager_main, active_ticker, test_date_scene_ab)

    holiday_ticker = TEST_TICKERS["holiday_check"]
    test_date_scene_cd = KNOWN_US_MARKET_HOLIDAY
    print(f"\n\n========== 測試市場假日: {holiday_ticker}, 日期: {test_date_scene_cd} ==========")
    scene_c_intelligent_fallback_holiday(hydrator_main, db_manager_main, holiday_ticker, test_date_scene_cd)
    time.sleep(1)
    scene_d_failure_memory_holiday(hydrator_main, db_manager_main, holiday_ticker, test_date_scene_cd)

    non_existent_ticker_val = TEST_TICKERS["non_existent"]
    test_date_scene_e = RECENT_TRADE_DATE
    print(f"\n\n========== 測試不存在的Ticker: {non_existent_ticker_val}, 日期: {test_date_scene_e} ==========")
    scene_e_non_existent_ticker(hydrator_main, db_manager_main, non_existent_ticker_val, test_date_scene_e)

    print("\n\n===== YFinanceHydrator 實彈測試結束 =====")
    print(f"測試數據已寫入/更新於: {TEST_DB_PATH}")
    print("請檢查上述日誌輸出以及資料庫內容以驗證結果。")
</tbody>
</table>
