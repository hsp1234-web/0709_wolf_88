import asyncio
import aiohttp
import pandas as pd
import yfinance as yf
import psutil
import duckdb
import os
from datetime import datetime

# --- 核心配置 ---
MEMORY_USAGE_THRESHOLD = 70.0  # 記憶體使用率閾值 (%)
DB_FILE = 'local_financial_data.duckdb'
PARQUET_DIR = 'data_lake'
os.makedirs(PARQUET_DIR, exist_ok=True)


class DataAcquisitionEngine:
    def __init__(self, tickers):
        self.tickers = tickers
        self.db_connection = duckdb.connect(DB_FILE)
        self._setup_database()

    def _setup_database(self):
        # 建立一個統一的歷史數據表
        self.db_connection.execute("""
        CREATE TABLE IF NOT EXISTS historical_ohlcv (
            date TIMESTAMP,
            symbol VARCHAR,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume BIGINT,
            interval VARCHAR
        );
        """)

    async def fetch_single_ticker(self, session, ticker, interval='1d', period='1y'):
        # 智慧降級探測
        try:
            print(f"智慧降級探測：正在為 {ticker} 獲取月線數據...")
            probe_ticker = yf.Ticker(ticker)
            # 使用 asyncio.to_thread 執行同步的 yfinance 調用
            # 移除 progress=False，加入 auto_adjust=False, actions=False 以保持一致性
            probe_data = await asyncio.to_thread(probe_ticker.history, period="3mo", interval="1mo", auto_adjust=False, actions=False)
            if not isinstance(probe_data, pd.DataFrame) or probe_data.empty:
                print(f"智慧降級: {ticker} 在月線探測中無有效數據或返回非預期類型 (類型: {type(probe_data).__name__})，跳過獲取。")
                return None
            print(f"智慧降級探測：{ticker} 通過，找到 {len(probe_data)} 筆月線數據。")
        except Exception as e:
            print(f"智慧降級: {ticker} 在月線探測中發生錯誤: {e}，跳過獲取。")
            return None

        # 探測通過，執行真正的數據獲取
        print(f"正在獲取 {ticker} 的 {interval} 數據 (週期: {period})...")
        try:
            # 改回使用 yf.Ticker().history()
            ticker_obj = yf.Ticker(ticker)
            data = await asyncio.to_thread(
                ticker_obj.history,
                period=period,
                interval=interval,
                auto_adjust=False, # 與 YFinanceClient/探測階段行為保持一致
                actions=False      # 通常不需要 actions 數據
                # Ticker.history() 不接受 progress 參數
            )

            if not isinstance(data, pd.DataFrame):
                print(f"警告: {ticker} Ticker.history() 返回了非 DataFrame 類型 ({type(data).__name__})。內容: {str(data)[:200]}")
                return None

            if data.empty:
                print(f"警告: {ticker} Ticker.history() 返回了空的 DataFrame。")
                return None

        except Exception as e:
            print(f"錯誤: 在為 {ticker} 執行 yf.download 時發生例外: {e}")
            return None

        data['symbol'] = ticker
        data['interval'] = interval
        data.reset_index(inplace=True) # 將 Date 索引變為欄位
        # 確保 'Date' 或 'Datetime' 欄位存在並重命名
        date_col = 'Datetime' if 'Datetime' in data.columns else 'Date'
        if date_col not in data.columns:
            print(f"警告: {ticker} 的數據中未找到 'Date' 或 'Datetime' 欄位。可用欄位: {data.columns.tolist()}")
            return None # 如果沒有日期欄位，數據無效

        data.rename(columns={date_col: 'date'}, inplace=True)

        # 欄位名標準化 (小寫，與資料庫欄位對應)
        data.columns = [col.lower() for col in data.columns]

        # 確保所有必要的欄位都存在，若缺少則以 None 或 0 填充
        # 注意：'adj close' 在 auto_adjust=False 時可能不存在，這裡不強制要求
        required_cols = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'interval']
        for col in required_cols:
            if col not in data.columns:
                if col in ['open', 'high', 'low', 'close']: # 價格數據用 NaN (duckdb 會處理為 NULL)
                    data[col] = pd.NA
                elif col == 'volume': # 成交量用 0
                    data[col] = 0
                # 'date', 'symbol', 'interval' 應該總是存在

        # 僅選擇我們定義在資料庫中的欄位
        # 順序也與資料庫一致，方便 INSERT
        final_columns = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'interval']
        data = data[final_columns]

        return data

    def process_and_store(self, df):
        if df is None or df.empty:
            return

        symbol = df['symbol'].iloc[0]
        # interval = df['interval'].iloc[0] # interval 已在 df 中

        # 資源感知儲存
        memory_usage = psutil.virtual_memory().percent
        if memory_usage > MEMORY_USAGE_THRESHOLD:
            print(f"警告：記憶體使用率 {memory_usage:.2f}% 超過閾值 {MEMORY_USAGE_THRESHOLD}%。")
            print(f"為 {symbol} 啟用 [本體硬碟模式]...")

            try:
                # 寫入 DuckDB
                # 使用參數化查詢以避免SQL注入風險，雖然此處symbol等來自內部
                self.db_connection.execute(
                    "INSERT INTO historical_ohlcv VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    df.values.tolist() # executemany 風格的插入
                )
                print(f"✔ {symbol} 數據已存入 DuckDB。")
            except Exception as e:
                print(f"錯誤: 將 {symbol} 數據存入 DuckDB 時失敗: {e}")

            # 同時也可寫入 Parquet 作為數據湖備份
            try:
                interval_val = df['interval'].iloc[0] # 從DataFrame中獲取interval值
                parquet_path = os.path.join(PARQUET_DIR, f"{symbol.replace('=F', '_F')}_{interval_val}_{datetime.now():%Y%m%d%H%M%S}.parquet")
                df.to_parquet(parquet_path)
                print(f"✔ {symbol} 數據已存入 Parquet 檔案: {parquet_path}")
            except Exception as e:
                print(f"錯誤: 將 {symbol} 數據存入 Parquet 時失敗: {e}")
        else:
            print(f"記憶體使用率 {memory_usage:.2f}% 正常。{symbol} 數據暫時保留在記憶體中 (未實作列表儲存)。")
            # 在此處可以將 df 存儲於一個實例變數中供後續使用 (如果需要)
            # if not hasattr(self, 'in_memory_data'):
            #     self.in_memory_data = {}
            # self.in_memory_data.setdefault(symbol, []).append(df)
            # 實際應用中，若不存盤也應有其他處理方式，此處簡化
            pass

    async def run(self):
        # aiohttp.ClientSession 在此 yfinance 實現中不是必需的，因為 yf.download 使用 requests
        # 但保留它以符合非同步模式的標準結構，未來可能用於其他 HTTP 請求
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_single_ticker(session, ticker, period='1y', interval='1d') for ticker in self.tickers]
            # 使用 asyncio.gather 並設定 return_exceptions=True 來處理個別任務的失敗
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, res_df_or_exc in enumerate(results):
            ticker_for_res = self.tickers[i] # 獲取對應的 ticker
            if isinstance(res_df_or_exc, Exception):
                print(f"錯誤: 非同步獲取 {ticker_for_res} 數據時發生例外: {res_df_or_exc}")
            elif res_df_or_exc is None:
                # fetch_single_ticker 中已打印日誌，此處可選擇不再打印或打印簡略信息
                print(f"資訊: {ticker_for_res} 未返回數據或探測失敗。")
            else:
                self.process_and_store(res_df_or_exc)

        print("\n--- 作戰引擎執行完畢 ---")

    def close(self):
        self.db_connection.close()
        print("DuckDB 連線已關閉。")


# 為了讓 _test_run.py 可以調用
if __name__ == '__main__':
    # 這是您的可測試代碼列表
    test_tickers = [
        'NQ=F', 'ES=F', 'YM=F', '^VIX', '^DJI', '^SPX', '^IXIC',
        '^TWII', '^HSI', '000001.SS', 'DX-Y.NYB', 'ZB=F', 'ZN=F',
        'ZT=F', 'ZF=F', '^TNX', 'TLT', 'SHY', 'IEI', 'CL=F', 'GC=F',
        'SI=F', 'GLD', 'AAPL', 'MSFT', 'NVDA', 'GOOG', 'TSM',
        '601318.SS', '688981.SS', '0981.HK', 'BTC-USD', 'NONEXISTENT_TICKER' # 加入一個無效標的測試探測
    ]

    engine = DataAcquisitionEngine(tickers=test_tickers)
    asyncio.run(engine.run())

    # 查詢已存入的數據作為驗證
    print("\n--- 從 DuckDB 驗證已儲存數據 ---")
    try:
        summary = engine.db_connection.execute("""
            SELECT
                symbol,
                interval,
                COUNT(*) as count,
                MIN(date) as first_date,
                MAX(date) as last_date
            FROM historical_ohlcv
            GROUP BY symbol, interval
            ORDER BY symbol, interval
        """).fetchdf()
        print(summary)
    except Exception as e:
        print(f"查詢 DuckDB 數據時發生錯誤: {e}")
    finally:
        engine.close()

    # 清理測試產生的DB文件和Parquet目錄
    # if os.path.exists(DB_FILE):
    #     os.remove(DB_FILE)
    #     print(f"已清理測試資料庫檔案: {DB_FILE}")
    # if os.path.exists(PARQUET_DIR) and os.path.isdir(PARQUET_DIR):
    #     import shutil
    #     shutil.rmtree(PARQUET_DIR)
    #     print(f"已清理測試 Parquet 目錄: {PARQUET_DIR}")
    print("--- 引擎獨立測試結束 ---")
