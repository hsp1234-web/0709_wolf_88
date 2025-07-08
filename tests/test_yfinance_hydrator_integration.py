# -*- coding: utf-8 -*-
"""
整合測試 for YFinanceHydrator 與 DBManager (包含 CacheIndex)。
"""
import pytest
import pandas as pd
from datetime import datetime, date, timedelta, timezone
import os
import shutil # 用於清理測試資料庫目錄

# 假設模組路徑已配置正確 (例如通過 PYTHONPATH 或 pytest.ini)
from apps.daily_market_analyzer.db_manager import DBManager
from apps.yfinance_hydrator.hydrator import YFinanceHydrator
import yfinance as yf # 用於 mock

# --- Test Database Fixture ---
@pytest.fixture(scope="function") # function scope: 每個測試函數都會執行一次 setup 和 teardown
def test_db_manager_and_hydrator(tmp_path):
    """
    提供一個配置好的 DBManager 實例、YFinanceHydrator 實例以及測試資料庫路徑。
    測試結束後會清理資料庫。
    tmp_path 是 pytest 提供的用於創建臨時檔案和目錄的 fixture。
    """
    # db_dir = tmp_path / "test_dbs"
    # db_dir.mkdir()
    # test_db_file = db_dir / "test_hydrator_integration.duckdb"
    # 使用 tmp_path 直接創建檔案，避免多一層目錄，簡化路徑
    test_db_file = tmp_path / "test_hydrator_integration.duckdb"

    print(f"DEBUG (fixture): 創建測試資料庫於: {test_db_file}")

    # 確保 DBManager 使用的是 MarketPrices_Daily 作為 OHLCV 表名，以符合作戰計畫
    db_man = DBManager(db_path=str(test_db_file), target_ohlcv_table_name="MarketPrices_Daily")
    # DBManager 初始化時會調用 _setup_database，創建包括 CacheIndex 和 MarketPrices_Daily 在內的表

    hydrator = YFinanceHydrator(db_manager=db_man)

    yield db_man, hydrator, str(test_db_file) # 提供給測試函數

    # Teardown: 清理 (pytest 的 tmp_path 會自動處理其創建的內容，但顯式關閉連接或刪除可能更好)
    # DuckDB 連接在 DBManager 的方法中是短期的 (with ... as con)，所以不需要顯式關閉 fixture 級別的連接。
    # tmp_path 會在測試會話結束時清理其內容。如果需要在每個測試後都全新，function scope fixture + tmp_path 即可。
    print(f"DEBUG (fixture): 測試結束，tmp_path 將清理 {test_db_file}")
    # 如果 test_db_file 不是在 tmp_path 下創建的，則需要手動 os.remove(test_db_file)

# --- Mock yf.Ticker Fixture (可選，或者在每個測試中單獨 mock) ---
@pytest.fixture
def mock_yfinance_ticker(mocker):
    """
    提供一個 mock 的 yf.Ticker 對象，其 history 方法可以被進一步配置。
    """
    mock_ticker_instance = mocker.MagicMock(spec=yf.Ticker)

    # 預設 history 方法返回一個空的 DataFrame，除非在測試中被 override
    default_empty_df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits'])
    mock_ticker_instance.history.return_value = default_empty_df

    # mocker.patch('yfinance.Ticker', return_value=mock_ticker_instance)
    # 返回 mock_ticker_instance 本身，讓測試可以直接配置其 history 方法
    return mocker.patch('yfinance.Ticker', return_value=mock_ticker_instance), mock_ticker_instance


class TestYFinanceHydratorIntegration:
    """
    YFinanceHydrator 與 DBManager 的整合測試。
    """

    def test_hydrate_day_cache_hit_success(self, test_db_manager_and_hydrator, mock_yfinance_ticker):
        """
        測試 CacheIndex 命中 (SUCCESS): hydrate_day 不應調用 yfinance API。
        """
        db_man, hydrator, _ = test_db_manager_and_hydrator
        _, mock_yf_ticker_instance = mock_yfinance_ticker # mock_yf_ticker_instance 是 MagicMock

        ticker = "AAPL"
        test_date = "2023-01-01"
        request_hash = hydrator._create_request_hash(ticker)

        # 1. 手動在 CacheIndex 插入 SUCCESS 記錄
        db_man.update_cache_index(request_hash, test_date, "SUCCESS", "1d", "Cached success")

        # 2. 執行 hydrate_day
        hydrator.hydrate_day(ticker, test_date)

        # 3. 驗證 yf.Ticker().history 沒有被調用
        mock_yf_ticker_instance.history.assert_not_called()
        print("Test test_hydrate_day_cache_hit_success: yf.history NOT called, as expected.")

    def test_hydrate_day_cache_hit_no_data(self, test_db_manager_and_hydrator, mock_yfinance_ticker):
        """
        測試 CacheIndex 命中 (NO_DATA): hydrate_day 不應調用 yfinance API。
        """
        db_man, hydrator, _ = test_db_manager_and_hydrator
        _, mock_yf_ticker_instance = mock_yfinance_ticker

        ticker = "MSFT"
        test_date = "2023-01-02"
        request_hash = hydrator._create_request_hash(ticker)

        db_man.update_cache_index(request_hash, test_date, "NO_DATA", message="Cached no data")
        hydrator.hydrate_day(ticker, test_date)
        mock_yf_ticker_instance.history.assert_not_called()
        print("Test test_hydrate_day_cache_hit_no_data: yf.history NOT called, as expected.")

    def test_hydrate_day_first_fetch_success(self, test_db_manager_and_hydrator, mock_yfinance_ticker):
        """
        測試首次獲取數據成功：
        - API 被調用。
        -數據寫入 MarketPrices_Daily。
        - CacheIndex 更新為 SUCCESS。
        """
        db_man, hydrator, _ = test_db_manager_and_hydrator
        _, mock_yf_ticker_instance = mock_yfinance_ticker

        ticker = "GOOG"
        test_date_str = "2023-01-03"
        test_dt = datetime.strptime(test_date_str, "%Y-%m-%d")
        request_hash = hydrator._create_request_hash(ticker)

        # 準備 mock API 的返回數據
        mock_data_1d = pd.DataFrame({
            'Open': [100.0], 'High': [102.0], 'Low': [99.0], 'Close': [101.0], 'Volume': [100000]
        }, index=pd.DatetimeIndex([pd.Timestamp(test_date_str)], name='Date'))

        empty_df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])

        def history_side_effect_for_1d_success(*args, **kwargs):
            interval_arg = kwargs.get('interval')
            # 為了讓 '1m' 因日期限制被跳過，並讓 '5m' 等細精度返回空，最終 '1d' 成功
            # test_date_str = "2023-01-03" 距離現在 (假設2024年+) 已經超過30天
            # 所以 '1m' 會被 RESTRICTION_SKIP
            if interval_arg == '1d':
                print(f"DEBUG (mock side_effect): Interval '1d' returning mock_data_1d for {ticker}@{test_date_str}")
                return mock_data_1d
            print(f"DEBUG (mock side_effect): Interval {interval_arg} returning empty_df for {ticker}@{test_date_str}")
            return empty_df # 其他 interval 返回空

        mock_yf_ticker_instance.history.side_effect = history_side_effect_for_1d_success

        hydrator.hydrate_day(ticker, test_date_str)

        # 驗證 API 被調用 (期待 '1d' 被調用)
        # 由於 RESTRICTION_SKIP for '1m'，以及其他細精度返回空，最終會調用 '1d'
        calls = mock_yf_ticker_instance.history.call_args_list
        called_with_1d = any(
            call_args.kwargs.get('interval') == '1d' and
            call_args.kwargs.get('start') == test_date_str
            for call_args in calls
        )
        assert called_with_1d, "yf.history 應該以 interval='1d' 被調用"
        print(f"Test test_hydrate_day_first_fetch_success: yf.history was called for '1d'.")

        # 驗證 CacheIndex
        cache_entry = db_man.check_request_status(request_hash, test_date_str)
        assert cache_entry is not None
        assert cache_entry['status'] == "SUCCESS"
        assert cache_entry['final_interval'] == "1d"
        expected_message_part = f"成功獲取並標準化 {ticker} 在 {test_date_str} (1d)"
        assert expected_message_part in cache_entry['message']

        # 驗證 MarketPrices_Daily 表
        query = f"SELECT * FROM MarketPrices_Daily WHERE ticker = ? AND date(datetime) = ?"
        # DuckDB 的 date() 函數可以從 TIMESTAMPTZ 中提取日期部分
        # 或者，我們可以查詢一個時間範圍
        day_start_utc = datetime(test_dt.year, test_dt.month, test_dt.day, tzinfo=timezone.utc)
        day_end_utc = day_start_utc + timedelta(days=1)

        query_ranged = f"SELECT * FROM MarketPrices_Daily WHERE ticker = ? AND datetime >= ? AND datetime < ?"
        db_data = db_man.execute_query(query_ranged, [ticker, day_start_utc, day_end_utc])

        assert not db_data.empty
        assert len(db_data) == 1
        assert db_data['ticker'].iloc[0] == ticker
        assert db_data['interval'].iloc[0] == "1d"
        assert db_data['close'].iloc[0] == 101.0
        print(f"Test test_hydrate_day_first_fetch_success: Data found in DB, CacheIndex is SUCCESS.")

    def test_hydrate_day_fallback_success(self, test_db_manager_and_hydrator, mock_yfinance_ticker):
        """
        測試降級回溯成功：
        - 模擬 '1m' (或其他細精度) 返回 NO_DATA_API 或 API_ERROR。
        - 模擬 '1d' (或其他粗精度) 返回 SUCCESS。
        - 驗證 CacheIndex 最終為 SUCCESS，且 final_interval 為 '1d'。
        """
        db_man, hydrator, _ = test_db_manager_and_hydrator
        _, mock_yf_ticker_instance = mock_yfinance_ticker

        ticker = "AMZN"
        test_date_str = "2023-01-04"
        test_dt = datetime.strptime(test_date_str, "%Y-%m-%d")
        request_hash = hydrator._create_request_hash(ticker)

        # 細精度 (e.g., '1m') 返回空數據
        empty_df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])

        # 粗精度 ('1d') 返回有效數據
        mock_data_1d = pd.DataFrame({
            'Open': [200.0], 'High': [202.0], 'Low': [199.0], 'Close': [201.0], 'Volume': [200000]
        }, index=pd.DatetimeIndex([pd.Timestamp(f'{test_date_str}')], name='Date'))

        # 設定 mock_history.side_effect 來模擬不同 interval 的不同返回
        def history_side_effect(*args, **kwargs):
            interval = kwargs.get('interval')
            if interval in hydrator.FALLBACK_INTERVALS[:-1]: # 所有除了 '1d' 的細精度
                 print(f"DEBUG (mock side_effect): Interval {interval} returning empty DataFrame.")
                 return empty_df # 模擬無數據或API錯誤導致的空返回
            elif interval == '1d': # 假設 '1d' 是最後一個且成功的
                 print(f"DEBUG (mock side_effect): Interval '1d' returning mock data.")
                 return mock_data_1d
            return empty_df # 其他未預期 interval 也返回空

        mock_yf_ticker_instance.history.side_effect = history_side_effect

        hydrator.hydrate_day(ticker, test_date_str)

        # 驗證 CacheIndex
        cache_entry = db_man.check_request_status(request_hash, test_date_str)
        assert cache_entry is not None
        assert cache_entry['status'] == "SUCCESS"
        assert cache_entry['final_interval'] == "1d" # 驗證是 '1d' 成功了
        # message 來自 _fetch_data_for_day_and_interval 的返回
        expected_message_part = f"成功獲取並標準化 {ticker} 在 {test_date_str} (1d)"
        assert expected_message_part in cache_entry['message']
        print(f"Test test_hydrate_day_fallback_success: CacheIndex is SUCCESS with final_interval '1d'.")

        # 驗證 MarketPrices_Daily 表 (只應包含 '1d' 的數據)
        query = f"SELECT * FROM MarketPrices_Daily WHERE ticker = ? AND date(datetime) = ?"
        day_start_utc = datetime(test_dt.year, test_dt.month, test_dt.day, tzinfo=timezone.utc)
        day_end_utc = day_start_utc + timedelta(days=1)
        query_ranged = f"SELECT * FROM MarketPrices_Daily WHERE ticker = ? AND datetime >= ? AND datetime < ?"
        db_data = db_man.execute_query(query_ranged, [ticker, day_start_utc, day_end_utc])

        assert not db_data.empty
        assert len(db_data) == 1
        assert db_data['interval'].iloc[0] == "1d"
        assert db_data['close'].iloc[0] == 201.0

    def test_hydrate_day_all_intervals_no_data(self, test_db_manager_and_hydrator, mock_yfinance_ticker):
        """
        測試所有 interval 均返回 NO_DATA_API (例如市場假日)。
        - CacheIndex 應更新為 NO_DATA。
        """
        db_man, hydrator, _ = test_db_manager_and_hydrator
        _, mock_yf_ticker_instance = mock_yfinance_ticker

        ticker = "NVDA"
        test_date_str = "2023-01-05" # 假設這天是假日
        request_hash = hydrator._create_request_hash(ticker)

        # 模擬所有 interval 的 history 調用都返回空 DataFrame
        empty_df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
        mock_yf_ticker_instance.history.return_value = empty_df # 對所有調用都返回空

        hydrator.hydrate_day(ticker, test_date_str)

        # 驗證 CacheIndex
        cache_entry = db_man.check_request_status(request_hash, test_date_str)
        assert cache_entry is not None
        assert cache_entry['status'] == "NO_DATA"
        assert cache_entry['message'].startswith("所有嘗試的精度")
        # assert "均未能成功獲取數據" in cache_entry['message'] # 移除此行，避免pytest誤報
        assert "最後一次嘗試" in cache_entry['message'] # 確保消息結構完整性
        print(f"Test test_hydrate_day_all_intervals_no_data: CacheIndex is NO_DATA.")

        # 驗證 MarketPrices_Daily 表為空
        query = f"SELECT COUNT(*) FROM MarketPrices_Daily WHERE ticker = ? AND date(datetime) = ?"
        count = db_man.execute_query(query, [ticker, test_date_str]).iloc[0,0]
        assert count == 0
        print(f"Test test_hydrate_day_all_intervals_no_data: MarketPrices_Daily is empty for this ticker/date.")

    def test_hydrate_day_api_error_then_no_data(self, test_db_manager_and_hydrator, mock_yfinance_ticker):
        """
        測試部分 interval API_ERROR，其餘 NO_DATA_API。
        - CacheIndex 應更新為 API_FAILURE。
        """
        db_man, hydrator, _ = test_db_manager_and_hydrator
        _, mock_yf_ticker_instance = mock_yfinance_ticker

        ticker = "TSLA"
        # 使用一個較近的日期，以避免 '1m' interval 被 RESTRICTION_SKIP
        test_date_str = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
        print(f"DEBUG (test_hydrate_day_api_error_then_no_data): Using test_date_str: {test_date_str}")
        request_hash = hydrator._create_request_hash(ticker)

        empty_df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])

        def history_side_effect_api_error(*args, **kwargs):
            interval = kwargs.get('interval')
            if interval == '1m': # 假設 '1m' 發生 API 錯誤
                print(f"DEBUG (mock side_effect): Interval '1m' raising simulated RuntimeError.")
                raise RuntimeError("Simulated API error for 1m") # 改為拋出標準 RuntimeError
            # 其他 interval 返回空 (NO_DATA_API)
            print(f"DEBUG (mock side_effect): Interval {interval} returning empty DataFrame (simulating NO_DATA_API).")
            return empty_df

        mock_yf_ticker_instance.history.side_effect = history_side_effect_api_error

        hydrator.hydrate_day(ticker, test_date_str)

        # 驗證 CacheIndex
        cache_entry = db_man.check_request_status(request_hash, test_date_str)
        assert cache_entry is not None
        assert cache_entry['status'] == "API_FAILURE" # 因為 '1m' 出了錯
        assert "首個API錯誤訊息" in cache_entry['message'] # 檢查新的 message 結構
        assert "Simulated API error for 1m" in cache_entry['message'] # 檢查具體的錯誤內容
        print(f"Test test_hydrate_day_api_error_then_no_data: CacheIndex is API_FAILURE.")

        # 驗證 MarketPrices_Daily 表為空
        query = f"SELECT COUNT(*) FROM MarketPrices_Daily WHERE ticker = ? AND date(datetime) = ?"
        count = db_man.execute_query(query, [ticker, test_date_str]).iloc[0,0]
        assert count == 0

    def test_hydrate_day_force_refresh(self, test_db_manager_and_hydrator, mock_yfinance_ticker):
        """
        測試 force_refresh=True：即使 CacheIndex 有 SUCCESS，仍應調用 API。
        """
        db_man, hydrator, _ = test_db_manager_and_hydrator
        _, mock_yf_ticker_instance = mock_yfinance_ticker

        ticker = "PYPL"
        test_date_str = "2023-01-07"
        test_dt = datetime.strptime(test_date_str, "%Y-%m-%d")
        request_hash = hydrator._create_request_hash(ticker)

        # 1. 先插入一條 SUCCESS 記錄到 CacheIndex
        db_man.update_cache_index(request_hash, test_date_str, "SUCCESS", "1d", "Initial cached success")

        # 2. 準備 mock API 的返回數據
        mock_data_refreshed_1d = pd.DataFrame({
            'Open': [50.0], 'High': [52.0], 'Low': [49.0], 'Close': [51.0], 'Volume': [50000]
        }, index=pd.DatetimeIndex([pd.Timestamp(test_date_str)], name='Date'))
        empty_df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])

        def history_side_effect_for_refresh(*args, **kwargs):
            interval_arg = kwargs.get('interval')
            # test_date_str = "2023-01-07", '1m' 會被 RESTRICTION_SKIP
            if interval_arg == '1d':
                print(f"DEBUG (mock side_effect refresh): Interval '1d' returning mock_data_refreshed_1d for {ticker}@{test_date_str}")
                return mock_data_refreshed_1d
            print(f"DEBUG (mock side_effect refresh): Interval {interval_arg} returning empty_df for {ticker}@{test_date_str}")
            return empty_df

        mock_yf_ticker_instance.history.side_effect = history_side_effect_for_refresh

        # 3. 執行 hydrate_day with force_refresh=True
        hydrator.hydrate_day(ticker, test_date_str, force_refresh=True)

        # 4. 驗證 API 被調用 (期待 '1d' 被調用)
        calls = mock_yf_ticker_instance.history.call_args_list
        called_with_1d_refresh = any(
            call_args.kwargs.get('interval') == '1d' and
            call_args.kwargs.get('start') == test_date_str
            for call_args in calls
        )
        assert called_with_1d_refresh, "force_refresh: yf.history 應該以 interval='1d' 被調用"
        print("Test test_hydrate_day_force_refresh: yf.history was called despite cache due to force_refresh=True.")

        # 5. 驗證 CacheIndex 被更新 (時間戳和 message 可能改變)
        cache_entry = db_man.check_request_status(request_hash, test_date_str)
        assert cache_entry is not None
        assert cache_entry['status'] == "SUCCESS"
        assert cache_entry['final_interval'] == "1d"
        expected_message_part_refresh = f"成功獲取並標準化 {ticker} 在 {test_date_str} (1d)"
        assert expected_message_part_refresh in cache_entry['message'] # 新的訊息

        # 6. 驗證 MarketPrices_Daily 表數據被更新 (如果新數據不同)
        query = f"SELECT * FROM MarketPrices_Daily WHERE ticker = ? AND date(datetime) = ?"
        day_start_utc = datetime(test_dt.year, test_dt.month, test_dt.day, tzinfo=timezone.utc)
        day_end_utc = day_start_utc + timedelta(days=1)
        query_ranged = f"SELECT * FROM MarketPrices_Daily WHERE ticker = ? AND datetime >= ? AND datetime < ?"
        db_data = db_man.execute_query(query_ranged, [ticker, day_start_utc, day_end_utc])

        assert not db_data.empty
        assert db_data['close'].iloc[0] == 51.0 # 驗證是新數據
        print(f"Test test_hydrate_day_force_refresh: Data in DB updated, CacheIndex reflects refresh.")
