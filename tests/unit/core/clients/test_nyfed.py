# tests/unit/core/clients/test_nyfed.py
# 針對 core.clients.nyfed 模組的單元測試。

import pytest
import pandas as pd
from pandas.testing import assert_frame_equal
from unittest.mock import patch, MagicMock
from io import BytesIO
import requests  # 用於 requests.exceptions

# 更新導入以反映重構後的客戶端
from core.clients.nyfed import NYFedClient, NYFED_DATA_CONFIGS  # 導入新的 Client


# 輔助函數和 mock 數據保持不變
def create_mock_excel_bytes(data_dict: dict, sheet_name="Sheet1") -> BytesIO:
    df = pd.DataFrame(data_dict)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output


mock_sbn_excel_data = {
    "AS OF DATE": ["2023-01-01", "2023-01-01", "2023-01-02"],
    "TIME SERIES": ["SERIES_A", "SERIES_B", "SERIES_A"],
    "VALUE (MILLIONS)": [100, 50, 75],
}
mock_sbn_excel_bytes = create_mock_excel_bytes(mock_sbn_excel_data)

mock_sbp_excel_data = {
    "AS OF DATE": ["2023-02-01", "2023-02-01", "2023-02-01", "2023-02-02"],
    "TIME SERIES": ["CODE1", "CODE2", "OTHER_CODE", "CODE1"],
    "VALUE (MILLIONS)": [200, 100, 50, 150],
}
mock_sbp_excel_bytes = create_mock_excel_bytes(mock_sbp_excel_data)

mock_test_config_sbn = {
    "url": "http://fakeurl.com/sbn_data.xlsx",
    "type": "SBN",
    "sheet_name": 0,
    "header_row": 0,
    "date_column_names": ["AS OF DATE"],
    "value_column_name": "VALUE (MILLIONS)",
    "notes": "Mock SBN data",
}
mock_test_config_sbp = {
    "url": "http://fakeurl.com/sbp_data.xlsx",
    "type": "SBP",
    "sheet_name": 0,
    "header_row": 0,
    "date_column_names": ["AS OF DATE"],
    "value_column_name": "VALUE (MILLIONS)",
    "cols_to_sum_if_sbp": ["CODE1", "CODE2"],
    "notes": "Mock SBP data",
}


@pytest.fixture
def nyfed_client_fixture():
    """提供一個 NYFedClient 實例，使用模擬配置。"""
    return NYFedClient(data_configs=[mock_test_config_sbn, mock_test_config_sbp])


@pytest.fixture
def nyfed_client_default_config_fixture():
    """提供一個使用預設 NYFED_DATA_CONFIGS 的 NYFedClient 實例。"""
    return NYFedClient()


class TestNYFedClientInitialization:
    """測試 NYFedClient 的初始化。"""

    def test_init_with_default_configs(
        self, nyfed_client_default_config_fixture: NYFedClient
    ):
        assert nyfed_client_default_config_fixture.data_configs == NYFED_DATA_CONFIGS
        assert len(nyfed_client_default_config_fixture.data_configs) > 0
        assert (
            nyfed_client_default_config_fixture.api_key is None
        )  # 驗證 BaseAPIClient 初始化
        assert nyfed_client_default_config_fixture.base_url is None
        assert isinstance(
            nyfed_client_default_config_fixture._session, requests.Session
        )

    def test_init_with_custom_configs(self):
        custom_configs = [mock_test_config_sbn]
        client = NYFedClient(data_configs=custom_configs)
        assert client.data_configs == custom_configs


# NYFedClient._download_excel_to_dataframe 現在使用 self._session.get
# 所以我們需要 mock requests.Session.get
@patch("requests.Session.get")
class TestNYFedClientDownloadExcel:
    """測試 _download_excel_to_dataframe 方法。"""

    def test_download_success(
        self, mock_session_get, nyfed_client_fixture: NYFedClient
    ):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = mock_sbn_excel_bytes.getvalue()
        mock_session_get.return_value = mock_response

        df = nyfed_client_fixture._download_excel_to_dataframe(mock_test_config_sbn)

        # 驗證 nyfed_client_fixture._session.get 被調用
        # nyfed_client_fixture._session 是一個 MagicMock (如果 BaseAPIClient.__init__ 被 mock)
        # 或者是一個真實的 Session 物件。
        # 如果我們 mock requests.Session.get，那麼它會捕獲所有 Session().get 調用。
        mock_session_get.assert_called_once_with(
            mock_test_config_sbn["url"], timeout=60
        )
        assert df is not None
        assert not df.empty
        assert "AS OF DATE" in df.columns

    def test_download_http_error(
        self, mock_session_get, nyfed_client_fixture: NYFedClient
    ):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Simulated 404 Error"
        )
        mock_session_get.return_value = mock_response

        df = nyfed_client_fixture._download_excel_to_dataframe(mock_test_config_sbn)
        assert df is None

    # 其他 _download_excel_to_dataframe 測試 (network error, bad excel) 保持類似，
    # 確保 mock_session_get 的行為被正確觸發。


class TestNYFedClientParseDealerPositions:
    """測試 _parse_dealer_positions 方法 (此方法邏輯未變，測試應仍然通過)。"""

    def test_parse_sbn_type_success(self, nyfed_client_fixture: NYFedClient):
        raw_df_sbn = pd.DataFrame(mock_sbn_excel_data)
        raw_df_sbn.columns = [str(col).strip().upper() for col in raw_df_sbn.columns]
        parsed_df = nyfed_client_fixture._parse_dealer_positions(
            raw_df_sbn, mock_test_config_sbn
        )
        expected_data = {
            "Date": pd.to_datetime(["2023-01-01", "2023-01-02"]),
            "Total_Positions": [150 * 1_000_000, 75 * 1_000_000],
        }
        expected_df = pd.DataFrame(expected_data)
        assert_frame_equal(parsed_df, expected_df)

    def test_parse_sbp_type_success(self, nyfed_client_fixture: NYFedClient):
        raw_df_sbp = pd.DataFrame(mock_sbp_excel_data)
        raw_df_sbp.columns = [str(col).strip().upper() for col in raw_df_sbp.columns]
        parsed_df = nyfed_client_fixture._parse_dealer_positions(
            raw_df_sbp, mock_test_config_sbp
        )
        expected_data = {
            "Date": pd.to_datetime(["2023-02-01", "2023-02-02"]),
            "Total_Positions": [300 * 1_000_000, 150 * 1_000_000],
        }
        expected_df = pd.DataFrame(expected_data)
        assert_frame_equal(parsed_df, expected_df)

    # 其他 _parse_dealer_positions 測試保持不變


# Mock NYFedClient 的內部方法 _download_excel_to_dataframe 和 _parse_dealer_positions
# 以專注測試 fetch_data (原 fetch_all_primary_dealer_positions) 的組合邏輯
@patch.object(NYFedClient, "_download_excel_to_dataframe")
@patch.object(NYFedClient, "_parse_dealer_positions")
class TestNYFedClientFetchData:  # 原 TestNYFedFetchAllPrimaryDealerPositions
    """測試 fetch_data 方法 (取代了 fetch_all_primary_dealer_positions)。"""

    def test_fetch_data_success_merges_data(
        self, mock_parse, mock_download, nyfed_client_fixture: NYFedClient
    ):
        mock_download.return_value = pd.DataFrame({"dummy_col": [1]})
        df_sbn_parsed = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2023-01-01", "2023-01-03"]),
                "Total_Positions": [1000, 1200],
            }
        )
        df_sbp_parsed = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2023-01-01", "2023-01-02"]),
                "Total_Positions": [2000, 2100],
            }
        )

        def parse_side_effect(df_raw, config_arg):
            if config_arg["type"] == "SBN":
                return df_sbn_parsed
            if config_arg["type"] == "SBP":
                return df_sbp_parsed
            return pd.DataFrame()

        mock_parse.side_effect = parse_side_effect

        # 調用新的 fetch_data 方法
        result_df = nyfed_client_fixture.fetch_data(
            symbol="any_symbol_ignored", kwarg_ignored="value"
        )

        expected_data = [
            {"Date": pd.to_datetime("2023-01-01"), "Total_Positions": 1000},
            {"Date": pd.to_datetime("2023-01-02"), "Total_Positions": 2100},
            {"Date": pd.to_datetime("2023-01-03"), "Total_Positions": 1200},
        ]
        expected_df = (
            pd.DataFrame(expected_data).sort_values(by="Date").reset_index(drop=True)
        )
        assert_frame_equal(result_df, expected_df)
        assert mock_download.call_count == len(nyfed_client_fixture.data_configs)
        assert mock_parse.call_count == len(nyfed_client_fixture.data_configs)

    def test_fetch_data_one_source_fails_download(
        self, mock_parse, mock_download, nyfed_client_fixture: NYFedClient
    ):
        df_sbp_parsed = pd.DataFrame(
            {"Date": pd.to_datetime(["2023-01-02"]), "Total_Positions": [2100]}
        )

        def download_side_effect(config_arg):
            if config_arg["type"] == "SBN":
                return None  # SBN 下載失敗
            if config_arg["type"] == "SBP":
                return pd.DataFrame({"dummy": [1]})
            return None

        mock_download.side_effect = download_side_effect
        mock_parse.side_effect = lambda df_raw, config_arg: (
            df_sbp_parsed if config_arg["type"] == "SBP" else pd.DataFrame()
        )

        result_df = nyfed_client_fixture.fetch_data()  # symbol 和 kwargs 被忽略
        assert_frame_equal(result_df, df_sbp_parsed)
        assert mock_download.call_count == len(nyfed_client_fixture.data_configs)
        # SBN 下載失敗，其 parse 不會被調用
        assert (
            mock_parse.call_count == (len(nyfed_client_fixture.data_configs) - 1)
            if any(c["type"] == "SBN" for c in nyfed_client_fixture.data_configs)
            else len(nyfed_client_fixture.data_configs)
        )

    def test_fetch_data_all_sources_fail_or_empty(
        self, mock_parse, mock_download, nyfed_client_fixture: NYFedClient
    ):
        mock_download.return_value = None  # 所有下載都失敗
        result_df = nyfed_client_fixture.fetch_data()
        assert result_df.empty
        assert list(result_df.columns) == ["Date", "Total_Positions"]


# pytest tests/unit/core/clients/test_nyfed.py -v
# (需要安裝 openpyxl: pip install openpyxl)
