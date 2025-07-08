# -*- coding: utf-8 -*-
"""
端到端實彈測試 (Live Test Harness) for YFinanceHydrator.
這些測試會實際訪問 yfinance API，因此執行時間較長且依賴網路。
標記為 'live'，可以通過 pytest -m "not live" 來跳過。
"""
import pytest
import pandas as pd
from datetime import datetime, date, timedelta, timezone
import os
import time # 用於在重複請求之間添加短暫延遲，確保 last_attempt 時間戳不同

# 假設模組路徑已配置正確
from apps.daily_market_analyzer.db_manager import DBManager
from apps.yfinance_hydrator.hydrator import YFinanceHydrator

# --- Test Database Fixture (與整合測試類似，但可能需要不同的scope或清理策略) ---
@pytest.fixture(scope="function")
def live_test_db_setup(tmp_path):
    """
    為每個實彈測試函數提供一個乾淨的資料庫環境。
    """
    test_db_file = tmp_path / "live_hydrator_test.duckdb"
    print(f"DEBUG (live_fixture): 創建實彈測試資料庫於: {test_db_file}")

    # 確保表名與作戰計畫一致
    db_man = DBManager(db_path=str(test_db_file), target_ohlcv_table_name="MarketPrices_Daily")
    hydrator = YFinanceHydrator(db_manager=db_man)

    yield db_man, hydrator, str(test_db_file)

    print(f"DEBUG (live_fixture): 實彈測試結束，tmp_path 將清理 {test_db_file}")

@pytest.mark.live
class TestYFinanceHydratorLive:
    """
    YFinanceHydrator 的端到端實彈測試。
    """

    def _get_recent_trading_day_str(self) -> str:
        """輔助函數：獲取一個可能是最近交易日的日期字串 (YYYY-MM-DD)。"""
        today = date.today()
        # 根據今天是周幾回溯到可能的上一個交易日 (不完美，未考慮特定假日)
        if today.weekday() == 0: # 週一 -> 上週五
            return (today - timedelta(days=3)).strftime("%Y-%m-%d")
        elif today.weekday() == 6: # 週日 -> 上週五
            return (today - timedelta(days=2)).strftime("%Y-%m-%d")
        else: # 其他工作日 -> 昨天
            return (today - timedelta(days=1)).strftime("%Y-%m-%d")

    # @pytest.mark.skip(reason="實彈測試，避免自動執行 CI 時頻繁觸發。本地測試時請移除 skip。") # 取消 skip 以便執行
    def test_scenario_a_b_first_run_and_cache_hit(self, live_test_db_setup):
        """
        場景 A (首次運行 - 成功) + 場景 B (快取命中)
        1. 選擇一個最近的交易日，force_refresh=True (或確保DB為空)，驗證成功獲取。
        2. 立即再次運行相同請求 (force_refresh=False)，驗證快取命中。
        """
        db_man, hydrator, _ = live_test_db_setup

        # 選擇一個流動性好的股票和一個較近的日期
        # 注意：即使是最近的交易日，也可能因數據源延遲而暫無 '1m' 數據
        # 為了測試穩定，優先測試 '1d' 是否能成功
        ticker = "AAPL"
        # 使用一個固定的、較久遠的過去日期，確保數據存在且穩定
        test_date_str = "2024-03-01" # 2024年3月1日 (週五)
        print(f"DEBUG (test_scenario_a_b): Using fixed test_date_str: {test_date_str}")

        request_hash = hydrator._create_request_hash(ticker)

        print(f"\n--- Live Test: 場景 A (首次運行) for {ticker} on {test_date_str} ---")
        # 首次運行，可以認為DB是空的，或使用 force_refresh=True 來確保API調用
        hydrator.hydrate_day(ticker, test_date_str, force_refresh=True)

        # 驗證場景 A
        # 1. CacheIndex 應為 SUCCESS
        cache_entry_A = db_man.check_request_status(request_hash, test_date_str)
        assert cache_entry_A is not None, f"CacheIndex 應有 {ticker}@{test_date_str} 的記錄"
        assert cache_entry_A['status'] == "SUCCESS", \
            f"CacheIndex 狀態應為 SUCCESS, 實際為 {cache_entry_A['status']}. Message: {cache_entry_A.get('message')}"
        assert cache_entry_A['final_interval'] is not None, "CacheIndex final_interval 不應為空"
        print(f"場景 A: CacheIndex 狀態: {cache_entry_A['status']}, Final Interval: {cache_entry_A['final_interval']}")

        # 2. MarketPrices_Daily 表應有數據
        day_dt = datetime.strptime(test_date_str, "%Y-%m-%d")
        day_start_utc = datetime(day_dt.year, day_dt.month, day_dt.day, tzinfo=timezone.utc)
        day_end_utc = day_start_utc + timedelta(days=1)
        query_ranged = f"SELECT * FROM MarketPrices_Daily WHERE ticker = ? AND datetime >= ? AND datetime < ?"
        db_data_A = db_man.execute_query(query_ranged, [ticker, day_start_utc, day_end_utc])
        assert not db_data_A.empty, f"MarketPrices_Daily 表中應有 {ticker}@{test_date_str} 的數據"
        print(f"場景 A: MarketPrices_Daily 獲取到 {len(db_data_A)} 筆數據 for {cache_entry_A['final_interval']} interval.")

        # 等待一小段時間，確保 last_attempt 時間戳會有差異，以便更好地區分 CacheIndex 更新
        time.sleep(1)

        print(f"\n--- Live Test: 場景 B (快取命中) for {ticker} on {test_date_str} ---")
        # 再次運行，不使用 force_refresh
        # 為了驗證 API 是否被調用，理想情況下我們需要 mock yfinance，但在實彈測試中這不可行。
        # 所以我們主要依賴 CacheIndex 的 last_attempt 時間戳是否改變，以及日誌（如果能捕獲）
        # 一個間接的驗證是執行速度，快取命中應該非常快。

        # 記錄 hydrate_day 執行前的 CacheIndex last_attempt
        last_attempt_before_b = cache_entry_A['last_attempt']

        start_time_b = time.time()
        hydrator.hydrate_day(ticker, test_date_str, force_refresh=False)
        duration_b = time.time() - start_time_b
        print(f"場景 B: hydrate_day 執行耗時: {duration_b:.4f} 秒")

        # 驗證場景 B
        cache_entry_B = db_man.check_request_status(request_hash, test_date_str)
        assert cache_entry_B is not None
        assert cache_entry_B['status'] == "SUCCESS" # 狀態應保持 SUCCESS

        # 驗證 last_attempt 是否未改變 (或日誌中應有 "快取命中" 訊息)
        # 由於 hydrate_day 內部邏輯，即使是快取命中，如果 force_refresh=False，
        # 它也會先 check_request_status，但不會更新 CacheIndex 除非狀態改變或 force_refresh=True
        # 然而，如果 hydrate_day 內部在快取命中時完全不觸碰 DB 更新 last_attempt，則此斷言成立。
        # 審查 YFinanceHydrator.hydrate_day 邏輯：如果快取命中 SUCCESS/NO_DATA 且非 force_refresh，它會直接 return。
        # 所以 last_attempt 應該不變。
        assert cache_entry_B['last_attempt'] == last_attempt_before_b, \
            f"CacheIndex 的 last_attempt 時間戳不應改變。Before: {last_attempt_before_b}, After: {cache_entry_B['last_attempt']}"

        assert duration_b < 0.5, f"快取命中執行時間過長 ({duration_b:.4f}s)，可能未命中快取或快取邏輯效率低。" # 假設快取命中在0.5秒內
        print(f"場景 B: CacheIndex 狀態為 SUCCESS，且 last_attempt 未改變。符合快取命中預期。")

    # @pytest.mark.skip(reason="實彈測試，避免自動執行 CI 時頻繁觸發。本地測試時請移除 skip。") # 取消 skip 以便執行
    def test_scenario_c_d_smart_fallback_and_failure_memory(self, live_test_db_setup):
        """
        場景 C (智能降級 - 市場假日) + 場景 D (失敗記憶)
        1. 選擇一個市場假日，驗證引擎嘗試所有精度，最終 CacheIndex 記錄 NO_DATA。
        2. 立即再次請求同一個假日，驗證直接從 CacheIndex 讀取 NO_DATA，跳過網路請求。
        """
        db_man, hydrator, _ = live_test_db_setup

        ticker = "MSFT" # 選擇一支活躍股票
        # 選擇一個幾乎肯定是全球市場假日或非交易日的日期
        # 例如：新年第一天，或一個已知的美國市場假日
        # 為了測試一致性，使用一個固定的過去假日
        holiday_date_str = "2024-01-01" # 假設為新年，美股休市
        request_hash = hydrator._create_request_hash(ticker)

        print(f"\n--- Live Test: 場景 C (智能降級 - 市場假日) for {ticker} on {holiday_date_str} ---")
        # 首次運行，確保API會被調用 (或DB為空)
        hydrator.hydrate_day(ticker, holiday_date_str, force_refresh=True)

        # 驗證場景 C
        cache_entry_C = db_man.check_request_status(request_hash, holiday_date_str)
        assert cache_entry_C is not None
        assert cache_entry_C['status'] == "NO_DATA", \
            f"CacheIndex 狀態應為 NO_DATA for holiday, 實際為 {cache_entry_C['status']}. Message: {cache_entry_C.get('message')}"
        assert "所有嘗試的精度" in cache_entry_C['message'] or "未返回數據" in cache_entry_C['message']
        print(f"場景 C: CacheIndex 狀態: {cache_entry_C['status']}. Message: {cache_entry_C['message']}")

        # MarketPrices_Daily 表應無此日數據
        day_dt = datetime.strptime(holiday_date_str, "%Y-%m-%d")
        query = f"SELECT COUNT(*) FROM MarketPrices_Daily WHERE ticker = ? AND date(datetime) = ?"
        count = db_man.execute_query(query, [ticker, day_dt.date()]).iloc[0,0]
        assert count == 0, f"MarketPrices_Daily 不應包含假日 {holiday_date_str} 的數據"

        time.sleep(1) # 確保時間戳可區分

        print(f"\n--- Live Test: 場景 D (失敗記憶) for {ticker} on {holiday_date_str} ---")
        last_attempt_before_d = cache_entry_C['last_attempt']
        start_time_d = time.time()
        hydrator.hydrate_day(ticker, holiday_date_str, force_refresh=False)
        duration_d = time.time() - start_time_d
        print(f"場景 D: hydrate_day 執行耗時: {duration_d:.4f} 秒")

        cache_entry_D = db_man.check_request_status(request_hash, holiday_date_str)
        assert cache_entry_D is not None
        assert cache_entry_D['status'] == "NO_DATA"
        assert cache_entry_D['last_attempt'] == last_attempt_before_d, "CacheIndex 的 last_attempt 不應改變 (失敗記憶命中)"
        assert duration_d < 0.5, f"失敗記憶命中執行時間過長 ({duration_d:.4f}s)"
        print(f"場景 D: CacheIndex 狀態為 NO_DATA，last_attempt 未改變。符合失敗記憶預期。")

# 注意：
# - 實彈測試的穩定性依賴外部 API 和網路。
# - _get_recent_trading_day_str 是一個簡化實現，可能無法完美處理所有市場的假日。
#   對於關鍵測試，使用確定的歷史日期可能更可靠。
# - 測試中對 API 是否被調用的判斷，在實彈測試中較難直接驗證（除非分析日誌）。
#   主要依賴 CacheIndex 的狀態和 last_attempt 時間戳，以及執行時間來間接推斷。
# - 考慮 yfinance API 的速率限制，過於頻繁的實彈測試執行可能導致暫時的 IP 封鎖。
#   這就是為什麼通常將它們標記並選擇性執行。
# - @pytest.mark.skip 預設添加，以避免在自動化流程中意外執行。本地測試時需要移除或註釋掉。
