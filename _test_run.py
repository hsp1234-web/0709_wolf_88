import pandas as pd
import pandas_ta as ta
import shutil
import os
from datetime import date
from core.clients.yfinance import YFinanceClient # 導入新的客戶端

# 清除 yfinance 快取 (保留此邏輯)
try:
    import appdirs
    cache_dir = appdirs.user_cache_dir('yfinance', 'yfinance')
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
        print(f"--- [快取清理] 已移除 yfinance 快取目錄: {cache_dir} ---")
except Exception as e:
    print(f"--- [快取清理警告] 清理 yfinance 快取時發生錯誤: {e} ---")

# 設置 Pandas DataFrame 顯示選項
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

print("--- [任務開始] 正在初始化 YFinanceClient 並獲取市場數據... ---")

# 初始化客戶端
client = YFinanceClient()

# 定義獲取數據的參數
symbol = 'SPY'
start_date = '2024-01-01'
end_date = date.today().strftime('%Y-%m-%d') # 獲取到今天

# 使用 YFinanceClient 獲取數據
# YFinanceClient 內部已處理 auto_adjust=False 和 progress=False
spy_data = client.fetch_data(symbol=symbol, start_date=start_date, end_date=end_date)

if spy_data.empty:
    print(f"錯誤：未能從 YFinanceClient 獲取 {symbol} 的數據。中止執行。")
    print("--- [任務失敗] ---")
else:
    print(f"✔ 市場數據獲取成功 (共 {len(spy_data)} 筆)。")
    print("--- [數據處理] 正在計算統計指標... ---")

    # 確保 'Close' 欄位存在
    if 'Close' not in spy_data.columns:
        print(f"錯誤：獲取的數據中缺少 'Close' 欄位。可用欄位: {spy_data.columns.tolist()}")
        print("--- [任務失敗] ---")
    else:
        # 1. 計算核心價格統計：20日與50日簡單移動平均線(SMA)
        spy_data['SMA_20'] = ta.sma(spy_data['Close'], length=20)
        spy_data['SMA_50'] = ta.sma(spy_data['Close'], length=50)

        # 2. 計算技術指標：14日相對強弱指數(RSI)
        spy_data['RSI_14'] = ta.rsi(spy_data['Close'], length=14)

        # 3. 移除計算初期產生的NaN值，使報告更整潔
        spy_data.dropna(inplace=True)

        # 4. 將數據四捨五入到小數點後兩位
        spy_data = spy_data.round(2)

        print("✔ 統計指標計算完畢。")
        print("\n--- [最終產出報告] ---")

        # 打印 DataFrame 的最後10筆數據作為最終報告
        print(spy_data.tail(10))
        print("\n--- [任務完成] ---")
