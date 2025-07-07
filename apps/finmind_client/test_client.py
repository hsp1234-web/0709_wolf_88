# apps/finmind_client/test_client.py
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from io import StringIO
import os
import sys
from datetime import datetime

# 將專案根目錄加到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from apps.finmind_client.client import FinMindClient, BASE_URL # Import BASE_URL

# 模擬的 API Token
MOCK_API_TOKEN = "test_token_12345"

def mock_successful_json_response(data_list: list):
    """輔助函數：建立一個模擬成功的 JSON API 回應"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": 200, "msg": "success", "data": data_list}
    mock_resp.headers = {'Content-Type': 'application/json'}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp

def mock_successful_csv_response(csv_string: str):
    """輔助函數：建立一個模擬成功的 CSV API 回應"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = csv_string
    mock_resp.headers = {'Content-Type': 'text/csv; charset=utf-8'}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp

def mock_failed_response(status_code: int, error_message: str = "API Error"):
    """輔助函數：建立一個模擬失敗的 API 回應"""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = {"status": status_code, "msg": error_message, "data": []}
    mock_resp.headers = {'Content-Type': 'application/json'}
    # mock requests.HTTPError for raise_for_status
    mock_resp.raise_for_status = MagicMock(side_effect=requests.exceptions.HTTPError(response=mock_resp))
    return mock_resp

# 為了 mock_failed_response 的 side_effect，我們需要 requests.exceptions.HTTPError
# 如果環境中沒有 requests，測試會出錯，所以我們也 mock 它 (雖然 client.py 會導入)
try:
    import requests.exceptions
except ImportError:
    class MockHTTPError(Exception): # 基本的模擬異常
        def __init__(self, response=None):
            self.response = response

    class MockRequestsModule:
        class exceptions:
            HTTPError = MockHTTPError

    requests = MockRequestsModule()


class TestFinMindClient(unittest.TestCase):

    def setUp(self):
        """在每個測試方法執行前呼叫"""
        # 直接傳遞 MOCK_API_TOKEN 給 client，而不是依賴 setUp 中的 patch.dict 來影響模組級變數
        self.client = FinMindClient(api_token=MOCK_API_TOKEN)
        self.test_stock_id = "2330"
        self.test_start_date = "2023-01-01"
        self.test_end_date = "2023-01-05"

    def test_initialization_with_provided_token(self):
        """測試使用提供的 token 初始化"""
        client = FinMindClient(api_token="custom_token")
        self.assertEqual(client.api_token, "custom_token")

    @patch.dict(os.environ, {"FINMIND_API_TOKEN": ""}, clear=True) # 確保環境變數 FINMIND_API_TOKEN 為空或不存在
    def test_initialization_without_token_or_env_raises_error(self):
        """測試未提供 token 且環境變數未設定時拋出錯誤"""
        # 為了讓 client.py 中的 os.getenv 能取到 patch 的值，需要在 patch 生效期間導入或重新加載
        # 但更簡單的方式是，確保 client 初始化時不傳 token
        with self.assertRaisesRegex(ValueError, "FinMind API token 未設定"):
            FinMindClient(api_token=None) # 明確傳遞 None

    @patch.dict(os.environ, {'FINMIND_API_TOKEN': 'env_token_test'}, clear=True)
    def test_initialization_with_env_variable_and_no_arg(self):
        """測試未傳入 token 時，從環境變數讀取 token 初始化"""
        # 需要在 patch 的上下文中重新導入或讓 client 重新讀取環境變數
        # 最直接的方法是 patch client.py 內部的 FINMIND_API_TOKEN 變數，或者 patch os.getenv
        with patch('apps.finmind_client.client.FINMIND_API_TOKEN', 'env_token_test'):
             # 重新導入或特定修改使得 client 初始化時能看到 patch 後的環境變數
             # 或者，直接在 client 內部修改為優先讀取構造函數參數
             # 目前 client.py 的設計是: self.api_token = api_token or FINMIND_API_TOKEN
             # 所以如果 api_token 是 None, 會 fallback 到 (可能被 patch 的) FINMIND_API_TOKEN
            client = FinMindClient(api_token=None) # 傳入 None 以觸發 FINMIND_API_TOKEN 的讀取
            self.assertEqual(client.api_token, 'env_token_test')

    # 測試 client 初始化時 api_token 參數優先於環境變數
    @patch.dict(os.environ, {'FINMIND_API_TOKEN': 'env_should_be_ignored'}, clear=True)
    def test_initialization_with_arg_overrides_env_variable(self):
        """測試初始化時傳入的 api_token 優先於環境變數"""
        # client.py 的邏輯是 self.api_token = api_token or FINMIND_API_TOKEN
        # 如果 api_token 不是 None，則 FINMIND_API_TOKEN 不會被使用
        client = FinMindClient(api_token="arg_token_should_be_used")
        self.assertEqual(client.api_token, "arg_token_should_be_used")


    @patch('apps.finmind_client.client.requests.get')
    def test_get_taiwan_stock_institutional_investors_buy_sell_success_json(self, mock_get):
        """測試成功獲取三大法人買賣超數據 (JSON response)"""
        mock_data = [
            {"date": "2023-01-02", "stock_id": "2330", "buy": 1000, "sell": 500, "name": "ForeignInvestor"},
            {"date": "2023-01-02", "stock_id": "2330", "buy": 200, "sell": 100, "name": "InvestmentTrust"},
        ]
        mock_get.return_value = mock_successful_json_response(mock_data)

        df = self.client.get_taiwan_stock_institutional_investors_buy_sell(
            self.test_stock_id, self.test_start_date, self.test_end_date
        )
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]['name'], "ForeignInvestor")

        expected_params = {
            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
            "data_id": self.test_stock_id,
            "start_date": self.test_start_date,
            "end_date": self.test_end_date,
            "token": MOCK_API_TOKEN
        }
        mock_get.assert_called_once()
        # 比較 call_args[1] (kwargs) 中的 params
        self.assertEqual(mock_get.call_args[1]['params'], expected_params)


    @patch('apps.finmind_client.client.requests.get')
    def test_get_taiwan_stock_institutional_investors_buy_sell_success_csv(self, mock_get):
        """測試成功獲取三大法人買賣超數據 (CSV response)"""
        csv_data_string = "date,stock_id,buy,sell,name\n2023-01-02,2330,1000,500,ForeignInvestor\n2023-01-02,2330,200,100,InvestmentTrust"
        mock_get.return_value = mock_successful_csv_response(csv_data_string)

        df = self.client.get_taiwan_stock_institutional_investors_buy_sell(
            self.test_stock_id, self.test_start_date, self.test_end_date
        )
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]['name'], "ForeignInvestor")
        self.assertEqual(df.iloc[0]['buy'], 1000)


    @patch('apps.finmind_client.client.requests.get')
    def test_get_financial_statement_success(self, mock_get):
        """測試成功獲取財務報表數據"""
        mock_data = [
            {"date": "2023-03-31", "stock_id": "2330", "type": "AccountsReceivable", "value": 100000},
            {"date": "2023-03-31", "stock_id": "2330", "type": "CashAndCashEquivalents", "value": 200000},
        ]
        mock_get.return_value = mock_successful_json_response(mock_data)

        df = self.client.get_financial_statement(self.test_stock_id, "2023-01-01", "BalanceSheet")
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]['type'], "AccountsReceivable")

        expected_params = {
            "dataset": "BalanceSheet",
            "data_id": self.test_stock_id,
            "start_date": "2023-01-01",
            "token": MOCK_API_TOKEN
        }
        mock_get.assert_called_once_with(BASE_URL, params=expected_params, headers=unittest.mock.ANY) # Use module-level BASE_URL


    @patch('apps.finmind_client.client.requests.get')
    def test_get_taiwan_stock_month_revenue_success(self, mock_get):
        """測試成功獲取月營收數據"""
        mock_data = [
            {"date":"2023-01-10","stock_id":"2330","country":"Taiwan","revenue":200000000,"revenue_month":1,"revenue_year":2023},
            {"date":"2023-02-10","stock_id":"2330","country":"Taiwan","revenue":180000000,"revenue_month":2,"revenue_year":2023}
        ]
        mock_get.return_value = mock_successful_json_response(mock_data)

        df = self.client.get_taiwan_stock_month_revenue(self.test_stock_id, self.test_start_date)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]['revenue_year'], 2023)

        expected_params = {
            "dataset": "TaiwanStockMonthRevenue",
            "data_id": self.test_stock_id,
            "start_date": self.test_start_date,
            "end_date": datetime.now().strftime("%Y-%m-%d"), # 預設 end_date
            "token": MOCK_API_TOKEN
        }
        mock_get.assert_called_once()
        # 比較 call_args[1] (kwargs) 中的 params
        self.assertEqual(mock_get.call_args[1]['params'], expected_params)


    @patch('apps.finmind_client.client.requests.get')
    def test_api_error_returns_none(self, mock_get):
        """測試 API 回應錯誤時，方法返回 None"""
        mock_get.return_value = mock_failed_response(500, "Internal Server Error")

        df = self.client.get_taiwan_stock_per_day(self.test_stock_id, self.test_start_date)
        self.assertIsNone(df)

    @patch('apps.finmind_client.client.requests.get')
    def test_request_exception_returns_none(self, mock_get):
        """測試請求過程中發生異常時 (例如網路問題)，方法返回 None"""
        mock_get.side_effect = requests.exceptions.RequestException("Connection error")

        df = self.client.get_taiwan_stock_per_day(self.test_stock_id, self.test_start_date)
        self.assertIsNone(df)

    @patch('apps.finmind_client.client.requests.get')
    def test_empty_data_returns_empty_dataframe(self, mock_get):
        """測試 API 回應成功但 data 欄位為空列表時，返回空的 DataFrame"""
        mock_get.return_value = mock_successful_json_response([]) # data is empty list

        df = self.client.get_taiwan_stock_per_day(self.test_stock_id, self.test_start_date)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)

    @patch('apps.finmind_client.client.requests.get')
    def test_get_taiwan_stock_per_day_success(self, mock_get):
        """測試成功獲取個股日成交資訊"""
        mock_data = [
            {"date":"2023-01-02","stock_id":"2330","Trading_Volume":5000,"Trading_money":2500000,"open":500.0,"max":502.0,"min":499.0,"close":501.0,"spread":1.0,"Trading_turnover":10000},
        ]
        mock_get.return_value = mock_successful_json_response(mock_data)

        df = self.client.get_taiwan_stock_per_day(self.test_stock_id, self.test_start_date, self.test_end_date)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertEqual(df.iloc[0]['stock_id'], self.test_stock_id)

        expected_params = {
            "dataset": "TaiwanStockPrice",
            "data_id": self.test_stock_id,
            "start_date": self.test_start_date,
            "end_date": self.test_end_date,
            "token": MOCK_API_TOKEN
        }
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args[1]['params'], expected_params)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

"""
此 `test_client.py` 檔案包含針對 `FinMindClient` 類別的單元測試。

測試內容涵蓋：
1.  **初始化**:
    *   使用提供的 API Token 初始化。
    *   未提供 Token 且環境變數未設定時拋出 `ValueError`。
    *   從環境變數讀取 Token 初始化。
2.  **API 方法調用**:
    *   針對 `get_taiwan_stock_institutional_investors_buy_sell`, `get_financial_statement`, `get_taiwan_stock_month_revenue`, `get_taiwan_stock_per_day` 等主要方法。
    *   **成功情況**: 模擬 API 返回成功的 JSON 和 CSV 回應，驗證返回的 DataFrame 是否符合預期。
    *   **API 錯誤**: 模擬 API 返回錯誤狀態碼 (例如 500)，驗證客戶端方法是否返回 `None`。
    *   **請求異常**: 模擬 `requests.get` 拋出 `RequestException` (例如網路問題)，驗證客戶端方法是否返回 `None`。
    *   **空數據情況**: 模擬 API 返回成功但數據列表為空，驗證客戶端方法是否返回一個空的 DataFrame。
3.  **參數驗證**: 驗證調用 `requests.get` 時傳遞的 URL 和 `params` 是否正確。

使用 `unittest.mock.patch` 來模擬 `requests.get` 的行為，避免實際發送網路請求，使得測試更快速且獨立於外部服務。
輔助函數 `mock_successful_json_response`, `mock_successful_csv_response`, `mock_failed_response` 用於簡化模擬 API 回應的建立。

若要執行測試，可以在 `apps/finmind_client/` 目錄下執行 `python -m unittest test_client.py`。
或者，如果配置了測試運行器 (test runner)，它可以自動發現並執行這些測試。
"""
