# -*- coding: utf-8 -*-
"""
YFinanceHydrator 整合測試
==============================
此檔案包含對 YFinanceHydrator 與 DBManager (特別是 CacheIndex) 之間交互的整合測試。
主要目標是驗證快取邏輯是否按預期工作。
"""
import pytest
import os
import pandas as pd
from datetime import datetime, date, timedelta, timezone
import hashlib # 用於生成 request_hash

from apps.yfinance_hydrator.hydrator import YFinanceHydrator
from apps.daily_market_analyzer.db_manager import DBManager

# 測試用的資料庫路徑
TEST_DB_PATH = "data_workspace/temp/test_hydrator_integration.duckdb" # 在 fixture 中使用 tmp_path 會更好

@pytest.fixture(scope="function")
def test_db_manager_and_hydrator(tmp_path, mocker): # tmp_path 是 pytest 提供的 fixture
    """
    提供一個測試用的 DBManager 和 YFinanceHydrator 實例。
    在每次測試前清理並初始化資料庫於臨時路徑。
    同時 mock yf.Ticker().history 以避免 실제 API 調用。
    """
    # 使用 tmp_path 創建唯一的測試資料庫檔案
    db_file = tmp_path / "test_integration.duckdb"
    # print(f"DEBUG (fixture): 創建測試資料庫於: {db_file}") # 避免在測試中 print

    db_manager = DBManager(db_path=str(db_file), target_ohlcv_table_name="MarketPrices_IntegrationTest")

    mock_yf_ticker_instance = mocker.MagicMock()
    # 預設API調用返回空DataFrame，代表無數據。測試案例可以覆蓋此行為。
    mock_yf_ticker_instance.history.return_value = pd.DataFrame()

    # Mock yf.Ticker 以返回我們的 MagicMock instance
    mocker.patch('yfinance.Ticker', return_value=mock_yf_ticker_instance)

    hydrator = YFinanceHydrator(db_manager=db_manager)

    yield db_manager, hydrator, mock_yf_ticker_instance

class TestYFinanceHydratorIntegration:
    """
    YFinanceHydrator 與 DBManager 整合測試集合。
    """

    def test_hydrate_day_cache_hit_success(self, test_db_manager_and_hydrator, mocker):
        db_manager, hydrator, mock_yf_ticker = test_db_manager_and_hydrator

        ticker = "CACHE_HIT_SUCCESS"
        date_str = "2023-01-01"
        request_hash = hydrator._create_request_hash(ticker)

        db_manager.update_cache_index(
            request_hash=request_hash, date_str=date_str, status="SUCCESS",
            final_interval="1d", message="Manually inserted for test"
        )

        mock_upsert_data = mocker.patch.object(db_manager, 'upsert_data')

        hydrator.hydrate_day(ticker=ticker, date_str=date_str, force_refresh=False)

        mock_yf_ticker.history.assert_not_called()
        mock_upsert_data.assert_not_called()

    def test_hydrate_day_cache_hit_no_data(self, test_db_manager_and_hydrator, mocker):
        db_manager, hydrator, mock_yf_ticker = test_db_manager_and_hydrator

        ticker = "CACHE_HIT_NO_DATA"
        date_str = "2023-01-02"
        request_hash = hydrator._create_request_hash(ticker)

        db_manager.update_cache_index(
            request_hash=request_hash, date_str=date_str, status="NO_DATA",
            message="Manually inserted for test"
        )
        mock_upsert_data = mocker.patch.object(db_manager, 'upsert_data')

        hydrator.hydrate_day(ticker=ticker, date_str=date_str, force_refresh=False)

        mock_yf_ticker.history.assert_not_called()
        mock_upsert_data.assert_not_called()

    def test_hydrate_day_cache_miss_then_success_first_interval(self, test_db_manager_and_hydrator, mocker):
        db_manager, hydrator, mock_yf_ticker = test_db_manager_and_hydrator

        ticker = "CACHE_MISS_SUCCESS_1M"
        # 使用一個非常近的日期，確保 '1m' 不會被 RESTRICTION_SKIP
        date_str = (datetime.now(timezone.utc).date() - timedelta(days=1)).strftime("%Y-%m-%d")
        request_hash = hydrator._create_request_hash(ticker)
        successful_interval = hydrator.FALLBACK_INTERVALS[0] # 應該是 '1m'

        mock_data = pd.DataFrame({
            'Open': [100.0], 'High': [101.0], 'Low': [99.0], 'Close': [100.5], 'Volume': [10000],
        }, index=pd.to_datetime([f"{date_str} 09:30:00"], utc=True).rename("Datetime"))

        # 只有當請求的 interval 是 successful_interval 時才返回數據
        def history_side_effect(*args, **kwargs):
            if kwargs.get('interval') == successful_interval:
                # yfinance history returns 'Datetime' or 'Date' in index or column
                return mock_data.reset_index()
            return pd.DataFrame() # 其他 interval 返回空

        mock_yf_ticker.history.side_effect = history_side_effect
        mock_upsert_data = mocker.patch.object(db_manager, 'upsert_data')
        mock_update_cache = mocker.patch.object(db_manager, 'update_cache_index', wraps=db_manager.update_cache_index)

        hydrator.hydrate_day(ticker=ticker, date_str=date_str, force_refresh=False)

        mock_yf_ticker.history.assert_called_once_with(
            start=date_str,
            end=(datetime.strptime(date_str, "%Y-%m-%d").date() + timedelta(days=1)).strftime("%Y-%m-%d"),
            interval=successful_interval,
            auto_adjust=True, prepost=False, raise_errors=False
        )
        mock_upsert_data.assert_called_once()
        mock_update_cache.assert_called_once_with(
            request_hash=request_hash, date_str=date_str, status="SUCCESS",
            final_interval=successful_interval, message=mocker.ANY
        )
        cached_info_after = db_manager.check_request_status(request_hash, date_str)
        assert cached_info_after['status'] == "SUCCESS"
        assert cached_info_after['final_interval'] == successful_interval

    def test_hydrate_day_cache_miss_fallback_to_1d_success(self, test_db_manager_and_hydrator, mocker):
        db_manager, hydrator, mock_yf_ticker = test_db_manager_and_hydrator
        ticker = "CACHE_MISS_FALLBACK_1D"
        date_str = "2023-01-03" # 較遠日期，'1m' 會 RESTRICTION_SKIP
        request_hash = hydrator._create_request_hash(ticker)

        mock_data_1d = pd.DataFrame({
            'Open': [200.0], 'High': [202.0], 'Low': [199.0], 'Close': [201.0], 'Volume': [200000]
        }, index=pd.to_datetime([f"{date_str} 16:00:00"], utc=True).rename("Datetime"))

        def history_side_effect(*args, **kwargs):
            interval = kwargs.get('interval')
            # '1m' 由於日期 '2023-01-03' 會被 _fetch_data_for_day_and_interval 內部跳過 (RESTRICTION_SKIP)
            # 其他分鐘級 interval 返回空
            if interval == '1d':
                return mock_data_1d.reset_index()
            return pd.DataFrame()

        mock_yf_ticker.history.side_effect = history_side_effect
        mock_upsert_data = mocker.patch.object(db_manager, 'upsert_data')

        hydrator.hydrate_day(ticker=ticker, date_str=date_str, force_refresh=False)

        # 驗證 API 調用次數 (1m 被跳過, 2m, 5m... 到 1h 返回空, 1d 成功)
        # FALLBACK_INTERVALS = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d']
        # '1m' is skipped by RESTRICTION_SKIP.
        # So, it will try '2m', '5m', '15m', '30m', '60m', '90m', '1h' (7 calls, empty) + '1d' (1 call, success)
        assert mock_yf_ticker.history.call_count == (len(hydrator.FALLBACK_INTERVALS) -1) # -1 because 1m is skipped internally

        mock_upsert_data.assert_called_once()
        cached_info_after = db_manager.check_request_status(request_hash, date_str)
        assert cached_info_after['status'] == "SUCCESS"
        assert cached_info_after['final_interval'] == "1d"


    def test_hydrate_day_all_intervals_no_data(self, test_db_manager_and_hydrator, mocker):
        db_manager, hydrator, mock_yf_ticker = test_db_manager_and_hydrator
        ticker = "ALL_NO_DATA"
        date_str = "2023-01-04" # 假設是市場假日
        request_hash = hydrator._create_request_hash(ticker)

        mock_yf_ticker.history.return_value = pd.DataFrame() # 所有調用都返回空
        mock_upsert_data = mocker.patch.object(db_manager, 'upsert_data')
        mock_update_cache = mocker.patch.object(db_manager, 'update_cache_index', wraps=db_manager.update_cache_index)

        hydrator.hydrate_day(ticker=ticker, date_str=date_str, force_refresh=False)

        # '1m' 被 RESTRICTION_SKIP, 其他的都被調用
        assert mock_yf_ticker.history.call_count == (len(hydrator.FALLBACK_INTERVALS) -1)
        mock_upsert_data.assert_not_called()
        mock_update_cache.assert_called_once_with(
            request_hash=request_hash, date_str=date_str, status="NO_DATA", message=mocker.ANY
        )
        cached_info_after = db_manager.check_request_status(request_hash, date_str)
        assert cached_info_after['status'] == "NO_DATA"

    def test_hydrate_day_api_error_then_no_data(self, test_db_manager_and_hydrator, mocker):
        db_manager, hydrator, mock_yf_ticker = test_db_manager_and_hydrator
        ticker = "API_ERROR_NO_DATA"
        # 使用近期日期，使 '1m' 不會被 RESTRICTION_SKIP
        date_str = (datetime.now(timezone.utc).date() - timedelta(days=2)).strftime("%Y-%m-%d")
        request_hash = hydrator._create_request_hash(ticker)

        def history_side_effect(*args, **kwargs):
            interval = kwargs.get('interval')
            if interval == hydrator.FALLBACK_INTERVALS[0]: # 第一個 interval (e.g. '1m') 拋出錯誤
                raise Exception("Simulated API Network Error")
            return pd.DataFrame() # 其他 interval 返回空

        mock_yf_ticker.history.side_effect = history_side_effect
        mock_update_cache = mocker.patch.object(db_manager, 'update_cache_index', wraps=db_manager.update_cache_index)

        hydrator.hydrate_day(ticker=ticker, date_str=date_str, force_refresh=False)

        # 所有 FALLBACK_INTERVALS 都會被嘗試
        assert mock_yf_ticker.history.call_count == len(hydrator.FALLBACK_INTERVALS)

        cached_info_after = db_manager.check_request_status(request_hash, date_str)
        assert cached_info_after['status'] == "API_FAILURE"
        assert "Simulated API Network Error" in cached_info_after['message']
        assert "首個API錯誤訊息: Simulated API Network Error" in cached_info_after['message']

    def test_hydrate_day_force_refresh_overrides_cache(self, test_db_manager_and_hydrator, mocker):
        db_manager, hydrator, mock_yf_ticker = test_db_manager_and_hydrator
        ticker = "FORCE_REFRESH_TEST"
        date_str = (datetime.now(timezone.utc).date() - timedelta(days=3)).strftime("%Y-%m-%d")
        request_hash = hydrator._create_request_hash(ticker)

        # 1. 預先填入快取
        db_manager.update_cache_index(
            request_hash=request_hash, date_str=date_str, status="SUCCESS",
            final_interval="1d", message="Initial cache entry"
        )

        # 2. 準備新的 API 返回數據
        new_mock_data = pd.DataFrame({
            'Open': [300.0], 'High': [301.0], 'Low': [299.0], 'Close': [300.5], 'Volume': [30000],
        }, index=pd.to_datetime([f"{date_str} 09:30:00"], utc=True).rename("Datetime"))

        successful_interval = hydrator.FALLBACK_INTERVALS[0] # 假設刷新時 '1m' 就成功
        def history_side_effect_refresh(*args, **kwargs):
            if kwargs.get('interval') == successful_interval:
                return new_mock_data.reset_index()
            return pd.DataFrame()
        mock_yf_ticker.history.side_effect = history_side_effect_refresh

        mock_upsert_data = mocker.patch.object(db_manager, 'upsert_data')

        # 3. 執行 hydrate_day 並強制刷新
        hydrator.hydrate_day(ticker=ticker, date_str=date_str, force_refresh=True)

        # 4. 驗證 API 被調用 (即使快取存在)
        mock_yf_ticker.history.assert_called_once_with(
            start=date_str,
            end=(datetime.strptime(date_str, "%Y-%m-%d").date() + timedelta(days=1)).strftime("%Y-%m-%d"),
            interval=successful_interval,
            auto_adjust=True, prepost=False, raise_errors=False
        )
        # 5. 驗證數據被更新
        mock_upsert_data.assert_called_once()

        # 6. 驗證快取被更新
        cached_info_after = db_manager.check_request_status(request_hash, date_str)
        assert cached_info_after['status'] == "SUCCESS"
        assert cached_info_after['final_interval'] == successful_interval
        assert "Initial cache entry" not in cached_info_after['message'] # 訊息應被覆蓋
</tbody>
</table>
