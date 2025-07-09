# tests/unit/core/clients/test_finmind.py
# 針對 core.clients.finmind 模組的單元測試。

import pytest
import pandas as pd
from pandas.testing import assert_frame_equal
from unittest.mock import patch, MagicMock
import os
from io import StringIO
import requests # 新增導入

# 假設 core 模組在 PYTHONPATH 中，或 pytest 能夠找到它
from core.clients.finmind import FinMindAPIClient, BASE_URL

# 測試用的 API Token
TEST_API_TOKEN = "test_token_123"

@pytest.fixture
def client_with_token():
    """提供一個已設定 API Token 的 FinMindAPIClient 實例。"""
    with patch.dict(os.environ, {"FINMIND_API_TOKEN": TEST_API_TOKEN}):
        client = FinMindAPIClient()
    return client

@pytest.fixture
def client_no_token_in_env():
    """確保環境變數中沒有 FINMIND_API_TOKEN。"""
    original_token = os.environ.pop("FINMIND_API_TOKEN", None)
    yield
    if original_token is not None:
        os.environ["FINMIND_API_TOKEN"] = original_token

class TestFinMindAPIClientInitialization:
    """測試 FinMindAPIClient 的初始化過程。"""

    def test_init_with_token_arg(self, client_no_token_in_env):
        """測試使用參數傳入 API token 初始化。"""
        client = FinMindAPIClient(api_token="param_token")
        assert client.api_token == "param_token"

    def test_init_with_env_variable(self):
        """測試從環境變數讀取 API token 初始化。"""
        with patch.dict(os.environ, {"FINMIND_API_TOKEN": "env_token"}):
            client = FinMindAPIClient()
            assert client.api_token == "env_token"

    def test_init_no_token_raises_value_error(self, client_no_token_in_env):
        """測試未提供 token 且環境變數也未設定時，應引發 ValueError。"""
        with pytest.raises(ValueError, match="FinMind API token 未設定"):
            FinMindAPIClient()

    def test_init_token_priority_arg_over_env(self):
        """測試參數傳入的 token 優先於環境變數。"""
        with patch.dict(os.environ, {"FINMIND_API_TOKEN": "env_token"}):
            client = FinMindAPIClient(api_token="param_token_override")
            assert client.api_token == "param_token_override"


@patch('requests.get') # Mock requests.get 以避免真實網路請求
class TestFinMindAPIMakeRequest:
    """測試 FinMindAPIClient._make_request 方法的各種情境。"""

    def test_make_request_success_json_response(self, mock_requests_get, client_with_token):
        """測試成功請求並處理 JSON 回應。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json; charset=utf-8'}
        # FinMind JSON 成功的 status code 在 payload 裡面
        mock_response.json.return_value = {
            "status": 200,
            "msg": "success",
            "data": [{"date": "2023-01-01", "value": 100}, {"date": "2023-01-02", "value": 101}]
        }
        mock_requests_get.return_value = mock_response

        params = {"dataset": "TestDataset", "data_id": "TestID", "start_date": "2023-01-01"}
        result_df = client_with_token._make_request(params)

        expected_df = pd.DataFrame([{"date": "2023-01-01", "value": 100}, {"date": "2023-01-02", "value": 101}])

        mock_requests_get.assert_called_once_with(
            BASE_URL,
            params={**params, "token": TEST_API_TOKEN}, # 驗證 token 是否被加入 params
            headers={}
        )
        assert_frame_equal(result_df, expected_df)

    def test_make_request_success_csv_response(self, mock_requests_get, client_with_token):
        """測試成功請求並處理 CSV 回應。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'text/csv; charset=utf-8'}
        csv_data = "date,value\n2023-01-01,100\n2023-01-02,101"
        mock_response.text = csv_data
        mock_requests_get.return_value = mock_response

        params = {"dataset": "TestCSVDataset", "data_id": "TestID", "start_date": "2023-01-01"}
        result_df = client_with_token._make_request(params)

        expected_df = pd.read_csv(StringIO(csv_data))

        mock_requests_get.assert_called_once()
        assert_frame_equal(result_df, expected_df)

    def test_make_request_json_api_error_status(self, mock_requests_get, client_with_token):
        """測試 FinMind API 返回 JSON 格式但 status 非 200 的情況。"""
        mock_response = MagicMock()
        mock_response.status_code = 200 # HTTP 狀態碼是 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.json.return_value = {
            "status": 400, # 但 API 內部狀態碼是錯誤
            "msg": "Invalid parameters",
            "data": []
        }
        mock_requests_get.return_value = mock_response

        params = {"dataset": "TestDataset", "data_id": "InvalidID", "start_date": "2023-01-01"}
        result_df = client_with_token._make_request(params)

        assert result_df is None # 預期返回 None

    def test_make_request_json_no_data(self, mock_requests_get, client_with_token):
        """測試 FinMind API 返回 JSON 格式，status 200 但 data 為空。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.json.return_value = {
            "status": 200,
            "msg": "success",
            "data": [] # data 列表為空
        }
        mock_requests_get.return_value = mock_response

        params = {"dataset": "NoDataDataset", "data_id": "ID", "start_date": "2023-01-01"}
        result_df = client_with_token._make_request(params)

        assert isinstance(result_df, pd.DataFrame) # 預期返回空的 DataFrame
        assert result_df.empty

    def test_make_request_http_error(self, mock_requests_get, client_with_token):
        """測試發生 HTTP 錯誤 (例如 401, 403, 500)。"""
        mock_response = MagicMock()
        mock_response.status_code = 401 # 未授權
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"error": "Unauthorized"}'
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Simulated HTTP Error")
        mock_requests_get.return_value = mock_response

        params = {"dataset": "ProtectedDataset", "data_id": "ID", "start_date": "2023-01-01"}
        result_df = client_with_token._make_request(params)

        assert result_df is None

    def test_make_request_network_error(self, mock_requests_get, client_with_token):
        """測試發生網路請求錯誤 (例如 requests.exceptions.RequestException)。"""
        mock_requests_get.side_effect = requests.exceptions.ConnectionError("Simulated Connection Error")

        params = {"dataset": "SomeDataset", "data_id": "ID", "start_date": "2023-01-01"}
        result_df = client_with_token._make_request(params)

        assert result_df is None

    def test_make_request_unknown_content_type(self, mock_requests_get, client_with_token):
        """測試 API 返回未知的 Content-Type。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/octet-stream'} # 未知類型
        mock_requests_get.return_value = mock_response

        params = {"dataset": "UnknownTypeDataset", "data_id": "ID", "start_date": "2023-01-01"}
        result_df = client_with_token._make_request(params)

        assert result_df is None


@patch.object(FinMindAPIClient, '_make_request') # Mock _make_request 方法
class TestFinMindAPIGetDataMethods:
    """測試 FinMindAPIClient 的高階 get_data 和特定資料集方法。"""

    def test_get_data_calls_make_request_correctly(self, mock_make_request, client_with_token):
        """測試 get_data 是否以正確的參數調用 _make_request。"""
        mock_df = pd.DataFrame({"test": [1]})
        mock_make_request.return_value = mock_df

        dataset = "MyDataset"
        data_id = "MyID"
        start_date = "2023-05-01"
        end_date = "2023-05-10"

        result = client_with_token.get_data(dataset, data_id, start_date, end_date)

        expected_params = {
            "dataset": dataset,
            "data_id": data_id,
            "start_date": start_date,
            "end_date": end_date,
        }
        mock_make_request.assert_called_once_with(expected_params)
        assert_frame_equal(result, mock_df)

    def test_get_data_default_end_date(self, mock_make_request, client_with_token):
        """測試 get_data 在未提供 end_date 時，是否使用當前日期。"""
        mock_make_request.return_value = pd.DataFrame() # 返回什麼不重要，重點是參數

        dataset = "MyDataset"
        data_id = "MyID"
        start_date = "2023-05-01"

        # 為了使測試穩定，我們需要 mock datetime.now()
        with patch('core.clients.finmind.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2023-12-25" # 假設今天是 2023-12-25
            client_with_token.get_data(dataset, data_id, start_date)

        expected_params = {
            "dataset": dataset,
            "data_id": data_id,
            "start_date": start_date,
            "end_date": "2023-12-25", # 預期使用 mock 的當前日期
        }
        mock_make_request.assert_called_once_with(expected_params)

    def test_get_taiwan_stock_institutional_investors_buy_sell(self, mock_make_request, client_with_token):
        """測試 get_taiwan_stock_institutional_investors_buy_sell 方法。"""
        mock_df = pd.DataFrame({"buy_sell": [1000]})
        mock_make_request.return_value = mock_df

        stock_id = "2330"
        start_date = "2024-01-01"
        end_date = "2024-01-05"

        result = client_with_token.get_taiwan_stock_institutional_investors_buy_sell(stock_id, start_date, end_date)

        expected_params = {
            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
            "data_id": stock_id,
            "start_date": start_date,
            "end_date": end_date,
        }
        # 驗證 _make_request 是透過 get_data 被間接調用的
        # 或者，如果我們想直接驗證 get_data 被調用，可以 patch get_data
        # 但這裡我們是測試這個特定方法是否正確地將參數傳遞給 get_data (並最終到 _make_request)
        mock_make_request.assert_called_once_with(expected_params)
        assert_frame_equal(result, mock_df)

# 運行測試:
# pytest tests/unit/core/clients/test_finmind.py -v
# 或在專案根目錄:
# python -m pytest -v
# (需要安裝 pytest, pandas, requests)
# pip install pytest pandas requests
# (requests-mock 不是必需的，因為我們用了 unittest.mock.patch)
