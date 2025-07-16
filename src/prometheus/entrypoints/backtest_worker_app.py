import time

from prometheus.core.queue.sqlite_queue import SQLiteQueue
from prometheus.services.backtesting_service import BacktestingService
from prometheus.core.logging.log_manager import LogManager

POISON_PILL = "STOP_WORKING"


def backtest_worker_loop(
    task_queue: SQLiteQueue, results_queue: SQLiteQueue, price_data, worker_id: int
):
    """
    一個遵守鋼鐵契約的回測工作者：永不放棄，直到收到毒丸。
    """
    logger = LogManager.get_instance().get_logger(f"Backtest-Worker-{worker_id}")
    logger.info("回測工作者已啟動，正在等待任務...")
    backtester = BacktestingService(price_data)

    while True:
        try:
            task = task_queue.get(block=True)

            if task == POISON_PILL:
                logger.info("收到關閉信號，正在優雅退出...")
                break

            if not isinstance(task, (list, tuple)) or len(task) != 2:
                logger.warning(f"收到無效任務格式，已忽略: {task}")
                continue

            item_id, genome_task = task

            if not isinstance(genome_task, dict):
                logger.warning(f"收到無效的 genome_task 格式，已忽略: {genome_task}")
                continue

            params = genome_task.get("params", {})
            logger.info(f"正在回測任務 #{item_id}...")
            logger.debug(f"任務 #{item_id} 的基因: {params}")

            try:
                # 【萬象引擎】調用新的回測方法
                report = backtester.run_backtest(genome=params)
            except Exception as e:
                logger.error(f"回測函數內部出錯: {e}", exc_info=True)
                report = {"error": str(e), "is_valid": False}

            result_payload = {
                "genome_id": genome_task.get("id"),
                "params": params,
                "report": report,
                "processed_by": worker_id,
            }
            results_queue.put(result_payload)
            logger.debug(f"任務 #{item_id} 回測完成。")

        except Exception as e:
            logger.error(f"處理迴圈發生嚴重錯誤: {e}", exc_info=True)
            time.sleep(10)

    logger.info("已成功關閉。")
