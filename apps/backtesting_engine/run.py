# In apps/backtesting_engine/run.py
import sys
from pathlib import Path
import pandas as pd

# 添加路徑以導入模組
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from apps.factor_engine.sma_crossover_factor import calculate_sma_crossover
from apps.backtesting_engine.engine import Backtester

def main():
    """
    回測管線主執行器。
    """
    print("--- 啟動回測管線 ---")

    # 步驟 1: 獲取交易信號
    print("[1/3] 正在從因子引擎獲取交易信號...")
    factor_result = calculate_sma_crossover()
    if factor_result is None:
        print("❌ 無法獲取因子數據，回測中止。")
        return

    # 提取所需序列
    price_series = factor_result['spy_close']
    signal_series = factor_result['position'] # 使用 position 而非 signal.diff()

    # 步驟 2: 初始化並運行回測引擎
    print("[2/3] 正在初始化並運行回測引擎...")
    backtester = Backtester(price_series, signal_series)
    backtester.run()

    # 步驟 3: 獲取並展示績效
    print("[3/3] 正在計算並展示績效報告...")
    performance = backtester.get_performance_metrics()

    print("\n--- SMA 交叉策略回測績效報告 ---")
    for key, value in performance.items():
        print(f"{key}: {value}")
    print("---------------------------------")

if __name__ == "__main__":
    main()
