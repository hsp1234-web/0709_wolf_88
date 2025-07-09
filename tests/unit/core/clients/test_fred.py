# tests/unit/core/clients/test_fred.py
# 針對 core.clients.fred 模듈的單元測試。

import pytest
import pandas as pd
from pandas.testing import assert_frame_equal
from unittest.mock import patch, MagicMock
import os
import requests # 用於 requests.exceptions

# 假設 core 模組在 PYTHONPATH 中，或 pytest 能夠找到它
from core.clients.fred import FREDAPIClient, FRED_API_BASE_URL

# 測試用的 API Key
TEST_FRED_API_KEY = "test_fred_api_key_456"

@pytest.fixture
def client_with_key():
    """提供一個已設定 API Key 的 FREDAPIClient 實例。"""
    with patch.dict(os.environ, {"FRED_API_KEY": TEST_FRED_API_KEY}):
        client = FREDAPIClient()
    return client

@pytest.fixture
def client_no_key_in_env():
    """確保環境變數中沒有 FRED_API_KEY。"""
    original_key = os.environ.pop("FRED_API_KEY", None)
    yield
    if original_key is not None:
        os.environ["FRED_API_KEY"] = original_key

class TestFREDAPIClientInitialization:
    """測試 FREDAPIClient 的初始化過程。"""

    def test_init_with_key_arg(self, client_no_key_in_env):
        client = FREDAPIClient(api_key="param_key")
        assert client.api_key == "param_key"

    def test_init_with_env_variable(self):
        with patch.dict(os.environ, {"FRED_API_KEY": "env_key"}):
            client = FREDAPIClient()
            assert client.api_key == "env_key"

    def test_init_no_key_raises_value_error(self, client_no_key_in_env):
        with pytest.raises(ValueError, match="FRED API Key 未設定"):
            FREDAPIClient()

@patch('requests.get') # Mock requests.get 以避免真實網路請求
class TestFREDAPIGetSeriesObservations:
    """測試 FREDAPIClient.get_series_observations 方法。"""

    def test_get_series_observations_success(self, mock_requests_get, client_with_key):
        """測試成功獲取並處理觀測數據。"""
        series_id = "DGS10"
        mock_json_response = {
            "realtime_start": "2023-01-01",
            "realtime_end": "2023-01-10",
            "observation_start": "1900-01-01", # API 回應中的，非請求參數
            "observation_end": "2023-01-10",
            "units": "lin",
            "output_type": 1,
            "file_type": "json",
            "order_by": "observation_date",
            "sort_order": "asc",
            "count": 2,
            "offset": 0,
            "limit": 100000,
            "observations": [
                {"realtime_start": "2023-01-05", "realtime_end": "2023-01-05", "date": "2023-01-01", "value": "3.88"},
                {"realtime_start": "2023-01-06", "realtime_end": "2023-01-06", "date": "2023-01-02", "value": "3.85"},
                {"realtime_start": "2023-01-07", "realtime_end": "2023-01-07", "date": "2023-01-03", "value": "."}, # 無效值
            ]
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_json_response
        mock_requests_get.return_value = mock_response

        result_df = client_with_key.get_series_observations(series_id, observation_start="2023-01-01", observation_end="2023-01-02")

        expected_params = {
            'series_id': series_id,
            'api_key': TEST_FRED_API_KEY,
            'file_type': 'json',
            'observation_start': "2023-01-01",
            'observation_end': "2023-01-02"
        }
        mock_requests_get.assert_called_once_with(FRED_API_BASE_URL, params=expected_params)

        expected_data = {
            'date': pd.to_datetime(["2023-01-01", "2023-01-02"]),
            'series_id': [series_id, series_id],
            'value': [3.88, 3.85]
        }
        expected_df = pd.DataFrame(expected_data)

        assert_frame_equal(result_df, expected_df)

    def test_get_series_observations_no_data(self, mock_requests_get, client_with_key):
        """測試 API 成功返回但 'observations' 為空或不存在。"""
        series_id = "EMPTYSERIES"
        mock_json_response_empty = {"observations": []}
        mock_json_response_none = {} # 'observations' 鍵不存在

        mock_response = MagicMock()
        mock_response.status_code = 200

        # 情況1: observations 是空列表
        mock_response.json.return_value = mock_json_response_empty
        mock_requests_get.return_value = mock_response
        result_df_empty = client_with_key.get_series_observations(series_id)
        assert isinstance(result_df_empty, pd.DataFrame)
        assert result_df_empty.empty

        # 情況2: observations 鍵不存在
        mock_response.json.return_value = mock_json_response_none
        mock_requests_get.return_value = mock_response
        result_df_none = client_with_key.get_series_observations(series_id)
        assert isinstance(result_df_none, pd.DataFrame)
        assert result_df_none.empty

    def test_get_series_observations_http_error(self, mock_requests_get, client_with_key):
        """測試發生 HTTP 錯誤 (例如 400 Bad Request for invalid series_id)。"""
        series_id = "INVALID_ID"
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error_code":400,"error_message":"Bad Request. The series_id provided does not exist."}'
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Simulated HTTP Error 400")
        mock_requests_get.return_value = mock_response

        result_df = client_with_key.get_series_observations(series_id)
        assert result_df is None

    def test_get_series_observations_network_error(self, mock_requests_get, client_with_key):
        """測試發生網路請求錯誤。"""
        mock_requests_get.side_effect = requests.exceptions.ConnectionError("Simulated Connection Error")

        result_df = client_with_key.get_series_observations("ANY_ID")
        assert result_df is None

    def test_get_series_observations_all_params(self, mock_requests_get, client_with_key):
        """測試所有可選參數是否正確傳遞。"""
        series_id = "GDPC1"
        params_to_test = {
            "realtime_start": "2020-01-01",
            "realtime_end": "2020-01-31",
            "limit": 10,
            "offset": 5,
            "sort_order": "desc",
            "observation_start": "2019-01-01",
            "observation_end": "2019-12-31"
        }

        # 預期 API 請求中的參數 (limit 和 offset 應為字串)
        expected_api_params = {
            'series_id': series_id,
            'api_key': TEST_FRED_API_KEY,
            'file_type': 'json',
            **params_to_test # Python 3.9+
        }
        expected_api_params['limit'] = str(params_to_test['limit'])
        expected_api_params['offset'] = str(params_to_test['offset'])


        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"observations": []} # 返回內容不重要，重點是參數
        mock_requests_get.return_value = mock_response

        client_with_key.get_series_observations(series_id, **params_to_test)
        mock_requests_get.assert_called_once_with(FRED_API_BASE_URL, params=expected_api_params)


@patch.object(FREDAPIClient, 'get_series_observations') # Mock get_series_observations
class TestFREDAPIGetMultipleSeries:
    """測試 FREDAPIClient.get_multiple_series 方法。"""

    def test_get_multiple_series_success(self, mock_get_series_obs, client_with_key):
        """測試成功獲取並合併多個系列。"""
        series_ids = ["DGS10", "CPIAUCSL"]
        df1_data = {'date': pd.to_datetime(['2023-01-01']), 'series_id': ["DGS10"], 'value': [3.5]}
        df2_data = {'date': pd.to_datetime(['2023-01-01']), 'series_id': ["CPIAUCSL"], 'value': [200.0]}
        df1 = pd.DataFrame(df1_data)
        df2 = pd.DataFrame(df2_data)

        # 設定 mock 方法的 side_effect，使其根據 series_id 返回不同的 DataFrame
        def side_effect_func(series_id_arg, **kwargs):
            if series_id_arg == "DGS10": return df1
            if series_id_arg == "CPIAUCSL": return df2
            return pd.DataFrame()
        mock_get_series_obs.side_effect = side_effect_func

        result_df = client_with_key.get_multiple_series(series_ids, observation_start="2023-01-01")

        expected_df = pd.concat([df1, df2], ignore_index=True)
        assert_frame_equal(result_df, expected_df)

        # 驗證 get_series_observations 被正確調用
        assert mock_get_series_obs.call_count == len(series_ids)
        mock_get_series_obs.assert_any_call("DGS10", observation_start="2023-01-01")
        mock_get_series_obs.assert_any_call("CPIAUCSL", observation_start="2023-01-01")

    def test_get_multiple_series_one_fails(self, mock_get_series_obs, client_with_key):
        """測試部分系列獲取失敗，但其他成功。"""
        series_ids = ["DGS10", "FAIL_ID", "UNRATE"]
        df_dgs10 = pd.DataFrame({'date': pd.to_datetime(['2023-01-01']), 'series_id': ["DGS10"], 'value': [3.5]})
        df_unrate = pd.DataFrame({'date': pd.to_datetime(['2023-01-01']), 'series_id': ["UNRATE"], 'value': [3.8]})

        def side_effect_func(series_id_arg, **kwargs):
            if series_id_arg == "DGS10": return df_dgs10
            if series_id_arg == "FAIL_ID": return None # 模擬失敗
            if series_id_arg == "UNRATE": return df_unrate
            return pd.DataFrame()
        mock_get_series_obs.side_effect = side_effect_func

        result_df = client_with_key.get_multiple_series(series_ids)
        expected_df = pd.concat([df_dgs10, df_unrate], ignore_index=True)
        assert_frame_equal(result_df, expected_df)

    def test_get_multiple_series_all_fail_or_empty(self, mock_get_series_obs, client_with_key):
        """測試所有系列都獲取失敗或返回空數據。"""
        series_ids = ["FAIL1", "EMPTY2"]

        def side_effect_func(series_id_arg, **kwargs):
            if series_id_arg == "FAIL1": return None
            if series_id_arg == "EMPTY2": return pd.DataFrame() # 空 DataFrame
            return None
        mock_get_series_obs.side_effect = side_effect_func

        result_df = client_with_key.get_multiple_series(series_ids)
        assert isinstance(result_df, pd.DataFrame)
        assert result_df.empty

# 運行測試指令:
# pytest tests/unit/core/clients/test_fred.py -v
# 或在專案根目錄:
# python -m pytest -v
# (需要安裝 pytest, pandas, requests)
