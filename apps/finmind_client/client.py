# apps/finmind_client/client.py
import os
import requests
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# 從環境變數讀取 API token
FINMIND_API_TOKEN = os.getenv("FINMIND_API_TOKEN")

# FinMind API 基礎 URL
BASE_URL = "https://api.finmindtrade.com/api/v4/data"

class FinMindClient:
    """
    FinMind API 客戶端，用於獲取台灣市場的財經數據。
    """
    def __init__(self, api_token: Optional[str] = None):
        """
        初始化 FinMindClient。

        Args:
            api_token (Optional[str]): FinMind API token。如果未提供，則從環境變數 FINMIND_API_TOKEN 讀取。
        """
        self.api_token = api_token or FINMIND_API_TOKEN
        if not self.api_token:
            raise ValueError("FinMind API token 未設定。請設定 FINMIND_API_TOKEN 環境變數或在初始化時傳入 api_token。")

    def _make_request(self, params: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        向 FinMind API 發送請求並處理回應。

        Args:
            params (Dict[str, Any]): API 請求參數。

        Returns:
            Optional[pd.DataFrame]: 包含 API 回應數據的 DataFrame，如果請求失敗則返回 None。
        """
        headers = {
            "Authorization": f"Bearer {self.api_token}"
        }
        try:
            response = requests.get(BASE_URL, params=params, headers=headers)
            response.raise_for_status()  # 如果 HTTP 狀態碼是 4xx 或 5xx，則拋出異常

            # FinMind API 有時會返回 CSV 格式的數據
            if 'text/csv' in response.headers.get('Content-Type', ''):
                data = StringIO(response.text)
                df = pd.read_csv(data)
            else: # 假設是 JSON，根據 FinMind API 文件，數據在 'data' 欄位
                json_response = response.json()
                if json_response.get("status") != 200:
                    print(f"FinMind API 錯誤：{json_response.get('msg', '未知錯誤')}")
                    return None
                data_list = json_response.get("data")
                if not data_list:
                    return pd.DataFrame() # 返回空的 DataFrame
                df = pd.DataFrame(data_list)

            return df
        except requests.exceptions.RequestException as e:
            print(f"請求 FinMind API 時發生錯誤：{e}")
            return None
        except Exception as e:
            print(f"處理 FinMind API 回應時發生未知錯誤：{e}")
            return None

    def get_taiwan_stock_institutional_investors_buy_sell(self, data_id: str, start_date: str, end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        獲取三大法人買賣超數據 (外資、投信、自營商)。
        對應分析點 #6。

        Args:
            data_id (str): 股票代碼，例如 "2330"。
            start_date (str): 開始日期，格式 "YYYY-MM-DD"。
            end_date (Optional[str]): 結束日期，格式 "YYYY-MM-DD"。如果為 None，則預設為今天。

        Returns:
            Optional[pd.DataFrame]: 包含三大法人買賣超數據的 DataFrame。
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        params = {
            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
            "data_id": data_id,
            "start_date": start_date,
            "end_date": end_date,
            "token": self.api_token # FinMind API v4 某些端點仍需 token 在參數中
        }
        return self._make_request(params)

    def get_taiwan_stock_per_day(self, data_id: str, start_date: str, end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        獲取個股每日股價與基本資訊 (用於券商分點進出數據分析的前置)。
        注意：FinMind API 並未直接提供個股的「券商分點進出」數據。
        此函數獲取日線數據，可以用於其他分析，但不是直接的券商分點數據。
        若要獲得券商分點數據，通常需要專門的券商 API 或其他數據源。
        這裡暫時獲取日成交資訊作為替代或補充。

        Args:
            data_id (str): 股票代碼，例如 "2330"。
            start_date (str): 開始日期，格式 "YYYY-MM-DD"。
            end_date (Optional[str]): 結束日期，格式 "YYYY-MM-DD"。如果為 None，則預設為今天。

        Returns:
            Optional[pd.DataFrame]: 包含個股每日股價數據的 DataFrame。
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        params = {
            "dataset": "TaiwanStockPrice", # 使用 TaiwanStockPrice 獲取日成交資訊
            "data_id": data_id,
            "start_date": start_date,
            "end_date": end_date,
            "token": self.api_token
        }
        # FinMind 的 TaiwanStockPrice 似乎需要用不同的方式處理 token
        # 根據 https://github.com/FinMind/FinMind/wiki/API Token
        # "TaiwanStockPrice" 是免費的，但有些 dataset 需要 token
        # 為了統一，我們先假設都需要 token，並在 _make_request 中處理
        return self._make_request(params)


    def get_financial_statement(self, data_id: str, start_date: str, statement_type: str) -> Optional[pd.DataFrame]:
        """
        獲取財務報表數據 (綜合損益表、資產負債表、現金流量表)。
        對應分析點 #24。

        Args:
            data_id (str): 股票代碼，例如 "2330"。
            start_date (str): 開始日期或季度 "YYYY-MM-DD" 或 "YYYY-QQ" (例如 "2020-Q1")。
                               FinMind API 似乎偏好 "YYYY-MM-DD" 格式的季度第一天。
            statement_type (str): 報表類型，可為 "FinancialStatements", "BalanceSheet", "CashFlowsStatement"。
                                  FinMind API 文件中對應的 dataset 名稱。

        Returns:
            Optional[pd.DataFrame]: 包含財務報表數據的 DataFrame。
        """
        # FinMind API 對於財報的 "start_date" 似乎是指該財報發布的日期，
        # 或是該財報所屬期間的開始日期，這部分需要根據 API 行為確認。
        # 這裡假設 start_date 是查詢的起始點。
        # FinMind 的財報資料是季報，所以日期範圍可能不是主要篩選條件，而是股票代號和報表類型。
        # 我們先假設 start_date 是篩選條件的一部分。

        # 根據 FinMind API 文件, dataset 應為 "FinancialStatements"
        # 然後透過 type 參數指定 'BalanceSheet', 'ComprehensiveIncomeStatement', 'CashFlowsStatement'
        # 然而，舊版 API (v3) 有不同的 dataset 名稱，v4 似乎更統一。
        # 這裡使用 'FinancialStatements' dataset 並假設 API 會返回所有相關欄位，
        # 或者需要用戶自行從綜合報表中提取。
        # 經查 FinMind Python package 範例，是直接使用 'BalanceSheet', 'ComprehensiveIncomeStatement', 'CashFlowsStatement'
        # 作為 dataset 名稱。

        params = {
            "dataset": statement_type, # 例如 "BalanceSheet", "ComprehensiveIncomeStatement", "CashFlowsStatement"
            "data_id": data_id,
            "start_date": start_date, # FinMind API 可能會忽略此參數，或用來指定特定季度開始日
            # "end_date": end_date, # 通常財報是點資料，不太需要 end_date
            "token": self.api_token
        }
        df = self._make_request(params)
        if df is not None and not df.empty:
            # 通常財報數據中的 'date' 和 'stock_id' 是關鍵欄位
            # FinMind API 返回的欄位名稱可能需要標準化
            pass
        return df

    def get_taiwan_stock_month_revenue(self, data_id: str, start_date: str, end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        獲取台股月營收數據。
        對應分析點 #24。

        Args:
            data_id (str): 股票代碼，例如 "2330"。
            start_date (str): 開始日期，格式 "YYYY-MM-DD"。FinMind 會抓取這個日期之後的營收數據。
            end_date (Optional[str]): 結束日期，格式 "YYYY-MM-DD"。如果為 None，則預設為今天。

        Returns:
            Optional[pd.DataFrame]: 包含月營收數據的 DataFrame。
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        params = {
            "dataset": "TaiwanStockMonthRevenue",
            "data_id": data_id,
            "start_date": start_date,
            "end_date": end_date,
            "token": self.api_token
        }
        return self._make_request(params)

# 測試代碼 (可以在開發時使用)
if __name__ == '__main__':
    # 請先設定環境變數 FINMIND_API_TOKEN
    if not FINMIND_API_TOKEN:
        print("請設定環境變數 FINMIND_API_TOKEN 以執行測試。")
        exit()

    client = FinMindClient()
    stock_id = "2330" # 台積電
    start_date_ins = "2023-01-01"
    end_date_ins = "2023-01-10"

    start_date_price = "2023-01-01"
    end_date_price = "2023-01-05"

    start_date_revenue = "2022-01-01" # 月營收通常看比較長的時間

    start_date_financial = "2022-01-01" # 查第一季財報，用該季第一天

    print(f"正在獲取 {stock_id} 的三大法人買賣超數據 ({start_date_ins} to {end_date_ins})...")
    institutional_data = client.get_taiwan_stock_institutional_investors_buy_sell(stock_id, start_date_ins, end_date_ins)
    if institutional_data is not None:
        print("三大法人買賣超數據：")
        print(institutional_data.head())
    else:
        print("無法獲取三大法人買賣超數據。")
    print("-" * 30)

    print(f"正在獲取 {stock_id} 的每日股價數據 ({start_date_price} to {end_date_price})...")
    price_data = client.get_taiwan_stock_per_day(stock_id, start_date_price, end_date_price)
    if price_data is not None:
        print("每日股價數據：")
        print(price_data.head())
    else:
        print("無法獲取每日股價數據。")
    print("-" * 30)

    print(f"正在獲取 {stock_id} 的資產負債表 (從 {start_date_financial} 開始)...")
    # FinMind 的 BalanceSheet dataset 的 start_date 似乎是指發布日期，所以如果想獲取特定季度的，需要調整
    # 或者，它會返回該日期之後的所有可用季度數據。
    # 根據 FinMind Python package，start_date 是 '2018-01-01' 這樣的格式
    balance_sheet_data = client.get_financial_statement(stock_id, start_date_financial, "BalanceSheet")
    if balance_sheet_data is not None:
        print("資產負債表數據：")
        print(balance_sheet_data.head())
    else:
        print("無法獲取資產負債表數據。")
    print("-" * 30)

    print(f"正在獲取 {stock_id} 的綜合損益表 (從 {start_date_financial} 開始)...")
    income_statement_data = client.get_financial_statement(stock_id, start_date_financial, "ComprehensiveIncomeStatement") # FinMind用此名稱
    if income_statement_data is not None:
        print("綜合損益表數據：")
        print(income_statement_data.head())
    else:
        print("無法獲取綜合損益表數據。")
    print("-" * 30)

    print(f"正在獲取 {stock_id} 的現金流量表 (從 {start_date_financial} 開始)...")
    cash_flow_data = client.get_financial_statement(stock_id, start_date_financial, "CashFlowsStatement")
    if cash_flow_data is not None:
        print("現金流量表數據：")
        print(cash_flow_data.head())
    else:
        print("無法獲取現金流量表數據。")
    print("-" * 30)

    print(f"正在獲取 {stock_id} 的月營收數據 (從 {start_date_revenue} 開始)...")
    revenue_data = client.get_taiwan_stock_month_revenue(stock_id, start_date_revenue)
    if revenue_data is not None:
        print("月營收數據：")
        print(revenue_data.head())
    else:
        print("無法獲取月營收數據。")
    print("-" * 30)

    print("測試 FinMindClient 完成。")

    # 關於券商分點進出數據：
    # FinMind API (免費版) 並不直接提供此類數據。
    # 如果需要此數據，可能需要考慮：
    # 1. FinMind 的付費方案是否包含。
    # 2. 其他台灣市場的數據提供商 (如 CMoney, TEJ 等，通常需要付費)。
    # 3. 自行爬蟲 (合規性與維護成本高)。
    # 目前 get_taiwan_stock_per_day 函數獲取的是日成交資訊，並非券商分點數據。
    # 任務描述中 "個股的券商分點進出數據" 這一點可能需要澄清數據源或調整預期。
    # 我會在後續的 feature_analyzer 中假設法人籌碼分析主要基於三大法人買賣超數據。
    # 若有券商分點數據的具體來源，可以再擴充 client。

    # 測試一個不存在的股票或日期範圍，看 API 如何回應
    print("測試無數據情況 (不存在的股票代碼 '99999')...")
    non_existent_data = client.get_taiwan_stock_per_day("99999", "2023-01-01", "2023-01-05")
    if non_existent_data is not None and non_existent_data.empty:
        print("成功處理：API 返回空的 DataFrame。")
    elif non_existent_data is None:
        print("API 請求失敗或返回 None (可能是預期的，如果 API 對錯誤的 data_id 返回錯誤狀態)。")
    else:
        print("未預期的回應：", non_existent_data)
    print("-" * 30)

    print("測試無數據情況 (未來日期)...")
    future_date = (datetime.now() + timedelta(days=100)).strftime("%Y-%m-%d")
    future_data = client.get_taiwan_stock_per_day(stock_id, future_date)
    if future_data is not None and future_data.empty:
        print("成功處理：API 返回空的 DataFrame。")
    elif future_data is None:
        print("API 請求失敗或返回 None。")
    else:
        print("未預期的回應：", future_data)

"""
注意：
1.  **API Token**: `FINMIND_API_TOKEN` 需要透過環境變數設定。如果沒有設定，`FinMindClient` 在初始化時會拋出 `ValueError`。
2.  **錯誤處理**: `_make_request` 方法中包含了基本的錯誤處理 (HTTP 錯誤、請求異常)。
3.  **數據格式**: FinMind API 可能返回 JSON 或 CSV。`_make_request` 嘗試處理這兩種情況。JSON 回應的數據通常在 "data" 鍵中。
4.  **券商分點數據**: 如註解中所述，FinMind 免費 API **不直接提供**個股的券商分點進出數據。`get_taiwan_stock_per_day` 獲取的是日成交資訊。這點需要在後續分析或需求澄清時注意。
5.  **財務報表日期**: FinMind API 對於財務報表的 `start_date` 參數的具體行為（是指報表期間開始日還是發布日篩選）可能需要更多測試來確認。目前的實作是基於一般的理解。
6.  **端點名稱**: 使用的 `dataset` 名稱 (如 `TaiwanStockInstitutionalInvestorsBuySell`, `BalanceSheet` 等) 是根據 FinMind API 文件和常見用法。
7.  **相依性**: 此客戶端需要 `requests` 和 `pandas` 庫。

此 `client.py` 檔案包含了與 FinMind API 互動的核心邏輯，用於獲取法人籌碼和基本面數據。
"""
