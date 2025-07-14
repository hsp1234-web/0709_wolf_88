from src.core.context import AppContext
from src.core.services.backtesting_service import BacktestingService

def main(context: AppContext):
    """ 背景回測工作者 v2.2 (模式感知版) """
    log_manager = context.log_manager
    backtester = BacktestingService(context.results_saver, log_manager, mode=context.mode)

    log_manager.log("INFO", f"背景回測工作者已在 '{context.mode}' 模式下啟動，等待任務...")

    while True:
        try:
            task = context.queue.get(block=True, timeout=None)
            if task is None:
                log_manager.log("INFO", "收到 None 任務，工作者將優雅地關閉。")
                break

            individual = task.get("individual")
            backtest_id = task.get("backtest_id")

            if individual and backtest_id:
                fitness = backtester.run_backtest(individual, backtest_id)
                context.queue.put_result({"backtest_id": backtest_id, "fitness": fitness})

        except Exception as e:
            log_manager.log("CRITICAL", f"背景工作者發生未預期的錯誤: {e}", exc_info=True)
            continue

    log_manager.log("SUCCESS", "背景回測工作者已成功關閉。")
