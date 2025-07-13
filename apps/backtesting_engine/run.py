# In apps/backtesting_engine/run.py
import os
import sys
from pathlib import Path

import pandas as pd

# 添加路徑以導入模組
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from apps.backtesting_engine.engine import Backtester
from apps.factor_engine.sma_crossover_factor import (
    calculate_sma_crossover,
)


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
    results_df = backtester.run() # 獲取回測結果 DataFrame

    # 步驟 3: 獲取並展示績效
    print("[3/3] 正在計算並展示績效報告...")
    performance = backtester.get_performance_metrics()

    print("\n--- SMA 交叉策略回測績效報告 ---")
    for key, value in performance.items():
        print(f"{key}: {value}")
    print("---------------------------------")

    # 步驟 4: 儲存結果以供視覺化
    print("[4/4] 正在儲存回測結果...")
    output_dir = project_root / "output"
    os.makedirs(output_dir, exist_ok=True)

    # 結合因子數據與回測結果
    # 注意：backtester.results 的索引可能與 factor_result 不完全對齊，我們用外部合併
    final_output_df = pd.concat([factor_result, results_df[['cumulative_returns', 'strategy_returns']]], axis=1)
    final_output_df.index.name = 'datetime'

    output_path = output_dir / "sma_crossover_result.csv"
    final_output_df.to_csv(output_path)
    print(f"✔ 結果已儲存至: {output_path}")

if __name__ == "__main__":
    main()
