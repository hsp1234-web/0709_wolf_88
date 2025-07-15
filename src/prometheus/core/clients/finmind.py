# core/clients/finmind.py
# 此模組包含與 FinMind API 互動的客戶端邏輯。
from __future__ import annotations

import os
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from .base import BaseAPIClient
from src.prometheus.core.logging.log_manager import LogManager

logger = LogManager.get_instance().get_logger("FinMindClient")

# FinMind API 基礎 URL (所有請求都使用此 URL)
FINMIND_API_BASE_URL = "https://api.finmindtrade.com/api/v4/data"


class FinMindClient(BaseAPIClient):
    """
    用於與 FinMind API 互動的客戶端。
    FinMind API 的特點是所有數據請求都使用同一個基礎 URL，
    具體的數據集和參數在請求的 params 中指定。
    它可能返回 JSON 或 CSV 格式的數據。
    """

    def __init__(self, api_token: Optional[str] = None):
        """
        初始化 FinMindClient。

        Args:
            api_token (Optional[str]): FinMind API Token。如果未提供，
                                       將嘗試從環境變數 FINMIND_API_TOKEN 讀取。
        Raises:
            ValueError: 如果 API Token 未提供且環境變數中也未設定。
        """
        finmind_api_token = api_token or os.getenv("FINMIND_API_TOKEN")
        if not finmind_api_token:
            raise ValueError(
                "FinMind API token 未設定。請設定 FINMIND_API_TOKEN 環境變數或在初始化時傳入 api_token。"
            )

        super().__init__(api_key=finmind_api_token, base_url=FINMIND_API_BASE_URL)
        logger.info("FinMindClient 初始化完成。")

    def _request(
        self, endpoint: str = "", params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        覆寫 BaseAPIClient._request 方法以處理 FinMind API 的特殊性：
        1. API Token 參數名為 "token"。
        2. 端點通常為空，所有資訊通過 params 傳遞。
        3. 回應可能是 JSON 或 CSV，都需要轉換為 DataFrame。
        4. FinMind 的 JSON 回應有自己的 status 和 msg 欄位需要檢查。

        Args:
            endpoint (str): 對於 FinMind 通常為空字串。
            params (Optional[Dict[str, Any]]): API 請求的查詢參數。
                                               必須包含 'dataset', 'data_id', 'start_date' 等。
        Returns:
            pd.DataFrame: 包含 API 回應數據的 DataFrame。如果請求失敗或無數據則返回空的 DataFrame。

        Raises:
            requests.exceptions.HTTPError: 如果 API 返回 HTTP 錯誤狀態碼。
            ValueError: 如果 params 為空或缺少必要參數。
        """
        if not params:
            raise ValueError("請求 FinMind API 時，params 參數不得為空。")

        request_params = params.copy()
        request_params["token"] = self.api_key

        if not self.base_url:
            raise ValueError(
                "FinMindClient: base_url is not set, cannot make a request."
            )

        current_url = (  # Renamed url to current_url to avoid confusion if self.base_url is used later directly
            f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            if endpoint
            else self.base_url
        )

        logger.debug(f"向 FinMind API 發送請求，URL: {current_url}, 資料集：'{request_params.get('dataset')}', 資料ID：'{request_params.get('data_id')}'")

        try:
            if not current_url:
                raise ValueError("FinMindClient: Calculated URL is empty, cannot make a request.")
            response: requests.Response = self._session.get(current_url, params=request_params)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")
            if "text/csv" in content_type:
                logger.debug("FinMind API 回應為 CSV 格式。")
                df = pd.read_csv(StringIO(response.text))
                return df if not df.empty else pd.DataFrame()

            elif "application/json" in content_type:
                logger.debug("FinMind API 回應為 JSON 格式。")
                json_response: Dict[str, Any] = response.json()

                if json_response.get("status") != 200:
                    error_msg = json_response.get("msg", "未知 API 內部錯誤")
                    status_code = json_response.get("status", "N/A")
                    logger.error(f"FinMind API 邏輯錯誤 (內部 status {status_code}): {error_msg}")
                    return pd.DataFrame()

                data_list: Optional[List[Dict[str, Any]]] = json_response.get("data")
                if data_list:
                    return pd.DataFrame(data_list)
                else:
                    logger.info(f"FinMind API 未返回任何數據 (data 列表為空或不存在)。資料集：'{request_params.get('dataset')}', ID：'{request_params.get('data_id')}'")
                    return pd.DataFrame()
            else:
                logger.error(f"未知的 FinMind API 回應 Content-Type: {content_type}")
                return pd.DataFrame()

        except requests.exceptions.HTTPError as http_err:
            logger.error(f"FinMind API HTTP 錯誤：{http_err} - 回應內容：{http_err.response.text if http_err.response else '無回應內容'}", exc_info=True)
            raise
        except requests.exceptions.RequestException as req_err:
            logger.error(f"請求 FinMind API 時發生網路或請求配置錯誤：{req_err}", exc_info=True)
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"處理 FinMind API 回應時發生未知錯誤：{e}", exc_info=True)
            return pd.DataFrame()

    def fetch_data(self, symbol: str, **kwargs) -> pd.DataFrame:
        """
        從 FinMind API 獲取數據。

        Args:
            symbol (str): 資料 ID (例如股票代碼 "2330")。在 FinMind 中對應 'data_id'。
            **kwargs:
                dataset (str): 必須提供。FinMind 資料集名稱 (例如 "TaiwanStockPrice")。
                start_date (str): 必須提供。開始日期 (格式 YYYY-MM-DD)。
                end_date (str, optional): 結束日期 (格式 YYYY-MM-DD)。預設為當前日期。

        Returns:
            pd.DataFrame: 包含請求數據的 DataFrame。如果失敗或無數據，則返回空的 DataFrame。

        Raises:
            ValueError: 如果缺少 'dataset' 或 'start_date' 參數。
            requests.exceptions.HTTPError: 如果 API 請求遭遇 HTTP 錯誤。
        """
        dataset = kwargs.get("dataset")
        start_date = kwargs.get("start_date")

        if not dataset:
            raise ValueError(
                "使用 FinMindClient.fetch_data 時，必須在 kwargs 中提供 'dataset' 參數。"
            )
        if not start_date:
            raise ValueError(
                "使用 FinMindClient.fetch_data 時，必須在 kwargs 中提供 'start_date' 參數。"
            )

        params: Dict[str, Any] = {  # Add type hint for params
            "dataset": dataset,
            "data_id": symbol,
            "start_date": start_date,
            "end_date": kwargs.get("end_date", datetime.now().strftime("%Y-%m-%d")),
        }

        # Add any other kwargs to params for FinMind API
        for key, value in kwargs.items():
            if key not in ["dataset", "start_date", "end_date", "data_id", "symbol"]:
                params[key] = value

        try:
            return self._request(endpoint="", params=params)
        except requests.exceptions.HTTPError:
            raise

    def get_taiwan_stock_institutional_investors_buy_sell(
        self, stock_id: str, start_date: str, end_date: Optional[str] = None
    ) -> pd.DataFrame:
        return self.fetch_data(
            symbol=stock_id,
            dataset="TaiwanStockInstitutionalInvestorsBuySell",
            start_date=start_date,
            end_date=end_date,
        )


if __name__ == "__main__":
    print("--- FinMindClient 重構後測試 (直接執行 core/clients/finmind.py) ---")
    try:
        client = FinMindClient()
        print("FinMindClient 初始化成功。")

        print("\n測試獲取台積電 (2330) 法人買賣超 (2024-01-01 至 2024-01-05)...")
        investor_data = client.get_taiwan_stock_institutional_investors_buy_sell(
            stock_id="2330", start_date="2024-01-01", end_date="2024-01-05"
        )
        if not investor_data.empty:
            print(f"成功獲取股票 2330 的法人買賣超數據 (共 {len(investor_data)} 筆):")
            print(investor_data.head())
        else:
            print(
                "股票 2330 的法人買賣超數據請求成功，但返回為空 DataFrame (請檢查 API Key, 日期範圍或日誌)。"
            )

        print(
            "\n測試使用 fetch_data 獲取聯發科 (2454) 股價 (2024-03-01 至 2024-03-05)..."
        )
        stock_price_data = client.fetch_data(
            symbol="2454",
            dataset="TaiwanStockPrice",
            start_date="2024-03-01",
            end_date="2024-03-05",
        )
        if not stock_price_data.empty:
            print(f"成功獲取股票 2454 的股價數據 (共 {len(stock_price_data)} 筆):")
            print(stock_price_data.head())
        else:
            print("股票 2454 的股價數據請求成功，但返回為空 DataFrame。")

        print("\n測試一個不存在的股票代碼 (XYZABC) 使用 fetch_data...")
        non_existent_data = client.fetch_data(
            symbol="XYZABC",
            dataset="TaiwanStockPrice",
            start_date="2023-01-01",
            end_date="2023-01-05",
        )
        if non_existent_data.empty:
            print(
                "獲取 XYZABC 數據返回空 DataFrame (符合預期，因為股票不存在或請求錯誤)。"
            )
        else:
            print(f"獲取 XYZABC 數據返回了非預期的數據: \n{non_existent_data.head()}")

        try:
            print("\n測試 fetch_data 缺少 'dataset'...")
            client.fetch_data(symbol="2330", start_date="2024-01-01")  # Missing dataset
        except ValueError as ve:
            print(f"成功捕獲錯誤 (符合預期): {ve}")

    except ValueError as ve_init:
        print(f"初始化錯誤: {ve_init}")
    except requests.exceptions.HTTPError as http_e:
        print(f"捕獲到 HTTP 錯誤 (可能是 API Token 無效或網路問題): {http_e}")
    except Exception as e:
        print(f"執行期間發生未預期錯誤: {e}")

    print("--- FinMindAPIClient 重構後測試結束 ---")
