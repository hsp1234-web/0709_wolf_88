# tests/unit/core/clients/test_fmp.py
# 針對 core.clients.fmp 模組的單元測試。

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests  # 用於 requests.exceptions
from pandas.testing import assert_frame_equal

# 更新導入以反映重構後的客戶端
from prometheus.core.clients.fmp import (
    FMP_API_BASE_URL_NO_VERSION,
    FMPClient,
)

# 測試用的 API Key
TEST_FMP_API_KEY = "test_fmp_api_key_123"


@pytest.fixture
def fmp_client_fixture():
    """
    提供一個 FMPClient 實例，並 mock 環境變數中的 API Key。
    使用固定的 default_api_version 以確保測試一致性。
    """
    with patch.dict(os.environ, {"FMP_API_KEY": TEST_FMP_API_KEY}):
        client = FMPClient(default_api_version="v3")
    return client


@pytest.fixture
def mock_env_no_fmp_key():
    """確保環境變數中沒有 FMP_API_KEY。"""
    original_key = os.environ.pop("FMP_API_KEY", None)
    yield
    if original_key is not None:
        os.environ["FMP_API_KEY"] = original_key


class TestFMPClientInitialization:
    """測試 FMPClient 的初始化過程。"""

    def test_init_with_key_arg(self, mock_env_no_fmp_key):
        """測試使用參數傳入 API key 初始化。"""
        client = FMPClient(api_key="param_key_direct", default_api_version="v3")
        assert client.api_key == "param_key_direct"
        assert client.base_url == FMP_API_BASE_URL_NO_VERSION
        assert client.default_api_version == "v3"
        assert isinstance(client._session, requests.Session)  # 驗證 session 初始化

    def test_init_with_env_variable(self):
        """測試從環境變數讀取 API key 初始化。"""
        with patch.dict(os.environ, {"FMP_API_KEY": "env_key_for_fmp"}):
            client = FMPClient(default_api_version="v4")
            assert client.api_key == "env_key_for_fmp"
            assert client.default_api_version == "v4"

    def test_init_no_key_raises_value_error(self, mock_env_no_fmp_key):
        """測試未提供 key 且環境變數也未設定時，應引發 ValueError。"""
        with pytest.raises(ValueError, match="FMP API key 未設定"):
            FMPClient()

    def test_init_key_priority_arg_over_env(self):
        """測試參數傳入的 key 優先於環境變數。"""
        with patch.dict(os.environ, {"FMP_API_KEY": "env_fmp_key_to_be_overridden"}):
            client = FMPClient(api_key="param_fmp_key_override")
            assert client.api_key == "param_fmp_key_override"


class TestFMPClientFetchData:
    """測試 FMPClient.fetch_data 方法的各種情境。"""

    def test_fetch_historical_price_success(self, fmp_client_fixture: FMPClient):
        """測試成功獲取歷史日線價格。"""
        symbol = "AAPL"
        api_version = "v3"
        raw_json_response = {
            "historical": [
                {"date": "2023-01-02", "open": 101, "close": 102},
                {"date": "2023-01-01", "open": 100, "close": 100},
            ]
        }
        mock_response_obj = MagicMock(spec=requests.Response)
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = raw_json_response

        with patch.object(
            fmp_client_fixture._session, "get", return_value=mock_response_obj
        ) as mock_actual_get:
            result_df = fmp_client_fixture.fetch_data(
                symbol=symbol,
                data_type="historical_price",
                from_date="2023-01-01",
                to_date="2023-01-02",
                api_version=api_version,
            )

            expected_endpoint = f"{api_version}/historical-price-full/{symbol}"
            expected_params_to_parent = {
                "from": "2023-01-01",
                "to": "2023-01-02",
                "apikey": TEST_FMP_API_KEY,
            }
            expected_url = f"{fmp_client_fixture.base_url}/{expected_endpoint}"
            mock_actual_get.assert_called_once_with(
                expected_url, params=expected_params_to_parent
            )

            expected_df_data = [
                {"date": pd.to_datetime("2023-01-01"), "open": 100, "close": 100},
                {"date": pd.to_datetime("2023-01-02"), "open": 101, "close": 102},
            ]
            expected_df = pd.DataFrame(expected_df_data)
            assert_frame_equal(
                result_df[["date", "open", "close"]],
                expected_df[["date", "open", "close"]],
                check_like=True,
            )

    def test_fetch_income_statement_success(self, fmp_client_fixture: FMPClient):
        """測試成功獲取損益表數據。"""
        symbol = "MSFT"
        api_version = "v3"
        raw_json_response_list = [
            {"date": "2023-03-31", "symbol": symbol, "netIncome": 20000},
            {"date": "2022-12-31", "symbol": symbol, "netIncome": 18000},
        ]
        mock_response_obj = MagicMock(spec=requests.Response)
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = raw_json_response_list

        with patch.object(
            fmp_client_fixture._session, "get", return_value=mock_response_obj
        ) as mock_actual_get:
            result_df = fmp_client_fixture.fetch_data(
                symbol=symbol,
                data_type="income-statement",
                period="quarter",
                limit=2,
                api_version=api_version,
            )

            expected_endpoint = f"{api_version}/income-statement/{symbol}"
            expected_params_to_parent = {
                "period": "quarter",
                "limit": "2",
                "apikey": TEST_FMP_API_KEY,
            }
            expected_url = f"{fmp_client_fixture.base_url}/{expected_endpoint}"
            mock_actual_get.assert_called_once_with(
                expected_url, params=expected_params_to_parent
            )

            expected_df_data = [
                {
                    "date": pd.to_datetime("2023-03-31"),
                    "symbol": symbol,
                    "netIncome": 20000,
                },
                {
                    "date": pd.to_datetime("2022-12-31"),
                    "symbol": symbol,
                    "netIncome": 18000,
                },
            ]
            expected_df = pd.DataFrame(expected_df_data)
            assert_frame_equal(
                result_df[["date", "symbol", "netIncome"]],
                expected_df[["date", "symbol", "netIncome"]],
                check_like=True,
            )

    def test_fetch_data_unsupported_type_raises_value_error(
        self, fmp_client_fixture: FMPClient
    ):
        """測試不支援的 data_type 時引發 ValueError。"""
        with pytest.raises(
            ValueError, match="不支援的 data_type: invalid_financial_product"
        ):
            fmp_client_fixture.fetch_data(
                symbol="AAPL", data_type="invalid_financial_product"
            )

    def test_fetch_data_missing_data_type_raises_value_error(
        self, fmp_client_fixture: FMPClient
    ):
        """測試未提供 data_type 時引發 ValueError。"""
        with pytest.raises(ValueError, match="必須在 kwargs 中提供 'data_type' 參數"):
            fmp_client_fixture.fetch_data(symbol="AAPL")

    def test_fetch_data_api_returns_error_message_in_json(
        self, fmp_client_fixture: FMPClient
    ):
        """測試 FMP API 在 200 OK 回應中返回業務錯誤訊息。"""
        mock_response_obj = MagicMock(spec=requests.Response)
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = {
            "Error Message": "Invalid symbol or API key."
        }
        with patch.object(
            fmp_client_fixture._session, "get", return_value=mock_response_obj
        ) as mock_actual_get:
            result_df = fmp_client_fixture.fetch_data(
                symbol="ERROR", data_type="historical_price"
            )
            assert result_df.empty
            mock_actual_get.assert_called_once()

    def test_fetch_data_http_error_from_session_get(
        self, fmp_client_fixture: FMPClient
    ):
        """測試 requests.Session.get 拋出 HTTPError 時的處理。"""
        mock_response_obj = MagicMock(spec=requests.Response)
        mock_response_obj.status_code = 401
        mock_response_obj.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Simulated HTTP 401 Error", response=mock_response_obj
        )
        with patch.object(
            fmp_client_fixture._session, "get", return_value=mock_response_obj
        ) as mock_actual_get:
            result_df = fmp_client_fixture.fetch_data(
                symbol="FAIL", data_type="income-statement"
            )
            assert result_df.empty
            mock_actual_get.assert_called_once()
            mock_response_obj.raise_for_status.assert_called_once()

    def test_fetch_data_empty_list_from_api(self, fmp_client_fixture: FMPClient):
        """測試 API 成功返回但數據列表為空。"""
        mock_response_obj = MagicMock(spec=requests.Response)
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = []
        with patch.object(
            fmp_client_fixture._session, "get", return_value=mock_response_obj
        ) as mock_actual_get:
            result_df = fmp_client_fixture.fetch_data(
                symbol="NODATA", data_type="income-statement"
            )
            assert result_df.empty
            mock_actual_get.assert_called_once()

            mock_actual_get.reset_mock()
            mock_response_obj_hist = MagicMock(spec=requests.Response)
            mock_response_obj_hist.status_code = 200
            mock_response_obj_hist.json.return_value = {"historical": []}
            mock_actual_get.return_value = mock_response_obj_hist

            result_df_hist = fmp_client_fixture.fetch_data(
                symbol="NODATA_HIST", data_type="historical_price"
            )
            assert result_df_hist.empty
            mock_actual_get.assert_called_once()

    def test_fetch_data_uses_default_api_version(self, fmp_client_fixture: FMPClient):
        """測試未使用 api_version kwarg 時，是否使用 client 的 default_api_version。"""
        fmp_client_fixture.default_api_version = "v4"

        mock_response_obj = MagicMock(spec=requests.Response)
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = []

        with patch.object(
            fmp_client_fixture._session, "get", return_value=mock_response_obj
        ) as mock_actual_get:
            fmp_client_fixture.fetch_data(symbol="AAPL", data_type="income-statement")

            assert mock_actual_get.call_args is not None, "session.get was not called"
            called_url = mock_actual_get.call_args[0][0]
            assert (
                f"{fmp_client_fixture.base_url}/v4/income-statement/AAPL" in called_url
            )

    def test_fetch_data_limit_param_is_string(self, fmp_client_fixture: FMPClient):
        """測試 limit 參數是否被正確轉換為字串。"""
        mock_response_obj = MagicMock(spec=requests.Response)
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = []

        with patch.object(
            fmp_client_fixture._session, "get", return_value=mock_response_obj
        ) as mock_actual_get:
            fmp_client_fixture.fetch_data(
                symbol="MSFT", data_type="income-statement", limit=5
            )

            assert mock_actual_get.call_args is not None, "session.get was not called"
            called_kwargs = mock_actual_get.call_args[1]
            assert "params" in called_kwargs
            assert called_kwargs["params"]["limit"] == "5"


# 運行測試指令:
# pytest tests/unit/core/clients/test_fmp.py -v
# (需要安裝 pytest, pandas, requests)
