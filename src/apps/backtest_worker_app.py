# 檔案: src/apps/backtest_worker_app.py
import asyncio
from src.core.context import AppContext
from src.core.services.backtesting_service import BacktestingService

async def main(context: AppContext):
    backtester = BacktestingService(context.results_saver)
    print("背景回測工作者已啟動...")
    while True:
        task = await context.queue.get()
        if task is None:
            context.queue.task_done()
            break

        try:
            fitness = await backtester.run_backtest(task["individual"], task["backtest_id"])
            await context.queue.put_result({"backtest_id": task["backtest_id"], "fitness": fitness})
        finally:
            context.queue.task_done()
    print("背景回測工作者已關閉。")
