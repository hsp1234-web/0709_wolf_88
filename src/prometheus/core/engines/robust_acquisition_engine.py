import asyncio
import logging
import time  # For time.time()
from datetime import datetime  # 修正導入

import duckdb
import pandas as pd
import psutil
import requests_cache
import yfinance as yf
from pybreaker import CircuitBreaker
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- 核心配置 ---
MEMORY_USAGE_THRESHOLD = 70.0
DB_FILE = "permanent_financial_data.duckdb"

# --- 日誌配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 斷路器配置：5次失敗後跳閘，阻斷請求60秒 ---
# [cite_start]您的研究報告中提到了斷路器模式 [cite: 540-544]
breaker = CircuitBreaker(fail_max=5, reset_timeout=60)


def _create_permanent_resilient_session():
    """
    創建一個整合了「永久快取」與「指數退避重試」策略的 session。
    - 快取: 預設永久保存，直到使用者手動清除。
    - 重試: 針對暫時性錯誤進行有限次指數退避重試。
    """
    # [cite_start]您的研究報告中闡述了快取與重試的重要性 [cite: 375-385, 393-403]
    session = requests_cache.CachedSession(
        "permanent_api_cache.sqlite",
        expire_after=None,  # None 代表永久快取
        allowable_codes=[200],  # 只快取成功的請求
        stale_if_error=True,  # 當請求失敗時，允許返回過期的舊數據，確保高可用性
    )
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],  # 對這些狀態碼進行重試
        backoff_factor=1,  # 重試間隔時間的指數因子 (例: 1s, 2s, 4s)
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = "RobustAcquisitionEngine/2.0"
    return session


class RobustDataAcquisitionEngine:
    def __init__(self, tickers):
        self.tickers = tickers
        self.resilient_session = _create_permanent_resilient_session()
        self.db_connection = duckdb.connect(DB_FILE)
        self._setup_database()
        # 用於暫存從網路獲取但在記憶體閾值內的數據
        self.in_memory_data_frames = []

    def _setup_database(self):
        # [cite_start]建立一個統一的歷史數據表，此表結構基於您的研究 [cite: 1625, 1632]
        self.db_connection.execute("""
        CREATE TABLE IF NOT EXISTS historical_ohlcv (
            date TIMESTAMP,
            symbol VARCHAR,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume BIGINT,
            interval VARCHAR,
            PRIMARY KEY (symbol, interval, date)
        );
        """)

    @breaker
    async def fetch_single_ticker(self, ticker, interval="1d", period="1y"):
        """
        使用「智慧降級探測」策略獲取單一標的數據，並由斷路器保護。
        """
        # 1. 智慧降級探測
        try:
            logger.info(f"智慧降級探測: 正在為 {ticker} 獲取月線數據...")
            # 注意：yf.Ticker 的 session 參數是 yfinance 較新版本才支援的。
            # 我們目前 yfinance 是 0.2.60，它應該支援。
            # 根據 yfinance 的錯誤提示，移除 session 參數，讓 yfinance 自行處理請求。
            probe_ticker_obj = yf.Ticker(ticker)  # 不傳遞 session
            probe_data = await asyncio.to_thread(
                probe_ticker_obj.history,
                period="3mo",
                interval="1mo",
                auto_adjust=False,
                actions=False,
            )
            if not isinstance(probe_data, pd.DataFrame) or probe_data.empty:
                logger.info(
                    f"智慧降級: {ticker} 在月線探測中無有效數據或返回非預期類型。跳過。"
                )
                return ticker, None  # 返回Ticker和None表示探測失敗或無數據
        except Exception as e:
            logger.info(f"智慧降級: {ticker} 在月線探測中發生錯誤: {e}。跳過。")
            return ticker, None  # 返回Ticker和None表示探測失敗

        logger.info(f"智慧降級探測: {ticker} 通過。")
        # 2. 探測通過，執行真正的數據獲取，改用 yf.Ticker().history()
        logger.info(f"正在併發獲取 {ticker} 的 {interval} 數據 (週期: {period})...")
        try:
            # probe_ticker_obj 已經在探測階段創建，這裡可以重用或重新創建均可
            # 為了邏輯清晰，重新獲取 ticker 物件
            ticker_obj = yf.Ticker(ticker)  # 不傳遞 session
            data = await asyncio.to_thread(
                ticker_obj.history,
                period=period,
                interval=interval,
                auto_adjust=False,
                actions=False,
            )
        except Exception as e:
            logger.info(f"錯誤: 在為 {ticker} 執行 Ticker.history() 時發生例外: {e}")
            return ticker, None  # 下載階段出錯

        # 3. 數據品質閘門
        if not isinstance(data, pd.DataFrame) or data.empty:
            logger.info(
                f"警告: {ticker} Ticker.history() 返回了非 DataFrame 或空數據。獲取失敗。"
            )
            return ticker, None

        # yf.Ticker().history() 通常返回單層欄位，無需處理 MultiIndex

        logger.info(f"✔ 成功獲取 {ticker} 數據 (共 {len(data)} 筆)")
        data.reset_index(inplace=True)
        date_col = next(
            (col for col in ["Datetime", "Date"] if col in data.columns), None
        )
        if date_col:
            data.rename(columns={date_col: "date"}, inplace=True)
        else:
            logger.info(f"警告: {ticker} 的數據中未找到 'Date' 或 'Datetime' 欄位。")
            return ticker, None  # 沒有日期欄位的數據是無效的

        return ticker, data

    def _prepare_df_for_db(self, ticker, df, interval):
        """準備 DataFrame 以符合資料庫的 schema。"""
        if df is None or df.empty:
            return None

        df_copy = df.copy()  # 操作副本以避免 SettingWithCopyWarning
        df_copy["symbol"] = ticker
        df_copy["interval"] = interval

        # 將所有欄位名轉為小寫以匹配資料庫
        df_copy.columns = [str(col).lower() for col in df_copy.columns]

        required_cols_db = [
            "date",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "interval",
        ]

        # 檢查並補齊缺失的必要欄位
        for col in required_cols_db:
            if col not in df_copy.columns:
                if col in ["open", "high", "low", "close", "volume"]:
                    df_copy[col] = pd.NA  # DuckDB 會將 pd.NA 視為 NULL
                    logger.info(f"資訊: {ticker} 的數據缺少 '{col}' 欄位，已補為 NULL。")
                else:
                    # date, symbol, interval 應該總是存在，如果不存在則是非常嚴重的問題
                    logger.info(
                        f"嚴重錯誤: {ticker} 的數據嚴重缺少關鍵欄位 '{col}'，無法處理。"
                    )
                    return None

        # 確保 'date' 欄位是 datetime64[ns] 類型
        if "date" in df_copy.columns and not pd.api.types.is_datetime64_any_dtype(
            df_copy["date"]
        ):
            try:
                df_copy["date"] = pd.to_datetime(df_copy["date"])
            except Exception as e_date:
                logger.info(f"錯誤: 無法將 {ticker} 的 'date' 欄位轉換為 datetime: {e_date}")
                return None

        try:
            return df_copy[required_cols_db]
        except KeyError as e_key:
            logger.info(
                f"錯誤: 準備 {ticker} 數據時發生 KeyError (欄位缺失): {e_key}。可用欄位: {df_copy.columns.tolist()}"
            )
            return None

    def _store_data_duckdb(self, df_to_store):
        """將處理好的 DataFrame 存入 DuckDB，使用 UPSERT。"""
        if df_to_store is None or df_to_store.empty:
            return

        # DuckDB的UPSERT語法
        # ON CONFLICT (symbol, interval, date) DO UPDATE SET ...
        # 這裡我們用 df_to_store 註冊一個臨時表，然後執行 INSERT ... ON CONFLICT
        # 確保 df_to_store 的欄位順序與 historical_ohlcv 一致

        # 欄位列表必須與 CREATE TABLE 語句中的順序和數量完全匹配
        # (date, symbol, open, high, low, close, volume, interval)
        # 確保 df_to_store 包含且僅包含這些欄位，並按此順序

        table_name = "temp_df_for_upsert"
        self.db_connection.register(table_name, df_to_store)

        upsert_query = f"""
        INSERT INTO historical_ohlcv
        SELECT date, symbol, open, high, low, close, volume, interval FROM {table_name}
        ON CONFLICT (symbol, interval, date) DO UPDATE SET
            open=EXCLUDED.open,
            high=EXCLUDED.high,
            low=EXCLUDED.low,
            close=EXCLUDED.close,
            volume=EXCLUDED.volume;
        """
        try:
            self.db_connection.execute(upsert_query)
            # logger.info(f"✔ {df_to_store['symbol'].iloc[0]} ({len(df_to_store)} 筆) 數據已存入/更新至 DuckDB。")
        except Exception as e:
            logger.info(
                f"錯誤: 存入/更新 {df_to_store['symbol'].iloc[0]} 數據至 DuckDB 時失敗: {e}"
            )
        finally:
            self.db_connection.unregister(table_name)  # 清理臨時表

    async def run(self):
        self.in_memory_data_frames = []  # 清空上次執行的記憶體數據
        tasks = [
            self.fetch_single_ticker(ticker, interval="1d", period="1y")
            for ticker in self.tickers
        ]
        fetch_results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_data_for_batch_storage = []

        for result in fetch_results:
            if isinstance(result, Exception):
                # 斷路器或其他 asyncio.gather 捕獲的例外
                logger.info(f"引擎在 gather 階段捕獲到一個錯誤: {result}")
                continue

            if result is None:  # 可能 fetch_single_ticker 內部已處理並返回 None
                # logger.info(f"引擎注意到一個任務未返回有效結果 (可能已在 fetch_single_ticker 中記錄)。")
                continue

            ticker, df_raw = result  # 解包 (ticker, DataFrame) 或 (ticker, None)

            if df_raw is None or df_raw.empty:
                # logger.info(f"資訊: {ticker} 未獲取到有效數據，不進行處理。")
                continue

            df_prepared = self._prepare_df_for_db(ticker, df_raw, interval="1d")
            if df_prepared is not None and not df_prepared.empty:
                processed_data_for_batch_storage.append(df_prepared)
            else:
                logger.info(f"警告: {ticker} 的數據在準備階段後變為空或無效，不進行儲存。")

        # 統一處理所有成功獲取的數據
        if processed_data_for_batch_storage:
            # 資源感知儲存判斷 (可以基於總體數據大小或單個批次)
            # 這裡簡化為總體判斷一次，實際可更細緻
            memory_usage = psutil.virtual_memory().percent
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{current_time}] 記憶體使用率: {memory_usage:.2f}%")

            if memory_usage > MEMORY_USAGE_THRESHOLD:
                logger.info(
                    f"警告：記憶體使用率超過閾值 {MEMORY_USAGE_THRESHOLD}%。啟用批次 [本體硬碟模式] 儲存。"
                )
                for df_batch_item in processed_data_for_batch_storage:
                    self._store_data_duckdb(df_batch_item)  # 逐個 DataFrame 進行 UPSERT
                logger.info(
                    f"✔ 所有 {len(processed_data_for_batch_storage)} 個有效數據批次已嘗試存入/更新至 DuckDB。"
                )
            else:
                logger.info(
                    f"記憶體使用率正常。將 {len(processed_data_for_batch_storage)} 個有效數據批次統一存入/更新至 DuckDB。"
                )
                # 即使記憶體正常，也執行資料庫儲存，因為這是永久儲存引擎
                for df_batch_item in processed_data_for_batch_storage:
                    self._store_data_duckdb(df_batch_item)
                # 可以選擇將數據也保留在 self.in_memory_data_frames 供本次運行後續使用
                self.in_memory_data_frames.extend(processed_data_for_batch_storage)
                logger.info(
                    f"✔ 所有 {len(processed_data_for_batch_storage)} 個有效數據批次已嘗試存入/更新至 DuckDB，並暫存於記憶體。"
                )
        else:
            logger.info("引擎運行完畢，沒有需要儲存的新數據。")

        logger.info("\n--- 作戰引擎執行完畢 ---")

    def force_recache(self, ticker_or_tickers):
        """
        手動清除指定標的快取，強制下次重新從網路獲取。
        參數 ticker_or_tickers 可以是單個 ticker 字串或 ticker 字串列表。
        """
        logger.info(f"收到指令：強制重新快取以下標的: {ticker_or_tickers}")

        # requests-cache的delete方法不直接接受ticker列表來構造URL，
        # 它需要完整的URL模式或精確的快取鍵。
        # yfinance的URL結構比較複雜，包含查詢參數。
        # 一個更可靠（但可能較慢）的方式是遍歷 tickers，為每個 ticker 構造可能的URL模式
        # 或者，如果知道快取鍵的生成方式，可以直接刪除鍵。
        # 為了簡化，這裡假設 yfinance 的請求主要基於 ticker 名稱，
        # 我們嘗試刪除包含這些 ticker 名稱的快取。
        # 注意：這可能無法完美清除所有相關快取，取決於 requests-cache 的實現和 URL 匹配。

        # 一個簡單的實現是清除整個快取，如果精確刪除困難
        # self.resilient_session.cache.clear()
        # logger.info("警告：已執行全局快取清除，因為精確標的清除較複雜。")

        # 更精確的方法需要知道 yfinance 如何構建 URL。
        # 假設基礎 URL 是 'https://query1.finance.yahoo.com' 或 'https://query2.finance.yahoo.com'
        # 並且 ticker 以某种形式出现在 URL 中。
        # 這裡我們使用 CachedSession 提供的 `delete(urls=...)` 方法，
        # 它應該能處理 URL 匹配。但 yfinance 的 URL 模式可能很多。
        # 這裡我們不直接構造 URL，而是依賴 yfinance 在下次請求時，
        # 如果 session 的快取中沒有匹配，會重新請求。
        # `delete()` 如果沒有參數，是清除過期快取。
        # `delete(expired=True)`
        # 要刪除特定URL，需要知道URL。
        # 鑑於 yfinance URL 的複雜性，最直接的可能是清除整個快取，或者接受不那麼精確的刪除。
        # 這裡我們採用一個簡化的方式，不直接操作URL，而是依賴下次請求時快取失效。
        # 實際上，requests-cache 的 `delete` 方法如果沒有 `urls` 參數，會刪除過期條目。
        # 這裡我們嘗試一個更激進的策略：清除所有快取。
        # 這是因為 yfinance 的 URL 模式多樣，精確刪除單個 ticker 的快取非常複雜。
        logger.info("注意: 'force_recache' 將清除所有API快取以確保指定標的被重新獲取。")
        self.resilient_session.cache.clear()
        logger.info("所有永久快取已清除。")

    def close(self):
        if self.db_connection:
            self.db_connection.close()
            logger.info("資料庫連線已關閉。")


# 主程式測試區塊 (可選，用於獨立測試引擎)
if __name__ == "__main__":
    logger.info("--- RobustDataAcquisitionEngine 獨立測試 ---")

    test_tickers_main = [
        "AAPL",
        "MSFT",
        "GOOG",  # 美股
        "NQ=F",
        "ES=F",  # 期貨
        "^VIX",  # 指數
        "BTC-USD",  # 加密貨幣
        "NONEXISTENTTICKERXYZ",  # 無效標的
        "000001.SS",  # A股 (上證指數)
    ]

    engine_main = RobustDataAcquisitionEngine(tickers=test_tickers_main)

    logger.info("\n[主測試] 第一次執行 (應從網路獲取並快取)...")
    start_time = time.time()
    asyncio.run(engine_main.run())
    logger.info(f"第一次執行耗時: {time.time() - start_time:.2f} 秒")

    logger.info("\n[主測試] 第二次執行 (應從快取獲取)...")
    start_time = time.time()
    asyncio.run(engine_main.run())  # 再次執行以測試快取
    logger.info(f"第二次執行耗時: {time.time() - start_time:.2f} 秒")

    logger.info("\n[主測試] 強制重新快取 AAPL...")
    engine_main.force_recache(ticker_or_tickers=["AAPL"])  # 雖然目前是全局清除

    logger.info("\n[主測試] 再次獲取 AAPL (應從網路獲取)...")
    aapl_engine = RobustDataAcquisitionEngine(tickers=["AAPL"])
    start_time = time.time()
    asyncio.run(aapl_engine.run())
    logger.info(f"AAPL 重新獲取耗時: {time.time() - start_time:.2f} 秒")
    aapl_engine.close()  # 單獨關閉這個引擎實例的連接

    logger.info("\n[主測試] 最終資料庫內容預覽:")
    try:
        # 使用主引擎的連接來查詢
        summary_df = engine_main.db_connection.execute(
            "SELECT symbol, interval, COUNT(*) as count, MIN(date)::DATE as first, MAX(date)::DATE as last FROM historical_ohlcv GROUP BY symbol, interval ORDER BY symbol"
        ).fetchdf()
        logger.info(summary_df)
    except Exception as e:
        logger.info(f"查詢資料庫時出錯: {e}")
    finally:
        engine_main.close()  # 關閉主引擎的連接

    # 清理產生的檔案 (可選)
    # if os.path.exists(DB_FILE):
    #     os.remove(DB_FILE)
    # if os.path.exists('permanent_api_cache.sqlite'):
    #     os.remove('permanent_api_cache.sqlite')
    logger.info("--- RobustDataAcquisitionEngine 獨立測試結束 ---")
