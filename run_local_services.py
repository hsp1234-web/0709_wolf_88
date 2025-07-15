import threading
import time
from pathlib import Path

from src.core.queue.sqlite_queue import SQLiteQueue
from src.core.utils.data_loader import load_ohlcv_data
from src.apps.evolution_app import evolution_loop
from src.apps.backtest_worker_app import backtest_worker_loop, POISON_PILL as WORKER_PILL
from src.apps.results_projector_app import projector_loop, POISON_PILL as PROJECTOR_PILL

# --- 設定 ---
DATA_DIR = Path("data")
OHLCV_DATA_PATH = DATA_DIR / "ohlcv_data.csv"
TASK_QUEUE_PATH = DATA_DIR / "task_queue.db"
RESULTS_QUEUE_PATH = DATA_DIR / "results_queue.db"
NUM_BACKTEST_WORKERS = 2

def main():
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

    # 建立演化引擎 (它不是 daemon，它的結束將觸發系統關閉)
    evolution_thread = threading.Thread(
        target=evolution_loop,
        args=(task_queue, results_queue)
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
        # 在這種情況下，我們不需要特別做什麼，finally區塊會處理關閉

    finally:
        # 【核心改變】發送毒丸，命令所有工作者關閉
        print("[Conductor] 正在向所有佇列發送關閉信號 (毒丸)...")

        # 有多少個工人，就發送多少個毒丸
        for _ in range(NUM_BACKTEST_WORKERS):
            task_queue.put(WORKER_PILL)

        # 結果投影器只有一個
        results_queue.put(PROJECTOR_PILL)

        # 短暫等待，讓 daemon 執行緒有時間處理毒丸並打印退出訊息
        print("[Conductor] 等待背景服務處理關閉信號...")
        time.sleep(3)

        task_queue.close()
        results_queue.close()
        print("[Conductor] 佇列已關閉。系統完全關閉。")

if __name__ == "__main__":
    main()
