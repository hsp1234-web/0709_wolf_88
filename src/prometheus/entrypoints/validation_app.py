import json
from pathlib import Path

from prometheus.core.queue.sqlite_queue import SQLiteQueue

HALL_OF_FAME_PATH = Path("data/hall_of_fame.json")


def validation_loop(task_queue: SQLiteQueue, results_queue: SQLiteQueue):
    """
    驗證者的主迴圈。它只執行一次，用於驗證名人堂中的最佳策略。
    """
    print("[Validator] 驗證者已啟動。")

    # 1. 讀取名人堂
    if not HALL_OF_FAME_PATH.exists():
        print(f"[Validator] 錯誤：找不到名人堂檔案 {HALL_OF_FAME_PATH}。無法進行驗證。")
        return

    try:
        with open(HALL_OF_FAME_PATH, "r") as f:
            best_strategy = json.load(f)

        in_sample_params = best_strategy["params"]
        # 【核心改變】直接從 fitness 物件中讀取 sharpe_ratio
        in_sample_fitness = best_strategy.get("fitness", {})
        in_sample_sharpe = in_sample_fitness.get("sharpe_ratio", "N/A")

        # 確保即使 in_sample_sharpe 是 'N/A' 也能正常打印
        sharpe_to_print = (
            f"{in_sample_sharpe:.2f}"
            if isinstance(in_sample_sharpe, (int, float))
            else in_sample_sharpe
        )
        print(f"[Validator] 已從名人堂讀取到最佳策略 (樣本內夏普: {sharpe_to_print})")

        # 2. 發送樣本外回測任務 (遵循 (id, payload) 的格式)
        task_id = "out_of_sample_validation"
        validation_task = {"id": task_id, "params": in_sample_params}
        task_queue.put((task_id, validation_task))
        print(f"[Validator] 已發送樣本外回測任務: {in_sample_params}")

        # 3. 等待驗證結果
        print("[Validator] 等待樣本外回測結果...")
        result_payload = results_queue.get(block=True)  # 只等待這唯一一個結果

        if result_payload:
            # 【核心改變】結果本身就是 payload，不再需要解包
            out_of_sample_report = result_payload.get("report", {})

            # 4. 打印最終對比報告
            print("\n" + "=" * 20 + " 最終驗證報告 " + "=" * 20)
            print(f"策略參數: {in_sample_params}")
            print("-" * 55)
            print("樣本內表現 (學習區):")
            print(f"  - 夏普比率: {in_sample_fitness['sharpe_ratio']:.2f}")
            print("樣本外表現 (未知區):")
            print(f"  - 夏普比率: {out_of_sample_report.get('sharpe_ratio', 'N/A')}")
            print(f"  - 總報酬率: {out_of_sample_report.get('total_return', 'N/A')}%")
            print(f"  - 最大回撤: {out_of_sample_report.get('max_drawdown', 'N/A')}%")
            print("=" * 55)

            # 簡單的結論
            if out_of_sample_report.get("sharpe_ratio", -99) > 0.5:
                print("結論：[通過] 策略在樣本外表現穩健，具備一定的泛化能力。")
            else:
                print("結論：[警告] 策略在樣本外表現不佳，可能存在過擬合風險。")

            # 【核心改變】將驗證結果儲存到檔案
            VALIDATION_REPORT_PATH = Path("data/validation_report.json")
            VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(VALIDATION_REPORT_PATH, "w", encoding="utf-8") as f:
                json.dump(result_payload, f, indent=4)
            print(f"[Validator] 驗證結果已儲存至 {VALIDATION_REPORT_PATH}")

    except Exception as e:
        print(f"!!!!!! [Validator] 驗證過程中發生錯誤: {e} !!!!!!")

    print("[Validator] 驗證完成，即將關閉。")
