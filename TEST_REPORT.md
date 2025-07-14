# **【普羅米修斯之火】系統測試作戰報告**
> 報告生成時間：2025-07-14 04:17:41

## **一、 戰況總覽**
> **結論：<font color='red'>任務失敗 (FAILURE)</font>** - 發現關鍵性錯誤。系統存在風險，需立即審查。
| 指標 (Metric) | 數量 (Count) |
|:---|:---:|
| ✅ **測試通過 (Passed)** | 73 |
| ❌ **測試失敗 (Failed)** | 5 |
| 🔥 **執行錯誤 (Errors)** | 3 |
| 🚧 **測試跳過 (Skipped)** | 17 |
| ⏱️ **總執行時間 (Time)** | 29.72 秒 |
| 🧮 **總執行數量 (Total)** | 98 |

## **二、 失敗與錯誤詳情**

### 1. Failure: TypeError: EvolutionChamber.__init__() missing 1 required positional argument: 'db_connection'
- **測試位置:** `tests.integration.test_evolution_pipeline.test_evolution_logic_in_loop`
- **詳細堆疊追蹤:**
```
app_context = AppContext(log_manager=<src.core.logger.LogManager object at 0x7f10e54a60f0>, duckdb_connection=<duckdb.duckdb.DuckDBPyConnection object at 0x7f10e524dff0>)

    def test_evolution_logic_in_loop(app_context: AppContext):
        """
        驗證演化核心邏輯的「完全內循環」測試。
        此測試不依賴任何背景執行緒或真實的佇列等待。
        """
        log_manager = app_context.log_manager
>       chamber = EvolutionChamber(queue=app_context.queue, log_manager=log_manager)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: EvolutionChamber.__init__() missing 1 required positional argument: 'db_connection'

tests/integration/test_evolution_pipeline.py:18: TypeError
```

### 2. Failure: duckdb.duckdb.ConnectionException: Connection Error: Can't open a connection to same database file with a different configuration than existing connections
- **測試位置:** `tests.integration.test_full_pipeline.test_end_to_end_pipeline`
- **詳細堆疊追蹤:**
```
app_context = AppContext(log_manager=<src.core.logger.LogManager object at 0x7f10e54a84a0>, duckdb_connection=<duckdb.duckdb.DuckDBPyConnection object at 0x7f10e4d6a430>)

    def test_end_to_end_pipeline(app_context: AppContext):
        """
        執行端到端管線測試，現在使用由工廠提供的乾淨上下文。
        """
        from src.apps.tools.task_adder_app import add_tasks

        log_manager = app_context.log_manager
        stop_event = threading.Event()

        # 1. 啟動背景工作者
        worker = threading.Thread(
            target=worker_thread_target,
            args=(app_context, stop_event),
            daemon=True
        )
        worker.start()
        log_manager.log("INFO", "[Main] 工作者執行緒已啟動。")

        # 2. 派發任務
        add_tasks(app_context)
        log_manager.log("INFO", f"[Main] 已新增 {NUM_TASKS_TO_ADD} 個任務。")

        # 3. 等待任務處理
        time.sleep(5)

        # 4. 停止工作者
        stop_event.set()
        worker.join(timeout=2)
        assert not worker.is_alive(), "工作者執行緒未能正常停止！"
        log_manager.log("SUCCESS", "[Main] 工作者執行緒已停止。")

        # 5. 驗證資料庫
>       conn = duckdb.connect(RESULTS_DB_PATH, read_only=True)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       duckdb.duckdb.ConnectionException: Connection Error: Can't open a connection to same database file with a different configuration than existing connections

tests/integration/test_full_pipeline.py:75: ConnectionException
```

### 3. Failure: AttributeError: 'SQLiteQueue' object has no attribute 'close'
- **測試位置:** `tests.unit.core.test_queue.test_initialization`
- **詳細堆疊追蹤:**
```
temp_db_path = PosixPath('/tmp/pytest-of-swebot/pytest-0/test_initialization0/test_queue.db')

    def test_initialization(temp_db_path: Path):
        """測試佇列初始化時是否會創建資料庫檔案。"""
        assert not temp_db_path.exists()
        q = SQLiteQueue(temp_db_path)
        assert temp_db_path.exists()
>       q.close()
        ^^^^^^^
E       AttributeError: 'SQLiteQueue' object has no attribute 'close'

tests/unit/core/test_queue.py:26: AttributeError
```

### 4. Error: failed on teardown with "AttributeError: 'SQLiteQueue' object has no attribute 'close'"
- **測試位置:** `tests.unit.core.test_queue.test_put_and_qsize`
- **詳細堆疊追蹤:**
```
temp_db_path = PosixPath('/tmp/pytest-of-swebot/pytest-0/test_put_and_qsize0/test_queue.db')

    @pytest.fixture
    def queue(temp_db_path: Path) -> SQLiteQueue:
        """提供一個 SQLiteQueue 的實例。"""
        q = SQLiteQueue(temp_db_path)
        yield q
>       q.close()
        ^^^^^^^
E       AttributeError: 'SQLiteQueue' object has no attribute 'close'

tests/unit/core/test_queue.py:19: AttributeError
```

### 5. Failure: KeyError: 'payload'
- **測試位置:** `tests.unit.core.test_queue.test_get_and_task_done`
- **詳細堆疊追蹤:**
```
queue = <src.core.queue.sqlite_queue.SQLiteQueue object at 0x7f10e4d494f0>

    def test_get_and_task_done(queue: SQLiteQueue):
        """測試取得任務、處理、並標記完成的完整流程。"""
        task_payload = {"url": "http://example.com"}
        queue.put(task_payload)

        # 待處理任務數為 1
        assert queue.qsize() == 1

        # 取得任務
        retrieved_task = queue.get()
        assert retrieved_task is not None
>       task_data = json.loads(retrieved_task['payload'])
                               ^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'payload'

tests/unit/core/test_queue.py:47: KeyError
```

### 6. Error: failed on teardown with "AttributeError: 'SQLiteQueue' object has no attribute 'close'"
- **測試位置:** `tests.unit.core.test_queue.test_get_and_task_done`
- **詳細堆疊追蹤:**
```
temp_db_path = PosixPath('/tmp/pytest-of-swebot/pytest-0/test_get_and_task_done0/test_queue.db')

    @pytest.fixture
    def queue(temp_db_path: Path) -> SQLiteQueue:
        """提供一個 SQLiteQueue 的實例。"""
        q = SQLiteQueue(temp_db_path)
        yield q
>       q.close()
        ^^^^^^^
E       AttributeError: 'SQLiteQueue' object has no attribute 'close'

tests/unit/core/test_queue.py:19: AttributeError
```

### 7. Error: failed on teardown with "AttributeError: 'SQLiteQueue' object has no attribute 'close'"
- **測試位置:** `tests.unit.core.test_queue.test_get_from_empty_queue`
- **詳細堆疊追蹤:**
```
temp_db_path = PosixPath('/tmp/pytest-of-swebot/pytest-0/test_get_from_empty_queue0/test_queue.db')

    @pytest.fixture
    def queue(temp_db_path: Path) -> SQLiteQueue:
        """提供一個 SQLiteQueue 的實例。"""
        q = SQLiteQueue(temp_db_path)
        yield q
>       q.close()
        ^^^^^^^
E       AttributeError: 'SQLiteQueue' object has no attribute 'close'

tests/unit/core/test_queue.py:19: AttributeError
```

### 8. Failure: AttributeError: 'SQLiteQueue' object has no attribute 'close'
- **測試位置:** `tests.unit.core.test_queue.test_persistence`
- **詳細堆疊追蹤:**
```
temp_db_path = PosixPath('/tmp/pytest-of-swebot/pytest-0/test_persistence0/test_queue.db')

    def test_persistence(temp_db_path: Path):
        """測試任務是否能被持久化儲存。"""
        # 第一個佇列實例，放入任務
        queue1 = SQLiteQueue(temp_db_path)
        queue1.put({"persistent": True})
        assert queue1.qsize() == 1
>       queue1.close()
        ^^^^^^^^^^^^
E       AttributeError: 'SQLiteQueue' object has no attribute 'close'

tests/unit/core/test_queue.py:71: AttributeError
```