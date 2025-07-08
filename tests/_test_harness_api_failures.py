# -*- coding: utf-8 -*-
"""
整合測試腳本：API 通訊故障模擬

此腳本用於驗證系統在遭遇外部 API (FinMind) 服務不穩定或拒絕服務時的健壯性。
"""
import unittest
from unittest.mock import patch, Mock
import requests.exceptions
import io
import sys

# 假設被測試的模組和函數位於上一層目錄的 finmind_ETF_scraper.py
# 為了讓測試腳本能夠找到該模組，我們可能需要調整 sys.path
# 或者期望測試執行器 (如 pytest 或 python -m unittest) 能正確處理路徑
# 這裡我們假設 finmind_ETF_scraper 在 Python 的搜索路徑中
# 如果不在，執行時需要PYTHONPATH=. python tests/_test_harness_api_failures.py
try:
    from finmind_ETF_scraper import fetch_etf_data
except ImportError:
    # 如果直接執行此文件且 finmind_ETF_scraper.py 在父目錄
    import os
    # 將父目錄添加到 sys.path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from finmind_ETF_scraper import fetch_etf_data

class TestAPIFailures(unittest.TestCase):
    """
    測試 API 通訊故障情境。
    """

    def setUp(self):
        """
        每個測試方法執行前都會呼叫此方法。
        用於設置捕獲 stdout。
        """
        self.held_stdout = sys.stdout
        sys.stdout = io.StringIO()

    def tearDown(self):
        """
        每個測試方法執行後都會呼叫此方法。
        用於恢復 stdout 並關閉 StringIO 物件。
        """
        sys.stdout.close()
        sys.stdout = self.held_stdout

    @patch('finmind_ETF_scraper.requests.get')
    def test_api_forbidden_error(self, mock_requests_get):
        """
        情境一：測試 API 回應 403 Forbidden 錯誤。

        驗證：
        1. 系統不會因此崩潰。
        2. 系統能捕獲異常並打印出對指揮官友善的作戰報告。
        """
        # 設定 mock_requests_get 的行為
        # 當 requests.get 被呼叫時，模擬一個 HTTP 403 錯誤
        mock_response = Mock()
        mock_response.status_code = 403
        # raise_for_status() 方法在狀態碼為 4xx 或 5xx 時應拋出 HTTPError
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "模擬的 403 Forbidden 錯誤", response=mock_response
        )
        mock_requests_get.return_value = mock_response

        # 呼叫被測試的函數
        # 我們期望它能處理這個異常，而不是讓測試本身因未捕獲的異常而失敗
        result = fetch_etf_data("2023-01-15")

        # 驗證1：系統不會崩潰 (即 fetch_etf_data 正常返回，這裡預期返回 None)
        self.assertIsNone(result, "fetch_etf_data 在 403 錯誤後應返回 None")

        # 驗證2：檢查 stdout 是否包含預期的作戰報告
        output = sys.stdout.getvalue()
        expected_report = "指揮官，數據獲取模組在連接 FinMind API 時遇到權限問題 (403 Forbidden)。請檢查 API 金鑰或權限設定。"
        self.assertIn(expected_report, output, "未找到 403 錯誤的作戰報告")
        # 也可以檢查初始的嘗試連接訊息
        self.assertIn("指揮官，數據獲取模組開始嘗試連接 FinMind API", output)

    @patch('finmind_ETF_scraper.requests.get')
    def test_api_timeout_error(self, mock_requests_get):
        """
        情境二：測試 API 請求超時。

        驗證：
        1. 系統不會因此崩潰。
        2. 系統能捕獲異常並打印出對指揮官友善的作戰報告。
        """
        # 設定 mock_requests_get 的行為
        # 當 requests.get 被呼叫時，拋出 Timeout 異常
        mock_requests_get.side_effect = requests.exceptions.Timeout("模擬的請求超時")

        # 呼叫被測試的函數
        result = fetch_etf_data("2023-01-16")

        # 驗證1：系統不會崩潰 (即 fetch_etf_data 正常返回，這裡預期返回 None)
        self.assertIsNone(result, "fetch_etf_data 在超時錯誤後應返回 None")

        # 驗證2：檢查 stdout 是否包含預期的作戰報告
        output = sys.stdout.getvalue()
        expected_report = "指揮官，數據獲取模組在連接 FinMind API 時因超時而失敗。網路連線可能不穩定或 API 服務繁忙。"
        self.assertIn(expected_report, output, "未找到超時錯誤的作戰報告")
        # 也可以檢查初始的嘗試連接訊息
        self.assertIn("指揮官，數據獲取模組開始嘗試連接 FinMind API", output)

if __name__ == '__main__':
    # 這允許直接從命令行運行測試
    # 例如：python tests/_test_harness_api_failures.py
    # 或者使用 unittest 發現機制：python -m unittest discover tests
    unittest.main()
