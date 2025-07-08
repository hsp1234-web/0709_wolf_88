import time
import random
import logging
from typing import Optional, Dict, Any, Callable
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry # type: ignore

# 為此模組設定日誌記錄器
http_client_logger = logging.getLogger(__name__)
if not http_client_logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    http_client_logger.addHandler(handler)
    http_client_logger.setLevel(logging.INFO)
    # http_client_logger.propagate = False # 可選，如果不想讓此 logger 的日誌傳播到 root logger

class HttpClient:
    """
    一個具有防禦性爬取策略的中央化 HTTP 客戶端。
    特性：
    - 偽裝 User-Agent。
    - 請求間隨機延遲。
    - 指數退避重試機制。
    """
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    DEFAULT_RETRY_STRATEGY = Retry(
        total=3,  # 總重試次數
        backoff_factor=1,  # 退避因子 (e.g., 1s, 2s, 4s)
        status_forcelist=[429, 500, 502, 503, 504],  # 需要重試的 HTTP 狀態碼
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"] # 允許重試的請求方法
    )
    MIN_DELAY_S = 0.5  # 最小延遲秒數
    MAX_DELAY_S = 2.0   # 最大延遲秒數

    def __init__(
        self,
        user_agent: Optional[str] = None,
        retry_strategy: Optional[Retry] = None,
        min_delay_s: float = MIN_DELAY_S,
        max_delay_s: float = MAX_DELAY_S
    ):
        """
        初始化 HttpClient。

        Args:
            user_agent (Optional[str]): 要使用的 User-Agent 字串。預設為常見的瀏覽器 User-Agent。
            retry_strategy (Optional[Retry]): requests 的 Retry 對象。預設為3次重試，針對常見的臨時錯誤。
            min_delay_s (float): 請求間的最小隨機延遲（秒）。
            max_delay_s (float): 請求間的最大隨機延遲（秒）。
        """
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.retry_strategy = retry_strategy or self.DEFAULT_RETRY_STRATEGY
        self.min_delay_s = min_delay_s
        self.max_delay_s = max_delay_s

        self.session = requests.Session()
        self.session.headers["User-Agent"] = self.user_agent

        # 掛載 HTTP 適配器以實現重試
        adapter = HTTPAdapter(max_retries=self.retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        http_client_logger.info(
            f"HttpClient 初始化完成。User-Agent: {self.user_agent}, "
            f"Retry: total={self.retry_strategy.total}, backoff={self.retry_strategy.backoff_factor}, "
            f"Delay: min={self.min_delay_s}s, max={self.max_delay_s}s"
        )

    def _random_delay(self):
        """在請求前執行一個隨機延遲。"""
        delay = random.uniform(self.min_delay_s, self.max_delay_s)
        http_client_logger.debug(f"隨機延遲 {delay:.2f} 秒...")
        time.sleep(delay)

    def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        **kwargs: Any
    ) -> requests.Response:
        """
        執行 HTTP 請求。

        Args:
            method (str): HTTP 方法 (e.g., "GET", "POST").
            url (str): 請求的 URL.
            params (Optional[Dict[str, Any]]): URL 查詢參數。
            data (Optional[Dict[str, Any]]): application/x-www-form-urlencoded 請求體。
            json_data (Optional[Dict[str, Any]]): application/json 請求體。
            headers (Optional[Dict[str, str]]): 自訂請求頭。
            timeout (int): 請求超時時間（秒）。
            **kwargs: 其他 requests.request 方法接受的參數。

        Returns:
            requests.Response: HTTP 回應物件。

        Raises:
            requests.exceptions.RequestException: 如果請求過程中發生錯誤且重試失敗。
        """
        self._random_delay()

        # 合併預設 session headers 和函數呼叫時傳入的 headers
        request_headers = self.session.headers.copy()
        if headers:
            request_headers.update(headers)

        http_client_logger.info(f"發送 {method} 請求到 {url}...")
        http_client_logger.debug(f"請求參數: params={params}, data={data}, json_data={json_data}, headers={request_headers}")

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json_data,
                headers=request_headers,
                timeout=timeout,
                **kwargs
            )
            # 觸發 HTTPError (如果狀態碼是 4xx 或 5xx)
            response.raise_for_status()
            http_client_logger.info(f"請求成功: {method} {url} - 狀態碼: {response.status_code}")
            return response
        except requests.exceptions.HTTPError as http_err:
            http_client_logger.warning(
                f"HTTP 錯誤: {method} {url} - 狀態碼: {http_err.response.status_code}. 回應: {http_err.response.text[:200]}"
            )
            raise # 重試機制已由 adapter 處理，若到此處表示重試已用盡或非重試範圍錯誤
        except requests.exceptions.RequestException as req_err:
            http_client_logger.error(f"請求失敗: {method} {url} - 錯誤: {req_err}")
            raise # 同上，重試已處理

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        """執行 GET 請求。"""
        return self.request(method="GET", url=url, **kwargs)

    def post(self, url: str, data: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> requests.Response:
        """執行 POST 請求。"""
        return self.request(method="POST", url=url, data=data, json_data=json_data, **kwargs)

    def close(self):
        """關閉 requests session。"""
        http_client_logger.info("關閉 HttpClient session...")
        self.session.close()

# 為了方便，可以提供一個預設的 HttpClient 實例
# default_http_client = HttpClient()

if __name__ == '__main__':
    # 簡易測試
    http_client_logger.info("--- 測試 HttpClient (樁) ---")

    # 測試 GET
    client = HttpClient(min_delay_s=0.1, max_delay_s=0.5) # 測試時使用較短延遲
    try:
        # 使用一個會成功的公開 API 進行測試
        # test_url_get = "https://httpbin.org/get"
        test_url_get = "https://jsonplaceholder.typicode.com/todos/1" # 另一個可靠的測試 API
        http_client_logger.info(f"測試 GET 請求到: {test_url_get}")
        response_get = client.get(test_url_get)
        http_client_logger.info(f"GET 請求成功。狀態碼: {response_get.status_code}")
        http_client_logger.info(f"GET 回應內容 (前100字元): {response_get.text[:100]}")

        # 測試 POST
        # test_url_post = "https://httpbin.org/post"
        test_url_post = "https://jsonplaceholder.typicode.com/posts" # 另一個可靠的測試 API
        post_data = {"title": "foo", "body": "bar", "userId": 1}
        http_client_logger.info(f"測試 POST 請求到: {test_url_post}，數據: {post_data}")
        response_post = client.post(test_url_post, json_data=post_data)
        http_client_logger.info(f"POST 請求成功。狀態碼: {response_post.status_code}")
        http_client_logger.info(f"POST 回應內容 (前100字元): {response_post.json() if response_post.content else 'N/A'}")

        # 測試重試 (模擬一個會暫時失敗的端點)
        # httpbin 可以模擬狀態碼
        retry_test_url = "https://httpbin.org/status/503,200" # 第一次503，之後200
        # 為了讓 httpbin.org/status/code1,code2... 生效，我們需要確保Retry策略允許對POST重試 (如果用POST)
        # 或者找到一個GET請求就能觸發重試的方式。
        # 這裡我們假設 GET 請求也可能遇到 503

        # 建立一個新的 client，讓重試次數少一點，方便觀察
        retry_client = HttpClient(
            retry_strategy=Retry(total=2, backoff_factor=0.1, status_forcelist=[503]),
            min_delay_s=0.1, max_delay_s=0.2
        )
        http_client_logger.info(f"測試重試機制，請求到: {retry_test_url}")
        try:
            # response_retry = retry_client.get(retry_test_url) # httpbin.org/status/503,200 似乎只對第一次請求有效
            # 我們需要一個能真正模擬多次失敗後成功的服務，或者手動在服務端控制
            # 為了演示，我們先假設一個總是失敗的端點，看重試是否發生
            failing_url = "https://httpbin.org/status/503" # 此端點總是返回 503
            http_client_logger.info(f"測試重試 (預期失敗) 到: {failing_url}")
            retry_client.get(failing_url)
        except requests.exceptions.HTTPError as e:
            http_client_logger.info(f"重試測試中捕獲到預期的 HTTPError: {e.response.status_code}")
            if e.response.status_code == 503:
                 http_client_logger.info("成功捕獲到 503 錯誤，重試機制已嘗試。")
            else:
                 http_client_logger.error("重試測試中捕獲到非預期的 HTTPError。")
        except Exception as e:
            http_client_logger.error(f"重試測試中發生非預期錯誤: {e}")


    except requests.exceptions.RequestException as e:
        http_client_logger.error(f"HttpClient 測試中發生錯誤: {e}")
    finally:
        client.close()
        if 'retry_client' in locals():
            retry_client.close()

    http_client_logger.info("--- HttpClient 測試完畢 ---")
