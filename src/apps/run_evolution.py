"""
【創世紀畫】主控台應用。

這是整個演化流程的統一入口點。它負責：
1. 啟動所有背景消費者（回測工作者、結果投影者）。
2. 運行主要的生產者（演化室）。
3. 在生產者完成後，發布一個「關機」事件。
4. 等待所有背景消費者確認關閉後，程序結束。
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import typer
import asyncio
from src.core.context import AppContext
from src.core.events.event_types import SystemShutdown
from src.apps import evolution_app, backtest_worker_app, results_projector_app

app = typer.Typer()

@app.command()
def run():
    """啟動並完整執行一次策略演化流程。"""
    asyncio.run(main())

async def main(db_path: str = "output/results.sqlite"):
    async with AppContext(db_path=db_path) as context:
        print("主控台：啟動背景服務...")
        worker_task = asyncio.create_task(backtest_worker_app.main(context))
        projector_task = asyncio.create_task(results_projector_app.main(context))

        # 給予背景任務一點啟動時間
        await asyncio.sleep(0.1)

        print("主控台：啟動演化流程...")
        await evolution_app.main(context)
        print("主控台：演化流程已完成。")

        # 在發布關機信號前，短暫等待，以確保所有進行中的事件能被初步處理
        await asyncio.sleep(2)

        print("主控台：發布系統關機信號...")
        shutdown_event = SystemShutdown(reason="Evolution completed.")
        await context.event_stream.append(shutdown_event)

        print("主控台：等待背景服務優雅關閉...")
        await asyncio.gather(worker_task, projector_task)
        print("主控台：所有服務已關閉。系統結束。")

if __name__ == "__main__":
    app()
