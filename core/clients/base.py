# core/clients/base.py
import requests
import pandas as pd
from abc import ABC, abstractmethod


class BaseAPIClient(ABC):
    """
    所有 API 客戶端的抽象基礎類，封裝了通用的請求、認證和錯誤處理 logique。
    """

    def __init__(self, api_key: str | None, base_url: str | None): # Changed to Optional[str]
        self.api_key = api_key
        self.base_url = base_url
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    def _request(self, endpoint: str, params: dict | None = None) -> dict:
        """
        執行動態請求的核心方法。

        Args:
            endpoint: API 的端點路徑。
            params: 請求的查詢參數。

        Returns:
            API 返回的 JSON 數據。

        Raises:
            requests.exceptions.HTTPError: 如果 API 返回錯誤狀態碼。
        """
        if params is None:
            params = {}
        # 統一處理 API Key，子類無需關心
        # 注意：這裡的 'apikey' 是通用名稱，部分 API 可能使用不同名稱，例如 'api_token', 'token'
        # 或甚至根本不在 params 中，而是在 headers。
        # 實際子類化時，如果 API Key 的參數名或傳遞方式不同，
        # 子類可能需要覆寫此 _request 方法，或在調用 super()._request() 前後調整 params/headers。
        # FinMind 使用 'token'，FRED 使用 'api_key'，FMP 使用 'apikey'。
        # NYFed 和 YFinance 不直接在 params 中使用 key。
        # 為了通用性，這裡暫定為 'apikey'，但後續重構各客戶端時需要特別注意。
        # 一個更彈性的做法可能是在 __init__ 中允許指定 API key 的參數名。
        # 或者，讓子類負責將 API key 加入到 params。
        # 根據計畫書，父類處理 'apikey'，這意味著 FMPClient 的 API Key 參數名是 'apikey'。
        # FinMind 和 FRED 需要調整。

        # 子類應負責準備包含其特定認證信息的 params。
        # BaseAPIClient._request 只負責執行請求。

        if not self.base_url:
            raise ValueError("BaseAPIClient: base_url is not set, cannot make a request.")

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        response = self._session.get(url, params=params)
        response.raise_for_status()  # type: ignore[no-untyped-call] # 如果狀態碼不是 2xx，則拋出異常
        return response.json()  # type: ignore[no-any-return]

    @abstractmethod
    def fetch_data(
        self, symbol: str, **kwargs
    ) -> pd.DataFrame:  # 增加 **kwargs 以適應不同客戶端的需求
        """
        子類必須實現此方法，定義如何獲取特定數據並轉換為 DataFrame。
        增加 **kwargs 以允許子類傳遞額外參數，例如日期範圍。
        """
        pass
