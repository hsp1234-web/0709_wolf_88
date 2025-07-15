# 檔案: run_local_services.py
import threading
import time
from pathlib import Path

from src.core.queue.sqlite_queue import SQLiteQueue
from src.apps.backtest_worker_app import backtest_worker_loop
from src.apps.evolution_app import evolution_loop
from src.apps.results_projector_app import projector_loop

# --- 設定 ---
QUEUE_DB_PATH = Path("data/task_queue.db")

def main():
    # 確保目錄存在
    QUEUE_DB_PATH.parent.mkdir(exist_ok=True)

    # 初始化共享的任務佇列
    task_queue = SQLiteQueue(db_path=QUEUE_DB_PATH)
    evolution_queue = SQLiteQueue(db_path=Path("data/evolution_queue.db"))
    projector_queue = SQLiteQueue(db_path=Path("data/projector_queue.db"))

    # --- 啟動所有背景工作者執行緒 ---
    workers = [
        # 啟動 2 個回測工作者
        threading.Thread(target=backtest_worker_loop, args=(task_queue, 1), daemon=True),
        threading.Thread(target=backtest_worker_loop, args=(task_queue, 2), daemon=True),
        # 啟動演化工作者
        threading.Thread(target=evolution_loop, args=(evolution_queue, 3), daemon=True),
        # 啟動結果投影工作者
        threading.Thread(target=projector_loop, args=(projector_queue, 4), daemon=True),
    ]

    for worker in workers:
        worker.start()

    print("[Conductor] 所有工作者已啟動。系統正在運行...")
    print("[Conductor] 使用 Ctrl+C 來關閉系統。")

    # --- 主執行緒可以做一些事情，例如定期添加任務 ---
    try:
        # 模擬定期產生任務
        task_counter = 0
        while True:
            task_counter += 1
            print(f"[Conductor] 正在產生第 {task_counter} 個基因組任務...")
            task_queue.put(f"Genome-{task_counter}")
            evolution_queue.put(f"EvolutionTask-{task_counter}")
            projector_queue.put(f"ResultTask-{task_counter}")

            # 每 10 秒產生一個會出錯的任務
            if task_counter % 5 == 0:
                print("[Conductor] 正在產生一個【會出錯的】任務！")
                task_queue.put("error_genome")
                evolution_queue.put("error_evolution")
                projector_queue.put("error_result")

            time.sleep(5)
    except KeyboardInterrupt:
        print("\n[Conductor] 偵測到 Ctrl+C！正在準備關閉...")
        # 由於執行緒是 daemon，主程式結束時它們會自動退出
        # 我們也可以在這裡加入更優雅的關閉邏輯，例如向佇列放入"毒丸"
    finally:
        task_queue.close()
        evolution_queue.close()
        projector_queue.close()
        print("[Conductor] 佇列已關閉。系統結束。")

if __name__ == "__main__":
    main()
