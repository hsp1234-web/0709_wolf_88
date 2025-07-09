# core/clients/fmp.py
# 此模組包含與 Financial Modeling Prep (FMP) API 互動的客戶端邏輯。

import os
import requests
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any

# FMP API 基礎 URL (不含版本號)
FMP_BASE_URL = "https://financialmodelingprep.com/api"

class FMPAPIClient:
    """
    Financial Modeling Prep (FMP) API 客戶端。
    用於獲取全球市場（尤其是美股）的財經數據，如歷史價格、公司財報等。
    """
    def __init__(self, api_key: Optional[str] = None, api_version: str = "v3"):
        """
        初始化 FMPAPIClient。

        Args:
            api_key (Optional[str]): FMP API key。如果未提供，將嘗試從環境變數 FMP_API_KEY 讀取。
            api_version (str): API 版本，預設為 "v3"。部分端點可能在 "v4"。

        Raises:
            ValueError: 如果 API key 未提供且環境變數中也未設定。
        """
        self.api_key = api_key or os.getenv("FMP_API_KEY")
        if not self.api_key:
            raise ValueError("FMP API key 未設定。請設定 FMP_API_KEY 環境變數或在初始化時傳入 api_key。")
        self.base_url_with_version = f"{FMP_BASE_URL}/{api_version}"
        print(f"資訊：FMPAPIClient 初始化完成，API 版本 '{api_version}'。")

    def _make_request(self, endpoint_path: str, params: Optional[Dict[str, Any]] = None) -> Optional[List[Dict[str, Any]]]:
        """
        向 FMP API 發送請求並處理回應。

        Args:
            endpoint_path (str): API 端點路徑 (例如 "historical-price-full/AAPL" 或 "income-statement/AAPL")。
            params (Optional[Dict[str, Any]]): API 請求的查詢參數。

        Returns:
            Optional[List[Dict[str, Any]]]: 包含 API 回應數據的字典列表，如果請求失敗或無數據則返回 None。
                                            注意：FMP 有些端點直接返回列表，有些返回字典，此方法旨在返回列表。
        """
        if params is None:
            params = {}

        # 將 API key 加入到每個請求的參數中
        params["apikey"] = self.api_key
        url = f"{self.base_url_with_version}/{endpoint_path}"

        print(f"資訊：向 FMP API 發送請求，URL: {url}, Params: { {k:v for k,v in params.items() if k != 'apikey'} }") # 不印出 apikey
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # 如果 HTTP 狀態碼是 4xx 或 5xx，則引發 HTTPError

            json_response = response.json()

            # 檢查 FMP API 特有的錯誤訊息格式
            if isinstance(json_response, dict) and "Error Message" in json_response:
                error_msg = json_response["Error Message"]
                print(f"錯誤：FMP API 返回錯誤訊息：'{error_msg}' (URL: {url})")
                return None

            # 處理 FMP API 可能的幾種成功回應結構
            if isinstance(json_response, list):
                # 如果直接是列表，則直接返回
                print(f"資訊：FMP API 成功返回數據列表，共 {len(json_response)} 筆記錄。")
                return json_response
            elif isinstance(json_response, dict):
                # 檢查常見的數據包裝鍵，例如 'historical' (用於股價) 或 'financialStatementList' (較少見)
                # 如果 API 設計變更，可能需要更新這些鍵
                possible_data_keys = ['historical', 'financialStatementList']
                for key in possible_data_keys:
                    if key in json_response and isinstance(json_response[key], list):
                        print(f"資訊：FMP API 成功返回數據，在鍵 '{key}' 下找到列表，共 {len(json_response[key])} 筆記錄。")
                        return json_response[key]

                # 如果是一個字典但沒有已知的數據列表鍵，且不是錯誤訊息，記錄此情況
                # 有些端點可能直接返回單一對象的字典，但此客戶端主要設計為處理列表型數據
                print(f"警告：FMP API 返回了一個字典，但未在預期鍵下找到數據列表，也不是標準錯誤格式。URL: {url}, 回應: {json_response}")
                # 根據需求，也可以選擇返回這個字典，但目前契約是 List[Dict] 或 None
                return None
            else:
                # 非列表也非字典的成功回應 (不太可能，但作為防禦)
                print(f"警告：FMP API 返回了非預期的回應類型: {type(json_response)}。URL: {url}")
                return None

        except requests.exceptions.HTTPError as http_err:
            print(f"錯誤：FMP API HTTP 錯誤：{http_err} (URL: {url}) - 回應內容：{response.text if response else '無回應內容'}")
            return None
        except requests.exceptions.RequestException as req_err:
            print(f"錯誤：請求 FMP API 時發生網路或請求配置錯誤：{req_err} (URL: {url})")
            return None
        except ValueError as json_err: # requests.json() 可能引發的錯誤
            print(f"錯誤：解析 FMP API JSON 回應時失敗：{json_err} (URL: {url})")
            return None
        except Exception as e:
            print(f"錯誤：處理 FMP API 回應時發生未知錯誤：{e} (URL: {url})")
            return None

    def get_historical_daily_prices(self, symbol: str, from_date: Optional[str] = None, to_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        獲取指定股票/ETF/指數的日線歷史價格數據。

        Args:
            symbol (str): 商品代碼 (例如 "AAPL", "SPY", "%5EGSPC" for S&P 500)。
                          注意：FMP 對指數的代碼可能需要 URL 編碼 (例如 ^GSPC -> %5EGSPC)。
            from_date (Optional[str]): 開始日期 (格式 "YYYY-MM-DD")。
            to_date (Optional[str]): 結束日期 (格式 "YYYY-MM-DD")。

        Returns:
            Optional[pd.DataFrame]: 包含日線價格數據的 DataFrame (欄位如 date, open, high, low, close, volume 等)。
                                     數據按日期升序排列。如果請求失敗或無數據則返回 None。
        """
        endpoint = f"historical-price-full/{symbol}"
        params: Dict[str, str] = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        # FMP 的 'historical-price-full' 端點返回的 'historical' 鍵下的列表
        data_list = self._make_request(endpoint, params)

        if data_list is not None:
            if not data_list: # API 成功返回，但 data_list 為空
                print(f"資訊：FMP API 未返回 '{symbol}' 在指定日期範圍的歷史價格數據。")
                return pd.DataFrame() # 返回空 DataFrame

            df = pd.DataFrame(data_list)
            # FMP 歷史數據通常從新到舊，我們將其反轉為從舊到新
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values(by='date').reset_index(drop=True)
            else:
                print(f"警告：FMP API 返回的歷史價格數據中缺少 'date' 欄位。Symbol: {symbol}")
            return df
        return None # _make_request 返回 None 表示獲取失敗

    def get_financial_statements(self, symbol: str, statement_type: str, period: str = "quarter", limit: int = 20) -> Optional[pd.DataFrame]:
        """
        獲取指定股票的財務報表數據 (例如損益表、資產負債表、現金流量表)。

        Args:
            symbol (str): 股票代碼 (例如 "AAPL")。
            statement_type (str): 報表類型。FMP API v3 中常見的有:
                                  "income-statement",
                                  "balance-sheet-statement",
                                  "cash-flow-statement"。
            period (str): 財報週期，"quarter" (季報) 或 "annual" (年報)。預設為 "quarter"。
            limit (int): 返回的財報期數。預設為 20。

        Returns:
            Optional[pd.DataFrame]: 包含財報數據的 DataFrame。
                                     如果請求失敗或無數據則返回 None。
        """
        endpoint = f"{statement_type}/{symbol}"
        params = {"period": period, "limit": str(limit)} # limit 參數通常是字串

        data_list = self._make_request(endpoint, params)

        if data_list is not None:
            if not data_list: # API 成功返回，但 data_list 為空
                print(f"資訊：FMP API 未返回 '{symbol}' 的 '{statement_type}' ({period}) 財報數據。")
                return pd.DataFrame() # 返回空 DataFrame

            df = pd.DataFrame(data_list)
            # 財報數據中的 'date' 和 'symbol' 通常是關鍵欄位
            # FMP 返回的欄位名通常是駝峰式 (camelCase)
            if 'date' in df.columns:
                 df['date'] = pd.to_datetime(df['date'])
                 # 財報數據通常按日期降序 (最新在前)，這裡保持 FMP 的順序
                 df = df.sort_values(by='date', ascending=False).reset_index(drop=True)
            return df
        return None

# 範例使用 (主要用於開發時測試)
if __name__ == '__main__':
    print("--- FMP API Client 測試 (直接執行 core/clients/fmp.py) ---")
    # 執行此測試前，請確保設定了 FMP_API_KEY 環境變數
    try:
        # 使用一個有效的 API Key 進行測試 (如果環境變數未設定，則會拋錯)
        client = FMPAPIClient(api_version="v3") # 可以指定 v3 或 v4
        print("FMPAPIClient 初始化成功。")

        # 測試獲取歷史股價
        print("\n測試獲取 AAPL 歷史日線價格 (2023-12-01 至 2023-12-05)...")
        # 注意：免費的 FMP API key 可能對數據範圍和頻率有限制
        aapl_prices = client.get_historical_daily_prices("AAPL", from_date="2023-12-01", to_date="2023-12-05")
        if aapl_prices is not None:
            if not aapl_prices.empty:
                print(f"成功獲取 AAPL 歷史價格數據 (共 {len(aapl_prices)} 筆):")
                print(aapl_prices.head())
            else:
                print("AAPL 歷史價格數據請求成功，但返回為空 DataFrame (該日期範圍可能無數據或 API key 權限不足)。")
        else:
            print("獲取 AAPL 歷史價格數據失敗。")

        # 測試獲取財報數據
        print("\n測試獲取 AAPL 季度損益表 (最近1期)...")
        income_statement = client.get_financial_statements("AAPL", "income-statement", period="quarter", limit=1)
        if income_statement is not None:
            if not income_statement.empty:
                print(f"成功獲取 AAPL 季度損益表數據 (共 {len(income_statement)} 筆):")
                print(income_statement.head())
            else:
                print("AAPL 季度損益表數據請求成功，但返回為空 DataFrame。")
        else:
            print("獲取 AAPL 季度損益表數據失敗。")

        # 測試一個可能不存在的股票
        print("\n測試獲取不存在股票 'XYZNOTASTOCK' 的歷史價格...")
        non_existent_stock_prices = client.get_historical_daily_prices("XYZNOTASTOCK", from_date="2023-01-01", to_date="2023-01-05")
        if non_existent_stock_prices is None:
            print("獲取不存在股票價格數據失敗 (符合預期，API 可能返回錯誤)。")
        elif non_existent_stock_prices.empty:
            print("獲取不存在股票價格數據返回空 DataFrame (符合預期，API 可能返回空列表)。")
        else:
            print(f"獲取不存在股票價格數據返回了非預期的數據: {non_existent_stock_prices.head()}")


    except ValueError as ve: # API Key 未設定等初始化問題
        print(f"初始化錯誤: {ve}")
    except Exception as e:
        print(f"執行期間發生未預期錯誤: {e}")

    print("--- FMP API Client 測試結束 ---")
