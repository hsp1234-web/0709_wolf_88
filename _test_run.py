import asyncio
import os  # 用於稍後清理檔案
import time

from core.engines.robust_acquisition_engine import (  # 導入 DB_FILE
    DB_FILE,
    RobustDataAcquisitionEngine,
)

print("--- [最終作戰計畫 004：全功能驗證] ---")

target_tickers = [
    "NQ=F",
    "ES=F",
    "YM=F",
    "^VIX",
    "^DJI",
    "^SPX",
    "^IXIC",
    "^TWII",
    "^HSI",
    "000001.SS",
    "DX-Y.NYB",
    "ZB=F",
    "ZN=F",
    "ZT=F",
    "ZF=F",
    "^TNX",
    "TLT",
    "SHY",
    "IEI",
    "CL=F",
    "GC=F",
    "SI=F",
    "GLD",
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOG",
    "TSM",
    "601318.SS",
    "688981.SS",
    "0981.HK",
    "BTC-USD",
    "INVALID_TICKER_FOR_TEST",  # 加入一個無效標的來測試智慧降級
]

# 0. 清理舊的資料庫和快取檔案 (如果存在)，以確保測試的純淨性
if os.path.exists(DB_FILE):  # 直接使用導入的 DB_FILE
    os.remove(DB_FILE)
    print(f"已移除舊的資料庫檔案: {DB_FILE}")
if os.path.exists("permanent_api_cache.sqlite"):
    os.remove("permanent_api_cache.sqlite")
    print("已移除舊的 API 快取檔案: permanent_api_cache.sqlite")


# 1. 初始化引擎
engine = RobustDataAcquisitionEngine(tickers=target_tickers)

# 2. 第一次執行：應該會從網路獲取數據並寫入永久快取和資料庫
print("\n--- 第一次執行 (從網路獲取) ---")
start_time_1 = time.time()
asyncio.run(engine.run())
end_time_1 = time.time()
print(f"第一次執行耗時: {end_time_1 - start_time_1:.2f} 秒")

# 3. 第二次執行：應該要非常快，因為所有數據都從永久快取中讀取
#    數據仍然會嘗試寫入資料庫，但由於主鍵衝突，應該是更新操作(UPSERT)
print("\n--- 第二次執行 (應從快取讀取，資料庫執行 UPSERT) ---")
start_time_2 = time.time()
asyncio.run(engine.run())
end_time_2 = time.time()
print(f"第二次執行耗時: {end_time_2 - start_time_2:.2f} 秒")

# 4. 驗證手動清除快取
print("\n--- 測試手動清除與重新獲取 'AAPL' 的快取 ---")
# 由於 force_recache 目前是全局清除，我們只用一個 ticker 列表來驗證其效果
# 創建一個新的引擎實例，只包含 AAPL，以模擬單獨重新獲取
engine.force_recache(ticker_or_tickers=["AAPL"])  # 清除全局快取
print("全局快取已清除。現在嘗試重新獲取 AAPL...")

# 重新初始化一個只包含 AAPL 的引擎，或者直接讓主引擎再次運行 AAPL
# 為了更清晰地展示 force_recache 的效果，我們讓主引擎針對 AAPL 再次運行
# 但由於 run() 會處理 self.tickers，我們需要一個只包含 AAPL 的新引擎實例
# 或者修改主引擎的 tickers 列表 (不推薦直接修改正在運行的實例的內部狀態進行這種測試)
# 這裡我們選擇創建一個新的、只包含 AAPL 的引擎實例
print("創建一個僅包含 AAPL 的新引擎實例進行重新獲取測試...")
recache_engine = RobustDataAcquisitionEngine(tickers=["AAPL"])
start_time_recache = time.time()
asyncio.run(recache_engine.run())
end_time_recache = time.time()
print(f"AAPL 快取清除後重新獲取耗時: {end_time_recache - start_time_recache:.2f} 秒")
recache_engine.close()  # 關閉此臨時引擎的連接

# 5. 最終驗證資料庫內容
print("\n--- 從 DuckDB 最終驗證已儲存數據 ---")
try:
    # 使用主引擎的連接來查詢，它應該包含了所有執行的結果
    summary = engine.db_connection.execute("""
        SELECT
            symbol,
            interval,
            COUNT(*) as count,
            MIN(date)::DATE as first_date,
            MAX(date)::DATE as last_date
        FROM historical_ohlcv
        GROUP BY symbol, interval
        ORDER BY symbol, interval
    """).fetchdf()
    print(summary)
    if not summary.empty:
        print(
            f"\n總計 {summary['count'].sum()} 筆數據記錄 (考慮 UPSERT 後的 최종計數) "
            f"已儲存於 {DB_FILE}"
        )  # 使用導入的 DB_FILE
    else:
        print(f"{DB_FILE} 中沒有數據。")  # 使用導入的 DB_FILE
except Exception as e:
    print(f"查詢 DuckDB 數據時發生錯誤: {e}")
finally:
    engine.close()  # 關閉主引擎的連接

print("\n--- [全功能驗證完畢] ---")
