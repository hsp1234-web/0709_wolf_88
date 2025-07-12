# apps/news_client/run.py
import argparse
import sys
import os
from datetime import datetime
import pandas as pd
from pathlib import Path  # 標準樣板碼需要 Path

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except (NameError):
    project_root = Path(os.getcwd())
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    # 此處的 print 暫時保留，因為 logger 可能尚未初始化或 sys.path 未設定
    print(
        f"警告 (apps/news_client/run.py __file__): __file__ 未定義，專案路徑校正可能不準確。已將 {project_root} 加入 sys.path。",
        file=sys.stderr,
    )
except Exception as e:
    print(f"專案路徑校正時發生錯誤 (apps/news_client/run.py): {e}", file=sys.stderr)

from core.logger import get_logger
logger = get_logger(__name__) # 在 sys.path 更新後初始化 logger

# 現在可以記錄路徑校正的結果 (如果需要更詳細的日誌)
# logger.debug(f"專案根目錄設定為: {project_root}")
# --- 標準化「路徑自我校正」樣板碼 END ---

from apps.news_client.client import NewsClient, VADER_AVAILABLE  # noqa: E402


def save_dataframe(df: pd.DataFrame, output_path: str, data_type: str, keywords: str):
    """
    將 DataFrame 儲存到指定的路徑。

    Args:
        df (pd.DataFrame): 要儲存的 DataFrame。
        output_path (str): 儲存的目錄路徑。
        data_type (str): 數據類型 (用於檔案命名，例如 "news_articles")。
        keywords (str): 搜尋的關鍵字 (用於檔案命名，會做一些清理)。
    """
    if df is None or df.empty:
        logger.info(f"沒有獲取到 '{data_type}' 數據 (關鍵字: {keywords})，不進行儲存。")
        return

    try:
        os.makedirs(output_path, exist_ok=True)
    except OSError as e:
        logger.error(f"創建輸出目錄 {output_path} 失敗: {e}", exc_info=True)
        return

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # 清理關鍵字，使其適合檔案名稱
    safe_keywords = (
        "".join(c if c.isalnum() or c in [" ", "_"] else "" for c in keywords)
        .strip()
        .replace(" ", "_")
    )
    if len(safe_keywords) > 50:  # 避免檔案名稱過長
        safe_keywords = safe_keywords[:50]

    if not safe_keywords: # 如果清理後關鍵字為空，使用預設名稱
        safe_keywords = "news_search"

    filename = f"{safe_keywords}_{data_type}_{timestamp}.csv"
    filepath = os.path.join(output_path, filename)

    try:
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        logger.info(f"數據已成功儲存到：{filepath}")
    except Exception as e:
        logger.error(f"儲存數據到 {filepath} 時發生錯誤：{e}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="新聞數據抓取與分析客戶端")

    parser.add_argument(
        "keywords",
        type=str,
        help="要搜尋的新聞關鍵字 (例如 '台積電 財報', 'AAPL earnings')。",
    )
    parser.add_argument(
        "--from_date",
        type=str,
        default=None,
        help="搜尋起始日期 (YYYY-MM-DD)。NewsAPI 免費版僅支援近一個月。",
    )
    parser.add_argument(
        "--to_date", type=str, default=None, help="搜尋結束日期 (YYYY-MM-DD)。"
    )
    parser.add_argument(
        "--language",
        type=str,
        default="zh",
        help="新聞語言 (例如 en, zh)。預設 'zh' (中文)。",
    )
    parser.add_argument(
        "--sort_by",
        type=str,
        default="publishedAt",
        choices=["relevance", "popularity", "publishedAt"],
        help="排序方式。預設 'publishedAt'。",
    )
    parser.add_argument(
        "--page_size",
        type=int,
        default=20,
        help="每頁返回的文章數量 (NewsAPI 上限 100)。預設 20。",
    )
    parser.add_argument("--page", type=int, default=1, help="請求的頁碼。預設 1。")

    parser.add_argument(
        "--add_sentiment",
        action="store_true",
        help=f"對抓取到的新聞標題進行情感分析 (使用 VaderSentiment)。需要安裝 vaderSentiment 套件。{'目前可用。' if VADER_AVAILABLE else '目前不可用 (套件未安裝)。'}",
    )
    parser.add_argument(
        "--sentiment_text_column",
        type=str,
        default="title",
        choices=["title", "description"],
        help="用於情感分析的文本欄位 ('title' 或 'description')。預設 'title'。",
    )

    parser.add_argument(
        "--output_path",
        type=str,
        default="data/news_data",
        help="儲存新聞數據的目錄路徑。預設 data/news_data。",
    )
    parser.add_argument(
        "--newsapi_key",
        type=str,
        default=None,
        help="NewsAPI.org 的 API Key。如果未提供，則從環境變數 NEWSAPI_API_KEY 讀取。",
    )

    args = parser.parse_args()
    logger.info(f"接收到的參數: {args}")

    # 從核心配置獲取設定
    from core.config import config
    api_key_from_core = config.get("news_client.api_key")
    max_retries_from_core = config.get("news_client.max_retries", 3) # 提供預設值

    # 決定最終使用的 API Key：優先使用命令行參數，其次是核心配置，最後是環境變數 (如果 NewsClient 內部還會檢查)
    # 根據任務要求，以中央配置為主。如果命令行也提供，則命令行優先。
    final_api_key = args.newsapi_key if args.newsapi_key else api_key_from_core

    if not final_api_key or "YOUR_" in final_api_key:
        logger.error("NewsClient 的 API Key 未在 config.yml 或命令行參數中有效設定。請檢查 config.yml 中的 'news_client.api_key' 或提供 --newsapi_key 參數。")
        sys.exit(1)

    logger.info(f"News client 即將使用 max_retries={max_retries_from_core} (來自核心配置)。")
    # 假設 NewsClient 的構造函數或其方法會使用 max_retries，這裡僅記錄
    # 注意: NewsClient 的實際定義未知，其如何處理 api_key 和 max_retries 需要確認

    try:
        # 假設 NewsClient 接受 api_key 參數
        # 如果 NewsClient 內部也處理環境變數，那麼這裡傳遞的 final_api_key 會覆蓋它
        client = NewsClient(newsapi_key=final_api_key)
                                           # max_retries 如何傳遞給 NewsClient 取決於其設計
                                           # 目前的 NewsClient 導入似乎有問題，這裡僅為示意
    except NameError: # 如果 NewsClient 真的無法導入
        logger.error("無法實例化 NewsClient，可能是因為 'apps.news_client.client' 模組不存在或導入失敗。請檢查檔案結構和導入路徑。")
        sys.exit(1)
    except ValueError as e: # 假設 NewsClient 的 __init__ 可能拋出 ValueError
        logger.error(f"NewsClient 初始化失敗: {e}", exc_info=True)
        sys.exit(1)


    logger.info(
        f"正在搜尋新聞：關鍵字='{args.keywords}', 語言='{args.language}', 排序='{args.sort_by}'"
    )
    if args.from_date:
        logger.info(f"日期範圍: {args.from_date} 至 {args.to_date or '最新'}")

    news_df = client.get_news_by_keyword(
        keywords=args.keywords,
        from_date=args.from_date,
        to_date=args.to_date,
        language=args.language,
        sort_by=args.sort_by,
        page_size=args.page_size,
        page=args.page,
    )

    if news_df is not None:
        if not news_df.empty:
            logger.info(f"成功獲取 {len(news_df)} 筆新聞。")
            logger.info("部分新聞標題：")
            for title in news_df["title"].head():
                logger.info(f"- {title}")

            if args.add_sentiment:
                if VADER_AVAILABLE:
                    logger.info(
                        f"正在對 '{args.sentiment_text_column}' 欄位添加 Vader 情感分析..."
                    )
                    news_df = client.add_sentiment_to_dataframe(
                        news_df, text_column=args.sentiment_text_column
                    )
                    logger.info("已添加情感分析結果。部分數據 (標題與情感分數):")
                    # 為了日誌美觀，可能需要格式化 DataFrame 的輸出，或者僅記錄摘要
                    try:
                        df_head_str = news_df[[args.sentiment_text_column, "vader_compound"]].head().to_string()
                        logger.info(f"\n{df_head_str}")
                    except Exception as e_df_log:
                         logger.warning(f"記錄情感分析結果表頭時出錯: {e_df_log}")

                else:
                    logger.warning("要求進行情感分析，但 VaderSentiment 套件未安裝或不可用。跳過情感分析步驟。")

            save_dataframe(news_df, args.output_path, "news_articles", args.keywords)
        else:
            logger.info(f"未找到關於 '{args.keywords}' 的新聞。")
    else:
        logger.warning(
            f"獲取新聞失敗 (關鍵字: '{args.keywords}')。請檢查 API Key、網路連線或 NewsAPI 的限制。"
        )


if __name__ == "__main__":
    # 使用範例 (需在環境變數中設定 NEWSAPI_API_KEY 或透過 --newsapi_key 傳入):
    # 抓取中文新聞
    # python apps/news_client/run.py "台積電 Q1財報" --language zh --page_size 5 --output_path temp_data/news

    # 抓取英文新聞並進行情感分析
    # python apps/news_client/run.py "Apple earnings results" --language en --page_size 5 --add_sentiment --output_path temp_data/news

    # 指定日期範圍 (注意 NewsAPI 免費版限制)
    # FROM_DATE=$(date -d "-3 days" +%Y-%m-%d) # Linux/macOS 示例
    # TO_DATE=$(date +%Y-%m-%d) # Linux/macOS 示例
    # python apps/news_client/run.py "石油輸出國組織 會議" --language zh --from_date $FROM_DATE --to_date $TO_DATE --output_path temp_data/news

    # 如果 vaderSentiment 未安裝，--add_sentiment 會提示但不會中斷
    logger.info("news_client/run.py 作為腳本執行...")
    main()

"""
此 `run.py` 腳本為新聞客戶端 (`NewsClient`) 提供了一個命令列介面，功能如下：

1.  **新聞搜尋**:
    *   接收用戶指定的關鍵字 (`keywords`)、語言 (`language`)、排序方式 (`sort_by`)、日期範圍 (`from_date`, `to_date`)、分頁參數 (`page_size`, `page`)。
    *   調用 `NewsClient` 的 `get_news_by_keyword` 方法從 NewsAPI.org 抓取新聞。

2.  **情感分析 (可選)**:
    *   提供 `--add_sentiment` 旗標，用戶可選擇是否對抓取到的新聞標題 (或摘要) 進行情感分析。
    *   情感分析使用 `NewsClient` 中整合的 VaderSentiment (主要適用於英文)。
    *   如果 `vaderSentiment` 套件未安裝，會提示用戶並跳過此步驟。
    *   可以透過 `--sentiment_text_column` 指定要分析的文本欄位 (預設為 "title")。

3.  **數據儲存**:
    *   將獲取到的新聞數據 (可能包含情感分析結果) 儲存為 CSV 檔案。
    *   檔案儲存在 `--output_path` 指定的目錄下，檔名包含清理後的關鍵字、"news_articles" 及時間戳。

4.  **API Key 管理**:
    *   允許透過 `--newsapi_key` 參數傳遞 NewsAPI.org 的 API Key。
    *   如果未提供，則會嘗試從環境變數 `NEWSAPI_API_KEY` 讀取。

執行前，請確保：
- `apps.news_client.client` 模組可被正確導入。
- `requests` 和 `pandas` 庫已安裝。
- 若要使用情感分析功能 (`--add_sentiment`)，需安裝 `vaderSentiment` 庫 (`pip install vaderSentiment`)。
- NewsAPI.org 的 API Key 已設定 (透過環境變數或參數)，並且該 Key 具有足夠的權限和請求配額。免費版 Key 有較多限制。
"""
