# apps/news_client/client.py
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
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

# NewsAPI (newsapi.org) 設定
NEWSAPI_KEY = os.getenv("NEWSAPI_API_KEY") # 注意環境變數名稱
NEWSAPI_BASE_URL = "https://newsapi.org/v2/everything"

# (可選) Google News (unofficial) - 如果要用 gnews 庫
# from gnews import GNews

# (可選) VaderSentiment (用於情感分析)
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False
    SentimentIntensityAnalyzer = None # 避免 NameError

class NewsClient:
    """
    新聞客戶端，用於抓取財經新聞並進行初步處理。
    目前主要實作 newsapi.org 的對接。
    """
    def __init__(self, newsapi_key: Optional[str] = None):
        """
        初始化 NewsClient。

        Args:
            newsapi_key (Optional[str]): NewsAPI.org 的 API Key。
                                         如果未提供，則從環境變數 NEWSAPI_API_KEY 讀取。
        """
        self.newsapi_key = newsapi_key or NEWSAPI_KEY
        if not self.newsapi_key:
            # 如果沒有 newsapi_key，某些功能可能無法使用，但暫不強制拋出錯誤，
            # 因為未來可能整合其他不需 key 的新聞來源。
            print("警告：NewsAPI.org 的 API Key 未設定。部分新聞抓取功能可能受限。")
            # raise ValueError("NewsAPI.org 的 API Key 未設定。請設定 NEWSAPI_API_KEY 環境變數或在初始化時傳入。")

        self.sentiment_analyzer = None
        if VADER_AVAILABLE:
            self.sentiment_analyzer = SentimentIntensityAnalyzer()

    def _make_newsapi_request(self, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        向 NewsAPI.org 發送請求並處理回應。

        Args:
            params (Dict[str, Any]): API 請求參數。

        Returns:
            Optional[List[Dict[str, Any]]]: 包含新聞文章數據的列表，如果請求失敗則返回 None。
        """
        if not self.newsapi_key:
            print("錯誤：NewsAPI.org API Key 未設定，無法發送請求。")
            return None

        headers = {"Authorization": f"Bearer {self.newsapi_key}"}
        # NewsAPI v2 的 key 也可以放在 params: params["apiKey"] = self.newsapi_key
        # 但 Authorization header 是推薦做法

        try:
            response = requests.get(NEWSAPI_BASE_URL, params=params, headers=headers)
            response.raise_for_status()
            json_response = response.json()

            if json_response.get("status") == "ok":
                return json_response.get("articles", [])
            else:
                print(f"NewsAPI 錯誤：{json_response.get('code')} - {json_response.get('message')}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"請求 NewsAPI 時發生錯誤：{e}")
            return None
        except Exception as e:
            print(f"處理 NewsAPI 回應時發生未知錯誤：{e}")
            return None

    def get_news_by_keyword(self,
                            keywords: str,
                            from_date: Optional[str] = None,
                            to_date: Optional[str] = None,
                            language: str = "zh", # NewsAPI 支援 'zh' 代表中文
                            sort_by: str = "publishedAt", # relevance, popularity, publishedAt
                            page_size: int = 20, # 免費版 NewsAPI 單次請求最多 100
                            page: int = 1
                           ) -> Optional[pd.DataFrame]:
        """
        根據關鍵字從 NewsAPI.org 抓取新聞。
        對應分析點 #10 (新聞事件漂移效應)。

        Args:
            keywords (str): 搜尋關鍵字 (例如 "台積電", "聯準會 升息", "TSLA earnings").
                            NewsAPI 的 q 參數支援 AND/OR/NOT 和引號。
            from_date (Optional[str]): 搜尋起始日期 "YYYY-MM-DD" 或 "YYYY-MM-DDTHH:MM:SSZ"。
                                       免費版 NewsAPI 只能搜尋過去一個月的文章。
            to_date (Optional[str]): 搜尋結束日期 "YYYY-MM-DD" 或 "YYYY-MM-DDTHH:MM:SSZ"。
            language (str): 新聞語言 (例如 "en", "zh", "de")。預設 "zh"。
            sort_by (str): 排序方式 ("relevance", "popularity", "publishedAt")。預設 "publishedAt"。
            page_size (int): 每頁返回的文章數量。
            page (int): 請求的頁碼。

        Returns:
            Optional[pd.DataFrame]: 包含新聞數據 (標題, 摘要/內容, 發布時間, 來源等) 的 DataFrame。
        """
        params = {
            "q": keywords,
            "language": language,
            "sortBy": sort_by,
            "pageSize": min(page_size, 100), # NewsAPI 上限
            "page": page,
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        # 免費版 NewsAPI 的日期限制 (通常是過去一個月)
        # 如果 from_date 太早，API 會報錯。這裡可以加入一個檢查。
        if from_date:
            try:
                from_dt = datetime.fromisoformat(from_date.replace("Z", ""))
                one_month_ago = datetime.now() - timedelta(days=30) # 大約一個月
                if from_dt < one_month_ago:
                    print(f"警告: NewsAPI 免費版可能不支援查詢一個月前的日期 ({from_date})。")
            except ValueError:
                print(f"警告: from_date '{from_date}' 格式錯誤。")


        articles_data = self._make_newsapi_request(params)

        if articles_data is not None:
            if not articles_data:
                return pd.DataFrame() # 返回空的 DataFrame

            # 提取需要的欄位
            processed_articles = []
            for article in articles_data:
                processed_articles.append({
                    "title": article.get("title"),
                    "description": article.get("description"), # 通常是摘要
                    "content": article.get("content"), # 可能不完整，或為 null
                    "url": article.get("url"),
                    "published_at": article.get("publishedAt"),
                    "source_id": article.get("source", {}).get("id"),
                    "source_name": article.get("source", {}).get("name"),
                    "author": article.get("author")
                })
            df = pd.DataFrame(processed_articles)
            return df
        return None

    def analyze_sentiment_vader(self, text: str) -> Optional[Dict[str, float]]:
        """
        (可選進階功能) 使用 VaderSentiment 對文本進行情感分析 (主要適用於英文)。

        Args:
            text (str): 要分析的文本。

        Returns:
            Optional[Dict[str, float]]: 包含情感分數的字典 (neg, neu, pos, compound)，
                                        如果 Vader 不可用或文本為空則返回 None。
        """
        if not self.sentiment_analyzer or not text:
            if not VADER_AVAILABLE:
                print("VaderSentiment 套件未安裝，無法進行情感分析。請執行 pip install vaderSentiment")
            return None

        # Vader 对于中文效果不佳，这里仅作演示，实际中文情感分析需要其他库
        if any("\u4e00" <= char <= "\u9fff" for char in text): # 简单判断是否含中文
            print("警告：VaderSentiment 主要用於英文文本，對中文效果可能不佳。")

        try:
            # Vader 的 polarity_scores 方法返回一个字典
            # {'neg': 0.0, 'neu': 0.0, 'pos': 1.0, 'compound': 0.4215}
            # compound 分數是 -1 (最負面) 到 +1 (最正面) 的標準化總和分數。
            vs = self.sentiment_analyzer.polarity_scores(text)
            return vs
        except Exception as e:
            print(f"使用 Vader 進行情感分析時發生錯誤: {e}")
            return None

    def add_sentiment_to_dataframe(self, df: pd.DataFrame, text_column: str = "title") -> pd.DataFrame:
        """
        (可選進階功能) 為 DataFrame 中的文本欄位添加情感分析結果 (使用 Vader)。

        Args:
            df (pd.DataFrame): 包含新聞數據的 DataFrame。
            text_column (str): DataFrame 中包含待分析文本的欄位名稱 (例如 "title" 或 "description")。

        Returns:
            pd.DataFrame: 增加了情感分析結果欄位 (vader_neg, vader_neu, vader_pos, vader_compound) 的 DataFrame。
        """
        if not self.sentiment_analyzer or text_column not in df.columns:
            if not VADER_AVAILABLE:
                print("VaderSentiment 套件未安裝，無法進行情感分析。")
            if text_column not in df.columns and not df.empty:
                 print(f"錯誤：DataFrame 中找不到指定的文本欄位 '{text_column}'。")
            return df # 返回原始 DataFrame

        print(f"正在對 '{text_column}' 欄位進行情感分析 (Vader)...")
        sentiments = df[text_column].astype(str).apply(lambda x: self.analyze_sentiment_vader(x) or {}) # Handle None from analyze_sentiment_vader

        df['vader_compound'] = sentiments.apply(lambda x: x.get('compound'))
        df['vader_pos'] = sentiments.apply(lambda x: x.get('pos'))
        df['vader_neu'] = sentiments.apply(lambda x: x.get('neu'))
        df['vader_neg'] = sentiments.apply(lambda x: x.get('neg'))

        return df

# 測試代碼
if __name__ == '__main__':
    if not NEWSAPI_KEY:
        print("警告：環境變數 NEWSAPI_API_KEY 未設定。NewsAPI.org 相關測試將受限或失敗。")

    # 初始化 NewsClient
    # 如果 NEWSAPI_KEY 未設定，client 仍會建立，但 newsapi 功能會印出錯誤並返回 None
    news_client = NewsClient()

    # 測試 NewsAPI.org (如果 API Key 可用)
    if news_client.newsapi_key:
        print("\n--- 測試 NewsAPI.org ---")
        keywords_example = "蘋果財報 OR AAPL earnings" # 測試 OR 邏輯和英文
        print(f"正在使用 NewsAPI 搜尋關鍵字: '{keywords_example}' (英文新聞, 最近)")

        # NewsAPI 免費版只能查過去一個月，所以 from_date/to_date 要小心設定
        # to_date_news = datetime.now().strftime("%Y-%m-%d")
        # from_date_news = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d") # 查過去7天

        # 為了讓測試更穩定，這裡不設日期，讓 API 返回最新的
        news_df_en = news_client.get_news_by_keyword(keywords_example, language="en", page_size=5)

        if news_df_en is not None:
            if not news_df_en.empty:
                print("獲取到的英文新聞 (部分):")
                print(news_df_en[['published_at', 'source_name', 'title']].head())

                # 測試情感分析 (Vader - 主要適用英文)
                if VADER_AVAILABLE:
                    print("\n對獲取的英文新聞標題進行情感分析 (Vader)...")
                    news_df_en_sentiment = news_client.add_sentiment_to_dataframe(news_df_en.copy(), text_column="title")
                    print(news_df_en_sentiment[['title', 'vader_compound']].head())
                else:
                    print("\nVaderSentiment 套件未安裝，跳過情感分析測試。")
            else:
                print(f"未找到關於 '{keywords_example}' 的新聞。")
        else:
            print(f"無法從 NewsAPI 獲取關於 '{keywords_example}' 的新聞。請檢查 API Key 權限或網路。")

        keywords_zh_example = "台積電 法說會"
        print(f"\n正在使用 NewsAPI 搜尋關鍵字: '{keywords_zh_example}' (中文新聞, 最近)")
        news_df_zh = news_client.get_news_by_keyword(keywords_zh_example, language="zh", page_size=3)
        if news_df_zh is not None:
            if not news_df_zh.empty:
                print("獲取到的中文新聞 (部分):")
                print(news_df_zh[['published_at', 'source_name', 'title']].head())
                if VADER_AVAILABLE: # 雖然 Vader 對中文不佳，但還是可以跑一下看流程
                    print("\n對獲取的中文新聞標題進行情感分析 (Vader - 效果可能不佳)...")
                    news_df_zh_sentiment = news_client.add_sentiment_to_dataframe(news_df_zh.copy(), text_column="title")
                    print(news_df_zh_sentiment[['title', 'vader_compound']].head())

            else:
                print(f"未找到關於 '{keywords_zh_example}' 的新聞。")
        else:
            print(f"無法從 NewsAPI 獲取關於 '{keywords_zh_example}' 的新聞。")
    else:
        print("\n跳過 NewsAPI.org 相關測試，因為 API Key 未設定。")

    # 測試 Vader 情感分析 (獨立測試)
    if VADER_AVAILABLE:
        print("\n--- 測試 VaderSentiment (獨立) ---")
        analyzer = SentimentIntensityAnalyzer() # 直接用
        test_sentence_pos = "This is a great and wonderful news!"
        vs_pos = analyzer.polarity_scores(test_sentence_pos)
        print(f"'{test_sentence_pos}' -> Vader: {vs_pos}")

        test_sentence_neg = "This is a terrible and bad news."
        vs_neg = analyzer.polarity_scores(test_sentence_neg)
        print(f"'{test_sentence_neg}' -> Vader: {vs_neg}")

        test_sentence_neu = "The weather is cloudy today."
        vs_neu = analyzer.polarity_scores(test_sentence_neu)
        print(f"'{test_sentence_neu}' -> Vader: {vs_neu}")

        # 測試 client 中的情感分析方法
        client_for_sentiment = NewsClient(newsapi_key="dummy_key_not_used_for_this_part") # key不影響純情感分析
        sentiment_result = client_for_sentiment.analyze_sentiment_vader(test_sentence_pos)
        print(f"Client method on '{test_sentence_pos}' -> Vader: {sentiment_result}")

        # 測試 DataFrame 添加情感分析
        sample_data = {'title': [test_sentence_pos, test_sentence_neg, test_sentence_neu, None, "這是中文句子，Vader 可能不準確。"]}
        sample_df = pd.DataFrame(sample_data)
        df_with_sentiment = client_for_sentiment.add_sentiment_to_dataframe(sample_df.copy(), text_column='title')
        print("\nDataFrame with Vader sentiment:")
        print(df_with_sentiment[['title', 'vader_compound', 'vader_pos', 'vader_neg', 'vader_neu']])

    else:
        print("\n--- VaderSentiment 套件未安裝，跳過相關獨立測試 ---")

    print("\nNewsClient 測試代碼執行完畢。")

"""
注意：
1.  **API Key (NewsAPI.org)**:
    *   需要 `NEWSAPI_API_KEY` 環境變數。若未設定，NewsAPI 功能會受限。
    *   NewsAPI.org 的免費方案有請求限制 (例如每日請求次數、只能查詢過去一個月的文章、回傳的文章總數限制等)。
2.  **新聞來源**:
    *   目前主要實現了與 `newsapi.org` 的對接。
    *   註解中提到了 `gnews` (非官方 Google News 庫) 作為一個潛在的免費替代方案，但未在本客戶端中直接實現其抓取邏輯。若要使用，需安裝 `gnews` 庫並添加相應的抓取方法。
3.  **情感分析**:
    *   整合了 `VaderSentiment` 庫進行情感分析 (透過 `SentimentIntensityAnalyzer`)。
    *   `VaderSentiment` 主要針對英文文本設計，對於中文或其他語言的效果可能不佳。若需高品質的多語言情感分析，應考慮使用專為該語言設計的模型或服務 (例如 SnowNLP for Chinese, Google Cloud Natural Language API, etc.)。
    *   情感分析功能是可選的，如果 `vaderSentiment` 套件未安裝，相關方法會提示並優雅地跳過或返回原始數據。
4.  **錯誤處理**: 包含了基本的 API 請求錯誤處理。
5.  **數據欄位**: 從 NewsAPI 提取了標題、摘要、內容、URL、發布時間、來源等關鍵資訊。
6.  **相依性**:
    *   `requests`: 用於發送 HTTP 請求。
    *   `pandas`: 用於數據處理和 DataFrame 格式。
    *   `vaderSentiment` (可選): 用於情感分析。如果計畫使用，需 `pip install vaderSentiment`。

此 `client.py` 檔案提供了抓取新聞和進行初步情感分析 (英文為主) 的基礎框架。
"""
