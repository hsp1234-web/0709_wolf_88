import json
from pathlib import Path

from prometheus.core.queue.sqlite_queue import SQLiteQueue
from prometheus.core.logging.log_manager import LogManager

HALL_OF_FAME_PATH = Path("data/hall_of_fame.json")
VALIDATION_REPORT_PATH = Path("data/reports/validation_report.json")
logger = LogManager.get_instance().get_logger("Validator")


def validation_loop(task_queue: SQLiteQueue, results_queue: SQLiteQueue):
    """
    驗證者的主迴圈。它只執行一次，用於驗證名人堂中的最佳策略。
    """
    logger.info("驗證者已啟動。")

    if not HALL_OF_FAME_PATH.exists():
        logger.error(f"找不到名人堂檔案 {HALL_OF_FAME_PATH}。無法進行驗證。")
        return

    try:
        with open(HALL_OF_FAME_PATH, "r") as f:
            # 【萬象引擎】名人堂現在是一個列表
            best_strategies = json.load(f)
            best_strategy = best_strategies[0]

        in_sample_params = best_strategy["params"]
        in_sample_fitness = best_strategy.get("fitness", {})
        in_sample_sharpe = in_sample_fitness.get("sharpe_ratio", "N/A")

        sharpe_to_print = (
            f"{in_sample_sharpe:.2f}"
            if isinstance(in_sample_sharpe, (int, float))
            else in_sample_sharpe
        )
        logger.info(f"已從名人堂讀取到最佳策略 (樣本內夏普: {sharpe_to_print})")

        task_id = "out_of_sample_validation"
        validation_task = {"id": task_id, "params": in_sample_params}
        task_queue.put((task_id, validation_task))
        logger.info(f"已發送樣本外回測任務: {in_sample_params}")

        logger.info("等待樣本外回測結果...")
        result = results_queue.get(block=True, timeout=60)
        _, result_payload = result

        if result_payload:
            out_of_sample_report = result_payload.get("report", {})

            report_str = "\n" + "=" * 20 + " 最終驗證報告 " + "=" * 20 + "\n"
            report_str += f"策略參數: {in_sample_params}\n"
            report_str += "-" * 55 + "\n"
            report_str += "樣本內表現 (學習區):\n"
            report_str += f"  - 夏普比率: {in_sample_sharpe:.2f}\n"
            report_str += "樣本外表現 (未知區):\n"
            report_str += f"  - 夏普比率: {out_of_sample_report.get('sharpe_ratio', 'N/A')}\n"
            report_str += f"  - 總報酬率: {out_of_sample_report.get('total_return', 'N/A')}%\n"
            report_str += f"  - 最大回撤: {out_of_sample_report.get('max_drawdown', 'N/A')}%\n"
            report_str += "=" * 55
            logger.info(report_str)

            if out_of_sample_report.get("is_valid") and out_of_sample_report.get("sharpe_ratio", -99) > 0.5:
                logger.info("結論：[通過] 策略在樣本外表現穩健，具備一定的泛化能力。")
            else:
                logger.warning("結論：[警告] 策略在樣本外表現不佳，可能存在過擬合風險。")

            VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(VALIDATION_REPORT_PATH, "w", encoding="utf-8") as f:
                json.dump(result_payload, f, indent=4)
            logger.info(f"驗證結果已儲存至 {VALIDATION_REPORT_PATH}")

    except Exception as e:
        logger.error(f"驗證過程中發生錯誤: {e}", exc_info=True)

    logger.info("驗證完成，即將關閉。")
