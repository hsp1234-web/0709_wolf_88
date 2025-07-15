import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import typer
import asyncio
from rich.live import Live
from src.core.context import AppContext
from src.core.events.event_types import SystemShutdown
from src.core.monitoring.dashboard import generate_status_table
from src.apps import evolution_app, backtest_worker_app, results_projector_app

app = typer.Typer()

@app.command()
def run(monitor: bool = typer.Option(False, "--monitor", help="啟動即時作戰情報中心。"),
        db_path: str = "output/results.sqlite"):
    """啟動並完整執行一次策略演化流程。"""
    asyncio.run(main(monitor=monitor, db_path=db_path))

async def main(monitor: bool, db_path: str = "output/results.sqlite"):
    async with AppContext(db_path=db_path) as context:
        # --- 統一啟動所有背景服務 ---
        tasks = [
            asyncio.create_task(backtest_worker_app.main(context)),
            asyncio.create_task(results_projector_app.main(context))
        ]

        # --- 如果啟用監控，則作為一個額外任務啟動 ---
        monitor_task = None
        if monitor:
            monitor_task = asyncio.create_task(run_dashboard(context))
            tasks.append(monitor_task)

        # --- 運行主流程 ---
        evo_task = asyncio.create_task(evolution_app.main(context))
        await evo_task

        # --- 發布關機信號 ---
        print("主控台：演化流程已完成。發布系統關機信號...")
        await context.event_stream.append(SystemShutdown(reason="Evolution completed."))

        # --- 等待所有背景服務優雅關閉 ---
        await asyncio.sleep(2) # 給予一點時間讓消費者處理關機信號
        if monitor_task:
            monitor_task.cancel()

        await asyncio.gather(*[t for t in tasks if not t.done()])

        print("主控台：所有服務已關閉。系統結束。")


async def run_dashboard(context: AppContext):
    """運行儀表板的非同步任務。"""
    with Live(generate_status_table({}), refresh_per_second=2, screen=True) as live:
        while True:
            try:
                total_events = await context.event_stream.get_total_event_count()
                checkpoints = await context.event_stream.get_all_checkpoints()
                metrics = {"total_events": total_events, "checkpoints": checkpoints}
                live.update(generate_status_table(metrics))
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                live.update(generate_status_table({"status": "關閉中..."}))
                await asyncio.sleep(0.5)
                break
            except Exception as e:
                # 在儀表板中顯示錯誤，但不停掉監控
                from rich.text import Text
                live.update(Text(f"儀表板錯誤: {e}", style="bold red"))
                await asyncio.sleep(5)


if __name__ == "__main__":
    app()
