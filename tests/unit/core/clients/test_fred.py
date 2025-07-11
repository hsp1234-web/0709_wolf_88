# tests/unit/core/clients/test_fred.py
# 針對 core.clients.fred 模組的單元測試。

import pytest
import pandas as pd
from pandas.testing import assert_frame_equal
from unittest.mock import patch, MagicMock
import os
import requests  # 用於 requests.exceptions

# 更新導入以反映重構後的客戶端
from core.clients.fred import FREDClient, FRED_API_HOST, FRED_OBSERVATIONS_ENDPOINT

# 測試用的 API Key
TEST_FRED_API_KEY = "test_fred_api_key_456"


@pytest.fixture
def fred_client_fixture():
    """提供一個 FREDClient 實例，並 mock 環境變數中的 API Key。"""
    with patch.dict(os.environ, {"FRED_API_KEY": TEST_FRED_API_KEY}):
        client = FREDClient()
    return client


@pytest.fixture
def mock_env_no_fred_key():
    """確保環境變數中沒有 FRED_API_KEY。"""
    original_key = os.environ.pop("FRED_API_KEY", None)
    yield
    if original_key is not None:
        os.environ["FRED_API_KEY"] = original_key


class TestFREDClientInitialization:
    """測試 FREDClient 的初始化過程。"""

    def test_init_with_key_arg(self, mock_env_no_fred_key):
        client = FREDClient(api_key="param_key_direct")
        assert client.api_key == "param_key_direct"
        assert client.base_url == FRED_API_HOST
        assert isinstance(client._session, requests.Session)

    def test_init_with_env_variable(self):
        with patch.dict(os.environ, {"FRED_API_KEY": "env_key_for_fred"}):
            client = FREDClient()
            assert client.api_key == "env_key_for_fred"

    def test_init_no_key_raises_value_error(self, mock_env_no_fred_key):
        with pytest.raises(ValueError, match="FRED API Key 未設定"):
            FREDClient()


# FREDClient 使用 BaseAPIClient 的 _request, 後者使用 self._session.get
# 因此我們 mock requests.Session.get
@patch("requests.Session.get")
class TestFREDClientFetchData:
    """測試 FREDClient.fetch_data 方法。"""

    def test_fetch_data_success(
        self, mock_session_get, fred_client_fixture: FREDClient
    ):
        """測試成功獲取並處理觀測數據。"""
        series_id = "DGS10"
        mock_json_response = {
            "observations": [
                {"date": "2023-01-01", "value": "3.88"},
                {"date": "2023-01-02", "value": "3.85"},
                {"date": "2023-01-03", "value": "."},  # 無效值
            ]
        }
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_json_response
        mock_session_get.return_value = mock_response_obj

        result_df = fred_client_fixture.fetch_data(
            symbol=series_id,
            observation_start="2023-01-01",
            observation_end="2023-01-02",
        )

        expected_params_to_session_get = {
            "series_id": series_id,
            "api_key": TEST_FRED_API_KEY,
            "file_type": "json",
            "observation_start": "2023-01-01",
            "observation_end": "2023-01-02",
        }
        expected_url = f"{fred_client_fixture.base_url}{FRED_OBSERVATIONS_ENDPOINT}"
        mock_session_get.assert_called_once_with(
            expected_url, params=expected_params_to_session_get
        )

        expected_data = {
            "date": pd.to_datetime(["2023-01-01", "2023-01-02"]),
            "series_id": [series_id, series_id],
            "value": [3.88, 3.85],
        }
        expected_df = pd.DataFrame(expected_data)
        assert_frame_equal(result_df, expected_df)

    def test_fetch_data_no_observations_in_response(
        self, mock_session_get, fred_client_fixture: FREDClient
    ):
        """測試 API 成功返回但 'observations' 為空或不存在。"""
        mock_response_obj_empty = MagicMock()
        mock_response_obj_empty.status_code = 200
        mock_response_obj_empty.json.return_value = {"observations": []}
        mock_session_get.return_value = mock_response_obj_empty
        result_df_empty = fred_client_fixture.fetch_data(symbol="EMPTYSERIES")
        assert result_df_empty.empty

        mock_session_get.reset_mock()
        mock_response_obj_none = MagicMock()
        mock_response_obj_none.status_code = 200
        mock_response_obj_none.json.return_value = {}
        mock_session_get.return_value = mock_response_obj_none
        result_df_none = fred_client_fixture.fetch_data(symbol="NOSERIESKEY")
        assert result_df_none.empty

    def test_fetch_data_http_error_from_session_get_propagates(
        self, mock_session_get, fred_client_fixture: FREDClient
    ):
        """測試 session.get 拋出 HTTPError 時，fetch_data 也應拋出。"""
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 400
        # 正確模擬 requests.Response 對象的行為，它本身不包含 raise_for_status 的 side_effect
        # raise_for_status 是在 BaseAPIClient._request 中被調用的
        # 我們需要讓 mock_session_get.return_value.raise_for_status() 拋出異常
        mock_session_get.return_value = mock_response_obj
        # 讓 session.get().raise_for_status() 拋出異常
        mock_response_obj.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "400 Client Error: Bad Request for url: http://simulated.url/fail",  # 匹配實際錯誤信息模式
            response=mock_response_obj,
        )

        with pytest.raises(
            requests.exceptions.HTTPError,
            match="400 Client Error: Bad Request for url: http://simulated.url/fail",
        ):
            fred_client_fixture.fetch_data(symbol="FAIL")

    def test_fetch_data_all_fred_params_passed_correctly(
        self, mock_session_get, fred_client_fixture: FREDClient
    ):
        """測試所有可選的 FRED API 參數是否都正確準備並傳遞給 _request。"""
        series_id = "GDPC1"
        kwargs_to_pass = {
            "realtime_start": "2020-01-01",
            "realtime_end": "2020-01-31",
            "limit": 10,
            "offset": 5,
            "sort_order": "desc",
            "observation_start": "2019-01-01",
            "observation_end": "2019-12-31",
        }
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = {"observations": []}
        mock_session_get.return_value = mock_response_obj

        fred_client_fixture.fetch_data(symbol=series_id, **kwargs_to_pass)

        expected_params_to_session_get = {
            "series_id": series_id,
            "api_key": TEST_FRED_API_KEY,
            "file_type": "json",
            **kwargs_to_pass,
        }
        expected_params_to_session_get["limit"] = str(kwargs_to_pass["limit"])
        expected_params_to_session_get["offset"] = str(kwargs_to_pass["offset"])

        expected_url = f"{fred_client_fixture.base_url}{FRED_OBSERVATIONS_ENDPOINT}"
        mock_session_get.assert_called_once_with(
            expected_url, params=expected_params_to_session_get
        )


@patch.object(FREDClient, "fetch_data")  # Mock FREDClient.fetch_data 仍然適用於此測試類
class TestFREDClientGetMultipleSeries:
    """測試 FREDClient.get_multiple_series 方法。"""

    def test_get_multiple_series_success(
        self, mock_fetch_data, fred_client_fixture: FREDClient
    ):
        """測試成功獲取並合併多個系列。"""
        series_ids = ["DGS10", "CPIAUCSL"]
        df1 = pd.DataFrame(
            {
                "date": pd.to_datetime(["2023-01-01"]),
                "series_id": ["DGS10"],
                "value": [3.5],
            }
        )
        df2 = pd.DataFrame(
            {
                "date": pd.to_datetime(["2023-01-01"]),
                "series_id": ["CPIAUCSL"],
                "value": [200.0],
            }
        )

        def fetch_data_side_effect(symbol, **kwargs):
            if symbol == "DGS10":
                return df1
            if symbol == "CPIAUCSL":
                return df2
            return pd.DataFrame()

        mock_fetch_data.side_effect = fetch_data_side_effect

        result_df = fred_client_fixture.get_multiple_series(
            series_ids, observation_start="2023-01-01"
        )
        expected_df = pd.concat([df1, df2], ignore_index=True)
        assert_frame_equal(result_df, expected_df)

        assert mock_fetch_data.call_count == len(series_ids)
        mock_fetch_data.assert_any_call(symbol="DGS10", observation_start="2023-01-01")
        mock_fetch_data.assert_any_call(
            symbol="CPIAUCSL", observation_start="2023-01-01"
        )

    def test_get_multiple_series_one_fetch_fails_http_error(
        self, mock_fetch_data, fred_client_fixture: FREDClient
    ):
        """測試當 fetch_data 對某個 series_id 拋出 HTTPError 時，get_multiple_series 如何處理。"""
        series_ids = ["DGS10", "FAIL_ID_HTTP", "UNRATE"]
        df_dgs10 = pd.DataFrame(
            {
                "date": pd.to_datetime(["2023-01-01"]),
                "series_id": ["DGS10"],
                "value": [3.5],
            }
        )
        df_unrate = pd.DataFrame(
            {
                "date": pd.to_datetime(["2023-01-01"]),
                "series_id": ["UNRATE"],
                "value": [3.8],
            }
        )

        def fetch_data_side_effect(symbol, **kwargs):
            if symbol == "DGS10":
                return df_dgs10
            if symbol == "FAIL_ID_HTTP":
                raise requests.exceptions.HTTPError(
                    "Simulated HTTP Error for FAIL_ID_HTTP"
                )
            if symbol == "UNRATE":
                return df_unrate
            return pd.DataFrame()

        mock_fetch_data.side_effect = fetch_data_side_effect

        result_df = fred_client_fixture.get_multiple_series(series_ids)
        # 預期只包含成功的系列
        expected_df = pd.concat([df_dgs10, df_unrate], ignore_index=True)
        assert_frame_equal(result_df, expected_df)
        assert mock_fetch_data.call_count == len(series_ids)  # 即使有異常，每個都嘗試了

    def test_get_multiple_series_all_fail_or_empty(
        self, mock_fetch_data, fred_client_fixture: FREDClient
    ):
        """測試所有系列都獲取失敗或返回空數據。"""
        series_ids = ["FAIL1", "EMPTY2"]

        def fetch_data_side_effect(symbol, **kwargs):
            if symbol == "FAIL1":
                # 模擬 fetch_data 捕獲 ConnectionError 並返回空 DataFrame
                # （基於我們對 FREDClient.fetch_data 錯誤處理的修改）
                print(
                    f"Mocking ConnectionError for {symbol}, fetch_data should return empty DF"
                )
                return pd.DataFrame()
            if symbol == "EMPTY2":
                return pd.DataFrame()  # 空 DataFrame
            return pd.DataFrame()

        mock_fetch_data.side_effect = fetch_data_side_effect

        result_df = fred_client_fixture.get_multiple_series(series_ids)
        assert result_df.empty
        # 驗證 fetch_data 確實被調用了兩次
        assert mock_fetch_data.call_count == len(series_ids)


# pytest tests/unit/core/clients/test_fred.py -v
