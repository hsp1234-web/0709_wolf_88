import pytest
import json
from pathlib import Path
from src.core.queue.sqlite_queue import SQLiteQueue

@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """提供一個臨時的資料庫檔案路徑。"""
    return tmp_path / "test_queue.db"

@pytest.fixture
def queue(temp_db_path: Path) -> SQLiteQueue:
    """提供一個 SQLiteQueue 的實例。"""
    q = SQLiteQueue(temp_db_path)
    yield q
    # No need to close, as we are using a shared connection

def test_initialization(temp_db_path: Path):
    """測試佇列初始化時是否會創建資料庫檔案。"""
    assert not temp_db_path.exists()
    q = SQLiteQueue(temp_db_path)
    assert temp_db_path.exists()

def test_put_and_qsize(queue: SQLiteQueue):
    """測試放入任務後，佇列的大小是否正確。"""
    assert queue.qsize() == 0
    queue.put({"test": "task"})
    assert queue.qsize() == 1

def test_get_and_task_done(queue: SQLiteQueue):
    """測試取得任務、處理、並標記完成的完整流程。"""
    task_payload = {"url": "http://example.com"}
    queue.put(task_payload)

    # 待處理任務數為 1
    assert queue.qsize() == 1

    # 取得任務
    retrieved_task = queue.get()
    assert retrieved_task is not None
    assert retrieved_task["url"] == "http://example.com"

    # 標記任務完成
    queue.task_done(retrieved_task['_task_id'])

    # 佇列應為空
    assert queue.qsize() == 0

def test_get_from_empty_queue(queue: SQLiteQueue):
    """測試從空佇列中取得任務，應返回 None。"""
    assert queue.get() is None

def test_persistence(temp_db_path: Path):
    """測試任務是否能被持久化儲存。"""
    # 第一個佇列實例，放入任務
    queue1 = SQLiteQueue(temp_db_path)
    queue1.put({"persistent": True})
    assert queue1.qsize() == 1

    # 第二個佇列實例，讀取同一個資料庫
    queue2 = SQLiteQueue(temp_db_path)
    assert queue2.qsize() == 1
    task = queue2.get()
    assert task is not None
    assert task["persistent"] is True
