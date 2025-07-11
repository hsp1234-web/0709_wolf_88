import asyncio
from core.engines.data_acquisition_engine import DataAcquisitionEngine

print("--- [作戰計畫 003：核心驗證] ---")
print("正在啟動高效率非同步數據獲取引擎...")

# 使用您提供的、已驗證可查詢的股票代碼列表
target_tickers = [
    'NQ=F', 'ES=F', 'YM=F', '^VIX', '^DJI', '^SPX', '^IXIC',
    '^TWII', '^HSI', '000001.SS', 'DX-Y.NYB', 'ZB=F', 'ZN=F',
    'ZT=F', 'ZF=F', '^TNX', 'TLT', 'SHY', 'IEI', 'CL=F', 'GC=F',
    'SI=F', 'GLD', 'AAPL', 'MSFT', 'NVDA', 'GOOG', 'TSM',
    '601318.SS', '688981.SS', '0981.HK', 'BTC-USD',
    'NONEXISTENTTICKERXYZ' # 加入一個無效標的以測試智慧降級
]

# 初始化引擎
engine = DataAcquisitionEngine(tickers=target_tickers)

# 執行非同步任務
asyncio.run(engine.run())

# 查詢已存入 DuckDB 的數據作為驗證
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

print("\n--- [驗證完畢] ---")
