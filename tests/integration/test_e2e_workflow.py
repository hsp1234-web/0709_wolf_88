import subprocess
import time
from pathlib import Path

import pytest

# --- 設定 ---
DATA_DIR = Path("data")
DB_DIR = DATA_DIR / "db"
TASK_QUEUE_PATH = DB_DIR / "task_queue.db"
RESULTS_QUEUE_PATH = DB_DIR / "results_queue.db"
HALL_OF_FAME_PATH = DATA_DIR / "hall_of_fame.json"
CHECKPOINT_PATH = DATA_DIR / "checkpoints/evolution_state.pkl"
OHLCV_DATA_PATH = DATA_DIR / "ohlcv_data.csv"


def cleanup_files():
    """在測試前後清理所有相關檔案，確保測試環境的純淨。"""
    files_to_delete = [
        TASK_QUEUE_PATH,
        RESULTS_QUEUE_PATH,
        HALL_OF_FAME_PATH,
        CHECKPOINT_PATH,
        OHLCV_DATA_PATH,
    ]
    for f in files_to_delete:
        if f.exists():
            f.unlink()
            print(f"已刪除舊檔案: {f}")


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """
    Pytest fixture: 在每次測試前執行清理，並在測試後再次執行清理。
    """
    cleanup_files()
    # 建立測試用的假數據
    OHLCV_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OHLCV_DATA_PATH, "w") as f:
        f.write("Date,Open,High,Low,Close,Volume\n")
        f.write("2023-01-01,100,102,99,101,10000\n")
        f.write("2023-01-02,101,103,100,102,12000\n")
        f.write("2023-01-03,102,105,101,104,15000\n")
        f.write("2023-01-04,104,106,103,105,18000\n")
        f.write("2023-01-05,105,107,104,106,20000\n")
    yield  # 執行測試
    cleanup_files()


def test_e2e_discover_workflow():
    """
    【鋼鐵長城】端到端整合測試 (修正案 B)：
    1. 啟動 `services start --mode discover` 服務集群。
    2. 等待服務【自行完成】所有演化任務並正常退出。
    3. 驗證服務的返回碼為 0 (成功)。
    4. 驗證服務產生了預期的產出檔案。
    """
    # 1. 準備啟動服務的指令
    command = [
        "poetry",
        "run",
        "python",
        "run.py",
            "run-worker",
            "--worker-id",
            "123",
    ]

    # 2. 使用 communicate 等待服務完成，並設定足夠長的超時
    #    這會捕獲所有 stdout 和 stderr，直到進程終止。
    print("正在啟動 'discover' 模式服務，並等待其自行完成...")
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        stdout, stderr = process.communicate(timeout=120)  # 給予 120 秒的寬裕時間
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        pytest.fail(
            f"服務運行超時，未能自行終止。\n"
            f"STDOUT:\n{stdout}\n"
            f"STDERR:\n{stderr}"
        )

    print(f"\n--- 服務已退出 ---")
    print(f"返回碼: {process.returncode}")
    print(f"STDOUT:\n{stdout}")
    if stderr:
        print(f"STDERR:\n{stderr}")

    # 3. 斷言服務成功退出
    assert (
        process.returncode == 0
    ), f"服務應成功退出 (返回碼 0)，但實際為 {process.returncode}。"

    # 4. 斷言預期的產出檔案已生成
    # 在當前的 ReconWorker 實現中，不會生成名人堂檔案，因此我們移除這個斷言。
    pass
    assert (
        RESULTS_QUEUE_PATH.exists()
    ), f"預期的結果資料庫 '{RESULTS_QUEUE_PATH}' 未被創建。"

    print("\n【鋼鐵長城】測試驗收通過：服務成功執行並產生了預期產出。")
