# -*- coding: utf-8 -*-
"""
核心客戶端模組：基礎 API 客戶端 (v2.0 - 快取注入版)

功能：
- 作為所有特定 API 客戶端 (如 FRED, NYFed) 的父類別。
- **關鍵升級**: 內建並整合了來自 core.utils.caching 的中央快取引擎。
- 為所有子類別提供統一的、具備永久快取和手動刷新能力的 requests Session。
"""

from contextlib import contextmanager
from typing import Iterator, Optional

import requests

from prometheus.core.utils.helpers import get_cached_session, temporary_disabled_cache
from prometheus.core.logging.log_manager import LogManager

logger = LogManager.get_instance().get_logger("BaseAPIClient")


class BaseAPIClient:
    """
    所有 API 客戶端的基礎類別，內建了基於 requests-cache 的同步快取機制。
    """

    def __init__(self, api_key: str = None, base_url: str = None):
        """
        初始化基礎客戶端。

        Args:
            api_key (str, optional): API 金鑰 (如果需要)。
            base_url (str, optional): API 的基礎 URL。
        """
        self.api_key = api_key
        self.base_url = base_url
        self._session: requests.Session = get_cached_session()
        logger.info(f"{self.__class__.__name__} 已初始化，並注入了永久快取 Session。")

    @contextmanager
    def _get_request_context(self, force_refresh: bool = False) -> Iterator[None]:
        """
        一個上下文管理器，根據 force_refresh 參數決定是否要暫時禁用快取。
        這是實現「手動刷新」的統一入口點。

        Args:
            force_refresh (bool): 是否強制刷新。
        """
        if force_refresh:
            logger.info(f"{self.__class__.__name__} 偵測到強制刷新指令。")
            with temporary_disabled_cache(self._session):
                yield
        else:
            yield

    def close_session(self):
        """
        關閉 requests session。
        """
        if self._session:
            self._session.close()
            logger.info(f"{self.__class__.__name__} 的 Session 已關閉。")

    def fetch_data(self, symbol: str, **kwargs):
        """
        獲取數據的抽象方法，應由子類別實現。
        這確保了所有子類別都有一個統一的數據獲取入口點。

        Args:
            symbol (str): 要獲取的數據標的 (例如股票代碼、指標代碼)。
            **kwargs: 其他特定於該次請求的參數，例如 `force_refresh`。

        Raises:
            NotImplementedError: 如果子類別沒有實現此方法。
        """
        raise NotImplementedError("子類別必須實現 fetch_data 方法")

    def _perform_request(
        self, endpoint: str, params: Optional[dict] = None, method: str = "GET"
    ) -> requests.Response:
        """
        執行實際的 HTTP 請求。

        Args:
            endpoint (str): API 的端點路徑。
            params (Optional[dict]): 請求參數。
            method (str): HTTP 方法 (例如 "GET", "POST")。

        Returns:
            requests.Response: API 的回應物件。

        Raises:
            requests.exceptions.HTTPError: 如果 API 回應 HTTP 錯誤。
            ValueError: 如果 base_url 未設定。
        """
        if not self.base_url:
            raise ValueError(
                f"{self.__class__.__name__}: base_url is not set, cannot make a request."
            )

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        logger.debug(f"{self.__class__.__name__} 正在向 {method} {url} 發送請求，參數：{params}")

        if method.upper() == "GET":
            response = self._session.get(url, params=params)
        elif method.upper() == "POST":
            response = self._session.post(
                url, params=params
            )  # Or json=params if API expects JSON body
        else:
            raise ValueError(f"不支援的 HTTP 方法: {method}")

        response.raise_for_status()
        return response


# 範例使用 (主要用於開發時測試)
if __name__ == "__main__":
    print("--- BaseAPIClient 升級後測試 (直接執行 core/clients/base.py) ---")

    class MockClient(BaseAPIClient):
        def __init__(self):
            super().__init__(base_url="https://httpbin.org")

        def fetch_data(self, symbol: str, **kwargs):
            endpoint = f"/delay/{symbol}"
            url = self.base_url + endpoint

            # 從 kwargs 中提取 force_refresh 參數
            force_refresh = kwargs.get("force_refresh", False)

            # 使用 _get_request_context 來控制快取
            with self._get_request_context(force_refresh=force_refresh):
                response = self._session.get(url)

            print(f"請求 URL: {url}, 是否來自快取: {response.from_cache}")
            response.raise_for_status()
            return response.json()

    client = MockClient()
    try:
        print("\n--- 執行第一次 (應會下載) ---")
        client.fetch_data("2")  # 延遲 2 秒

        print("\n--- 執行第二次 (應從快取讀取) ---")
        client.fetch_data("2")

        print("\n--- 執行第三次 (強制刷新) ---")
        client.fetch_data("2", force_refresh=True)

    finally:
        client.close_session()

    print("\n--- BaseAPIClient 升級後測試結束 ---")
