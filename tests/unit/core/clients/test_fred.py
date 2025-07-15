# tests/unit/core/clients/test_fred.py
# 針對 core.clients.fred 模組的單元測試。

from unittest.mock import patch

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

# 更新導入以反映重構後的客戶端
from prometheus.core.clients.fred import FredClient  # Corrected import name

# FRED_API_HOST, FRED_OBSERVATIONS_ENDPOINT are not defined in the new client, remove imports

# 測試用的 API Key
TEST_FRED_API_KEY = (
    "test_fred_api_key_456"  # This will be used by mocked get_fred_api_key
)


@pytest.fixture
def mock_get_fred_api_key():
    """Mocks core.config.get_fred_api_key."""
    with patch("prometheus.core.clients.fred.get_fred_api_key") as mock_get_key:
        yield mock_get_key


@pytest.fixture
def fred_client_fixture(mock_get_fred_api_key):
    """提供一個 FredClient 實例，並 mock get_fred_api_key。"""
    mock_get_fred_api_key.return_value = TEST_FRED_API_KEY
    client = FredClient()
    return client


# This fixture is problematic as FredClient now gets key from get_fred_api_key
# @pytest.fixture
# def mock_env_no_fred_key():
#     """確保環境變數中沒有 FRED_API_KEY。"""
#     original_key = os.environ.pop("FRED_API_KEY", None)
#     yield
#     if original_key is not None:
#         os.environ["FRED_API_KEY"] = original_key


class TestFredClientInitialization:  # Renamed for consistency
    """測試 FredClient 的初始化過程。"""

    # This test is invalid as FredClient() doesn't take api_key argument directly.
    # It relies on get_fred_api_key().
    # def test_init_with_key_arg(self, mock_env_no_fred_key):
    #     client = FredClient(api_key="param_key_direct") # FredClient doesn't accept api_key here
    #     assert client.api_key == "param_key_direct"
    #     # assert client.base_url == FRED_API_HOST # FRED_API_HOST is removed
    #     assert isinstance(client._session, requests.Session)

    def test_init_with_api_key_from_config(self, mock_get_fred_api_key):
        mock_get_fred_api_key.return_value = "env_key_for_fred"
        client = FredClient()
        assert client.api_key == "env_key_for_fred"
        # BaseAPIClient's base_url is set, but less relevant for fredapi library itself
        assert client.base_url == "https://api.stlouisfed.org/fred"
        assert hasattr(
            client, "_fred_official_client"
        )  # Check if fredapi lib instance created

    def test_init_no_key_raises_value_error(self, mock_get_fred_api_key):
        mock_get_fred_api_key.side_effect = ValueError("FRED API Key 未設定 (mocked)")
        with pytest.raises(
            ValueError, match=r"FredClient 初始化失敗: FRED API Key 未設定 \(mocked\)"
        ):  # Used raw string
            FredClient()


# FredClient now uses the fredapi library, so we mock fredapi.Fred.get_series
@patch("fredapi.Fred.get_series")  # Correct patch target
class TestFredClientFetchData:  # Renamed for consistency
    """測試 FredClient.fetch_data 方法。"""

    def test_fetch_data_success(
        self,
        mock_fred_get_series,
        fred_client_fixture: FredClient,  # Corrected fixture name
    ):
        """測試成功獲取並處理觀測數據。"""
        series_id = "DGS10"
        # fredapi.Fred.get_series returns a pandas Series
        mock_series_data = pd.Series(
            [3.88, 3.85],
            index=pd.to_datetime(["2023-01-01", "2023-01-02"]),
            name=series_id,
        )
        mock_fred_get_series.return_value = mock_series_data

        result_df = fred_client_fixture.fetch_data(
            symbol=series_id,
            observation_start="2023-01-01",
            observation_end="2023-01-02",
        )

        # Verify that the mocked fredapi.Fred.get_series was called correctly
        mock_fred_get_series.assert_called_once_with(
            series_id=series_id,
            observation_start="2023-01-01",
            observation_end="2023-01-02",
            # Other potential fred_params from FredClient.fetch_data if passed
        )

        # Expected DataFrame structure from FredClient.fetch_data
        expected_df = mock_series_data.to_frame()
        expected_df.index.name = "Date"
        assert_frame_equal(result_df, expected_df)

    def test_fetch_data_empty_series_from_fred_api(
        self, mock_fred_get_series, fred_client_fixture: FredClient
    ):
        """測試 FRED API 返回空 Series。"""
        series_id = "EMPTYSERIES"
        mock_fred_get_series.return_value = pd.Series(
            dtype=float, name=series_id
        )  # Empty series

        result_df = fred_client_fixture.fetch_data(symbol=series_id)

        expected_df = pd.DataFrame(columns=["Date", series_id]).set_index("Date")
        assert_frame_equal(
            result_df, expected_df, check_dtype=False
        )  # Empty DFs might have object dtype for index

    def test_fetch_data_fred_api_exception(
        self, mock_fred_get_series, fred_client_fixture: FredClient
    ):
        """測試 fredapi.Fred.get_series 拋出異常時，fetch_data 返回標準化空 DataFrame。"""
        series_id = "FAILINGSERIES"
        mock_fred_get_series.side_effect = Exception("Mocked fredapi error")

        result_df = fred_client_fixture.fetch_data(symbol=series_id)

        expected_df = pd.DataFrame(columns=["Date", series_id]).set_index("Date")
        assert_frame_equal(result_df, expected_df, check_dtype=False)

    def test_fetch_data_all_fred_params_passed_correctly_to_fredapi(
        self, mock_fred_get_series, fred_client_fixture: FredClient
    ):
        """測試所有可選的 FRED API 參數是否都正確傳遞給 fredapi.Fred.get_series。"""
        series_id = "GDPC1"
        kwargs_to_pass = {
            "observation_start": "2019-01-01",
            "observation_end": "2019-12-31",
            "realtime_start": "2020-01-01",
            "realtime_end": "2020-01-31",
            "limit": 10,
            "offset": 5,
            "sort_order": "desc",
            "aggregation_method": "avg",
            "frequency": "q",
            "units": "lin",
        }
        # fredapi returns a series, even if empty due to params
        mock_fred_get_series.return_value = pd.Series(dtype=float, name=series_id)

        fred_client_fixture.fetch_data(symbol=series_id, **kwargs_to_pass)

        # Construct expected parameters for fredapi.Fred.get_series call
        expected_call_kwargs = {"series_id": series_id, **kwargs_to_pass}

        mock_fred_get_series.assert_called_once_with(**expected_call_kwargs)


# The method get_multiple_series is not defined in the provided core.clients.fred.py (v2.1)
# So, TestFREDClientGetMultipleSeries class should be removed or adapted if the method is re-added.
# For now, I will remove it.
# @patch.object(FredClient, "fetch_data")
# class TestFREDClientGetMultipleSeries:
#     """測試 FredClient.get_multiple_series 方法。"""
#     ... (rest of the class was here)


# pytest tests/unit/core/clients/test_fred.py -v
