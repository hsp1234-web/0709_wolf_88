# tests/unit/core/clients/test_fmp.py
# 針對 core.clients.fmp 模組的單元測試。

import pytest
import pandas as pd
from pandas.testing import assert_frame_equal
from unittest.mock import patch, MagicMock
import os
import requests # 用於 requests.exceptions

# 假設 core 模組在 PYTHONPATH 中，或 pytest 能夠找到它
from core.clients.fmp import FMPAPIClient, FMP_BASE_URL

# 測試用的 API Key
TEST_FMP_API_KEY = "test_fmp_api_key_123"

@pytest.fixture
def client_with_key():
    """提供一個已設定 API Key 的 FMPAPIClient 實例。"""
    with patch.dict(os.environ, {"FMP_API_KEY": TEST_FMP_API_KEY}):
        client = FMPAPIClient(api_version="v3") # 固定版本以利測試
    return client

@pytest.fixture
def client_no_key_in_env():
    """確保環境變數中沒有 FMP_API_KEY。"""
    original_key = os.environ.pop("FMP_API_KEY", None)
    yield
    if original_key is not None:
        os.environ["FMP_API_KEY"] = original_key

class TestFMPAPIClientInitialization:
    """測試 FMPAPIClient 的初始化過程。"""

    def test_init_with_key_arg(self, client_no_key_in_env):
        client = FMPAPIClient(api_key="param_key", api_version="v3")
        assert client.api_key == "param_key"
        assert client.base_url_with_version == f"{FMP_BASE_URL}/v3"

    def test_init_with_env_variable(self):
        with patch.dict(os.environ, {"FMP_API_KEY": "env_key"}):
            client = FMPAPIClient(api_version="v4")
            assert client.api_key == "env_key"
            assert client.base_url_with_version == f"{FMP_BASE_URL}/v4"

    def test_init_no_key_raises_value_error(self, client_no_key_in_env):
        with pytest.raises(ValueError, match="FMP API key 未設定"):
            FMPAPIClient()

    def test_init_key_priority_arg_over_env(self):
        with patch.dict(os.environ, {"FMP_API_KEY": "env_key"}):
            client = FMPAPIClient(api_key="param_key_override")
            assert client.api_key == "param_key_override"

@patch('requests.get') # Mock requests.get 以避免真實網路請求
class TestFMPAPIMakeRequest:
    """測試 FMPAPIClient._make_request 方法。"""

    def test_make_request_success_direct_list(self, mock_requests_get, client_with_key):
        """測試 API 直接返回列表數據。"""
        mock_data = [{"field": "value1"}, {"field": "value2"}]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_requests_get.return_value = mock_response

        result = client_with_key._make_request("some_endpoint")

        expected_url = f"{client_with_key.base_url_with_version}/some_endpoint"
        mock_requests_get.assert_called_once_with(expected_url, params={"apikey": TEST_FMP_API_KEY})
        assert result == mock_data

    def test_make_request_success_wrapped_list(self, mock_requests_get, client_with_key):
        """測試 API 返回的列表數據被包裝在 'historical' 鍵下。"""
        mock_hist_data = [{"date": "2023-01-01"}, {"date": "2023-01-02"}]
        mock_response_json = {"symbol": "AAPL", "historical": mock_hist_data}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_json
        mock_requests_get.return_value = mock_response

        result = client_with_key._make_request("historical-price-full/AAPL")
        assert result == mock_hist_data

    def test_make_request_api_error_message(self, mock_requests_get, client_with_key):
        """測試 API 返回包含 "Error Message" 的 JSON。"""
        mock_error_json = {"Error Message": "Invalid API KEY or symbol."}
        mock_response = MagicMock()
        mock_response.status_code = 200 # 有時 FMP 錯誤也返回 200 OK，但內容是錯誤訊息
        mock_response.json.return_value = mock_error_json
        mock_requests_get.return_value = mock_response

        result = client_with_key._make_request("some_endpoint")
        assert result is None

    def test_make_request_http_error(self, mock_requests_get, client_with_key):
        """測試發生 HTTP 錯誤 (例如 401, 403)。"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Simulated HTTP Error")
        mock_requests_get.return_value = mock_response

        result = client_with_key._make_request("protected_endpoint")
        assert result is None

    def test_make_request_network_error(self, mock_requests_get, client_with_key):
        """測試發生網路請求錯誤。"""
        mock_requests_get.side_effect = requests.exceptions.ConnectionError("Simulated Connection Error")

        result = client_with_key._make_request("any_endpoint")
        assert result is None

    def test_make_request_empty_list_response(self, mock_requests_get, client_with_key):
        """測試 API 成功返回但數據列表為空。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [] # 直接返回空列表
        mock_requests_get.return_value = mock_response

        result = client_with_key._make_request("empty_data_endpoint")
        assert result == []

    def test_make_request_unexpected_dict_response(self, mock_requests_get, client_with_key):
        """測試 API 返回未預期 (非錯誤、非列表、非已知包裝) 的字典。"""
        mock_response_json = {"unexpected_key": "unexpected_value"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_json
        mock_requests_get.return_value = mock_response

        result = client_with_key._make_request("unexpected_dict_endpoint")
        assert result is None # 根據目前 _make_request 設計，應返回 None

@patch.object(FMPAPIClient, '_make_request') # Mock _make_request 方法
class TestFMPAPIGetDataMethods:
    """測試 FMPAPIClient 的高階數據獲取方法。"""

    def test_get_historical_daily_prices_success(self, mock_make_request, client_with_key):
        """測試成功獲取歷史日線價格。"""
        raw_data = [
            {"date": "2023-01-02", "open": 101, "close": 102}, # 較新日期在前 (FMP 原始順序)
            {"date": "2023-01-01", "open": 100, "close": 100},
        ]
        mock_make_request.return_value = raw_data

        result_df = client_with_key.get_historical_daily_prices("AAPL", "2023-01-01", "2023-01-02")

        expected_df_data = [
            {"date": pd.to_datetime("2023-01-01"), "open": 100, "close": 100}, # 排序後較舊日期在前
            {"date": pd.to_datetime("2023-01-02"), "open": 101, "close": 102},
        ]
        expected_df = pd.DataFrame(expected_df_data)

        mock_make_request.assert_called_once_with(
            "historical-price-full/AAPL",
            {"from": "2023-01-01", "to": "2023-01-02"}
        )
        assert_frame_equal(result_df, expected_df, check_like=True) # check_like 忽略欄位順序

    def test_get_historical_daily_prices_no_data(self, mock_make_request, client_with_key):
        """測試獲取歷史價格時 API 返回空列表。"""
        mock_make_request.return_value = [] # API 返回空列表

        result_df = client_with_key.get_historical_daily_prices("NODATA", "2023-01-01", "2023-01-02")

        assert isinstance(result_df, pd.DataFrame)
        assert result_df.empty

    def test_get_historical_daily_prices_fail(self, mock_make_request, client_with_key):
        """測試獲取歷史價格時 _make_request 返回 None。"""
        mock_make_request.return_value = None # _make_request 失敗

        result_df = client_with_key.get_historical_daily_prices("FAIL", "2023-01-01", "2023-01-02")
        assert result_df is None

    def test_get_financial_statements_success(self, mock_make_request, client_with_key):
        """測試成功獲取財務報表。"""
        raw_data = [
            {"date": "2023-03-31", "symbol": "MSFT", "netIncome": 20000}, # FMP 財報通常日期降序
            {"date": "2022-12-31", "symbol": "MSFT", "netIncome": 18000},
        ]
        mock_make_request.return_value = raw_data

        result_df = client_with_key.get_financial_statements("MSFT", "income-statement", "quarter", 2)

        expected_df_data = [
            {"date": pd.to_datetime("2023-03-31"), "symbol": "MSFT", "netIncome": 20000},
            {"date": pd.to_datetime("2022-12-31"), "symbol": "MSFT", "netIncome": 18000},
        ]
        expected_df = pd.DataFrame(expected_df_data)

        mock_make_request.assert_called_once_with(
            "income-statement/MSFT",
            {"period": "quarter", "limit": "2"}
        )
        assert_frame_equal(result_df, expected_df, check_like=True)

    def test_get_financial_statements_no_data(self, mock_make_request, client_with_key):
        """測試獲取財報時 API 返回空列表。"""
        mock_make_request.return_value = []
        result_df = client_with_key.get_financial_statements("EMPTY", "balance-sheet-statement")
        assert isinstance(result_df, pd.DataFrame)
        assert result_df.empty

    def test_get_financial_statements_fail(self, mock_make_request, client_with_key):
        """測試獲取財報時 _make_request 返回 None。"""
        mock_make_request.return_value = None
        result_df = client_with_key.get_financial_statements("ERROR", "cash-flow-statement")
        assert result_df is None

# 運行測試指令:
# pytest tests/unit/core/clients/test_fmp.py -v
# 或在專案根目錄:
# python -m pytest -v
# (需要安裝 pytest, pandas, requests)
