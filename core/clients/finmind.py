# core/clients/finmind.py
# 此模組包含與 FinMind API 互動的客戶端邏輯。

import os
import requests
import pandas as pd
from io import StringIO
from datetime import datetime
from typing import Optional, Dict, Any

# FinMind API 基礎 URL
BASE_URL = "https://api.finmindtrade.com/api/v4/data"

class FinMindAPIClient:
    """
    用於與 FinMind API 互動的客戶端。
    """
    def __init__(self, api_token: Optional[str] = None):
        """
        初始化 FinMindAPIClient。

        Args:
            api_token (Optional[str]): FinMind API Token。如果未提供，
                                       將嘗試從環境變數 FINMIND_API_TOKEN 讀取。

        Raises:
            ValueError: 如果 API Token 未提供且環境變數中也未設定。
        """
        self.api_token = api_token or os.getenv("FINMIND_API_TOKEN")
        if not self.api_token:
            raise ValueError("FinMind API token 未設定。請設定 FINMIND_API_TOKEN 環境變數或在初始化時傳入 api_token。")

    def _make_request(self, endpoint_params: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        向 FinMind API 發送請求並處理回應。

        Args:
            endpoint_params (Dict[str, Any]): API 端點所需的參數字典。
                                               此字典應包含 'dataset', 'data_id', 'start_date' 等。

        Returns:
            Optional[pd.DataFrame]: 包含 API 回應數據的 DataFrame，如果請求失敗或無數據則返回 None。
        """
        # 移除 params 中的 token 參數，因為它將透過 headers 傳遞
        # 或者 FinMind API 也接受 params 中的 token，原始碼是這樣做的
        # 為了與原始碼行為一致，此處保留 params["token"] = self.api_token
        request_params = endpoint_params.copy()
        request_params["token"] = self.api_token

        # 雖然原始碼也將 token 放入 params，但通常 token 是放在 header
        # headers = {"Authorization": f"Bearer {self.api_token}"}
        # 根據 FinMind 文件，token 確實是作為查詢參數 "token" 傳遞
        headers = {} # FinMind API token 是透過 params 傳遞

        print(f"資訊：向 FinMind API 發送請求，目標資料集：'{request_params.get('dataset')}', 資料ID：'{request_params.get('data_id')}'")
        try:
            response = requests.get(BASE_URL, params=request_params, headers=headers)
            response.raise_for_status()  # 如果 HTTP 狀態碼是 4xx 或 5xx，則引發 HTTPError

            # FinMind API 可能返回 CSV 或 JSON
            content_type = response.headers.get('Content-Type', '')
            if 'text/csv' in content_type:
                print("資訊：FinMind API 回應為 CSV 格式。")
                return pd.read_csv(StringIO(response.text))
            elif 'application/json' in content_type:
                print("資訊：FinMind API 回應為 JSON 格式。")
                json_response = response.json()
                if json_response.get("status") != 200:
                    error_msg = json_response.get('msg', '未知錯誤')
                    print(f"錯誤：FinMind API 邏輯錯誤 (status {json_response.get('status')}): {error_msg}")
                    return None

                data_list = json_response.get("data")
                if data_list:
                    return pd.DataFrame(data_list)
                else:
                    print(f"資訊：FinMind API 未返回任何數據 (data 列表為空或不存在)。資料集：'{request_params.get('dataset')}', ID：'{request_params.get('data_id')}'")
                    return pd.DataFrame() # 返回空的 DataFrame 表示成功請求但無數據
            else:
                print(f"錯誤：未知的 FinMind API 回應 Content-Type: {content_type}")
                return None

        except requests.exceptions.HTTPError as http_err:
            print(f"錯誤：FinMind API HTTP 錯誤：{http_err} - 回應內容：{response.text}")
            return None
        except requests.exceptions.RequestException as req_err:
            print(f"錯誤：請求 FinMind API 時發生網路或請求配置錯誤：{req_err}")
            return None
        except Exception as e:
            # 捕捉 pd.read_csv 或 response.json() 可能引發的錯誤
            print(f"錯誤：處理 FinMind API 回應時發生未知錯誤：{e}")
            return None

    def get_data(self, dataset: str, data_id: str, start_date: str, end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        從 FinMind API 獲取指定資料集和股票的數據。

        Args:
            dataset (str): FinMind 資料集名稱 (例如 "TaiwanStockPrice")。
            data_id (str): 股票代碼或特定資料ID。
            start_date (str): 開始日期 (格式 YYYY-MM-DD)。
            end_date (Optional[str]): 結束日期 (格式 YYYY-MM-DD)。預設為當前日期。

        Returns:
            Optional[pd.DataFrame]: 包含請求數據的 DataFrame，如果失敗則為 None。
        """
        params = {
            "dataset": dataset,
            "data_id": data_id,
            "start_date": start_date,
            "end_date": end_date or datetime.now().strftime("%Y-%m-%d"),
        }
        return self._make_request(params)

    # 為了與舊版 client.py 的方法簽名保持一定程度的兼容性，
    # 以及提供一個更具體的範例方法，保留此方法。
    # 但通用的 get_data 方法更具彈性。
    def get_taiwan_stock_institutional_investors_buy_sell(
        self,
        stock_id: str,
        start_date: str,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        獲取台灣股市特定股票的法人買賣超數據。
        (此為對 `get_data` 方法使用 "TaiwanStockInstitutionalInvestorsBuySell" 資料集的一個封裝)

        Args:
            stock_id (str): 股票代碼 (例如 "2330")。
            start_date (str): 開始日期 (格式 YYYY-MM-DD)。
            end_date (Optional[str]): 結束日期 (格式 YYYY-MM-DD)。預設為當前日期。

        Returns:
            Optional[pd.DataFrame]: 包含法人買賣超數據的 DataFrame，如果失敗則為 None。
        """
        return self.get_data(
            dataset="TaiwanStockInstitutionalInvestorsBuySell",
            data_id=stock_id,
            start_date=start_date,
            end_date=end_date
        )

# 範例使用 (主要用於開發時測試，實際使用時應由其他模組導入 Client)
if __name__ == '__main__':
    print("--- FinMind API Client 測試 (直接執行 core/clients/finmind.py) ---")
    # 執行此測試前，請確保設定了 FINMIND_API_TOKEN 環境變數
    try:
        client = FinMindAPIClient()
        print("FinMindAPIClient 初始化成功。")

        # 測試台灣股市股價資料集
        print("\n測試 TaiwanStockPrice (台積電 2330)...")
        # stock_data = client.get_data(dataset="TaiwanStockPrice", data_id="2330", start_date="2023-01-01", end_date="2023-01-10")
        # 為了避免 Token 實際調用產生費用或依賴外部服務，這裡使用一個較不易變動的、可能不需要 Token 的端點 (例如台灣股市日曆)
        # 不過，FinMind 大部分數據都需要 Token。
        # 這裡改為測試一個虛構或已知的小範圍數據，假設 API Token 已設定。
        # 根據 FinMind 文件，"TaiwanStockInfo" 似乎是一個不需要頻繁更新的數據集，用來獲取股票基本資訊

        # 測試法人買賣超 (使用特定方法)
        # 注意：FinMind 的免費方案可能對此數據集有限制
        investor_data = client.get_taiwan_stock_institutional_investors_buy_sell(
            stock_id="2330",
            start_date="2024-01-01",
            end_date="2024-01-05"
        )

        if investor_data is not None:
            if not investor_data.empty:
                print(f"成功獲取股票 2330 的法人買賣超數據 (共 {len(investor_data)} 筆):")
                print(investor_data.head())
            else:
                print("股票 2330 的法人買賣超數據請求成功，但返回為空 DataFrame (該日期範圍可能無數據或 Token 權限不足)。")
        else:
            print("獲取股票 2330 的法人買賣超數據失敗。")

        # 測試一個可能不存在的資料
        print("\n測試一個不存在的股票代碼 (XYZABC)...")
        non_existent_data = client.get_data(dataset="TaiwanStockPrice", data_id="XYZABC", start_date="2023-01-01", end_date="2023-01-05")
        if non_existent_data is not None:
            if non_existent_data.empty:
                print("獲取 XYZABC 數據成功，返回空的 DataFrame (符合預期，因為股票不存在或無數據)。")
            else:
                print(f"獲取 XYZABC 數據返回了非預期的數據: \n{non_existent_data.head()}")
        else:
            print("獲取 XYZABC 數據失敗 (符合預期，因為股票不存在或請求錯誤)。")

    except ValueError as ve:
        print(f"初始化錯誤: {ve}")
    except Exception as e:
        print(f"執行期間發生未預期錯誤: {e}")

    print("--- FinMind API Client 測試結束 ---")
