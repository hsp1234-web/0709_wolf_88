# tests/unit/core/clients/test_finmind.py
# 針對 core.clients.finmind 模組的單元測試。

import pytest
import requests
import pandas as pd
from pandas.testing import assert_frame_equal
from unittest.mock import patch, MagicMock
import os
from io import StringIO

# 更新導入以反映重構後的客戶端
from core.clients.finmind import FinMindClient, FINMIND_API_BASE_URL

# 測試用的 API Token
TEST_API_TOKEN = "test_token_123"


@pytest.fixture
def finmind_client_fixture():
    """提供一個已設定 API Token 的 FinMindClient 實例。"""
    with patch.dict(os.environ, {"FINMIND_API_TOKEN": TEST_API_TOKEN}):
        client = FinMindClient()
    return client


@pytest.fixture
def mock_env_no_finmind_token():
    """確保環境變數中沒有 FINMIND_API_TOKEN。"""
    original_token = os.environ.pop("FINMIND_API_TOKEN", None)
    yield
    if original_token is not None:
        os.environ["FINMIND_API_TOKEN"] = original_token


class TestFinMindClientInitialization:
    """測試 FinMindClient 的初始化過程。"""

    def test_init_with_token_arg(self, mock_env_no_finmind_token):
        client = FinMindClient(api_token="param_token_direct")
        assert (
            client.api_key == "param_token_direct"
        )  # BaseAPIClient stores it as api_key
        assert client.base_url == FINMIND_API_BASE_URL
        assert isinstance(client._session, requests.Session)

    def test_init_with_env_variable(self):
        with patch.dict(os.environ, {"FINMIND_API_TOKEN": "env_token_for_finmind"}):
            client = FinMindClient()
            assert client.api_key == "env_token_for_finmind"

    def test_init_no_token_raises_value_error(self, mock_env_no_finmind_token):
        with pytest.raises(ValueError, match="FinMind API token 未設定"):
            FinMindClient()

    def test_init_token_priority_arg_over_env(self):
        with patch.dict(
            os.environ, {"FINMIND_API_TOKEN": "env_finmind_token_to_be_overridden"}
        ):
            client = FinMindClient(api_token="param_finmind_token_override")
            assert client.api_key == "param_finmind_token_override"


# FinMindClient 覆寫了 _request 方法，所以我們直接 mock requests.Session.get
# 或者，如果 _request 內部使用了 self._session，我們可以 mock self._session.get
@patch("requests.Session.get")
class TestFinMindClientRequestOverride:
    """測試 FinMindClient 覆寫的 _request 方法。"""

    def test_request_override_success_json(
        self, mock_session_get, finmind_client_fixture: FinMindClient
    ):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json; charset=utf-8"}
        mock_response.json.return_value = {
            "status": 200,
            "msg": "success",
            "data": [{"col_a": "val1"}, {"col_a": "val2"}],
        }
        mock_session_get.return_value = mock_response

        params = {"dataset": "TestDS", "data_id": "ID001", "start_date": "2023-01-01"}
        # _request 內部會添加 token
        result_df = finmind_client_fixture._request(params=params)

        expected_df = pd.DataFrame([{"col_a": "val1"}, {"col_a": "val2"}])

        # 驗證 requests.Session.get 被調用的參數
        # _request 方法會將 self.api_key (即 TEST_API_TOKEN) 加入到 params['token']
        expected_call_params = params.copy()
        expected_call_params["token"] = TEST_API_TOKEN
        mock_session_get.assert_called_once_with(
            FINMIND_API_BASE_URL, params=expected_call_params
        )

        assert_frame_equal(result_df, expected_df)

    def test_request_override_success_csv(
        self, mock_session_get, finmind_client_fixture: FinMindClient
    ):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/csv; charset=utf-8"}
        csv_content = "header1,header2\nvalue1,value2\nvalue3,value4"
        mock_response.text = csv_content
        mock_session_get.return_value = mock_response

        params = {"dataset": "CSV_DS", "data_id": "ID002", "start_date": "2023-02-01"}
        result_df = finmind_client_fixture._request(params=params)

        expected_df = pd.read_csv(StringIO(csv_content))
        assert_frame_equal(result_df, expected_df)

    def test_request_override_json_api_logic_error(
        self, mock_session_get, finmind_client_fixture: FinMindClient
    ):
        mock_response = MagicMock()
        mock_response.status_code = 200  # HTTP OK
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {
            "status": 400,
            "msg": "API specific error",
            "data": [],
        }
        mock_session_get.return_value = mock_response

        result_df = finmind_client_fixture._request(params={"dataset": "ErrorDS"})
        assert result_df.empty  # 預期返回空 DataFrame

    def test_request_override_http_error_raises(
        self, mock_session_get, finmind_client_fixture: FinMindClient
    ):
        mock_response = MagicMock()
        mock_response.status_code = 403  # Forbidden
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Simulated HTTP 403 Error", response=mock_response
        )
        mock_session_get.return_value = mock_response

        with pytest.raises(
            requests.exceptions.HTTPError, match="Simulated HTTP 403 Error"
        ):
            finmind_client_fixture._request(params={"dataset": "ProtectedDS"})

    def test_request_override_empty_params_value_error(
        self, mock_session_get, finmind_client_fixture: FinMindClient
    ):
        with pytest.raises(
            ValueError, match="請求 FinMind API 時，params 參數不得為空。"
        ):
            finmind_client_fixture._request(params=None)
        mock_session_get.assert_not_called()


# 由於 FinMindClient._request 已經被徹底測試，fetch_data 的測試主要關注它如何調用 _request
@patch.object(FinMindClient, "_request")
class TestFinMindClientFetchData:
    """測試 FinMindClient.fetch_data 方法。"""

    def test_fetch_data_calls_request_correctly(
        self, mock_internal_request, finmind_client_fixture: FinMindClient
    ):
        mock_df_response = pd.DataFrame({"data": [1, 2, 3]})
        mock_internal_request.return_value = mock_df_response

        symbol_id = "0050"
        dataset_name = "TaiwanStockPrice"
        start = "2023-01-01"
        end = "2023-01-31"

        result = finmind_client_fixture.fetch_data(
            symbol=symbol_id, dataset=dataset_name, start_date=start, end_date=end
        )

        expected_params_to_request = {
            "dataset": dataset_name,
            "data_id": symbol_id,
            "start_date": start,
            "end_date": end,
            # 'token' 會在 _request 內部添加
        }
        mock_internal_request.assert_called_once_with(
            endpoint="", params=expected_params_to_request
        )
        assert_frame_equal(result, mock_df_response)

    def test_fetch_data_default_end_date(
        self, mock_internal_request, finmind_client_fixture: FinMindClient
    ):
        mock_internal_request.return_value = pd.DataFrame()  # 返回不重要

        with patch(
            "core.clients.finmind.datetime"
        ) as mock_dt:  # Patch datetime in finmind.py
            mock_dt.now.return_value.strftime.return_value = (
                "2023-12-25"  # Mocked current date
            )

            finmind_client_fixture.fetch_data(
                symbol="2330",
                dataset="TaiwanStockInfo",
                start_date="2023-01-01",
                # end_date is omitted
            )

        expected_params = {
            "dataset": "TaiwanStockInfo",
            "data_id": "2330",
            "start_date": "2023-01-01",
            "end_date": "2023-12-25",  # Defaulted to mocked now
        }
        mock_internal_request.assert_called_once_with(
            endpoint="", params=expected_params
        )

    def test_fetch_data_missing_required_kwargs(
        self, mock_internal_request, finmind_client_fixture: FinMindClient
    ):
        with pytest.raises(ValueError, match="必須在 kwargs 中提供 'dataset' 參數"):
            finmind_client_fixture.fetch_data(symbol="2330", start_date="2023-01-01")

        with pytest.raises(ValueError, match="必須在 kwargs 中提供 'start_date' 參數"):
            finmind_client_fixture.fetch_data(symbol="2330", dataset="TaiwanStockPrice")

        mock_internal_request.assert_not_called()

    def test_get_taiwan_stock_institutional_investors_buy_sell(
        self, mock_internal_request, finmind_client_fixture: FinMindClient
    ):
        """測試便捷方法是否正確調用 fetch_data。"""
        # mock_df = pd.DataFrame({"buy_sell": [1000]}) # F841 - removed
        # fetch_data 會調用 _request, 所以我們 mock _request
        # 或者，如果我們假設 fetch_data 內部正確調用 _request,
        # 我們可以讓 mock_internal_request (代表 _request) 返回預期結果
        # 這裡的 mock_internal_request 是 mock FinMindClient._request

        # 為了測試 get_taiwan_stock_institutional_investors_buy_sell
        # 它調用 fetch_data, fetch_data 調用 _request
        # 所以我們 patch _request

        finmind_client_fixture.get_taiwan_stock_institutional_investors_buy_sell(
            stock_id="2330", start_date="2024-01-01", end_date="2024-01-05"
        )

        expected_params_for_request = {
            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
            "data_id": "2330",
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",
        }
        # 驗證 _request 被調用時的參數
        mock_internal_request.assert_called_once_with(
            endpoint="", params=expected_params_for_request
        )


# pytest tests/unit/core/clients/test_finmind.py -v
