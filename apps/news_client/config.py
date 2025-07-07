# apps/news_client/config.py
import os

class NewsClientConfig:
    """
    新聞客戶端設定類別。
    """
    # NewsAPI.org 設定
    NEWSAPI_API_KEY = os.getenv("NEWSAPI_API_KEY")
    NEWSAPI_BASE_URL = "https://newsapi.org/v2/everything" # 'everything' 端點用於搜尋
    # NEWSAPI_TOP_HEADLINES_URL = "https://newsapi.org/v2/top-headlines" # 另一個常用端點

    # 預設數據輸出目錄
    DEFAULT_OUTPUT_PATH = "data/news_data"

    # 情感分析相關設定 (如果有的話)
    # DEFAULT_SENTIMENT_MODEL = "vader"

    # 預設新聞搜尋參數
    DEFAULT_LANGUAGE = "zh" # 預設搜尋中文新聞
    DEFAULT_PAGE_SIZE = 20
    DEFAULT_SORT_BY = "publishedAt" # publishedAt, relevancy, popularity

    @staticmethod
    def get_newsapi_key() -> str:
        """
        獲取 NewsAPI.org 的 API Key。
        如果環境變數 NEWSAPI_API_KEY 未設定，則返回 None 或可拋出錯誤。
        目前 client 和 run.py 的邏輯是如果 key 為 None，則 NewsAPI 功能受限。

        Returns:
            Optional[str]: NewsAPI.org API Key 或 None。
        """
        key = NewsClientConfig.NEWSAPI_API_KEY
        if not key:
            # 可以選擇在這裡印出警告或讓調用者處理 None
            # print("警告: NewsAPI Key (NEWSAPI_API_KEY) 未在環境變數中設定。")
            pass
        return key

# 使用範例
if __name__ == '__main__':
    key = NewsClientConfig.get_newsapi_key()
    if key:
        print(f"NewsAPI Key (前三碼): {key[:3]}...")
    else:
        print("NewsAPI Key 未設定。")

    print(f"NewsAPI 'everything' 端點 URL: {NewsClientConfig.NEWSAPI_BASE_URL}")
    print(f"預設新聞輸出路徑: {NewsClientConfig.DEFAULT_OUTPUT_PATH}")
    print(f"預設搜尋語言: {NewsClientConfig.DEFAULT_LANGUAGE}")

"""
此 `config.py` 檔案目的：
1.  集中管理新聞客戶端相關的設定，例如：
    *   NewsAPI.org 的 API Key 和基礎 URL。
    *   預設的數據輸出路徑。
    *   預設的新聞搜尋參數 (如語言、排序方式等)。
2.  提供一個標準的方式來獲取這些設定值。
3.  使設定與客戶端的核心邏輯 (`client.py`) 和執行腳本 (`run.py`) 分離，方便未來修改設定。

`client.py` 和 `run.py` 目前是直接使用 `os.getenv` 或透過參數傳遞 NewsAPI Key，
並在代碼中直接定義了一些預設值。它們可以被修改來從 `NewsClientConfig` 獲取這些設定，
使得設定更加集中和易於管理。

例如，在 `client.py` 中：
```python
# from .config import NewsClientConfig # 假設在同一個 package

class NewsClient:
    def __init__(self, newsapi_key: Optional[str] = None):
        self.newsapi_key = newsapi_key or NewsClientConfig.get_newsapi_key()
        # ...
```
在 `run.py` 中，可以將 `parser.add_argument` 的 `default` 值設為從 `NewsClientConfig` 讀取。

現階段，此 `config.py` 檔案作為一個已建立的結構，供未來可能的重構或擴展設定時使用。
目前的 `client.py` 和 `run.py` 仍保持其現有的 API Key 處理優先順序 (參數 > 環境變數) 和內部預設值。
"""
