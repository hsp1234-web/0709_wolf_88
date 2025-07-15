import typer
import asyncio
from rich.live import Live
from src.core.context import AppContext
from src.core.events.event_types import SystemShutdown
from src.core.monitoring.dashboard import generate_status_table
from src.core.services.checkpoint_manager import CheckpointManager
from src.apps import evolution_app, backtest_worker_app, results_projector_app

app = typer.Typer()

@app.command()
def run(
    monitor: bool = typer.Option(False, "--monitor", help="啟動即時作戰情報中心。"),
    resume: bool = typer.Option(False, "--resume", help="從上次的檢查點恢復演化。"),
    clean: bool = typer.Option(False, "--clean", help="強制進行一次全新的演化，將忽略並清除所有舊的檢查點。")
):
    """啟動並完整執行一次策略演化流程。"""
    if resume and clean:
        print("錯誤：--resume 和 --clean 旗標不能同時使用。"); raise typer.Exit(code=1)
    asyncio.run(main(monitor=monitor, resume=resume, clean=clean))

async def main(monitor: bool, resume: bool, clean: bool):
    if clean: CheckpointManager().clear()
    async with AppContext() as context:
        tasks = [
            asyncio.create_task(backtest_worker_app.main(context)),
            asyncio.create_task(results_projector_app.main(context))
        ]
        if monitor: tasks.append(asyncio.create_task(run_dashboard(context)))

        await evolution_app.main(context, resume=resume)
        await context.event_stream.append(SystemShutdown(reason="Evolution completed."))
        await asyncio.gather(*tasks)
        print("主控台：所有服務已關閉。系統結束。")

async def run_dashboard(context: AppContext):
    with Live(generate_status_table({}), refresh_per_second=0.5, screen=True) as live:
        while True:
            try:
                total_events = await context.event_stream.get_total_event_count()
                checkpoints = await context.event_stream.get_all_checkpoints()
                metrics = {"total_events": total_events, "checkpoints": checkpoints}
                live.update(generate_status_table(metrics))
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break

if __name__ == "__main__": app()
