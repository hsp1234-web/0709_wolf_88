import threading
import time
from pathlib import Path
import typer

from src.core.queue.sqlite_queue import SQLiteQueue
from src.core.utils.data_loader import load_ohlcv_data
from src.apps.evolution_app import evolution_loop
from src.apps.backtest_worker_app import backtest_worker_loop, POISON_PILL as WORKER_PILL
from src.apps.results_projector_app import projector_loop, POISON_PILL as PROJECTOR_PILL

# --- 設定 ---
DATA_DIR = Path("data")
OHLCV_DATA_PATH = DATA_DIR / "ohlcv_data.csv"
DB_DIR = DATA_DIR / "db"
TASK_QUEUE_PATH = DB_DIR / "task_queue.db"
RESULTS_QUEUE_PATH = DB_DIR / "results_queue.db"
NUM_BACKTEST_WORKERS = 2

# 建立一個 Typer 應用
app = typer.Typer()

@app.command()
def run(
    resume: bool = typer.Option(False, "--resume", help="從上次的檢查點恢復演化。"),
    clean: bool = typer.Option(False, "--clean", help="強制進行一次全新的演化，忽略所有檢查點。")
):
    """
    啟動【普羅米修斯之火】本地服務。
    """
    if resume and clean:
        print("錯誤：--resume 和 --clean 旗標不能同時使用。")
        raise typer.Exit(code=1)

    # --- 數據加載和佇列初始化 ---
    print("[Conductor] 正在加載歷史價格數據...")
    try:
        price_data = load_ohlcv_data(OHLCV_DATA_PATH)
        print(f"[Conductor] 數據加載成功，共 {len(price_data)} 筆。")
    except FileNotFoundError as e:
        print(f"[Conductor] 致命錯誤: {e}")
        print("[Conductor] 請確保 'data/ohlcv_data.csv' 檔案存在。")
        return

    task_queue = SQLiteQueue(db_path=TASK_QUEUE_PATH, table_name="tasks")
    results_queue = SQLiteQueue(db_path=RESULTS_QUEUE_PATH, table_name="results")

    # --- 建立並啟動所有執行緒 ---
    threads = []

    # 建立回測工作者
    for i in range(NUM_BACKTEST_WORKERS):
        worker_thread = threading.Thread(
            target=backtest_worker_loop,
            args=(task_queue, results_queue, price_data, i + 1),
            daemon=True
        )
        threads.append(worker_thread)

    # 建立結果投影器
    projector_thread = threading.Thread(
        target=projector_loop,
        args=(results_queue,),
        daemon=True
    )
    threads.append(projector_thread)

    # 【核心改變】將 evolution_loop 的參數傳入
    evolution_thread = threading.Thread(
        target=evolution_loop,
        args=(task_queue, results_queue, resume, clean)
    )
    threads.append(evolution_thread)

    for thread in threads:
        thread.start()

    print("[Conductor] 所有工作者已啟動。系統正在運行...")
    print("[Conductor] 等待演化引擎完成任務...")

    try:
        # 主執行緒現在等待演化引擎執行緒結束
        evolution_thread.join()
        print("\n[Conductor] 偵測到演化引擎已完成！正在準備關閉所有背景服務...")

    except KeyboardInterrupt:
        print("\n[Conductor] 偵測到手動中斷 (Ctrl+C)！正在準備關閉所有服務...")

    finally:
        # 發送毒丸，命令所有工作者關閉
        print("[Conductor] 正在向所有佇列發送關閉信號 (毒丸)...")

        for _ in range(NUM_BACKTEST_WORKERS):
            task_queue.put(WORKER_PILL)

        results_queue.put(PROJECTOR_PILL)

        print("[Conductor] 等待背景服務處理關閉信號...")
        time.sleep(3)

        task_queue.close()
        results_queue.close()
        print("[Conductor] 佇列已關閉。系統完全關閉。")


if __name__ == "__main__":
    app()
