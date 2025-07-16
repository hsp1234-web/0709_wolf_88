# core/clients/fmp.py
# 此模組包含與 Financial Modeling Prep (FMP) API 互動的客戶端邏輯。

import os
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from .base import BaseAPIClient
from prometheus.core.logging.log_manager import LogManager

logger = LogManager.get_instance().get_logger("FMPClient")

# 假設配置統一由 BaseAPIClient 或環境變數處理，不再從 core.config 導入 settings
# 如果有統一的 settings 物件，可以後續加入

# FMP API 基礎 URL (不含版本號，版本號將在 endpoint 中處理)
FMP_API_BASE_URL_NO_VERSION = "https://financialmodelingprep.com/api"


class FMPClient(BaseAPIClient):
    """
    Financial Modeling Prep (FMP) API 客戶端。
    用於獲取全球市場（尤其是美股）的財經數據，如歷史價格、公司財報等。
    """

    def __init__(self, api_key: Optional[str] = None, default_api_version: str = "v3"):
        """
        初始化 FMPClient。

        Args:
            api_key (Optional[str]): FMP API key。如果未提供，將嘗試從環境變數 FMP_API_KEY 讀取。
            default_api_version (str): 預設使用的 API 版本 (例如 "v3", "v4")。
                                       實際請求時，端點路徑應包含版本號。
        """
        fmp_api_key = api_key or os.getenv("FMP_API_KEY")
        if not fmp_api_key:
            raise ValueError(
                "FMP API key 未設定。請設定 FMP_API_KEY 環境變數或在初始化時傳入 api_key。"
            )

        super().__init__(api_key=fmp_api_key, base_url=FMP_API_BASE_URL_NO_VERSION)
        self.default_api_version = default_api_version
        logger.info(f"FMPClient 初始化完成，預設 API 版本 '{self.default_api_version}'。")

    def _prepare_params(
        self, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        準備請求參數，特別是添加 FMP 所需的 'apikey'。
        """
        request_params = params.copy() if params else {}
        request_params["apikey"] = self.api_key  # FMP 使用 'apikey'
        return request_params

    def fetch_data(self, symbol: str, **kwargs) -> pd.DataFrame:
        """
        從 FMP API 獲取數據。此方法作為一個統一的入口，
        通過 kwargs 中的 data_type 參數來決定獲取何種數據。

        Args:
            symbol (str): 商品代碼 (例如 "AAPL")。
            **kwargs:
                data_type (str): 必須提供。指定要獲取的數據類型。
                                 可選值: "historical_price", "income_statement",
                                          "balance_sheet_statement", "cash_flow_statement"。
                api_version (str, optional): 指定此次請求使用的 API 版本，預設為客戶端初始化時的 default_api_version。
                from_date (str, optional): 開始日期 (YYYY-MM-DD)，用於歷史價格。
                to_date (str, optional): 結束日期 (YYYY-MM-DD)，用於歷史價格。
                period (str, optional): 財報週期 ("quarter" 或 "annual")，用於財報。預設 "quarter"。
                limit (int, optional): 返回的財報期數或歷史數據點數。預設 20 (用於財報)。

        Returns:
            pd.DataFrame: 包含請求數據的 DataFrame。如果失敗或無數據，則返回空的 DataFrame。

        Raises:
            ValueError: 如果 data_type 未提供或不受支持。
            requests.exceptions.HTTPError: 如果 API 請求失敗。
        """
        data_type = kwargs.pop("data_type", None)
        if not data_type:
            raise ValueError(
                "必須在 kwargs 中提供 'data_type' 參數 (例如 'historical_price', 'income_statement')。"
            )

        api_version = kwargs.pop("api_version", self.default_api_version)
        params: Dict[str, Any] = {}
        endpoint_path_template: str = ""

        if data_type == "historical_price":
            endpoint_path_template = f"{api_version}/historical-price-full/{symbol}"
            if "from_date" in kwargs:
                params["from"] = kwargs["from_date"]
            if "to_date" in kwargs:
                params["to"] = kwargs["to_date"]
            # FMP 的 limit for historical prices might be 'serietype' or implied by date range
            if "limit" in kwargs:
                params["limit"] = str(kwargs["limit"])

        elif data_type in [
            "income-statement",
            "balance-sheet-statement",
            "cash-flow-statement",
        ]:
            endpoint_path_template = f"{api_version}/{data_type}/{symbol}"
            params["period"] = kwargs.get("period", "quarter")
            params["limit"] = str(kwargs.get("limit", 20))

        else:
            raise ValueError(
                f"不支援的 data_type: {data_type}。支援的值為 'historical_price', 'income_statement', 'balance_sheet_statement', 'cash_flow_statement'。"
            )

        final_params = self._prepare_params(params)

        logger.debug(f"正在獲取 '{data_type}' 數據，代碼: {symbol}, Endpoint: {endpoint_path_template}, Params: {params}")

        try:
            response = super()._perform_request(
                endpoint=endpoint_path_template, params=final_params, method="GET"
            )
            json_response = response.json()

            if isinstance(json_response, dict) and "Error Message" in json_response:
                error_msg = json_response["Error Message"]
                logger.error(f"FMP API 返回業務邏輯錯誤：'{error_msg}' (Endpoint: {endpoint_path_template})")
                return pd.DataFrame()

            data_list: Optional[List[Dict[str, Any]]] = None
            if isinstance(json_response, list):
                data_list = json_response
            elif isinstance(json_response, dict):
                possible_data_keys = ["historical"]
                found_key = False
                for key in possible_data_keys:
                    if key in json_response and isinstance(json_response[key], list):
                        data_list = json_response[key]
                        found_key = True
                        break
                if not found_key and data_type not in ["historical_price"]:
                    logger.warning(f"FMP API 返回了一個字典，但未在預期鍵下找到數據列表。Endpoint: {endpoint_path_template}")
                    return pd.DataFrame()

            if data_list is None:
                logger.warning(f"FMP API 回應無法解析為預期的列表結構。Endpoint: {endpoint_path_template}")
                return pd.DataFrame()

            if not data_list:
                logger.info(f"FMP API 未返回 '{symbol}' 的 '{data_type}' 數據。")
                return pd.DataFrame()

            df = pd.DataFrame(data_list)

            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                if data_type == "historical_price":
                    df = df.sort_values(by="date").reset_index(drop=True)
                elif data_type in ["income-statement", "balance-sheet-statement", "cash-flow-statement"]:
                    df = df.sort_values(by="date", ascending=False).reset_index(drop=True)

            logger.info(f"成功獲取並處理了 {len(df)} 筆 '{data_type}' 數據，代碼: {symbol}。")
            return df

        except requests.exceptions.HTTPError as http_err:
            logger.error(f"請求失敗 (HTTP 錯誤)：{http_err}。Endpoint: {endpoint_path_template}", exc_info=True)
            return pd.DataFrame()
        except ValueError as json_err:
            logger.error(f"解析 JSON 回應失敗：{json_err}。Endpoint: {endpoint_path_template}", exc_info=True)
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"處理數據時發生未知錯誤：{e}。Endpoint: {endpoint_path_template}", exc_info=True)
            return pd.DataFrame()


# 範例使用 (主要用於開發時測試)
if __name__ == "__main__":
    print("--- FMPClient 重構後測試 (直接執行 core/clients/fmp.py) ---")
    # 執行此測試前，請確保設定了 FMP_API_KEY 環境變數
    try:
        client = FMPClient(default_api_version="v3")
        print("FMPClient 初始化成功。")

        # 測試獲取歷史股價
        print("\n測試獲取 AAPL 歷史日線價格 (2023-12-01 至 2023-12-05)...")
        aapl_prices = client.fetch_data(
            symbol="AAPL",
            data_type="historical_price",
            from_date="2023-12-01",
            to_date="2023-12-05",
        )
        if not aapl_prices.empty:
            print(f"成功獲取 AAPL 歷史價格數據 (共 {len(aapl_prices)} 筆):")
            print(aapl_prices.head())
        else:
            print(
                "獲取 AAPL 歷史價格數據返回空 DataFrame (請檢查 API Key 權限、日期範圍或日誌中的錯誤)。"
            )

        # 測試獲取財報數據 (v3 income-statement)
        print("\n測試獲取 MSFT 季度損益表 (最近1期, v3)...")
        income_statement_msft = client.fetch_data(
            symbol="MSFT",
            data_type="income-statement",
            period="quarter",
            limit=1,
            api_version="v3",  # 明確指定版本
        )
        if not income_statement_msft.empty:
            print(f"成功獲取 MSFT 季度損益表數據 (共 {len(income_statement_msft)} 筆):")
            print(income_statement_msft.head())
        else:
            print("獲取 MSFT 季度損益表數據返回空 DataFrame。")

        # 測試一個不存在的股票
        print("\n測試獲取不存在股票 'XYZNOTASTOCK' 的歷史價格...")
        non_existent_prices = client.fetch_data(
            symbol="XYZNOTASTOCK",
            data_type="historical_price",
            from_date="2023-01-01",
            to_date="2023-01-05",
        )
        if non_existent_prices.empty:
            print(
                "獲取不存在股票價格數據返回空 DataFrame (符合預期，或 API 返回錯誤)。"
            )
        else:
            print(
                f"獲取不存在股票價格數據返回了非預期的數據: {non_existent_prices.head()}"
            )

        # 測試無效 data_type
        try:
            print("\n測試無效的 data_type...")
            client.fetch_data(symbol="AAPL", data_type="invalid_type")
        except ValueError as ve:
            print(f"成功捕獲到錯誤 (符合預期): {ve}")

    except ValueError as ve_init:  # API Key 未設定等初始化問題
        print(f"初始化錯誤: {ve_init}")
    except Exception as e:
        print(f"執行期間發生未預期錯誤: {e}")

    print("--- FMPClient 重構後測試結束 ---")
