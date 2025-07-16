# 檔案: scripts/debug_factor_engine.py
# --- 抽象程式碼草圖 ---

# 概念：
# 一個隔離的偵錯腳本，用於直接測試因子引擎。

import pandas as pd
import numpy as np
import sys
from pathlib import Path

# 將 src 目錄添加到 PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from prometheus.core.engines.universal_factor_engine import UniversalFactorEngine
from prometheus.core.logging.log_manager import LogManager

logger = LogManager.get_instance().get_logger("DebugScript")

def load_dummy_data() -> pd.DataFrame:
    """
    建立一個用於測試的虛構 OHLCV DataFrame。
    """
    logger.info("正在載入虛擬原始數據...")
    date_range = pd.to_datetime(
        pd.date_range(start="2022-01-01", periods=100, freq="D")
    )
    open_prices = np.random.uniform(90, 110, size=100)
    data = {
        "Date": date_range,
        "Open": open_prices,
        "High": open_prices + np.random.uniform(0, 5, size=100),
        "Low": open_prices - np.random.uniform(0, 5, size=100),
        "Close": open_prices + np.random.uniform(-2, 2, size=100),
        "Volume": np.random.randint(100000, 500000, size=100),
    }
    df = pd.DataFrame(data)
    df.set_index("Date", inplace=True)
    logger.info(f"虛擬數據載入完畢，維度為 {df.shape}。")
    return df

def main():
    """
    偵錯腳本主函數。
    """
    logger.info("--- 開始執行因子引擎偵錯腳本 ---")

    # 1. 載入數據
    raw_data = load_dummy_data()

    # 2. 實例化引擎
    factor_engine = UniversalFactorEngine()

    # 3. 執行計算
    logger.info("準備呼叫因子引擎的 calculate 方法...")
    factor_df = factor_engine.calculate(raw_data)
    logger.info("因子引擎的 calculate 方法執行完畢。")

    # 4. 檢查輸出
    print("\n--- 最終輸出 DataFrame 資訊 ---")
    factor_df.info()

    print("\n--- 最終輸出 DataFrame 頭部數據 ---")
    print(factor_df.head())

    logger.info("--- 偵錯腳本執行完畢 ---")

if __name__ == "__main__":
    main()
