# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch, MagicMock, call
import pandas as pd
from datetime import datetime, timedelta # Keep standard imports for test logic
import queue # Import the queue module

# Path adjustments
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from apps.daily_market_analyzer.yfinance_client import YFinanceClient, _convert_missing_dates_to_ranges
from apps.daily_market_analyzer.db_manager import DBManager

def create_sample_df(dates: list[str], ticker="TEST", interval="1d", data_prefix=100) -> pd.DataFrame:
    if not dates: return pd.DataFrame()
    dts = pd.to_datetime(dates, utc=True)
    data = {'datetime': dts, 'ticker': [ticker]*len(dts), 'interval': [interval]*len(dts),
            'open': [data_prefix+i for i in range(len(dts))], 'high': [data_prefix+i+1 for i in range(len(dts))],
            'low': [data_prefix+i-1 for i in range(len(dts))], 'close': [data_prefix+i+0.5 for i in range(len(dts))],
            'volume': [1000+i*100 for i in range(len(dts))]}
    return pd.DataFrame(data)

class TestYFinanceClient(unittest.TestCase):
    def setUp(self):
        self.mock_db_manager = MagicMock(spec=DBManager)
        # Add necessary attributes that are accessed by the real DBManager's methods if not fully mocked
        self.mock_db_manager.db_path = ":memory:" # Or a mock/temp path
        self.mock_db_manager.duckdb_config = {}

        self.mock_data_queue = MagicMock(spec=queue.Queue) # Use spec=queue.Queue
        self.client = YFinanceClient(db_manager=self.mock_db_manager, data_queue=self.mock_data_queue, cache_dir="temp_test_cache")
        self.ticker = "TEST_TICKER"
        self.table_name = "test_ohlcv"

        # Default mock for methods that might interfere with control flow if not specifically set in a test
        # For most hydrate_data_range tests, we want to control the flow into fetching.
        self.mock_db_manager.check_data_exists_for_date_and_ticker.return_value = False
        self.mock_db_manager.check_no_data_record_exists.return_value = False # Ensure this doesn't skip fetches by default

    def test_convert_missing_dates_to_ranges_empty(self):
        self.assertEqual(_convert_missing_dates_to_ranges([]), [])
    def test_convert_missing_dates_to_ranges_single_date(self):
        self.assertEqual(_convert_missing_dates_to_ranges(["2023-01-01"]), [("2023-01-01", "2023-01-01")])
    def test_convert_missing_dates_to_ranges_continuous(self):
        self.assertEqual(_convert_missing_dates_to_ranges(["2023-01-01", "2023-01-02", "2023-01-03"]), [("2023-01-01", "2023-01-03")])
    def test_convert_missing_dates_to_ranges_scattered(self):
        self.assertEqual(_convert_missing_dates_to_ranges(["2023-01-01", "2023-01-03", "2023-01-04", "2023-01-06"]),
                         [("2023-01-01", "2023-01-01"), ("2023-01-03", "2023-01-04"), ("2023-01-06", "2023-01-06")])
    def test_convert_missing_dates_to_ranges_with_duplicates_and_unsorted(self):
        self.assertEqual(_convert_missing_dates_to_ranges(["2023-01-03", "2023-01-01", "2023-01-03", "2023-01-02"]),
                         [("2023-01-01", "2023-01-03")])

    @patch.object(YFinanceClient, 'check_cache') # Mock YFinanceClient.check_cache
    @patch('apps.daily_market_analyzer.yfinance_client.YFinanceClient.fetch_single_chunk')
    @patch('apps.daily_market_analyzer.yfinance_client.datetime') # Added datetime mock for consistency
    def test_hydrate_data_range_full_cache_hit(self, mock_dt_module, mock_fetch_single_chunk, mock_yf_check_cache):
        from datetime import datetime as real_datetime, timedelta as real_timedelta, date as real_date
        # Mock datetime module attributes if necessary for this test's path
        mock_dt_module.now.return_value = real_datetime(2023, 3, 1) # Example, adjust if hydrate_data_range uses it
        mock_dt_module.strptime = real_datetime.strptime
        mock_dt_module.timedelta = real_timedelta
        mock_dt_module.date = real_date
        mock_dt_module.datetime = real_datetime

        start_date_str = "2023-01-01"; end_date_str = "2023-01-02"
        # For historical date, HISTORICAL_FALLBACK is used.
        hit_interval = self.client.HISTORICAL_FALLBACK[0] if self.client.HISTORICAL_FALLBACK else self.client.FALLBACK_INTERVALS[0]
        sample_cached_data = create_sample_df([start_date_str, end_date_str], interval=hit_interval)

        # Configure the mock for YFinanceClient.check_cache
        mock_yf_check_cache.return_value = (sample_cached_data.copy(), []) # Fully cached, no missing dates

        result_df, exec_log = self.client.hydrate_data_range(self.ticker, start_date_str, end_date_str, db_table_name=self.table_name)

        mock_yf_check_cache.assert_called_once_with(
            ticker=self.ticker, start_date_str=start_date_str, end_date_str=end_date_str,
            interval=hit_interval, table_name=self.table_name)
        mock_fetch_single_chunk.assert_not_called()
        self.mock_data_queue.put.assert_not_called()
        self.assertIsNone(result_df, "Result DataFrame should be None on a full cache hit that doesn't require fetching.")
        # If check_cache returns data and no missing dates for that interval, status should be 'cached_current_interval'
        # because the 'cached_full_range_verified_after_filter' is only set if the status was 'pending' before the final check.
        self.assertEqual(exec_log[start_date_str][self.ticker]['status'], "cached_current_interval")
        self.assertEqual(exec_log[end_date_str][self.ticker]['status'], "cached_current_interval")
        self.assertEqual(exec_log[start_date_str][self.ticker]['interval'], hit_interval)

    @patch.object(YFinanceClient, 'check_cache')
    @patch('apps.daily_market_analyzer.yfinance_client.YFinanceClient.fetch_single_chunk')
    @patch('apps.daily_market_analyzer.yfinance_client.datetime')
    def test_hydrate_data_range_full_miss_fetch_success(self, mock_dt_module, mock_fetch_single_chunk, mock_yf_check_cache):
        from datetime import datetime as real_datetime, timedelta as real_timedelta, date as real_date
        mock_dt_module.now.return_value = real_datetime(2023, 3, 1) # Ensures HISTORICAL_FALLBACK is used
        mock_dt_module.strptime = real_datetime.strptime
        mock_dt_module.timedelta = real_timedelta
        mock_dt_module.date = real_date
        mock_dt_module.datetime = real_datetime

        start_date_str = "2023-01-01"; end_date_str = "2023-01-02"

        # This test simulates:
        # 1. First historical fallback interval (e.g., '1d'): cache miss, API fetch fails (returns None).
        # 2. Second historical fallback interval (e.g., '1wk'): cache miss, API fetch succeeds.

        mock_yf_check_cache.reset_mock() # Ensure clean state for this mock
        mock_fetch_single_chunk.reset_mock()
        self.mock_data_queue.reset_mock()

        if len(self.client.HISTORICAL_FALLBACK) < 2:
            self.fail("HISTORICAL_FALLBACK needs at least 2 intervals for this test logic.")

        interval_fail_api = self.client.HISTORICAL_FALLBACK[0] # e.g., '1d'
        interval_succeed_api = self.client.HISTORICAL_FALLBACK[1] # e.g., '1wk'

        # YFClient.check_cache will be called for interval_fail_api, then for interval_succeed_api.
        # Both should return a full miss.
        mock_yf_check_cache.return_value = (pd.DataFrame(), [start_date_str, end_date_str])

        # mock_fetch_single_chunk side effect: fail for interval_fail_api, succeed for interval_succeed_api
        api_data_for_succeed_interval = create_sample_df([start_date_str, end_date_str], interval=interval_succeed_api, data_prefix=200)
        mock_fetch_single_chunk.side_effect = [
            None,  # API call for interval_fail_api returns None
            api_data_for_succeed_interval.copy()  # API call for interval_succeed_api returns data
        ]

        result_df, exec_log = self.client.hydrate_data_range(self.ticker, start_date_str, end_date_str, db_table_name=self.table_name)

        # Assert YFinanceClient.check_cache calls
        expected_check_cache_calls = [
            call(ticker=self.ticker, start_date_str=start_date_str, end_date_str=end_date_str, interval=interval_fail_api, table_name=self.table_name),
            call(ticker=self.ticker, start_date_str=start_date_str, end_date_str=end_date_str, interval=interval_succeed_api, table_name=self.table_name)
        ]
        mock_yf_check_cache.assert_has_calls(expected_check_cache_calls, any_order=False)
        self.assertEqual(mock_yf_check_cache.call_count, 2)

        # Assert mock_fetch_single_chunk calls
        expected_yfinance_end = (real_datetime.strptime(end_date_str, "%Y-%m-%d") + real_timedelta(days=1)).strftime("%Y-%m-%d")
        expected_fetch_calls = [
            call(self.ticker, start_date_str, expected_yfinance_end, interval_fail_api),
            call(self.ticker, start_date_str, expected_yfinance_end, interval_succeed_api)
        ]
        mock_fetch_single_chunk.assert_has_calls(expected_fetch_calls, any_order=False)
        self.assertEqual(mock_fetch_single_chunk.call_count, 2)

        self.mock_data_queue.put.assert_called_once()
        queued_data = self.mock_data_queue.put.call_args[0][0]
        pd.testing.assert_frame_equal(queued_data['data'], api_data_for_succeed_interval, check_dtype=False)
        self.assertEqual(queued_data['ticker'], self.ticker)
        self.assertEqual(queued_data['interval'], interval_succeed_api)

        self.assertIsNone(result_df, "hydrate_data_range should return None for DataFrame when processing is complete for an interval.")

        self.assertEqual(exec_log[start_date_str][self.ticker]['status'], "success_producer")
        self.assertEqual(exec_log[start_date_str][self.ticker]['interval'], interval_succeed_api)
        self.assertIn(str(exec_log[start_date_str][self.ticker]['count']), [str(len(api_data_for_succeed_interval[api_data_for_succeed_interval['datetime'].dt.strftime('%Y-%m-%d') == start_date_str])), '>0'])
        self.assertIn(str(exec_log[end_date_str][self.ticker]['count']), [str(len(api_data_for_succeed_interval[api_data_for_succeed_interval['datetime'].dt.strftime('%Y-%m-%d') == end_date_str])), '>0'])
        self.assertTrue(len(api_data_for_succeed_interval[api_data_for_succeed_interval['datetime'].dt.strftime('%Y-%m-%d') == start_date_str]) > 0)

    @patch.object(YFinanceClient, 'check_cache') # Mock YFinanceClient.check_cache
    @patch('apps.daily_market_analyzer.yfinance_client.YFinanceClient.fetch_single_chunk')
    @patch('apps.daily_market_analyzer.yfinance_client.datetime')
    def test_hydrate_data_range_partial_hit_fetch_success(self, mock_dt_module, mock_fetch_single_chunk, mock_yf_check_cache): # Corrected name
        from datetime import datetime as real_datetime, timedelta as real_timedelta, date as real_date
        mock_dt_module.now.return_value = real_datetime(2023, 3, 1)
        mock_dt_module.strptime = real_datetime.strptime
        mock_dt_module.timedelta = real_timedelta
        mock_dt_module.date = real_date
        mock_dt_module.datetime = real_datetime

        start_date_str="2023-01-01"; mid_date_str="2023-01-02"; end_date_str="2023-01-03"
        # For historical date, HISTORICAL_FALLBACK is used.
        if len(self.client.HISTORICAL_FALLBACK) < 2:
            self.fail("HISTORICAL_FALLBACK must have at least 2 intervals for this test.")
        first_historical_interval = self.client.HISTORICAL_FALLBACK[0]
        second_historical_interval = self.client.HISTORICAL_FALLBACK[1] # This will be our fetch_interval for the test logic

        # Data cached for start_date_str with the first_historical_interval
        cached_data_first_interval = create_sample_df([start_date_str], interval=first_historical_interval, data_prefix=100)
        # Data cached for start_date_str with the second_historical_interval (which is also our target fetch_interval)
        cached_data_second_interval_for_start_date = create_sample_df([start_date_str], interval=second_historical_interval, data_prefix=150)

        # Configure YFinanceClient.check_cache mock side_effect
        # 1. Call for first_historical_interval: returns cached_data_first_interval for start_date_str, missing mid_date_str, end_date_str
        # 2. Call for second_historical_interval: returns cached_data_second_interval_for_start_date for start_date_str, missing mid_date_str, end_date_str
        mock_yf_check_cache.side_effect = [
             (cached_data_first_interval.copy(), [mid_date_str, end_date_str]),
             (cached_data_second_interval_for_start_date.copy(), [mid_date_str, end_date_str])]

        api_missing_data = create_sample_df([mid_date_str, end_date_str], interval=second_historical_interval, data_prefix=200)
        mock_fetch_single_chunk.return_value = api_missing_data.copy()
        result_df, exec_log = self.client.hydrate_data_range(self.ticker, start_date_str, end_date_str, db_table_name=self.table_name)

        # Only the first interval (first_historical_interval) should be checked via YFClient.check_cache
        # because data is found/fetched for it, and then the function returns.
        mock_yf_check_cache.assert_called_once_with(
            ticker=self.ticker,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
            interval=first_historical_interval, # This is the interval that was set up in side_effect[0]
            table_name=self.table_name
        )
        # The fetch_single_chunk should be called for the first_historical_interval's missing parts.
        expected_yfinance_end = (real_datetime.strptime(end_date_str, "%Y-%m-%d") + real_timedelta(days=1)).strftime("%Y-%m-%d")
        mock_fetch_single_chunk.assert_called_once_with(self.ticker, mid_date_str, expected_yfinance_end, first_historical_interval)

        self.mock_data_queue.put.assert_called_once()
        queued_data = self.mock_data_queue.put.call_args[0][0]
        # Data put to queue should only be the newly fetched data (api_missing_data)
        pd.testing.assert_frame_equal(queued_data['data'], api_missing_data, check_dtype=False)
        self.assertEqual(queued_data['ticker'], self.ticker)
        self.assertEqual(queued_data['interval'], first_historical_interval) # Should be fetched with the interval that was being processed

        self.assertIsNone(result_df, "hydrate_data_range should return None for DataFrame when processing is complete.")

        # Log for the cached part (start_date_str)
        # The first call to YFClient.check_cache (for first_historical_interval) returned cached_data_first_interval for start_date_str.
        self.assertEqual(exec_log[start_date_str][self.ticker]['status'], "cached_current_interval")
        self.assertEqual(exec_log[start_date_str][self.ticker]['interval'], first_historical_interval)
        self.assertEqual(exec_log[start_date_str][self.ticker]['count'], len(cached_data_first_interval))

        # Log for the fetched part (mid_date_str, end_date_str) for the first_historical_interval
        self.assertEqual(exec_log[mid_date_str][self.ticker]['status'], "success_producer")
        self.assertEqual(exec_log[mid_date_str][self.ticker]['interval'], first_historical_interval)
        self.assertIn(str(exec_log[mid_date_str][self.ticker]['count']), [str(len(api_missing_data[api_missing_data['datetime'].dt.strftime('%Y-%m-%d') == mid_date_str])), '>0'])

        self.assertEqual(exec_log[end_date_str][self.ticker]['status'], "success_producer")
        self.assertEqual(exec_log[end_date_str][self.ticker]['interval'], first_historical_interval)
        self.assertIn(str(exec_log[end_date_str][self.ticker]['count']), [str(len(api_missing_data[api_missing_data['datetime'].dt.strftime('%Y-%m-%d') == end_date_str])), '>0'])

    @patch.object(YFinanceClient, 'check_cache')
    @patch('apps.daily_market_analyzer.yfinance_client.YFinanceClient.fetch_single_chunk')
    @patch('apps.daily_market_analyzer.yfinance_client.datetime')
    def test_hydrate_data_range_partial_miss_api_fails_fallback_succeeds(self, mock_dt_module, mock_fetch_single_chunk, mock_yf_check_cache):
        from datetime import datetime as real_datetime, timedelta as real_timedelta, date as real_date
        mock_dt_module.now.return_value = real_datetime(2023, 3, 1) # This makes start_date historical
        mock_dt_module.strptime = real_datetime.strptime
        mock_dt_module.timedelta = real_timedelta
        mock_dt_module.date = real_date
        mock_dt_module.datetime = real_datetime

        start_date_str = "2023-01-01"; end_date_str = "2023-01-01" # Single day historical

        # Configure YFinanceClient.check_cache to simulate misses for all relevant intervals
        # For historical data, HISTORICAL_FALLBACK will be used.
        mock_yf_check_cache.return_value = (pd.DataFrame(), [start_date_str])

        # Determine the intervals that will actually be tried (HISTORICAL_FALLBACK)
        hist_fb_intervals = self.client.HISTORICAL_FALLBACK
        if not hist_fb_intervals: self.fail("HISTORICAL_FALLBACK is empty")

        # The last interval in HISTORICAL_FALLBACK should succeed.
        succeeding_interval = hist_fb_intervals[-1]
        api_data_succeeding_interval = create_sample_df([start_date_str], interval=succeeding_interval, data_prefix=300)

        # Set up side_effect for fetch_single_chunk: None for all but the last hist_fb_intervals
        side_effects = [None] * (len(hist_fb_intervals) - 1) + [api_data_succeeding_interval.copy()]
        mock_fetch_single_chunk.side_effect = side_effects

        result_df, exec_log = self.client.hydrate_data_range(self.ticker, start_date_str, end_date_str, db_table_name=self.table_name)

        # Assertions for check_cache calls
        self.assertEqual(mock_yf_check_cache.call_count, len(hist_fb_intervals))
        for interval_to_check in hist_fb_intervals:
            mock_yf_check_cache.assert_any_call(
                ticker=self.ticker,
                start_date_str=start_date_str,
                end_date_str=end_date_str,
                interval=interval_to_check,
                table_name=self.table_name
            )

        # Assertions for fetch_single_chunk calls
        yfinance_exclusive_end = (real_datetime.strptime(end_date_str, "%Y-%m-%d") + real_timedelta(days=1)).strftime("%Y-%m-%d")
        expected_fetch_calls = [
            call(self.ticker, start_date_str, yfinance_exclusive_end, interval_val)
            for interval_val in hist_fb_intervals
        ]
        mock_fetch_single_chunk.assert_has_calls(expected_fetch_calls, any_order=False) # Calls should be in order of hist_fb_intervals
        self.assertEqual(mock_fetch_single_chunk.call_count, len(hist_fb_intervals))

        # Assertions for data queue
        self.mock_data_queue.put.assert_called_once()
        queued_data = self.mock_data_queue.put.call_args[0][0]
        pd.testing.assert_frame_equal(queued_data['data'], api_data_succeeding_interval, check_dtype=False)
        self.assertEqual(queued_data['ticker'], self.ticker)
        self.assertEqual(queued_data['interval'], succeeding_interval)

        # Assertion for result_df (should be None)
        self.assertIsNone(result_df, "hydrate_data_range should return None for DataFrame when processing is complete.")

        # Log for the successfully fetched data
        log_entry = exec_log[start_date_str][self.ticker]
        self.assertEqual(log_entry['status'], "success_producer")
        self.assertEqual(log_entry['interval'], succeeding_interval)
        self.assertIn(str(log_entry['count']), [str(len(api_data_succeeding_interval)), '>0'])

    # --- Tests for fetch_single_chunk retry logic ---
    @patch('apps.daily_market_analyzer.yfinance_client.yf.Ticker')
    @patch('apps.daily_market_analyzer.yfinance_client.time.sleep')
    def test_fetch_single_chunk_success_on_first_try(self, mock_sleep, mock_yf_ticker):
        mock_stock_instance = MagicMock()
        mock_history_data = create_sample_df(["2023-01-01"], ticker=self.ticker, interval="1d")
        mock_stock_instance.history.return_value = mock_history_data
        mock_yf_ticker.return_value = mock_stock_instance

        result_df = self.client.fetch_single_chunk(self.ticker, "2023-01-01", "2023-01-02", "1d")

        mock_yf_ticker.assert_called_once_with(self.ticker)
        mock_stock_instance.history.assert_called_once_with(start="2023-01-01", end="2023-01-02", interval="1d", auto_adjust=True, prepost=False)
        mock_sleep.assert_not_called()
        self.assertIsNotNone(result_df)
        # mock_history_data from create_sample_df is already in the expected output format of fetch_single_chunk
        pd.testing.assert_frame_equal(result_df, mock_history_data, check_dtype=False, rtol=1e-5)


    @patch('apps.daily_market_analyzer.yfinance_client.yf.Ticker')
    @patch('apps.daily_market_analyzer.yfinance_client.time.sleep')
    def test_fetch_single_chunk_retry_on_exception_then_success(self, mock_sleep, mock_yf_ticker):
        mock_stock_instance = MagicMock()
        mock_history_data = create_sample_df(["2023-01-01"], ticker=self.ticker, interval="1d")
        # Simulate failure on first call, success on second
        mock_stock_instance.history.side_effect = [
            Exception("API Error"),
            mock_history_data
        ]
        mock_yf_ticker.return_value = mock_stock_instance

        result_df = self.client.fetch_single_chunk(self.ticker, "2023-01-01", "2023-01-02", "1d")

        self.assertEqual(mock_stock_instance.history.call_count, 2)
        mock_sleep.assert_called_once() # Corrected: sleep IS called when API call raises an Exception
        self.assertIsNotNone(result_df)
        pd.testing.assert_frame_equal(result_df, mock_history_data, check_dtype=False, rtol=1e-5)

    @patch('apps.daily_market_analyzer.yfinance_client.yf.Ticker')
    @patch('apps.daily_market_analyzer.yfinance_client.time.sleep')
    def test_fetch_single_chunk_retry_on_none_then_success(self, mock_sleep, mock_yf_ticker):
        mock_stock_instance = MagicMock()
        mock_history_data = create_sample_df(["2023-01-01"], ticker=self.ticker, interval="1d")
        mock_stock_instance.history.side_effect = [
            None,  # First call returns None
            mock_history_data # Second call returns data
        ]
        mock_yf_ticker.return_value = mock_stock_instance

        result_df = self.client.fetch_single_chunk(self.ticker, "2023-01-01", "2023-01-02", "1d")
        self.assertEqual(mock_stock_instance.history.call_count, 2)
        mock_sleep.assert_not_called() # Corrected: sleep is not called when API returns None directly
        self.assertIsNotNone(result_df)
        pd.testing.assert_frame_equal(result_df, mock_history_data, check_dtype=False, rtol=1e-5)


    @patch('apps.daily_market_analyzer.yfinance_client.yf.Ticker')
    @patch('apps.daily_market_analyzer.yfinance_client.time.sleep')
    def test_fetch_single_chunk_max_retries_on_exception(self, mock_sleep, mock_yf_ticker):
        mock_stock_instance = MagicMock()
        mock_stock_instance.history.side_effect = Exception("Persistent API Error")
        mock_yf_ticker.return_value = mock_stock_instance

        result_df = self.client.fetch_single_chunk(self.ticker, "2023-01-01", "2023-01-02", "1d")

        self.assertEqual(mock_stock_instance.history.call_count, 3) # max_retries = 3
        self.assertEqual(mock_sleep.call_count, 2) # Sleeps after 1st and 2nd failure
        self.assertIsNone(result_df)


    @patch('apps.daily_market_analyzer.yfinance_client.yf.Ticker')
    @patch('apps.daily_market_analyzer.yfinance_client.time.sleep')
    def test_fetch_single_chunk_returns_empty_df_no_retry(self, mock_sleep, mock_yf_ticker):
        mock_stock_instance = MagicMock()
        empty_df = pd.DataFrame(columns=['datetime', 'ticker', 'interval', 'open', 'high', 'low', 'close', 'volume'])
        # Ensure correct dtypes for empty df to match expected structure after processing
        empty_df['datetime'] = pd.to_datetime(empty_df['datetime'])
        empty_df['volume'] = empty_df['volume'].astype('int64')

        mock_stock_instance.history.return_value = pd.DataFrame() # yfinance returns empty df
        mock_yf_ticker.return_value = mock_stock_instance

        # Expected behavior: fetch_single_chunk processes the empty yf result,
        # which then results in its own empty_df (with standardized columns) or None.
        # The retry logic should break if `data.empty` is true.
        result_df = self.client.fetch_single_chunk(self.ticker, "2023-01-01", "2023-01-02", "1d")

        mock_stock_instance.history.assert_called_once() # Should not retry if yf returns empty df
        mock_sleep.assert_not_called()
        # The method should record "no data" and return None after processing an empty df from yfinance
        self.assertIsNone(result_df)
        self.mock_db_manager.record_no_data_range.assert_called_once_with(
            ticker=self.ticker, interval="1d", start_date="2023-01-01", end_date="2023-01-01"
        )

    @patch('apps.daily_market_analyzer.yfinance_client.yf.Ticker')
    @patch('apps.daily_market_analyzer.yfinance_client.time.sleep')
    def test_fetch_single_chunk_max_retries_on_none(self, mock_sleep, mock_yf_ticker):
        mock_stock_instance = MagicMock()
        mock_stock_instance.history.return_value = None # Consistently returns None
        mock_yf_ticker.return_value = mock_stock_instance

        self.mock_db_manager.reset_mock() # Reset mock before the call

        result_df = self.client.fetch_single_chunk(self.ticker, "2023-01-01", "2023-01-02", "1d")

        # max_retries is 3 in the implementation
        self.assertEqual(mock_stock_instance.history.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 0) # Corrected: sleep is not called when API returns None directly
        self.assertIsNone(result_df)
        # Check if record_no_data_range was called, as consistently None might mean no data
        # The current logic in fetch_single_chunk calls record_no_data_range if data is None or empty *after* the retry loop.
        self.mock_db_manager.record_no_data_range.assert_called_once_with(
            ticker=self.ticker, interval="1d", start_date="2023-01-01", end_date="2023-01-01"
        )

    @patch.object(YFinanceClient, 'check_cache') # Mock YFinanceClient.check_cache
    @patch('apps.daily_market_analyzer.yfinance_client.YFinanceClient.fetch_single_chunk')
    @patch('apps.daily_market_analyzer.yfinance_client.datetime')
    def test_hydrate_data_range_api_fails_all_intervals(self, mock_dt_module, mock_fetch_single_chunk, mock_yf_check_cache): # Added mock_yf_check_cache
        # Setup similar to other tests, ensuring datetime is properly mocked if needed by the client
        from datetime import datetime as real_datetime, timedelta as real_timedelta, date as real_date
        # Ensure specific datetime components are mocked correctly
        mock_dt_module.now.return_value = real_datetime(2024, 3, 15) # A recent date to use FALLBACK_INTERVALS
        mock_dt_module.strptime = real_datetime.strptime
        mock_dt_module.timedelta = real_timedelta
        mock_dt_module.date = real_date
        mock_dt_module.datetime = real_datetime # Critically, ensure the datetime class itself is the real one for pd.to_datetime

        start_date_str = "2024-03-01" # Using a date that would trigger FALLBACK_INTERVALS
        end_date_str = "2024-03-01"

        # Configure YFinanceClient.check_cache mock to simulate a full miss for all calls
        mock_yf_check_cache.return_value = (pd.DataFrame(), [start_date_str])

        # Simulate API (fetch_single_chunk) always returning None (failure or no data)
        mock_fetch_single_chunk.return_value = None
        # Simulate no existing "no_data_record"
        self.mock_db_manager.check_no_data_record_exists.return_value = False

        # For this test, we'll use a YFinanceClient instance where data_queue is also a mock,
        # as the original bug is about logging before data might even be produced for the queue.
        mock_data_queue = MagicMock(spec=queue.Queue) # Corrected spec
        client_for_test = YFinanceClient(db_manager=self.mock_db_manager, data_queue=mock_data_queue, cache_dir="temp_test_cache_fail_all")

        # Call the method under test
        _ , exec_log = client_for_test.hydrate_data_range(
            self.ticker,
            start_date_str,
            end_date_str,
            db_table_name=self.table_name,
            force_refresh=False
        )

        # Assertions
        num_expected_calls = len(client_for_test.FALLBACK_INTERVALS)
        self.assertEqual(mock_fetch_single_chunk.call_count, num_expected_calls,
                         f"Expected fetch_single_chunk to be called {num_expected_calls} times, but was {mock_fetch_single_chunk.call_count}")

        self.assertIn(start_date_str, exec_log, "Execution log should contain the start date.")
        self.assertIn(self.ticker, exec_log[start_date_str], "Execution log for the date should contain the ticker.")

        log_entry = exec_log[start_date_str][self.ticker]
        self.assertEqual(log_entry['status'], 'failed_all_intervals',
                         f"Log entry status was '{log_entry['status']}', expected 'failed_all_intervals'. Message: {log_entry.get('message')}")
        self.assertIsNone(log_entry['interval'], "Interval should be None after all failures.")
        self.assertEqual(log_entry['count'], 0, "Count should be 0 after all failures.")
        # Check if the message reflects the failure for the specific date
        self.assertIn(f"All intervals failed for {start_date_str}", log_entry['message'],
                      f"Log message '{log_entry['message']}' should indicate that all intervals failed for {start_date_str}.")

        # The message should contain the failure reason for the *last* attempted interval before the "All intervals failed" part.
        last_interval_tried = client_for_test.FALLBACK_INTERVALS[-1]
        self.assertIn(f"Interval {last_interval_tried} failed", log_entry['message'],
                      f"Log message should mention failure of the last interval {last_interval_tried}. Message: {log_entry['message']}")
        # And it should also contain the "api_chunk_no_data" part for that last interval
        self.assertIn(f"API fetch for chunk covering {start_date_str} with {last_interval_tried} returned no data or failed.", log_entry['message'],
                      f"Log message should mention API chunk failure for {last_interval_tried}. Message: {log_entry['message']}")

        self.mock_db_manager.upsert_data.assert_not_called()
        # In this specific test (test_hydrate_data_range_api_fails_all_intervals),
        # client_for_test uses a separate mock_data_queue.
        # Accessing client_for_test.data_queue.put might be more direct if it's not the same as self.mock_data_queue
        client_for_test.data_queue.put.assert_not_called()

        self.assertEqual(self.mock_db_manager.check_no_data_record_exists.call_count, num_expected_calls,
                         "check_no_data_record_exists should be called for each interval.")

        # This assertion also needs to be specific to the client_for_test's db_manager if it were different,
        # but since it's self.mock_db_manager, this is fine.
        # However, the actual calls to check_cache are made by the YFinanceClient instance itself,
        # so we should be asserting calls on a mock of YFinanceClient.check_cache if we go that route.
        # For now, this check relies on YFinanceClient.check_cache calling the db_manager's methods as expected.
        # The previous failures indicated that YFinanceClient.check_cache was not being called as expected.
        # This will be addressed in the next step by mocking YFinanceClient.check_cache itself.
        # For this commit, we expect this to still fail until check_cache mocking is corrected.
        # self.assertEqual(self.mock_db_manager.check_cache.call_count, num_expected_calls, # This will be changed later
        #                  "check_cache should be called for each interval.")
        # Corrected assertion:
        self.assertEqual(mock_yf_check_cache.call_count, num_expected_calls,
                         "YFinanceClient.check_cache should be called for each interval.")

if __name__ == '__main__':
    unittest.main()
