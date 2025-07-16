import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from prometheus.core.context import AppContext
from prometheus.core.db.sqlite_queue import SQLiteQueue
from prometheus.core.db.duckdb_writer import DuckDBWriter
from prometheus.core.engines.robust_acquisition_engine import RobustDataAcquisitionEngine
from rich.console import Console

console = Console()

async def probe_ticker(engine, ticker, interval, config):
    """探測單一資產的數據可用性"""
    period = config.get("period")
    if not period and "days" in config:
        period = f"{config['days']}d"

    try:
        ticker_instance, df = await engine.fetch_single_ticker(
            ticker=ticker,
            interval=interval,
            period=period
        )
        if df is not None and not df.empty:
            return {
                "status": "✅ 成功",
                "count": len(df),
                "start_date": df['date'].min().strftime('%Y-%m-%d'),
                "end_date": df['date'].max().strftime('%Y-%m-%d'),
            }
    except Exception as e:
        console.log(f"探測 {ticker} ({interval}) 時發生錯誤: {e}", style="bold red")

    return {"status": "❌ 失敗", "count": 0, "start_date": "N/A", "end_date": "N/A"}

async def main():
    """主執行函數"""
    queue = SQLiteQueue(db_path="output/recon_queue.sqlite", queue_name="recon_tasks")
    writer = DuckDBWriter(db_path="output/recon_results.duckdb")

    all_tickers = []
    # We need to get all tickers to initialize the engine, but the queue doesn't expose them.
    # We'll need to read them from the asset universe again.
    # This is a bit redundant, but it's the simplest way for now.
    from seed_recon_tasks import ASSET_UNIVERSE
    all_tickers = [ticker for details in ASSET_UNIVERSE.values() for ticker in details['tickers']]


    async with AppContext() as context:
        engine = RobustDataAcquisitionEngine(tickers=all_tickers)

        while True:
            task_id, task = queue.get()
            if not task:
                break

            console.print(f"正在處理任務: [yellow]{task['ticker']}[/yellow] @ [magenta]{task['interval']}[/magenta]...")

            result = await probe_ticker(engine, task['ticker'], task['interval'], task['config'])

            data_to_write = {
                "category": task['category'],
                "ticker": task['ticker'],
                "interval": task['interval'],
                "label": task['config']['label'],
                "status": result['status'],
                "count": result['count'],
                "start_date": result['start_date'],
                "end_date": result['end_date'],
            }
            writer.write(data_to_write)

            queue.ack(task_id)

    writer.close()
    console.print("[bold green]所有偵察任務已完成。[/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
