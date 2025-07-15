import threading
import time
from pathlib import Path
import typer
from enum import Enum

from src.core.queue.sqlite_queue import SQLiteQueue
from src.core.utils.data_loader import load_ohlcv_data
from src.apps.evolution_app import evolution_loop
from src.apps.backtest_worker_app import backtest_worker_loop, POISON_PILL as WORKER_PILL
from src.apps.validation_app import validation_loop
from src.apps.ai_analyst_app import analyst_job

# --- 設定 ---
DATA_DIR = Path("data")
OHLCV_DATA_PATH = DATA_DIR / "ohlcv_data.csv"
DB_DIR = DATA_DIR / "db"
TASK_QUEUE_PATH = DB_DIR / "task_queue.db"
RESULTS_QUEUE_PATH = DB_DIR / "results_queue.db"
NUM_BACKTEST_WORKERS = 2

# 建立一個 Typer 應用
app = typer.Typer()

# 定義可選的運行模式
class RunMode(str, Enum):
    discover = "discover"
    validate = "validate"
    report = "report"

@app.command()
def run(
    mode: RunMode = typer.Option(..., help="選擇運行模式：'discover', 'validate', 或 'report'。"),
    split_ratio: float = typer.Option(0.7, help="樣本內數據的分割比例。"),
    resume: bool = typer.Option(False, "--resume", help="從上次的檢查點恢復演化。"),
    clean: bool = typer.Option(False, "--clean", help="強制進行一次全新的演化，忽略所有檢查點。")
):
    """
    啟動【普羅米修斯之火】本地服務。
    """
    print(f"[Conductor] 正在以 '{mode.value}' 模式運行...")

    # --- 報告模式 ---
    if mode == RunMode.report:
        print("[Conductor] 正在啟動【報告模式】...")
        analyst_job()
        print("[Conductor] 報告模式已執行完畢。")
        return

    # --- 探索與驗證模式的共享邏輯 ---
    if resume and clean:
        print("錯誤：--resume 和 --clean 旗標不能同時使用。")
        raise typer.Exit(code=1)

    try:
        in_sample_data, out_of_sample_data = load_ohlcv_data(OHLCV_DATA_PATH, split_ratio=split_ratio)
    except FileNotFoundError as e:
        print(f"[Conductor] 致命錯誤: {e}")
        print(f"[Conductor] 請確保 '{OHLCV_DATA_PATH}' 檔案存在。")
        raise typer.Exit(code=1)

    price_data_for_workers = in_sample_data if mode == RunMode.discover else out_of_sample_data
    threads = []
    task_queue = SQLiteQueue(db_path=TASK_QUEUE_PATH, table_name="tasks")
    results_queue = SQLiteQueue(db_path=RESULTS_QUEUE_PATH, table_name="results")

    if mode == RunMode.discover:
        print("[Conductor] 正在啟動【探索模式】服務...")
        threads.append(threading.Thread(target=evolution_loop, args=(task_queue, results_queue, resume, clean)))
        for i in range(NUM_BACKTEST_WORKERS):
            worker_task_queue = SQLiteQueue(db_path=TASK_QUEUE_PATH, table_name="tasks")
            worker_results_queue = SQLiteQueue(db_path=RESULTS_QUEUE_PATH, table_name="results")
            threads.append(threading.Thread(target=backtest_worker_loop, args=(worker_task_queue, worker_results_queue, price_data_for_workers, i + 1), daemon=True))

    elif mode == RunMode.validate:
        print("[Conductor] 正在啟動【驗證模式】服務...")
        threads.append(threading.Thread(target=validation_loop, args=(task_queue, results_queue)))
        worker_task_queue = SQLiteQueue(db_path=TASK_QUEUE_PATH, table_name="tasks")
        worker_results_queue = SQLiteQueue(db_path=RESULTS_QUEUE_PATH, table_name="results")
        threads.append(threading.Thread(target=backtest_worker_loop, args=(worker_task_queue, worker_results_queue, price_data_for_workers, 1), daemon=True))

    for thread in threads:
        thread.start()

    print("[Conductor] 所有服務已啟動。系統正在運行...")
    main_thread = next((t for t in threads if not t.daemon), None)

    try:
        if main_thread:
            target_name = main_thread._target.__name__ if hasattr(main_thread, '_target') and main_thread._target else "Unknown"
            print(f"[Conductor] 等待主服務 ({target_name}) 完成任務...")
            main_thread.join()
            print(f"\n[Conductor] 偵測到主服務 ({target_name}) 已完成！正在準備關閉所有背景服務...")
        else:
            while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Conductor] 偵測到手動中斷 (Ctrl+C)！正在準備關閉所有服務...")
    finally:
        print("[Conductor] 正在向所有佇列發送關閉信號 (毒丸)...")
        num_pills = NUM_BACKTEST_WORKERS if mode == RunMode.discover else 1
        for _ in range(num_pills):
            task_queue.put(WORKER_PILL)
        print("[Conductor] 等待背景服務處理關閉信號...")
        time.sleep(3)
        task_queue.close()
        results_queue.close()
        print("[Conductor] 佇列已關閉。系統完全關閉。")

if __name__ == "__main__":
    app()
