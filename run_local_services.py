import asyncio
from pathlib import Path

from src.core.queue.sqlite_queue import SQLiteQueue
from src.core.data.data_loader import load_ohlcv_data
from src.apps.evolution_app import main as evolution_main
from src.apps.backtest_worker_app import backtest_worker_loop
from src.apps.results_projector_app import main as projector_main
from src.core.context import AppContext

# --- 設定 ---
DATA_DIR = Path("data")
OHLCV_DATA_PATH = DATA_DIR / "ohlcv_data.csv" # 指定數據檔案路徑
TASK_QUEUE_PATH = DATA_DIR / "task_queue.db"
RESULTS_QUEUE_PATH = DATA_DIR / "results_queue.db"

async def main():
    # 【核心改變】在啟動時預加載一次數據
    print("[Conductor] 正在加載歷史價格數據...")
    try:
        price_data = load_ohlcv_data(OHLCV_DATA_PATH)
        print(f"[Conductor] 數據加載成功，共 {len(price_data)} 筆。")
    except FileNotFoundError as e:
        print(f"[Conductor] 致命錯誤: {e}")
        print("[Conductor] 請確保 'data/ohlcv_data.csv' 檔案存在。")
        return

    task_queue = SQLiteQueue(db_path=TASK_QUEUE_PATH)
    results_queue = SQLiteQueue(db_path=RESULTS_QUEUE_PATH)

    async with AppContext() as context:
        loop = asyncio.get_running_loop()

        # 將同步的 backtest_worker_loop 放在執行緒中運行
        worker_thread_1 = loop.run_in_executor(None, backtest_worker_loop, task_queue, results_queue, price_data, 1)
        worker_thread_2 = loop.run_in_executor(None, backtest_worker_loop, task_queue, results_queue, price_data, 2)

        # 異步任務
        evolution_task = asyncio.create_task(evolution_main(context))
        projector_task = asyncio.create_task(projector_main(context))

        try:
            await asyncio.gather(
                evolution_task,
                projector_task,
                worker_thread_1,
                worker_thread_2,
            )
        except KeyboardInterrupt:
            print("[Conductor] 正在關閉所有服務...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Conductor] 服務已終止。")
