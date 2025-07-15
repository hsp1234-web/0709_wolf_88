import sqlite3
import subprocess
import time
from pathlib import Path

import pytest

# --- 設定 ---
DB_DIR = Path("data/db")
TASK_QUEUE_PATH = DB_DIR / "task_queue.db"
RESULTS_QUEUE_PATH = DB_DIR / "results_queue.db"


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown_dbs():
    """在模組測試前後清理並準備資料庫"""
    # 測試前清理
    if TASK_QUEUE_PATH.exists():
        TASK_QUEUE_PATH.unlink()
    if RESULTS_QUEUE_PATH.exists():
        RESULTS_QUEUE_PATH.unlink()

    DB_DIR.mkdir(exist_ok=True)

    yield

    # 測試後清理
    if TASK_QUEUE_PATH.exists():
        TASK_QUEUE_PATH.unlink()
    if RESULTS_QUEUE_PATH.exists():
        RESULTS_QUEUE_PATH.unlink()


def test_e2e_discover_workflow():
    """
    端到端整合測試：
    1. 啟動 `services start --mode discover` 服務集群。
    2. 運行一小段時間，讓其產生任務並處理。
    3. 終止服務。
    4. 檢查結果資料庫，驗證是否有結果寫入。
    """
    # 1. 啟動服務集群
    command = [
        "poetry",
        "run",
        "python",
        "run.py",
        "services",
        "start",
        "--mode",
        "discover",
    ]

    # 使用 Popen 在背景啟動服務
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    # 2. 運行一小段時間
    run_time = 45  # 秒
    print(f"讓服務運行 {run_time} 秒...")

    try:
        # 等待，同時可以監控輸出來判斷服務是否正常啟動
        start_time = time.time()
        while time.time() - start_time < run_time:
            # 可以在這裡添加更複雜的健康檢查邏輯
            if process.poll() is not None:
                # 如果進程在此期間意外終止，則測試失敗
                stdout, stderr = process.communicate()
                pytest.fail(f"服務意外終止。\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")
            time.sleep(1)

    finally:
        # 3. 終止服務
        print("正在終止服務...")
        process.terminate()  # 發送 SIGTERM
        try:
            # 等待進程終止，設置超時
            stdout, stderr = process.communicate(timeout=10)
            print("服務已成功終止。")
        except subprocess.TimeoutExpired:
            print("終止超時，強制終止服務...")
            process.kill()  # 發送 SIGKILL
            stdout, stderr = process.communicate()
            print("服務已被強制終止。")

        print(f"\nSTDOUT:\n{stdout}")
        print(f"\nSTDERR:\n{stderr}")

    # 4. 檢查結果資料庫
    print("正在檢查結果資料庫...")
    assert RESULTS_QUEUE_PATH.exists(), "結果資料庫檔案未被創建"

    conn = sqlite3.connect(RESULTS_QUEUE_PATH)
    cursor = conn.cursor()

    # 檢查 'results' 表是否存在
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='results';"
    )
    assert cursor.fetchone() is not None, "結果表中 'results' 表未被創建"

    # 檢查是否有數據寫入
    cursor.execute("SELECT COUNT(*) FROM results")
    count = cursor.fetchone()[0]

    conn.close()

    assert count > 0, "沒有任何結果被寫入資料庫，端到端流程可能已中斷"
    print(f"測試成功！在結果資料庫中發現 {count} 條記錄。")
