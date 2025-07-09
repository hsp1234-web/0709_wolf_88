# apps/fmp_client/client.py
import sys
import os

# --- 標準化「路徑自我校正」樣板碼 START ---
# 取得目前腳本檔案的目錄
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 自動偵測專案根目錄 (假設 .git 在根目錄，或存在 README.md)
project_root = current_script_dir
max_levels_up = 5 # 防止無限迴圈，可根據專案深度調整
for _ in range(max_levels_up):
    # 檢查是否存在 .git 目錄或 AGENTS.md (或 README.md) 作為根目錄標記
    if os.path.isdir(os.path.join(project_root, '.git')) or \
       os.path.isfile(os.path.join(project_root, 'AGENTS.md')) or \
       os.path.isfile(os.path.join(project_root, 'README.md')):
        break
    parent_dir = os.path.dirname(project_root)
    if parent_dir == project_root: # 已達檔案系統頂層
        project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..'))
        print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑: {project_root}")
        break
    project_root = parent_dir
else: # 如果迴圈正常結束 (未 break)
    project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..')) # 後備方案
    print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑: {project_root}")

if project_root not in sys.path:
    sys.path.insert(0, project_root)
# print(f"DEBUG: 專案根目錄 {project_root} 已添加到 sys.path")
# --- 標準化「路徑自我校正」樣板碼 END ---

# import os # os 已在上面導入
import requests
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any

# 從環境變數讀取 API key
FMP_API_KEY = os.getenv("FMP_API_KEY")

# FMP API 基礎 URL
BASE_URL = "https://financialmodelingprep.com/api"

class FMPClient:
    """
    Financial Modeling Prep (FMP) API 客戶端，用於獲取全球市場（尤其是美股）的財經數據。
    """
    def __init__(self, api_key: Optional[str] = None, api_version: str = "v3"):
        """
        初始化 FMPClient。

        Args:
            api_key (Optional[str]): FMP API key。如果未提供，則從環境變數 FMP_API_KEY 讀取。
            api_version (str): API 版本，預設為 "v3"。部分端點可能在 "v4"。
        """
        self.api_key = api_key or FMP_API_KEY
        if not self.api_key:
            raise ValueError("FMP API key 未設定。請設定 FMP_API_KEY 環境變數或在初始化時傳入 api_key。")
        self.base_url = f"{BASE_URL}/{api_version}"

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[List[Dict[str, Any]]]:
        """
        向 FMP API 發送請求並處理回應。

        Args:
            endpoint (str): API 端點路徑 (例如 "historical-price-full/AAPL")。
            params (Optional[Dict[str, Any]]): API 請求的查詢參數。

        Returns:
            Optional[List[Dict[str, Any]]]: 包含 API 回應數據的列表，如果請求失敗則返回 None。
        """
        if params is None:
            params = {}

        # 將 API key 加入到每個請求的參數中
        params["apikey"] = self.api_key

        url = f"{self.base_url}/{endpoint}"

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # 如果 HTTP 狀態碼是 4xx 或 5xx，則拋出異常

            json_response = response.json()

            # FMP API 有時會在錯誤時返回帶有 "Error Message" 的 JSON
            if isinstance(json_response, dict) and "Error Message" in json_response:
                print(f"FMP API 錯誤：{json_response['Error Message']}")
                return None

            # 有些端點直接返回列表，有些則將列表包在 'historical' 等鍵中
            if isinstance(json_response, list):
                return json_response
            elif isinstance(json_response, dict): # 例如歷史股價，數據在 'historical' 鍵
                # 常見的 FMP 數據包裝鍵
                possible_keys = ['historical', 'financialStatementList']
                for key in possible_keys:
                    if key in json_response and isinstance(json_response[key], list):
                        return json_response[key]
                # 如果找不到標準包裝，但又是字典，且非錯誤訊息，可能API結構有變
                print(f"FMP API 回應格式可能已變更或非預期 (非列表，非錯誤訊息): {json_response}")
                return None # 或者返回 json_response 如果調用者期望處理字典

            return json_response # 理論上應該是列表或None

        except requests.exceptions.RequestException as e:
            print(f"請求 FMP API 時發生錯誤 ({url})：{e}")
            return None
        except Exception as e:
            print(f"處理 FMP API 回應時發生未知錯誤 ({url})：{e}")
            return None

    def get_historical_daily_prices(self, symbol: str, from_date: Optional[str] = None, to_date: Optional[str] = None, series_type: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        獲取指定商品的日線歷史價格數據。
        對應分析點 #3 (跨市場關聯性)。

        Args:
            symbol (str): 商品代碼 (例如 "AAPL", "GOOGL", "^GSPC" for S&P 500, "GC=F" for Gold Future).
                          FMP 對於指數和期貨的代碼可能與 Yahoo Finance 不同，需要確認。
            from_date (Optional[str]): 開始日期 "YYYY-MM-DD"。
            to_date (Optional[str]): 結束日期 "YYYY-MM-DD"。
            series_type (Optional[str]): 'line' or 'ohlc' (預設 'ohlc'，但FMP API通常直接返回OHLCV)
                                        FMP API 中，'line' 類型通常用於圖表，數據點較少。
                                        此參數在 FMP 中可能通過不同端點實現，而非參數。
                                        'historical-price-full' 端點預設返回日線 OHLCV。

        Returns:
            Optional[pd.DataFrame]: 包含日線價格數據的 DataFrame。
        """
        endpoint = f"historical-price-full/{symbol}"
        params = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        # series_type 在 FMP 中通常不由 'historical-price-full' 的參數控制
        # 如果需要 'line' 數據，可能要用 'historical-chart/{timeframe}/{symbol}' 端點

        data = self._make_request(endpoint, params)

        if data is not None: # 修正：處理 data 為空列表 [] 的情況
            # FMP 的歷史價格數據通常包在一個 'historical' 鍵裡，但 _make_request 已處理
            df = pd.DataFrame(data)
            # FMP 的歷史數據是從新到舊排序，如果需要可以反轉
            if not df.empty and 'date' in df.columns:
                 df = df.sort_values(by='date').reset_index(drop=True)
            return df
        return None

    def get_etf_historical_daily_prices(self, etf_symbol: str, from_date: Optional[str] = None, to_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        獲取 ETF 的日線歷史價格數據。FMP 中 ETF 和股票使用相同的端點。
        對應分析點 #3。

        Args:
            etf_symbol (str): ETF 代碼 (例如 "SPY", "QQQ").
            from_date (Optional[str]): 開始日期 "YYYY-MM-DD"。
            to_date (Optional[str]): 結束日期 "YYYY-MM-DD"。

        Returns:
            Optional[pd.DataFrame]: 包含 ETF 日線價格數據的 DataFrame。
        """
        # FMP API 通常將 ETF 視為普通股票進行查詢
        return self.get_historical_daily_prices(symbol=etf_symbol, from_date=from_date, to_date=to_date)

    def get_index_historical_daily_prices(self, index_symbol: str, from_date: Optional[str] = None, to_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        獲取指數的日線歷史價格數據。
        對應分析點 #3。
        FMP 對指數的 symbol 有特定格式，例如 S&P 500 是 "%5EGSPC" (URL encoded ^GSPC) 或 "SPY" (ETF a proxy)。
        需要查閱 FMP 文件確認其支援的指數代碼。常見指數如 S&P 500, Nasdaq, Dow Jones.
        FMP 官方文件建議使用 ETF (如 SPY, QQQ, DIA) 來代表指數，因為它們的數據更完整。
        或者使用如 `major-indexes/%5EGSPC` 這樣的端點 (但這是v3/stock/list的一部分)。
        `historical-price-full/%5EGSPC` 也可以。

        Args:
            index_symbol (str): 指數代碼 (例如 "%5EGSPC" for S&P 500, "%5EIXIC" for Nasdaq).
            from_date (Optional[str]): 開始日期 "YYYY-MM-DD"。
            to_date (Optional[str]): 結束日期 "YYYY-MM-DD"。

        Returns:
            Optional[pd.DataFrame]: 包含指數日線價格數據的 DataFrame。
        """
        return self.get_historical_daily_prices(symbol=index_symbol, from_date=from_date, to_date=to_date)

    def get_financial_statements(self, symbol: str, statement_type: str, period: str = "quarter", limit: int = 20) -> Optional[pd.DataFrame]:
        """
        獲取美股的財報數據 (Income Statement, Balance Sheet, Cash Flow Statement)。
        對應分析點 #24 (市場定價錯誤 - 美股財報)。

        Args:
            symbol (str): 股票代碼 (例如 "AAPL").
            statement_type (str): 報表類型。
                                  FMP API v3: "income-statement", "balance-sheet-statement", "cash-flow-statement".
            period (str): 財報週期，"quarter" 或 "annual"。預設 "quarter"。
            limit (int): 返回的財報期數。預設 20。

        Returns:
            Optional[pd.DataFrame]: 包含財報數據的 DataFrame。
        """
        # FMP API v3 的端點格式
        endpoint = f"{statement_type}/{symbol}"
        params = {"period": period, "limit": limit}

        data = self._make_request(endpoint, params)
        if data is not None: # 修正：處理 data 為空列表 [] 的情況
            df = pd.DataFrame(data)
            # 通常財報數據中的 'date' 和 'symbol' 是關鍵欄位
            # FMP 返回的欄位名稱通常是駝峰式 (e.g., netIncome)
            return df
        return None

# 測試代碼
if __name__ == '__main__':
    if not FMP_API_KEY:
        print("請設定環境變數 FMP_API_KEY 以執行測試。")
        # exit() # 先不退出，允許無 KEY 時 client 初始化失敗的測試

    try:
        client = FMPClient() # 如果沒有 API Key 會在此處拋出 ValueError
        print("FMPClient 初始化成功。")

        # 測試獲取日線數據
        print("\n正在獲取 AAPL 的日線數據 (最近5天)...")
        # FMP 免費方案可能只提供幾年前的數據，或有限的 symbol
        # 若要測試特定日期範圍，需注意 API Key 的權限
        # to_date = datetime.now().strftime("%Y-%m-%d")
        # from_date = (datetime.now() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        # aapl_prices = client.get_historical_daily_prices("AAPL", from_date=from_date, to_date=to_date)

        # 由於免費 API 的限制，這裡可能不會返回數據，或者返回的是較舊的數據
        # 先嘗試獲取無日期限制的，看 API key 能否取到
        aapl_prices = client.get_historical_daily_prices("AAPL", to_date="2023-12-31", from_date="2023-12-01") # 假設測試用key有此權限
        if aapl_prices is not None:
            print("AAPL 日線數據 (部分):")
            print(aapl_prices.head())
        else:
            print("無法獲取 AAPL 日線數據。免費 API 可能有延遲或限制。")

        # 測試獲取 ETF 數據 (SPY)
        print("\n正在獲取 SPY (S&P 500 ETF) 的日線數據...")
        spy_prices = client.get_etf_historical_daily_prices("SPY", to_date="2023-12-31", from_date="2023-12-01")
        if spy_prices is not None:
            print("SPY 日線數據 (部分):")
            print(spy_prices.head())
        else:
            print("無法獲取 SPY 日線數據。")

        # 測試獲取指數數據 (S&P 500 - 使用 %5EGSPC)
        # FMP 對指數的直接支持可能依賴於 API key 的等級
        print("\n正在獲取 S&P 500 指數 (%5EGSPC) 的日線數據...")
        # FMP 免費版可能不支援直接查 %5EGSPC，但付費版支援
        gspc_prices = client.get_index_historical_daily_prices("%5EGSPC", to_date="2023-12-31", from_date="2023-12-01")
        if gspc_prices is not None:
            print("S&P 500 指數日線數據 (部分):")
            print(gspc_prices.head())
        else:
            print("無法獲取 S&P 500 指數日線數據。可能需要付費 API Key 或使用 SPY (ETF) 作為替代。")

        # 測試獲取財報數據 (AAPL 季度損益表)
        print("\n正在獲取 AAPL 的季度損益表 (最近幾期)...")
        income_statement = client.get_financial_statements("AAPL", "income-statement", period="quarter", limit=2)
        if income_statement is not None:
            print("AAPL 季度損益表 (部分):")
            print(income_statement.head())
        else:
            print("無法獲取 AAPL 季度損益表。免費 API 可能有財報數據的限制。")

        print("\n正在獲取 AAPL 的年度資產負債表 (最近幾期)...")
        balance_sheet = client.get_financial_statements("AAPL", "balance-sheet-statement", period="annual", limit=2)
        if balance_sheet is not None:
            print("AAPL 年度資產負債表 (部分):")
            print(balance_sheet.head())
        else:
            print("無法獲取 AAPL 年度資產負債表。")

        # 測試錯誤處理：無效的 symbol
        print("\n測試無效的 symbol (INVALID)...")
        invalid_prices = client.get_historical_daily_prices("INVALID")
        if invalid_prices is None:
            print("成功處理無效 symbol 的情況 (返回 None)。")
        elif invalid_prices.empty:
             print("成功處理無效 symbol 的情況 (返回 empty DataFrame)。")
        else:
            print(f"對無效 symbol 的處理未如預期: {invalid_prices}")

    except ValueError as e:
        print(f"FMPClient 初始化失敗: {e}")
    except Exception as e:
        print(f"執行 FMPClient 測試時發生未預期錯誤: {e}")

    print("\nFMPClient 測試代碼執行完畢。")

"""
注意：
1.  **API Key**: `FMP_API_KEY` 需要透過環境變數設定。如果沒有設定，`FMPClient` 在初始化時會拋出 `ValueError`。
2.  **API 版本**: 目前基於 FMP API v3。如果未來 FMP 更新 API 結構，可能需要調整端點和解析邏輯。
3.  **錯誤處理**: `_make_request` 方法中包含了基本的錯誤處理 (HTTP 錯誤、請求異常、FMP 特定錯誤訊息)。
4.  **數據格式**: FMP API 主要返回 JSON。`_make_request` 解析 JSON 並提取數據列表。
    -   歷史價格數據 (`historical-price-full`) 返回的 JSON 中，實際的 OHLCV 數據通常在一個名為 "historical" 的鍵對應的列表中。`_make_request` 已處理此情況。
    -   財報數據直接返回列表。
5.  **指數數據**: FMP 對於直接查詢指數（如 `^GSPC`）的支援可能依賴於 API key 的等級。免費或低階方案可能不支援，或數據不完整。FMP 官方常建議使用對應的 ETF (如 SPY 代表 S&P 500) 作為替代。
6.  **欄位名稱**: FMP API 返回的財報數據欄位通常是駝峰式命名 (camelCase)，例如 `netIncome`, `totalAssets`。
7.  **相依性**: 此客戶端需要 `requests` 和 `pandas` 庫。
8.  **免費 API 限制**: FMP 的免費 API key 可能有每日請求次數限制、數據延遲、支援的 symbols 有限等。測試時返回 `None` 或空 DataFrame 可能是由於這些限制。

此 `client.py` 檔案包含了與 FMP API 互動的核心邏輯，用於獲取全球股票/ETF/指數的日線數據和美股的財報數據。
"""
