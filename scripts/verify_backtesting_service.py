# -*- coding: utf-8 -*-
"""
作戰指令：【磐石行動 - 模組驗證腳本】
任務目標：獨立驗證 BacktestingService 的核心功能。
"""
import pandas as pd

# 將 src 目錄添加到 PYTHONPATH
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prometheus.services.backtesting_service import BacktestingService

# 定義測試數據檔案的路徑
# 使用 Path(__file__) 來確保無論從哪裡執行腳本，路徑都是正確的
TEST_DATA_PATH = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sample_spy_data.csv"

def run_verification():
    """
    執行一次獨立的回測驗證流程。
    """
    print("--- [階段 1] 從本地 CSV 載入歷史價格數據 ---")
    try:
        if not TEST_DATA_PATH.is_file():
            raise FileNotFoundError(f"測試數據檔案未找到: {TEST_DATA_PATH}")

        price_data = pd.read_csv(TEST_DATA_PATH, index_col="Date", parse_dates=True)

        # vectorbt 需要小寫的欄位名稱
        price_data.columns = [col.lower() for col in price_data.columns]
        print(f"成功載入 {len(price_data)} 筆本地 SPY 數據。")
    except Exception as e:
        print(f"錯誤：無法從 CSV 載入價格數據。{e}")
        return

    print("\n--- [階段 2] 初始化回測服務 ---")
    try:
        backtester = BacktestingService(price_data)
        print("BacktestingService 初始化成功。")
    except Exception as e:
        print(f"錯誤：BacktestingService 初始化失敗。{e}")
        return

    print("\n--- [階段 3] 定義並執行一個簡單的 RSI 策略 ---")
    # 定義一個簡單的基因：當 14 日 RSI 低於 30 時買入
    simple_genome = [
        {
            "factor": "RSI",
            "params": {"window": 14},
            "operator": "less_than",
            "value": 30
        }
    ]
    print(f"測試基因: {simple_genome}")

    try:
        results = backtester.run_backtest(simple_genome)
        print("回測執行成功。")
    except Exception as e:
        print(f"錯誤：回測執行期間發生未預期的錯誤。{e}")
        return

    print("\n--- [階段 4] 驗證績效報告 ---")
    print("產出的績效報告:")
    print("--------------------")
    for key, value in results.items():
        print(f"- {key}: {value}")
    print("--------------------")

    # 驗證報告的完整性和基本合理性
    required_keys = ["sharpe_ratio", "total_return", "max_drawdown", "win_rate", "is_valid"]
    if all(key in results for key in required_keys) and results["is_valid"]:
        print("\n✔ [驗證通過] 績效報告包含所有必要欄位，且策略被標記為有效。")
        # 進行一個非常寬鬆的合理性檢查
        if -5 < results["sharpe_ratio"] < 5 and -100 < results["total_return"] < 500:
            print("✔ [驗證通過] 關鍵指標數值在一個合理的範圍內。")
        else:
            print("⚠️ [警告] 績效指標數值看起來可能不尋常，建議手動檢查。")
    else:
        print("\n❌ [驗證失敗] 績效報告不完整或策略被標記為無效。")
        if "error" in results:
            print(f"  錯誤訊息: {results['error']}")


if __name__ == "__main__":
    run_verification()
