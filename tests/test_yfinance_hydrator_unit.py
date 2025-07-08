# -*- coding: utf-8 -*-
"""
YFinanceHydrator 單元測試
===========================
此檔案包含對 YFinanceHydrator 中輔助函數純邏輯的單元測試。
主要測試目標：
- _split_date_range_into_chunks
- _convert_missing_dates_to_ranges
- _get_chunk_size_for_interval
- _create_request_hash
- _compare_intervals
"""
import pytest
from datetime import date, timedelta
import hashlib # 為了 _create_request_hash 的預期結果

from apps.yfinance_hydrator.hydrator import YFinanceHydrator

# 偽造一個 DBManager mock 類，僅為了能實例化 YFinanceHydrator
class MockDBManager:
    def __init__(self, db_path=None, target_ohlcv_table_name=None):
        self.ohlcv_table_name = target_ohlcv_table_name or "mock_ohlcv_table"
        # print(f"MockDBManager initialized with table: {self.ohlcv_table_name}") # 在測試中避免 print

    def check_request_status(self, request_hash, date_str):
        return None

    def update_cache_index(self, request_hash, date_str, status, final_interval=None, message=None):
        pass

@pytest.fixture
def hydrator_for_unit_tests():
    """提供一個 YFinanceHydrator 實例用於單元測試，使用 MockDBManager。"""
    mock_db_manager = MockDBManager()
    return YFinanceHydrator(db_manager=mock_db_manager)

class TestYFinanceHydratorUnit:
    """
    YFinanceHydrator 輔助函數的單元測試集合。
    """

    # --- 測試 _get_chunk_size_for_interval ---
    @pytest.mark.parametrize("interval, expected_days", [
        ('1m', 7),
        ('2m', 60), ('5m', 60), ('15m', 60), ('30m', 60),
        ('60m', 730), ('90m', 730), ('1h', 730),
        ('1d', 365 * 2), ('5d', 365 * 2), ('1wk', 365 * 2),
        ('1mo', 365 * 10), ('3mo', 365 * 10),
        ('invalid_interval', 30),
        ('2h', 30), # 假設未明確列出的，但可被 _compare_intervals 解析的，也可能走到預設
    ])
    def test_get_chunk_size_for_interval(self, hydrator_for_unit_tests, interval, expected_days):
        """測試 _get_chunk_size_for_interval 方法。"""
        assert hydrator_for_unit_tests._get_chunk_size_for_interval(interval) == expected_days

    # --- 測試 _split_date_range_into_chunks ---
    @pytest.mark.parametrize("start_date_str, end_date_str, chunk_size_days, expected_chunks_count, expected_first_chunk, expected_last_chunk_end_exclusive", [
        ("2023-01-01", "2023-01-10", 3, 4, ("2023-01-01", "2023-01-04"), "2023-01-11"),
        ("2023-01-01", "2023-01-03", 3, 1, ("2023-01-01", "2023-01-04"), "2023-01-04"),
        ("2023-01-01", "2023-01-02", 3, 1, ("2023-01-01", "2023-01-03"), "2023-01-03"),
        ("2023-01-01", "2023-01-01", 3, 1, ("2023-01-01", "2023-01-02"), "2023-01-02"),
        ("2023-01-01", "2023-01-03", 1, 3, ("2023-01-01", "2023-01-02"), "2023-01-04"),
        ("2023-01-30", "2023-02-02", 2, 2, ("2023-01-30", "2023-02-01"), "2023-02-03"),
    ])
    def test_split_date_range_into_chunks_valid(self, hydrator_for_unit_tests, start_date_str, end_date_str, chunk_size_days, expected_chunks_count, expected_first_chunk, expected_last_chunk_end_exclusive):
        chunks = hydrator_for_unit_tests._split_date_range_into_chunks(start_date_str, end_date_str, chunk_size_days)
        assert len(chunks) == expected_chunks_count
        if expected_chunks_count > 0:
            assert chunks[0] == expected_first_chunk
            assert chunks[-1][1] == expected_last_chunk_end_exclusive
            for chunk_start, chunk_end in chunks:
                # 驗證 yfinance_exclusive_end_date (chunk_end) 確實比 chunk_start 晚
                # 並且 chunk_start 和 chunk_end 都是有效的 YYYY-MM-DD 格式 (由strptime隱式檢查)
                assert date.fromisoformat(chunk_start) < date.fromisoformat(chunk_end)


    @pytest.mark.parametrize("start_date_str, end_date_str, chunk_size_days, expected_result", [
        ("2023/01/01", "2023-01-10", 3, []),
        ("2023-01-01", "2023/01/10", 3, []),
        ("2023-01-01", "2023-01-10", 0, []),
        ("2023-01-01", "2023-01-10", -1, []),
        ("2023-01-10", "2023-01-01", 3, []),
    ])
    def test_split_date_range_into_chunks_invalid(self, hydrator_for_unit_tests, start_date_str, end_date_str, chunk_size_days, expected_result):
        chunks = hydrator_for_unit_tests._split_date_range_into_chunks(start_date_str, end_date_str, chunk_size_days)
        assert chunks == expected_result

    # --- 測試 _convert_missing_dates_to_ranges ---
    @pytest.mark.parametrize("missing_dates_list, expected_ranges", [
        ([], []),
        ([date(2023, 1, 1)], [(date(2023, 1, 1), date(2023, 1, 1))]),
        ([date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)], [(date(2023, 1, 1), date(2023, 1, 3))]),
        (
            [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 4), date(2023, 1, 5), date(2023, 1, 6)],
            [(date(2023, 1, 1), date(2023, 1, 2)), (date(2023, 1, 4), date(2023, 1, 6))]
        ),
        ([date(2023, 1, 1), date(2023, 1, 3), date(2023, 1, 5)],
            [(date(2023, 1, 1), date(2023, 1, 1)), (date(2023, 1, 3), date(2023, 1, 3)), (date(2023, 1, 5), date(2023, 1, 5))]
        ),
    ])
    def test_convert_missing_dates_to_ranges(self, hydrator_for_unit_tests, missing_dates_list, expected_ranges):
        ranges = hydrator_for_unit_tests._convert_missing_dates_to_ranges(missing_dates_list)
        assert ranges == expected_ranges

    # --- 測試 _create_request_hash ---
    @pytest.mark.parametrize("ticker, expected_hash_value", [
        ("AAPL", hashlib.md5("AAPL".encode()).hexdigest()),
        ("MSFT", hashlib.md5("MSFT".encode()).hexdigest()),
        ("中華電信", hashlib.md5("中華電信".encode()).hexdigest()),
    ])
    def test_create_request_hash(self, hydrator_for_unit_tests, ticker, expected_hash_value):
        """測試 _create_request_hash 方法。"""
        actual_hash = hydrator_for_unit_tests._create_request_hash(ticker)
        assert actual_hash == expected_hash_value
        assert len(actual_hash) == 32

    # --- 測試 _compare_intervals ---
    @pytest.mark.parametrize("interval1, interval2, expected_comparison_result", [
        ("1m", "5m", 1),
        ("5m", "1m", -1),
        ("1h", "60m", 0),
        ("1d", "24h", 0), # 假設 '24h' 也被 to_minutes 正確處理為一天
        ("1d", "1h", -1),
        ("1m", "1d", 1),
        ("5m", "5m", 0),
        ("15m", "1h", 1),
        ("90m", "1h", -1), # 90 min vs 60 min
        ("2m", "1m", -1),
        (None, "1m", 0),
        ("1m", None, 0),
        (None, None, 0),
        ("unknown", "1m", -1), # 'unknown' to_minutes -> inf, '1m' to_minutes -> 1. inf > 1, so 'unknown' is coarser.
        ("1m", "unknown", 1), # '1m' to_minutes -> 1, 'unknown' to_minutes -> inf. 1 < inf, so '1m' is finer.
        ("5d", "1wk", 1),    # 5*24*60 vs 7*24*60. 5d is finer.
        ("2h", "120m", 0),
        ("30m", "1h", 1)
    ])
    def test_compare_intervals(self, hydrator_for_unit_tests, interval1, interval2, expected_comparison_result):
        result = hydrator_for_unit_tests._compare_intervals(interval1, interval2)
        assert result == expected_comparison_result
</tbody>
</table>
