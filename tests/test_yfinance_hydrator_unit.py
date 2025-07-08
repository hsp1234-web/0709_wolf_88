# -*- coding: utf-8 -*-
"""
單元測試 for YFinanceHydrator 中的輔助函數。
"""
import pytest
from datetime import datetime, date

# 假設 YFinanceHydrator 類在 apps.yfinance_hydrator.hydrator 路徑下
# 為了讓測試腳本能找到它，可能需要在 pytest.ini 中配置 python_paths
# 或者在測試執行時調整 PYTHONPATH，或使用相對導入（如果結構允許）
# 暫時直接導入，如果 pytest 找不到，再調整導入路徑或測試執行方式
from apps.yfinance_hydrator.hydrator import YFinanceHydrator

# 初始化一個虛擬的 hydrator 實例，因為我們要測試的是它的靜態方法或不受 state 影響的輔助方法
# 這些輔助方法實際上可以被定義為靜態方法或模組級別的函數，這樣就不需要實例化了
# 但既然它們目前是類方法，我們就創建一個 dummy 實例 (不需要真實的 db_manager)
dummy_hydrator = YFinanceHydrator(db_manager=None)

class TestYFinanceHydratorUnit:
    """
    對 YFinanceHydrator 中輔助方法的單元測試。
    """

    @pytest.mark.parametrize("interval, expected_days", [
        ('1m', 7),
        ('5m', 60),
        ('15m', 60),
        ('30m', 60),
        ('1h', 730), ('60m', 730),
        ('1d', 365 * 2),
        ('1wk', 365 * 2),
        ('1mo', 365 * 10),
        ('3mo', 365 * 10),
        ('invalid_interval', 30), # 測試未知 interval 的預設值
    ])
    def test_get_chunk_size_for_interval(self, interval, expected_days):
        """測試 _get_chunk_size_for_interval 方法能否為不同 interval 返回正確的建議天數。"""
        assert dummy_hydrator._get_chunk_size_for_interval(interval) == expected_days

    @pytest.mark.parametrize("start_date_str, end_date_str, chunk_size_days, expected_chunks", [
        # 測試案例 1: 正常範圍，可以被整除
        ("2023-01-01", "2023-01-10", 5, [
            ("2023-01-01", "2023-01-06"), # 01 to 05 (inclusive), yf_end is 06 (exclusive)
            ("2023-01-06", "2023-01-11")  # 06 to 10 (inclusive), yf_end is 11 (exclusive)
        ]),
        # 測試案例 2: 範圍不能被 chunk_size 整除，最後一個 chunk 較小
        ("2023-01-01", "2023-01-07", 5, [
            ("2023-01-01", "2023-01-06"), # 01 to 05
            ("2023-01-06", "2023-01-08")  # 06 to 07
        ]),
        # 測試案例 3: 範圍小於 chunk_size
        ("2023-01-01", "2023-01-03", 5, [
            ("2023-01-01", "2023-01-04")  # 01 to 03
        ]),
        # 測試案例 4: start_date 等于 end_date
        ("2023-01-01", "2023-01-01", 5, [
            ("2023-01-01", "2023-01-02")  # 01 to 01
        ]),
        # 測試案例 5: chunk_size 為 1
        ("2023-01-01", "2023-01-03", 1, [
            ("2023-01-01", "2023-01-02"),
            ("2023-01-02", "2023-01-03"),
            ("2023-01-03", "2023-01-04")
        ]),
        # 測試案例 6: 較大的日期範圍和 chunk_size
        ("2023-01-01", "2023-03-15", 30, [
            ("2023-01-01", "2023-01-31"), # Jan 1-30
            ("2023-01-31", "2023-03-02"), # Jan 31 - Mar 1
            ("2023-03-02", "2023-03-16")  # Mar 2 - Mar 15
        ]),
        # 測試案例 7: 無效日期格式 (預期返回空列表)
        ("2023/01/01", "2023-01-10", 5, []),
        ("2023-01-01", "invalid-date", 5, []),
        # 測試案例 8: chunk_size_days 為 0 或負數 (預期返回空列表)
        ("2023-01-01", "2023-01-10", 0, []),
        ("2023-01-01", "2023-01-10", -2, []),
    ])
    def test_split_date_range_into_chunks(self, start_date_str, end_date_str, chunk_size_days, expected_chunks):
        """測試 _split_date_range_into_chunks 方法能否正確地將日期範圍分塊。"""
        # dummy_hydrator = YFinanceHydrator(db_manager=None) # 確保每次測試使用乾淨的實例或方法是靜態的
        # 由於 _get_chunk_size_for_interval 和 _split_date_range_into_chunks 是無狀態的，
        # 使用類級別的 dummy_hydrator 是可以的。
        result_chunks = dummy_hydrator._split_date_range_into_chunks(start_date_str, end_date_str, chunk_size_days)
        assert result_chunks == expected_chunks

    @pytest.mark.parametrize("ticker, expected_full_hash", [
        ("AAPL", "8b10e4ae9eeb5684921a9ab27e4d87aa"),
        ("MSFT", "b004b3ecde24c85e32c1923f10d3fb62"),
        ("GOOGL", "e15ce71ff533c9125f11a46c09e2412b"),
        ("BRK-A", "872e23a1f74cee9d02197d43571016f4"),
        ("中華電信", "b96bfc55d9925a229c1e33e72ca60200"), # hashlib.md5("中華電信".encode()).hexdigest()
    ])
    def test_create_request_hash(self, ticker, expected_full_hash):
        """測試 _create_request_hash 方法能否生成正確的 MD5 哈希值。"""
        actual_hash = dummy_hydrator._create_request_hash(ticker)
        assert isinstance(actual_hash, str)
        assert len(actual_hash) == 32 # MD5 hexdigest length
        assert actual_hash == expected_full_hash


    # 作戰計畫書中提到的 _convert_missing_dates_to_ranges:
    # 此函數原位於 YFinanceClient。如果 YFinancePulseEngine 需要此功能來確定
    # 「缺失日期範圍」傳遞給 YFinanceHydrator (如果 hydrate_day 被設計為接收範圍而非單日)，
    # 那麼這個函數應該位於 PulseEngine 或作為一個通用工具函數。
    # YFinanceHydrator 的 hydrate_day 設計為處理單日，其內部快取檢查隱含處理了「缺失」。
    # 因此，目前不在 YFinanceHydrator 中測試此函數。
    # 如果未來設計變更，可將此函數及其測試移入。

    # def test_placeholder_for_convert_missing_dates_to_ranges(self):
    #     """如果 _convert_missing_dates_to_ranges 被移入，可以在此添加測試。"""
    #     pass

# 注意：如果 YFinanceHydrator 的方法依賴 self 的某些狀態（例如 self.db_manager），
# 則在單元測試中需要 mock 掉這些依賴，或者確保測試的方法確實不依賴它們。
# 目前測試的 _get_chunk_size_for_interval, _split_date_range_into_chunks, _create_request_hash
# 實際上不依賴 self 的狀態 (db_manager)，所以使用 dummy_hydrator 是安全的。
# 更好的做法可能是將這些純邏輯函數定義為靜態方法 (@staticmethod) 或模組級別的函數。
