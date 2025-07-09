# tests/unit/core/clients/test_nyfed.py
# 針對 core.clients.nyfed 模組的單元測試。

import pytest
import pandas as pd
from pandas.testing import assert_frame_equal
from unittest.mock import patch, MagicMock, call
from io import BytesIO
import requests # 用於 requests.exceptions

# 假設 core 模組在 PYTHONPATH 中，或 pytest 能夠找到它
from core.clients.nyfed import NYFedAPIClient, NYFED_DATA_CONFIGS # 導入預設配置以供參考

# 輔助函數：創建一個模擬的 Excel BytesIO 物件
def create_mock_excel_bytes(data_dict: dict, sheet_name="Sheet1") -> BytesIO:
    """根據字典數據創建一個模擬的 Excel (xlsx) BytesIO 物件。"""
    df = pd.DataFrame(data_dict)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0) # 重置指標到開頭，以便 pd.read_excel 可以讀取
    return output

# --- 測試用的模擬 Excel 數據 ---
# 模擬 SBN 類型 Excel 的數據
mock_sbn_excel_data = {
    "AS OF DATE": ["2023-01-01", "2023-01-01", "2023-01-02"],
    "TIME SERIES": ["SERIES_A", "SERIES_B", "SERIES_A"], # SBN 的 TIME SERIES 欄位通常不直接用於加總篩選
    "VALUE (MILLIONS)": [100, 50, 75]
}
mock_sbn_excel_bytes = create_mock_excel_bytes(mock_sbn_excel_data)

# 模擬 SBP 類型 Excel 的數據
mock_sbp_excel_data = {
    "AS OF DATE": ["2023-02-01", "2023-02-01", "2023-02-01", "2023-02-02"],
    "TIME SERIES": ["CODE1", "CODE2", "OTHER_CODE", "CODE1"], # SBP 會根據 cols_to_sum_if_sbp 篩選
    "VALUE (MILLIONS)": [200, 100, 50, 150]
}
mock_sbp_excel_bytes = create_mock_excel_bytes(mock_sbp_excel_data)

# 測試用的 NYFed 配置 (簡化版)
mock_test_config_sbn = {
    "url": "http://fakeurl.com/sbn_data.xlsx", "type": "SBN", "sheet_name": 0,
    "header_row": 0, "date_column_names": ["AS OF DATE"], "value_column_name": "VALUE (MILLIONS)",
    "notes": "Mock SBN data"
}
mock_test_config_sbp = {
    "url": "http://fakeurl.com/sbp_data.xlsx", "type": "SBP", "sheet_name": 0,
    "header_row": 0, "date_column_names": ["AS OF DATE"], "value_column_name": "VALUE (MILLIONS)",
    "cols_to_sum_if_sbp": ["CODE1", "CODE2"], "notes": "Mock SBP data"
}

@pytest.fixture
def nyfed_client():
    """提供一個 NYFedAPIClient 實例，使用模擬配置。"""
    # 在測試時，通常會傳入模擬的配置，或者 patch 掉 NYFED_DATA_CONFIGS
    return NYFedAPIClient(data_configs=[mock_test_config_sbn, mock_test_config_sbp])

@pytest.fixture
def nyfed_client_default_config():
    """提供一個使用預設 NYFED_DATA_CONFIGS 的 NYFedAPIClient 實例 (用於測試預設行為)。"""
    return NYFedAPIClient()


class TestNYFedAPIClientInitialization:
    """測試 NYFedAPIClient 的初始化。"""
    def test_init_with_default_configs(self, nyfed_client_default_config):
        assert nyfed_client_default_config.data_configs == NYFED_DATA_CONFIGS
        assert len(nyfed_client_default_config.data_configs) > 0

    def test_init_with_custom_configs(self):
        custom_configs = [mock_test_config_sbn]
        client = NYFedAPIClient(data_configs=custom_configs)
        assert client.data_configs == custom_configs

@patch('requests.get')
class TestNYFedDownloadExcel:
    """測試 _download_excel_to_dataframe 方法。"""

    def test_download_success(self, mock_requests_get, nyfed_client):
        """測試成功下載並讀取 Excel。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = mock_sbn_excel_bytes.getvalue() # 使用 BytesIO 的內容
        mock_requests_get.return_value = mock_response

        df = nyfed_client._download_excel_to_dataframe(mock_test_config_sbn)

        mock_requests_get.assert_called_once_with(mock_test_config_sbn["url"], timeout=60)
        assert df is not None
        assert not df.empty
        # 驗證欄位名是否已大寫並清理 (pd.read_excel 後，我們的代碼會處理)
        assert "AS OF DATE" in df.columns
        assert "VALUE (MILLIONS)" in df.columns

    def test_download_http_error(self, mock_requests_get, nyfed_client):
        """測試下載時發生 HTTP 錯誤。"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Simulated 404 Error")
        mock_requests_get.return_value = mock_response

        df = nyfed_client._download_excel_to_dataframe(mock_test_config_sbn)
        assert df is None

    def test_download_network_error(self, mock_requests_get, nyfed_client):
        """測試下載時發生網路錯誤。"""
        mock_requests_get.side_effect = requests.exceptions.ConnectionError("Simulated Connection Error")
        df = nyfed_client._download_excel_to_dataframe(mock_test_config_sbn)
        assert df is None

    def test_download_bad_excel_file(self, mock_requests_get, nyfed_client):
        """測試下載的檔案不是有效的 Excel 格式。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"this is not an excel file" # 無效內容
        mock_requests_get.return_value = mock_response

        # pandas.read_excel 在讀取無效檔案時可能引發多種錯誤，例如 zipfile.BadZipFile
        # (openpyxl 引擎底層使用 zipfile) 或 ValueError
        # 這裡我們期望它返回 None，因為內部有 try-except
        df = nyfed_client._download_excel_to_dataframe(mock_test_config_sbn)
        assert df is None


class TestNYFedParseDealerPositions:
    """測試 _parse_dealer_positions 方法。"""

    def test_parse_sbn_type_success(self, nyfed_client):
        """測試成功解析 SBN 類型的數據。"""
        raw_df_sbn = pd.DataFrame(mock_sbn_excel_data)
        # 模擬 _download_excel_to_dataframe 中對欄位名的處理
        raw_df_sbn.columns = [str(col).strip().upper() for col in raw_df_sbn.columns]

        parsed_df = nyfed_client._parse_dealer_positions(raw_df_sbn, mock_test_config_sbn)

        expected_data = {
            'Date': pd.to_datetime(['2023-01-01', '2023-01-02']),
            'Total_Positions': [150 * 1_000_000, 75 * 1_000_000] # (100+50) for 01-01, 75 for 01-02
        }
        expected_df = pd.DataFrame(expected_data)

        assert_frame_equal(parsed_df, expected_df)

    def test_parse_sbp_type_success(self, nyfed_client):
        """測試成功解析 SBP 類型的數據 (需要篩選和加總特定欄位)。"""
        raw_df_sbp = pd.DataFrame(mock_sbp_excel_data)
        raw_df_sbp.columns = [str(col).strip().upper() for col in raw_df_sbp.columns]

        parsed_df = nyfed_client._parse_dealer_positions(raw_df_sbp, mock_test_config_sbp)

        # 根據 mock_test_config_sbp["cols_to_sum_if_sbp"] = ["CODE1", "CODE2"]
        # 2023-02-01: CODE1 (200) + CODE2 (100) = 300
        # 2023-02-02: CODE1 (150)
        expected_data = {
            'Date': pd.to_datetime(['2023-02-01', '2023-02-02']),
            'Total_Positions': [300 * 1_000_000, 150 * 1_000_000]
        }
        expected_df = pd.DataFrame(expected_data)

        assert_frame_equal(parsed_df, expected_df)

    def test_parse_missing_date_column(self, nyfed_client):
        """測試當日期欄位不存在時的處理。"""
        bad_data = {"SOME_OTHER_DATE_COLUMN": ["2023-01-01"], "VALUE (MILLIONS)": [10]}
        raw_df_bad = pd.DataFrame(bad_data)
        raw_df_bad.columns = [str(col).strip().upper() for col in raw_df_bad.columns]

        parsed_df = nyfed_client._parse_dealer_positions(raw_df_bad, mock_test_config_sbn)
        assert parsed_df.empty
        assert list(parsed_df.columns) == ['Date', 'Total_Positions']


    def test_parse_sbp_missing_cols_to_sum_config(self, nyfed_client):
        """測試 SBP 類型但 config 中缺少 'cols_to_sum_if_sbp'。"""
        raw_df_sbp = pd.DataFrame(mock_sbp_excel_data)
        raw_df_sbp.columns = [str(col).strip().upper() for col in raw_df_sbp.columns]

        bad_sbp_config = mock_test_config_sbp.copy()
        del bad_sbp_config["cols_to_sum_if_sbp"] # 移除關鍵配置

        parsed_df = nyfed_client._parse_dealer_positions(raw_df_sbp, bad_sbp_config)
        assert parsed_df.empty

    def test_parse_sbp_target_series_not_found(self, nyfed_client):
        """測試 SBP 類型，但 'cols_to_sum_if_sbp' 中的 series 在數據中找不到。"""
        raw_df_sbp = pd.DataFrame(mock_sbp_excel_data) # 包含 CODE1, CODE2
        raw_df_sbp.columns = [str(col).strip().upper() for col in raw_df_sbp.columns]

        config_with_wrong_codes = mock_test_config_sbp.copy()
        config_with_wrong_codes["cols_to_sum_if_sbp"] = ["NON_EXISTENT_CODE_A", "NON_EXISTENT_CODE_B"]

        parsed_df = nyfed_client._parse_dealer_positions(raw_df_sbp, config_with_wrong_codes)
        assert parsed_df.empty # 因為篩選後 df_filtered 會是空的


@patch.object(NYFedAPIClient, '_download_excel_to_dataframe')
@patch.object(NYFedAPIClient, '_parse_dealer_positions')
class TestNYFedFetchAllPrimaryDealerPositions:
    """測試 fetch_all_primary_dealer_positions 方法。"""

    def test_fetch_all_success_merges_data(self, mock_parse, mock_download, nyfed_client):
        """測試成功下載、解析並合併來自多個配置的數據。"""
        # 模擬 _download_excel_to_dataframe 返回非空 DataFrame
        mock_download.return_value = pd.DataFrame({"dummy_col": [1]}) # 內容不重要，只要非 None/empty

        # 模擬 _parse_dealer_positions 返回的數據
        df_sbn_parsed = pd.DataFrame({
            'Date': pd.to_datetime(['2023-01-01', '2023-01-03']),
            'Total_Positions': [1000, 1200]
        })
        df_sbp_parsed = pd.DataFrame({
            'Date': pd.to_datetime(['2023-01-01', '2023-01-02']), # 注意日期重疊
            'Total_Positions': [2000, 2100] # 假設 SBP 的數據更優先 (或第一個)
        })

        # 讓 mock_parse 根據調用時的 config 返回不同數據
        # nyfed_client 使用的是 [mock_test_config_sbn, mock_test_config_sbp]
        def parse_side_effect(df_raw, config_arg):
            if config_arg["type"] == "SBN": return df_sbn_parsed
            if config_arg["type"] == "SBP": return df_sbp_parsed
            return pd.DataFrame()
        mock_parse.side_effect = parse_side_effect

        result_df = nyfed_client.fetch_all_primary_dealer_positions()

        # 預期結果：合併後，對於重疊的 '2023-01-01'，應保留第一個 (SBN)
        # 因為 mock_test_config_sbn 在 nyfed_client.data_configs 中是第一個
        expected_data = [
            {'Date': pd.to_datetime('2023-01-01'), 'Total_Positions': 1000}, # 來自 SBN (第一個)
            {'Date': pd.to_datetime('2023-01-02'), 'Total_Positions': 2100}, # 來自 SBP
            {'Date': pd.to_datetime('2023-01-03'), 'Total_Positions': 1200}  # 來自 SBN
        ]
        expected_df = pd.DataFrame(expected_data).sort_values(by='Date').reset_index(drop=True)

        assert_frame_equal(result_df, expected_df)
        assert mock_download.call_count == 2
        assert mock_parse.call_count == 2

    def test_fetch_all_one_source_fails_download(self, mock_parse, mock_download, nyfed_client):
        """測試部分數據源下載失敗。"""
        df_sbp_parsed = pd.DataFrame({'Date': pd.to_datetime(['2023-01-02']), 'Total_Positions': [2100]})

        # 模擬 SBN 下載失敗 (返回 None)，SBP 成功
        def download_side_effect(config_arg):
            if config_arg["type"] == "SBN": return None
            if config_arg["type"] == "SBP": return pd.DataFrame({"dummy": [1]})
            return None
        mock_download.side_effect = download_side_effect

        # 模擬 SBP 解析成功
        mock_parse.side_effect = lambda df_raw, config_arg: df_sbp_parsed if config_arg["type"] == "SBP" else pd.DataFrame()

        result_df = nyfed_client.fetch_all_primary_dealer_positions()
        assert_frame_equal(result_df, df_sbp_parsed) # 只包含 SBP 的數據
        assert mock_download.call_count == 2
        assert mock_parse.call_count == 1 # SBN 下載失敗，不會調用其 parse

    def test_fetch_all_all_sources_fail_or_empty(self, mock_parse, mock_download, nyfed_client):
        """測試所有數據源均下載失敗或返回空數據。"""
        mock_download.return_value = None # 所有下載都失敗
        # 或者 mock_download 成功但 mock_parse 返回空 DataFrame
        # mock_download.return_value = pd.DataFrame({"dummy": [1]})
        # mock_parse.return_value = pd.DataFrame()

        result_df = nyfed_client.fetch_all_primary_dealer_positions()
        assert result_df.empty
        assert list(result_df.columns) == ['Date', 'Total_Positions']

# 運行測試指令:
# pytest tests/unit/core/clients/test_nyfed.py -v
# 或在專案根目錄:
# python -m pytest -v
# (需要安裝 pytest, pandas, requests, openpyxl)
