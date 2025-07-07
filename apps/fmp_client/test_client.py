# apps/fmp_client/test_client.py
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import os
import sys

# 將專案根目錄加到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from apps.fmp_client.client import FMPClient, BASE_URL as FMP_BASE_URL # Import BASE_URL for assertion

# 模擬的 API Key
MOCK_API_KEY = "test_fmp_api_key"

# 輔助函數，用於建立模擬的 requests.Response 物件
def mock_api_response(json_data, status_code=200, is_list_directly=True):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code

    # FMP 有些端點直接返回列表，有些是字典包含列表 (如 "historical")
    if status_code == 200:
        if is_list_directly: # e.g., financial statements
            mock_resp.json.return_value = json_data
        else: # e.g., historical prices in {"symbol": "AAPL", "historical": [...]}
            # 這裡的模擬需要根據 client._make_request 的解析邏輯來調整
            # 假設 client._make_request 會處理 'historical' 鍵
            if isinstance(json_data, list): # 如果傳入的直接是 data list
                 mock_resp.json.return_value = {"historical": json_data} # 包裝一下
            else: # 如果傳入的是完整的 dict
                 mock_resp.json.return_value = json_data

    elif "Error Message" in json_data: # FMP 的錯誤格式
        mock_resp.json.return_value = json_data

    if status_code >= 400:
        mock_resp.raise_for_status = MagicMock(side_effect=requests.exceptions.HTTPError(response=mock_resp))
    else:
        mock_resp.raise_for_status = MagicMock()

    return mock_resp

# 為了 mock_failed_response 的 side_effect，我們需要 requests.exceptions.HTTPError
try:
    import requests.exceptions
except ImportError:
    class MockHTTPError(Exception):
        def __init__(self, response=None):
            self.response = response

    class MockRequestsModule:
        class exceptions:
            HTTPError = MockHTTPError

    requests = MockRequestsModule()


class TestFMPClient(unittest.TestCase):

    def setUp(self):
        # 直接傳遞 MOCK_API_KEY 給 client
        self.client_v3 = FMPClient(api_key=MOCK_API_KEY, api_version="v3")
        self.test_symbol = "AAPL"
        self.from_date = "2023-01-01"
        self.to_date = "2023-01-10"

    def test_initialization_with_provided_key(self):
        """測試使用提供的 API Key 初始化"""
        client = FMPClient(api_key="custom_key_test")
        self.assertEqual(client.api_key, "custom_key_test")
        self.assertEqual(client.base_url, f"{FMP_BASE_URL}/v3") # default v3

    def test_initialization_with_version_and_key(self):
        """測試使用 API Key 和指定版本初始化"""
        client = FMPClient(api_key=MOCK_API_KEY, api_version="v4")
        self.assertEqual(client.api_key, MOCK_API_KEY)
        self.assertEqual(client.base_url, f"{FMP_BASE_URL}/v4")

    @patch.dict(os.environ, {"FMP_API_KEY": ""}, clear=True) # 確保環境變數 FMP_API_KEY 為空或不存在
    def test_initialization_without_key_or_env_raises_error(self):
        """測試未提供 API Key 且環境變數未設定時拋出錯誤"""
        with self.assertRaisesRegex(ValueError, "FMP API key 未設定"):
            FMPClient(api_key=None) # 明確傳遞 None

    @patch.dict(os.environ, {'FMP_API_KEY': 'env_fmp_key_test'}, clear=True)
    def test_initialization_with_env_variable_and_no_arg(self):
        """測試未傳入 API Key 時，從環境變數讀取"""
        with patch('apps.fmp_client.client.FMP_API_KEY', 'env_fmp_key_test'): # Patch 模組級變數
            client = FMPClient(api_key=None, api_version="v3") # 傳入 None 觸發環境變數讀取
            self.assertEqual(client.api_key, 'env_fmp_key_test')

    @patch.dict(os.environ, {'FMP_API_KEY': 'env_should_be_ignored_fmp'}, clear=True)
    def test_initialization_with_arg_overrides_env_variable(self):
        """測試初始化時傳入的 api_key 優先於環境變數"""
        client = FMPClient(api_key="arg_fmp_key_should_be_used", api_version="v3")
        self.assertEqual(client.api_key, "arg_fmp_key_should_be_used")

    @patch('apps.fmp_client.client.requests.get')
    def test_get_historical_daily_prices_success(self, mock_get):
        mock_data = [
            {"date": "2023-01-02", "open": 130.0, "close": 132.0, "volume": 100000},
            {"date": "2023-01-01", "open": 128.0, "close": 129.0, "volume": 90000}, # FMP data is newest first usually
        ]
        # _make_request expects 'historical' key for this endpoint usually
        mock_get.return_value = mock_api_response(mock_data, is_list_directly=False)

        df = self.client_v3.get_historical_daily_prices(self.test_symbol, self.from_date, self.to_date)

        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]['date'], "2023-01-01") # Check sorting
        self.assertEqual(df.iloc[1]['close'], 132.0)

        expected_url = f"{self.client_v3.base_url}/historical-price-full/{self.test_symbol}"
        expected_params = {"from": self.from_date, "to": self.to_date, "apikey": MOCK_API_KEY}
        mock_get.assert_called_once_with(expected_url, params=expected_params)

    @patch('apps.fmp_client.client.requests.get')
    def test_get_etf_historical_daily_prices_calls_correct_method(self, mock_get):
        # This test just ensures it calls the main historical price function
        with patch.object(self.client_v3, 'get_historical_daily_prices', return_value=pd.DataFrame()) as mock_internal_call:
            self.client_v3.get_etf_historical_daily_prices("SPY", self.from_date, self.to_date)
            mock_internal_call.assert_called_once_with(symbol="SPY", from_date=self.from_date, to_date=self.to_date)

    @patch('apps.fmp_client.client.requests.get')
    def test_get_index_historical_daily_prices_calls_correct_method(self, mock_get):
        # This test just ensures it calls the main historical price function
        index_symbol = "%5EGSPC"
        with patch.object(self.client_v3, 'get_historical_daily_prices', return_value=pd.DataFrame()) as mock_internal_call:
            self.client_v3.get_index_historical_daily_prices(index_symbol, self.from_date, self.to_date)
            mock_internal_call.assert_called_once_with(symbol=index_symbol, from_date=self.from_date, to_date=self.to_date)

    @patch('apps.fmp_client.client.requests.get')
    def test_get_financial_statements_success(self, mock_get):
        statement_type = "income-statement"
        mock_data = [
            {"date": "2023-03-31", "symbol": "AAPL", "netIncome": 25000000000},
            {"date": "2022-12-31", "symbol": "AAPL", "netIncome": 30000000000},
        ]
        mock_get.return_value = mock_api_response(mock_data, is_list_directly=True)

        df = self.client_v3.get_financial_statements(self.test_symbol, statement_type, period="quarter", limit=2)

        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]['netIncome'], 25000000000)

        expected_url = f"{self.client_v3.base_url}/{statement_type}/{self.test_symbol}"
        expected_params = {"period": "quarter", "limit": 2, "apikey": MOCK_API_KEY}
        mock_get.assert_called_once_with(expected_url, params=expected_params)

    @patch('apps.fmp_client.client.requests.get')
    def test_api_error_message_returns_none(self, mock_get):
        """Test when FMP API returns a JSON with 'Error Message' key"""
        mock_get.return_value = mock_api_response({"Error Message": "Invalid symbol."}, status_code=200) # Sometimes FMP returns 200 OK with error in JSON

        df = self.client_v3.get_historical_daily_prices("INVALID_SYMBOL")
        self.assertIsNone(df)

    @patch('apps.fmp_client.client.requests.get')
    def test_http_error_returns_none(self, mock_get):
        """Test when a non-200 HTTP status code is returned"""
        mock_get.return_value = mock_api_response({}, status_code=401) # Unauthorized

        df = self.client_v3.get_historical_daily_prices(self.test_symbol)
        self.assertIsNone(df)

    @patch('apps.fmp_client.client.requests.get')
    def test_request_exception_returns_none(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        df = self.client_v3.get_historical_daily_prices(self.test_symbol)
        self.assertIsNone(df)

    @patch('apps.fmp_client.client.requests.get')
    def test_empty_data_list_returns_empty_dataframe(self, mock_get):
        # Simulate API returning success, but an empty list of data
        # For historical prices, it's wrapped in 'historical'
        mock_get.return_value = mock_api_response([], is_list_directly=False)
        df_prices = self.client_v3.get_historical_daily_prices(self.test_symbol)
        self.assertIsInstance(df_prices, pd.DataFrame)
        self.assertTrue(df_prices.empty)

        # For financial statements, it's a direct list
        mock_get.return_value = mock_api_response([], is_list_directly=True)
        df_financials = self.client_v3.get_financial_statements(self.test_symbol, "income-statement")
        self.assertIsInstance(df_financials, pd.DataFrame)
        self.assertTrue(df_financials.empty)

    @patch('apps.fmp_client.client.requests.get')
    def test_make_request_unexpected_json_structure(self, mock_get):
        """Test _make_request with unexpected (but valid JSON) FMP response structure."""
        # Simulate a response that is a dict but not an error and not matching known structures
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"some_unexpected_key": "some_value"} # Not a list, not an error
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        # We expect _make_request to return None in this case after printing a message
        with patch('builtins.print') as mock_print: # Capture print output
            result = self.client_v3._make_request("some_endpoint")
            self.assertIsNone(result)
            mock_print.assert_any_call(unittest.mock.ANY) # Check that something was printed


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

"""
此 `test_client.py` 檔案包含針對 `FMPClient` 類別的單元測試。

測試內容涵蓋：
1.  **初始化**:
    *   使用提供的 API Key 和 API 版本初始化。
    *   未提供 API Key 且環境變數未設定時拋出 `ValueError`。
2.  **API 方法調用**:
    *   `get_historical_daily_prices`: 測試成功獲取數據、數據排序是否正確。
    *   `get_etf_historical_daily_prices` 和 `get_index_historical_daily_prices`: 驗證它們是否正確調用了 `get_historical_daily_prices`。
    *   `get_financial_statements`: 測試成功獲取財報數據。
3.  **錯誤與邊界情況**:
    *   **API 錯誤訊息**: 模擬 FMP API 返回包含 "Error Message" 的 JSON，驗證客戶端方法返回 `None`。
    *   **HTTP 錯誤**: 模擬非 200 的 HTTP 狀態碼，驗證客戶端方法返回 `None`。
    *   **請求異常**: 模擬 `requests.get` 拋出 `RequestException` (例如網路問題)，驗證客戶端方法返回 `None`。
    *   **空數據列表**: 模擬 API 成功返回但數據列表為空，驗證客戶端方法返回空的 DataFrame。
    *   **非預期 JSON 結構**: 測試 `_make_request` 如何處理未預期的 FMP API JSON 回應結構。
4.  **參數驗證**: 驗證調用 `requests.get` 時傳遞的 URL 和 `params` (包括 API Key) 是否正確。

使用 `unittest.mock.patch` 來模擬 `requests.get` 的行為，避免實際發送網路請求。
輔助函數 `mock_api_response` 用於簡化模擬 FMP API 回應的建立，考慮到 FMP API 可能直接返回列表或將列表包裝在字典中。

執行測試:
在 `apps/fmp_client/` 目錄下執行 `python -m unittest test_client.py`。
"""
