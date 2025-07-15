import time

from rich.table import Table


def generate_status_table(metrics: dict) -> Table:
    table = Table(title=f"作戰情報中心 (更新於 {time.strftime('%H:%M:%S')})")
    table.add_column("監控指標", justify="right", style="cyan", no_wrap=True)
    table.add_column("數值", style="magenta")
    total_events = metrics.get("total_events", 0)
    table.add_row("事件流總量", str(total_events))
    table.add_row("---", "---")
    checkpoints = metrics.get("checkpoints", {})
    if not checkpoints:
        table.add_row("消費者進度", "[yellow]正在等待消費者上線...[/yellow]")
    else:
        for consumer_id, last_id in checkpoints.items():
            lag = total_events - last_id
            table.add_row(f"消費者 [{consumer_id}] 進度", str(last_id))
            table.add_row(
                f"消費者 [{consumer_id}] 延遲",
                f"[red]{lag}[/red]" if lag > 10 else f"[green]{lag}[/green]",
            )
            table.add_row("---", "---")
    return table
