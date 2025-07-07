# apps/news_client/test_client.py
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import os
import sys
from datetime import datetime, timedelta
from typing import Optional # Import Optional

# 將專案根目錄加到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from apps.news_client.client import NewsClient, NEWSAPI_BASE_URL, VADER_AVAILABLE

# 模擬的 API Key
MOCK_NEWSAPI_KEY = "test_newsapi_key"

# 輔助函數：建立模擬的 NewsAPI 回應
def mock_newsapi_response(articles_data: Optional[list], status: str = "ok", code: Optional[str] = None, message: Optional[str] = None, http_status_code: int = 200):
    mock_resp = MagicMock()
    mock_resp.status_code = http_status_code

    response_json = {"status": status}
    if articles_data is not None:
        response_json["articles"] = articles_data
        response_json["totalResults"] = len(articles_data)
    if code:
        response_json["code"] = code
    if message:
        response_json["message"] = message

    mock_resp.json.return_value = response_json

    if http_status_code >= 400:
        mock_resp.raise_for_status = MagicMock(side_effect=requests.exceptions.HTTPError(response=mock_resp))
    else:
        mock_resp.raise_for_status = MagicMock()
    return mock_resp

try:
    import requests.exceptions
except ImportError:
    class MockHTTPError(Exception):
        def __init__(self, response=None):
            self.response = response
    class MockRequestsModule:
        class exceptions:
            HTTPError = MockHTTPError
    requests = MockRequestsModule()


class TestNewsClient(unittest.TestCase):

    def setUp(self):
        # 測試時總是假設有 key，除非特定測試要驗證無 key 的情況
        self.client_with_key = NewsClient(newsapi_key=MOCK_NEWSAPI_KEY)
        # 用於測試無 key 時的行為，不依賴環境變數
        self.client_without_key = NewsClient(newsapi_key=None)

        self.keywords = "test keyword"
        self.from_date = "2023-01-01"
        self.to_date = "2023-01-02"

        # 模擬的 NewsAPI 文章數據
        self.mock_article_1 = {
            "source": {"id": "test-source", "name": "Test Source"},
            "author": "Test Author",
            "title": "Test Title 1 about keyword",
            "description": "Test description 1.",
            "url": "http://example.com/article1",
            "urlToImage": "http://example.com/image1.jpg",
            "publishedAt": "2023-01-01T10:00:00Z",
            "content": "Test content 1..."
        }
        self.mock_article_2 = {
            "source": {"id": None, "name": "Another Source"}, # source.id might be None
            "author": None,
            "title": "Another Test Title 2",
            "description": None, # description might be None
            "url": "http://example.com/article2",
            "urlToImage": None,
            "publishedAt": "2023-01-02T12:00:00Z",
            "content": None
        }

    @patch.dict(os.environ, {"NEWSAPI_API_KEY": "env_key_test"}, clear=True)
    def test_initialization_with_env_variable(self):
        # 為了讓 NewsClient 初始化時讀取到 patch 的環境變數，
        # 我們 patch client 模組中的 NEWSAPI_KEY 變數，
        # 然後在初始化 Client 時傳入 newsapi_key=None 來觸發其讀取。
        with patch('apps.news_client.client.NEWSAPI_KEY', 'env_key_test'):
            client = NewsClient(newsapi_key=None)
            self.assertEqual(client.newsapi_key, "env_key_test")

    def test_initialization_with_provided_key(self):
        client = NewsClient(newsapi_key="provided_key_test")
        self.assertEqual(client.newsapi_key, "provided_key_test")

    @patch.dict(os.environ, {}, clear=True) # 確保環境變數是空的
    def test_initialization_without_key_prints_warning(self):
        with patch('builtins.print') as mock_print:
            NewsClient(newsapi_key=None) # 也測試明確傳入 None
            mock_print.assert_any_call("警告：NewsAPI.org 的 API Key 未設定。部分新聞抓取功能可能受限。")

    @patch('apps.news_client.client.requests.get')
    def test_get_news_by_keyword_success(self, mock_get):
        mock_articles = [self.mock_article_1, self.mock_article_2]
        mock_get.return_value = mock_newsapi_response(articles_data=mock_articles)

        df = self.client_with_key.get_news_by_keyword(
            self.keywords, self.from_date, self.to_date, language="en", sort_by="relevance", page_size=10, page=1
        )
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]["title"], self.mock_article_1["title"])
        self.assertEqual(df.iloc[1]["source_name"], self.mock_article_2["source"]["name"])
        self.assertTrue("description" in df.columns) # 確保所有預期欄位存在

        expected_params = {
            "q": self.keywords,
            "from": self.from_date,
            "to": self.to_date,
            "language": "en",
            "sortBy": "relevance",
            "pageSize": 10,
            "page": 1
        }
        # API Key 是透過 header 傳遞的，所以不在 params 裡
        mock_get.assert_called_once_with(
            NEWSAPI_BASE_URL,
            params=expected_params,
            headers={"Authorization": f"Bearer {MOCK_NEWSAPI_KEY}"}
        )

    @patch('apps.news_client.client.requests.get')
    def test_get_news_by_keyword_no_key(self, mock_get):
        # client_without_key 初始化時 newsapi_key 為 None
        with patch('builtins.print') as mock_print:
            df = self.client_without_key.get_news_by_keyword(self.keywords)
            self.assertIsNone(df) # 應該返回 None
            mock_print.assert_any_call("錯誤：NewsAPI.org API Key 未設定，無法發送請求。")
        mock_get.assert_not_called() # 不應該發出請求

    @patch('apps.news_client.client.requests.get')
    def test_get_news_by_keyword_api_error_status_not_ok(self, mock_get):
        mock_get.return_value = mock_newsapi_response(None, status="error", code="apiKeyInvalid", message="Your API key is invalid.")
        with patch('builtins.print') as mock_print:
            df = self.client_with_key.get_news_by_keyword(self.keywords)
            self.assertIsNone(df)
            mock_print.assert_any_call("NewsAPI 錯誤：apiKeyInvalid - Your API key is invalid.")

    @patch('apps.news_client.client.requests.get')
    def test_get_news_by_keyword_http_error(self, mock_get):
        mock_get.return_value = mock_newsapi_response(None, http_status_code=500, status="error") # 模擬伺服器錯誤
        with patch('builtins.print') as mock_print:
            df = self.client_with_key.get_news_by_keyword(self.keywords)
            self.assertIsNone(df)
            mock_print.assert_any_call(unittest.mock.ANY) # 應該有 requests.exceptions.RequestException 的錯誤訊息

    @patch('apps.news_client.client.requests.get')
    def test_get_news_by_keyword_request_exception(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("Connection timeout")
        with patch('builtins.print') as mock_print:
            df = self.client_with_key.get_news_by_keyword(self.keywords)
            self.assertIsNone(df)
            mock_print.assert_any_call("請求 NewsAPI 時發生錯誤：Connection timeout")

    @patch('apps.news_client.client.requests.get')
    def test_get_news_by_keyword_no_articles_found(self, mock_get):
        mock_get.return_value = mock_newsapi_response(articles_data=[]) # API 成功，但文章列表為空
        df = self.client_with_key.get_news_by_keyword(self.keywords)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)

    @patch('apps.news_client.client.requests.get')
    def test_get_news_by_keyword_date_warning(self, mock_get):
        """測試當 from_date 過早時是否印出警告"""
        mock_articles = [self.mock_article_1]
        mock_get.return_value = mock_newsapi_response(articles_data=mock_articles)

        very_old_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")

        with patch('builtins.print') as mock_print:
            self.client_with_key.get_news_by_keyword(self.keywords, from_date=very_old_date)
            mock_print.assert_any_call(f"警告: NewsAPI 免費版可能不支援查詢一個月前的日期 ({very_old_date})。")


    # --- Sentiment Analysis Tests ---
    @unittest.skipIf(not VADER_AVAILABLE, "VaderSentiment套件未安裝，跳過情感分析相關測試。")
    def test_analyze_sentiment_vader_positive(self):
        client = NewsClient(newsapi_key="dummy") # key 不影響此測試
        text = "This is a great and wonderful event!"
        sentiment = client.analyze_sentiment_vader(text)
        self.assertIsNotNone(sentiment)
        self.assertTrue(sentiment['compound'] > 0)
        self.assertTrue(sentiment['pos'] > sentiment['neg'])

    @unittest.skipIf(not VADER_AVAILABLE, "VaderSentiment套件未安裝，跳過情感分析相關測試。")
    def test_analyze_sentiment_vader_negative(self):
        client = NewsClient(newsapi_key="dummy")
        text = "This is a terrible and awful situation."
        sentiment = client.analyze_sentiment_vader(text)
        self.assertIsNotNone(sentiment)
        self.assertTrue(sentiment['compound'] < 0)
        self.assertTrue(sentiment['neg'] > sentiment['pos'])

    @unittest.skipIf(not VADER_AVAILABLE, "VaderSentiment套件未安裝，跳過情感分析相關測試。")
    def test_analyze_sentiment_vader_empty_text(self):
        client = NewsClient(newsapi_key="dummy")
        sentiment = client.analyze_sentiment_vader("")
        self.assertIsNone(sentiment) # Vader 對空字串可能返回中性，但我們 client 應返回 None

    @unittest.skipIf(not VADER_AVAILABLE, "VaderSentiment套件未安裝，跳過情感分析相關測試。")
    def test_add_sentiment_to_dataframe(self):
        client = NewsClient(newsapi_key="dummy")
        data = {
            "title": ["Great news!", "Bad news.", "Okay news."],
            "description": ["Very positive content.", "Very negative content.", "Neutral content."]
        }
        df = pd.DataFrame(data)
        df_with_sentiment = client.add_sentiment_to_dataframe(df.copy(), text_column="title")

        self.assertIn("vader_compound", df_with_sentiment.columns)
        self.assertIn("vader_pos", df_with_sentiment.columns)
        self.assertIn("vader_neu", df_with_sentiment.columns)
        self.assertIn("vader_neg", df_with_sentiment.columns)
        self.assertTrue(df_with_sentiment.loc[0, "vader_compound"] > 0) # Great news!
        self.assertTrue(df_with_sentiment.loc[1, "vader_compound"] < 0) # Bad news.

    @unittest.skipIf(not VADER_AVAILABLE, "VaderSentiment套件未安裝，跳過情感分析相關測試。")
    def test_add_sentiment_to_dataframe_wrong_column(self):
        client = NewsClient(newsapi_key="dummy")
        df = pd.DataFrame({"title": ["some text"]})
        with patch('builtins.print') as mock_print:
            # 嘗試使用不存在的欄位
            df_result = client.add_sentiment_to_dataframe(df.copy(), text_column="non_existent_column")
            self.assertTrue(df_result.equals(df)) # 應返回原 DataFrame
            mock_print.assert_any_call("錯誤：DataFrame 中找不到指定的文本欄位 'non_existent_column'。")

    # 測試 Vader 不可用時的情感分析調用
    @patch('apps.news_client.client.VADER_AVAILABLE', False)
    @patch('apps.news_client.client.SentimentIntensityAnalyzer', None) # 確保分析器也是 None
    def test_sentiment_functions_when_vader_unavailable(self):
        # 重新初始化 client 以便 VADER_AVAILABLE 的 patch 生效
        client_no_vader = NewsClient(newsapi_key="dummy")
        self.assertIsNone(client_no_vader.sentiment_analyzer)

        with patch('builtins.print') as mock_print:
            # 測試 analyze_sentiment_vader
            sentiment = client_no_vader.analyze_sentiment_vader("Some text")
            self.assertIsNone(sentiment)
            mock_print.assert_any_call("VaderSentiment 套件未安裝，無法進行情感分析。請執行 pip install vaderSentiment")

            # 測試 add_sentiment_to_dataframe
            df = pd.DataFrame({"title": ["some text"]})
            df_original = df.copy()
            df_result = client_no_vader.add_sentiment_to_dataframe(df, text_column="title")
            self.assertTrue(df_result.equals(df_original)) # 應返回原 DataFrame
            mock_print.assert_any_call("VaderSentiment 套件未安裝，無法進行情感分析。")


if __name__ == '__main__':
    # 如果直接執行此檔案，需要確保 requests.exceptions.HTTPError 存在
    # 即使 requests 未安裝，也定義一個模擬的，以便測試能運行
    if 'requests' not in sys.modules:
        class MockHTTPError(Exception): pass
        sys.modules['requests'] = MagicMock()
        sys.modules['requests.exceptions'] = MagicMock()
        sys.modules['requests.exceptions.HTTPError'] = MockHTTPError

    unittest.main(argv=['first-arg-is-ignored'], exit=False)

"""
此 `test_client.py` 檔案包含針對 `NewsClient` 類別的單元測試。

測試內容涵蓋：
1.  **初始化**:
    *   使用環境變數或提供的 API Key 初始化。
    *   未提供 API Key 時，客戶端應能建立但 NewsAPI 功能受限，並印出警告。
2.  **`get_news_by_keyword` (NewsAPI.org)**:
    *   **成功情況**: 模擬 API 成功返回新聞文章，驗證 DataFrame 格式和內容，以及請求參數是否正確。
    *   **無 API Key**: 驗證在沒有 API Key 的情況下調用此方法，不會發出請求並返回 `None`。
    *   **API 錯誤**: 模擬 NewsAPI 返回 "status": "error" (例如 API Key 無效)，驗證返回 `None`。
    *   **HTTP 錯誤**: 模擬網路請求返回 HTTP 錯誤狀態碼 (例如 500)，驗證返回 `None`。
    *   **請求異常**: 模擬 `requests.get` 拋出 `RequestException` (例如網路問題)，驗證返回 `None`。
    *   **無結果**: 模擬 API 成功但未找到任何文章，驗證返回空的 DataFrame。
    *   **日期警告**: 測試當查詢過舊日期時，是否會印出 NewsAPI 免費版限制的警告。
3.  **情感分析 (VaderSentiment)**:
    *   使用 `@unittest.skipIf(not VADER_AVAILABLE, ...)` 來跳過這些測試 (如果 `vaderSentiment` 未安裝)。
    *   `analyze_sentiment_vader`: 測試正面、負面文本的情感分數是否符合預期，以及空文本的處理。
    *   `add_sentiment_to_dataframe`: 測試是否能成功為 DataFrame 添加情感分析結果欄位，以及處理不存在的文本欄位。
    *   **Vader 不可用**: 測試當 `vaderSentiment` 套件不可用時，情感分析相關方法是否能優雅處理 (例如返回 `None` 或原始數據，並印出提示)。

使用 `unittest.mock.patch` 來模擬 `requests.get` 的行為和 `VADER_AVAILABLE` 的狀態。
輔助函數 `mock_newsapi_response` 用於簡化模擬 NewsAPI.org 回應的建立。

執行測試:
在 `apps/news_client/` 目錄下執行 `python -m unittest test_client.py`。
"""
