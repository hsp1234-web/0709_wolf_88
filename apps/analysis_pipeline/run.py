# In apps/analysis_pipeline/run.py
import argparse
import sys
from pathlib import Path

# 將專案根目錄加入 sys.path 以便導入其他模組
# 這是【核心架構原則】中「路徑獨立性」的體現
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from apps.factor_engine.sma_crossover_factor import calculate_sma_crossover

def main():
    """
    分析管線主執行器。

    核心邏輯:
    1. 解析命令行參數，決定要執行哪個分析任務。
    2. 根據參數，呼叫對應的分析模組。
    3. 處理並輸出分析結果。
    """
    parser = argparse.ArgumentParser(description="【普羅米修斯之火】分析管線執行器")
    parser.add_argument(
        '--factor',
        type=str,
        choices=['sma_crossover'],
        default='sma_crossover',
        help='要運行的因子或分析名稱'
    )
    # 未來可增加更多參數，如 ticker, start_date 等
    args = parser.parse_args()

    print(f"--- 啟動分析管線，執行任務: {args.factor} ---")

    if args.factor == 'sma_crossover':
        # 執行我們的 SMA 交叉因子計算
        result = calculate_sma_crossover()
        if result is not None:
            # 將結果儲存到 CSV 檔案
            output_path = project_root / "output" / "sma_crossover_result.csv"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            result.to_csv(output_path)
            print(f"✔ 分析結果已成功儲存至: {output_path}")
    else:
        print(f"未知的分析任務: {args.factor}")

    print("--- 分析管線執行完畢 ---")


if __name__ == "__main__":
    main()
