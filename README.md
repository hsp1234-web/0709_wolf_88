# **【普羅米修斯之火】金融數據與分析框架 - 開發者手冊 v1.3.0 (鳳凰版)**

## **一、 專案概覽與目的**

【普羅米修斯之火】是一個專為進階量化研究與金融市場分析而設計的 Python 框架。本專案旨在提供一個從多樣化數據源獲取金融數據、進行複雜指標計算、回測交易策略、並將結果視覺化的完整解決方案。

**最新更新（作戰計畫 080：「鳳凰計畫」非同步重構）：**
*   **架構升級**: 徹底廢棄了基於 `threading` 的多線程同步模型，以 `asyncio` 為核心，將整個系統重構為一個非同步事件驅動架構。
*   **核心組件**:
    *   引入 `AsyncEventBus` (`core/queue/async_event_bus.py`) 作為系統內非阻塞通訊的中樞。
    *   `ResultsSaver`、`AppContext`、`BacktestingService`、`EvolutionChamber` 及所有相關應用程式 (`apps`) 全面 `async` 化。
*   **穩定性**: 根除了所有因線程競爭、資源鎖定、生命週期管理混亂導致的錯誤，實現了系統的終極穩定。

## **二、 技術棧 (Technology Stack)**

*   **核心程式語言:** Python (>=3.12, <3.14)
*   **依賴管理:** Poetry (v1.8.2 或相容版本)
*   **非同步框架:**
    *   `asyncio` (內建)
    *   `aiosqlite` (`^0.21.0`)
*   **命令列介面**: Typer (`^0.16.0`)
*   **數據處理:**
    *   Pandas (`^2.3.1`)
    *   NumPy (`<2.0`)
    *   Pandas-TA (`0.3.14b0`)
*   **遺傳演算法:** DEAP (`^1.4.3`)
*   **API 客戶端與網路請求:**
    *   Requests (`^2.32.4`)
    *   Requests-Cache (`^1.2.1`)
    *   FredAPI (`^0.5.2`)
    *   YFinance (`^0.2.40`)
*   **資料庫**:
    *   SQLite3 (內建)
*   **設定檔管理:**
    *   PyYAML (`^6.0.2`)
*   **視覺化**:
    *   Plotly (`^5.24.1`)
    *   VectorBT (`^0.28.0`)
*   **測試與品質保證:**
    *   Pytest (`^8.4.1`)
    *   Pytest-Mock (`^3.14.1`)
    *   `pytest-asyncio` (`^1.0.0`)
    *   Ruff (用於程式碼檢查與格式化)

## **三、 完整檔案目錄結構 (v1.2.0)**

以下為專案目前的完整檔案目錄結構 (已移除 `__pycache__` 和 `.pyc` 檔案)。

> **[文件化說明]**
> 關於下表中每一個檔案的詳細功能、職責與執行邏輯，請參閱 **[`PROJECT_FILES_GLOSSARY.md`](./PROJECT_FILES_GLOSSARY.md)** 檔案。

```
.
├── PROJECT_FILES_GLOSSARY.md
├── README.md
├── TEST_REPORT.md
├── config.yml
├── mypy.ini
├── pipelines
│   ├── __init__.py
│   ├── p0_downloader
│   │   └── run.py
│   ├── p1_explorer
│   │   ├── __init__.py
│   │   └── run.py
│   ├── p2_elt_pipeline
│   │   └── run_elt.py
│   └── p3_backfill_hourly_data
│       └── run.py
├── poetry.lock
├── pyproject.toml
├── pytest.ini
├── run.py
├── src
│   ├── apps
│   │   ├── __init__.py
│   │   ├── analysis_pipeline
│   │   │   └── run.py
│   │   ├── backtest_worker_app.py
│   │   ├── backtesting_engine
│   │   │   ├── __init__.py
│   │   │   ├── engine.py
│   │   │   └── run.py
│   │   ├── dashboard
│   │   │   └── dashboard.html
│   │   ├── db_manager
│   │   │   └── setup_database.py
│   │   ├── evolution_app.py
│   │   ├── factor_engine
│   │   │   ├── engine.py
│   │   │   ├── run_factor_etl.py
│   │   │   └── sma_crossover_factor.py
│   │   ├── optimizer_app.py
│   │   ├── pipeline_metadata_manager
│   │   │   ├── __init__.py
│   │   │   └── manager.py
│   │   ├── portfolio_optimizer
│   │   │   ├── __init__.py
│   │   │   └── main.py
│   │   ├── py.typed
│   │   ├── query_gateway.py
│   │   ├── report_generator
│   │   │   ├── __init__.py
│   │   │   ├── generator.py
│   │   │   └── run.py
│   │   ├── tools
│   │   │   ├── clear_results.py
│   │   │   ├── report_generator_app.py
│   │   │   ├── show_results.py
│   │   │   └── task_adder_app.py
│   │   └── visualization
│   │       └── plot_sma_crossover.py
│   └── core
│       ├── __init__.py
│       ├── analysis
│       │   ├── data_engine.py
│       │   └── stress_index.py
│       ├── analyzers
│       │   ├── __init__.py
│       │   └── base_analyzer.py
│       ├── clients
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── finmind.py
│       │   ├── fmp.py
│       │   ├── fred.py
│       │   ├── nyfed.py
│       │   ├── taifex_db.py
│       │   └── yfinance.py
│       ├── config.py
│       ├── constants.py
│       ├── context.py
│       ├── db
│       │   ├── __init__.py
│       │   ├── db_manager.py
│       │   ├── evolution_logger.py
│       │   ├── results_saver.py
│       │   └── transactional_writer.py
│       ├── engines
│       │   ├── __init__.py
│       │   └── robust_acquisition_engine.py
│       ├── logger.py
│       ├── pipelines
│       │   ├── __init__.py
│       │   ├── base_step.py
│       │   ├── pipeline.py
│       │   └── steps
│       │       ├── __init__.py
│       │       ├── aggregators.py
│       │       ├── financial_steps.py
│       │       └── loaders.py
│       ├── py.typed
│       ├── queue
│       │   ├── __init__.py
│       │   ├── async_event_bus.py
│       │   ├── base.py
│       │   └── sqlite_queue.py
│       ├── services
│       │   ├── __init__.py
│       │   ├── backtesting_service.py
│       │   ├── evolution_chamber.py
│       │   └── optimizer_service.py
│       └── utils
│           ├── __init__.py
│           ├── caching.py
│           └── path_utils.py
└── tests
    ├── __pycache__
    │   └── conftest.cpython-312-pytest-8.4.1.pyc
    ├── conftest.py
    ├── fixtures
    │   ├── corrupted.zip
    │   ├── no_data_response.html
    │   └── sample_daily_ohlc_20250711.zip
    ├── ignition_test.py
    ├── integration
    │   ├── __pycache__
    │   │   └── test_final_acceptance.cpython-312-pytest-8.4.1.pyc
    │   ├── analysis
    │   │   └── test_data_engine_cache.py
    │   ├── apps
    │   │   └── test_analysis_pipeline.py
    │   ├── pipelines
    │   │   ├── test_data_pipeline.py
    │   │   └── test_example_flow.py
    │   ├── test_evolution_pipeline.py
    │   ├── test_final_acceptance.py
    │   ├── test_full_pipeline.py
    │   ├── test_genome_backtester.py
    │   └── test_real_backtesting_service.py
    ├── test_p0_downloader.py
    ├── test_p1_explorer.py
    ├── test_p2_elt_pipeline.py
    └── unit
        ├── analysis
        │   └── test_data_engine.py
        ├── core
        │   ├── analyzers
        │   │   └── test_base_analyzer.py
        │   ├── clients
        │   │   ├── test_finmind.py
        │   │   ├── test_fmp.py
        │   │   ├── test_fred.py
        │   │   ├── test_nyfed.py
        │   │   └── test_yfinance.py
        │   ├── test_genome_evolution_chamber.py
        │   └── test_queue.py
        └── test_feature_analyzer.py
```

## **四、 環境設定與執行**

本專案使用 [Poetry](https://python-poetry.org/) 進行依賴管理。

1.  **安裝 Poetry** (如果尚未安裝)。
2.  **克隆專案**。
3.  **配置 Poetry 虛擬環境** (推薦 `poetry config virtualenvs.in-project true`)。
4.  **安裝依賴**: `poetry install`。
5.  **激活虛擬環境**: `poetry shell` (或使用 `poetry run <command>`)。

## **五、 主要功能執行與測試 (鳳凰版)**

### **5.1 主要工作流程**

本專案的核心是透過 `test_final_acceptance.py` 進行端到端的整合測試來驅動的。此測試模擬了完整的策略演化生命週期。

1.  **啟動命令**:
    ```bash
    poetry run pytest -v tests/integration/test_final_acceptance.py
    ```
2.  **測試啟動**: `pytest-asyncio` 插件識別 `@pytest.mark.asyncio` 標記，並為測試提供一個 `asyncio` 事件循環。
3.  **上下文初始化**:
    *   測試函數 `test_full_async_evolution_flow` 的第一步是 `async with AppContext(...) as context:`。
    *   這會非同步地進入 `AppContext` 的 `__aenter__` 方法，該方法會：
        *   建立一個 `AsyncEventBus` 實例，其中包含兩個 `asyncio.Queue`：`task_queue` 和 `result_queue`。
        *   非同步地連接到一個記憶體中的 SQLite 資料庫 (`aiosqlite.connect(":memory:")`)。
        *   初始化 `ResultsSaver`，並將非同步資料庫連接傳遞給它。
        *   建立 `backtest_results` 資料表。
        *   將初始化完成的 `context` 物件返回。
4.  **並發任務創建**:
    *   **背景工作者**: `asyncio.create_task(backtest_worker_app.main(context))` 創建一個背景任務。此任務立即開始在事件循環中運行，執行 `backtest_worker_app.main` 的邏輯：一個 `while True` 循環，該循環 `await context.queue.get()`，非同步地等待 `task_queue` 中出現新任務。
    *   **主流程 (演化室)**: 測試的主協程繼續前進，`await evolution_app.main(context)`。
5.  **非同步協作與事件驅動**:
    *   `evolution_app` 調用 `EvolutionChamber.evolve()`。
    *   `EvolutionChamber` 生成一批策略（個體），並循環呼叫 `await self.queue.put(task)`，將這些策略作為任務放入 `task_queue`。
    *   每次 `put` 操作都會喚醒正在 `await get()` 的背景工作者任務。
    *   背景工作者從 `task_queue` 中獲取任務，調用 `BacktestingService.run_backtest()` 執行 CPU 密集的計算（這部分是同步的，但在 `async` 函數中運行是安全的）。
    *   回測完成後，工作者 `await context.queue.put_result(result)` 將結果放入 `result_queue`，然後 `context.queue.task_done()` 通知 `task_queue` 該任務已完成。
    *   與此同時，`EvolutionChamber` 在提交完一批任務後，會 `await self.queue.join()`。這會非同步地暫停 `EvolutionChamber` 的執行，直到背景工作者對 `task_queue` 中所有被 `put` 的項目都調用了 `task_done()`。
    *   一旦 `join()` 返回（表示所有回測都已完成），`EvolutionChamber` 就會從 `result_queue` 中獲取所有結果，並更新其策略族群的適應度。
    *   這個「提交-等待-收集」的循環會持續進行，直到所有演化世代完成。
6.  **優雅關閉 (Graceful Shutdown)**:
    *   演化流程結束後，測試主協程 `await context.queue.put(None)`。這個 `None` 是一個特殊的信號，被稱為「毒丸 (Poison Pill)」。
    *   背景工作者的 `while` 循環在 `get()` 到 `None` 後，會 `break` 循環，從而結束其無限循環。
    *   測試主協程 `await worker_task`，確保工作者任務已完全終止。
7.  **最終驗證與清理**:
    *   測試斷言 `context.results_saver.count_results()` 的計數是否符合預期。
    *   `async with` 區塊結束，自動調用 `AppContext` 的 `__aexit__` 方法，該方法會優雅地關閉資料庫連接。

這個流程完美地展示了 `asyncio` 如何在單一執行緒中，透過任務之間的協作與切換，高效地管理 I/O 操作（如佇列和資料庫訪問）與 CPU 密集型計算，而無需複雜的多線程鎖。

### **5.2 測試**
*   **運行所有測試**:
    ```bash
    poetry run pytest
    ```

## **六、 版本歷史與變更日誌**

### **v1.2.0 (鳳凰計畫) - 作戰計畫 080**
*   **【重大架構升級】非同步事件驅動重構**
    *   **背景**: 舊有的多線程模型存在線程競爭、死鎖以及複雜的生命週期管理問題，導致系統不穩定且難以擴展。
    *   **實作細節**:
        *   **廢棄 Threading**: 完全移除了基於 `threading` 的並發模型。
        *   **擁抱 Asyncio**: 以 `asyncio` 為核心，將 `EvolutionChamber` (生產者) 和 `BacktestingService` (消費者) 的互動模式改為非同步事件驅動。
        *   **AsyncEventBus**: 實現了一個基於 `asyncio.Queue` 的 `AsyncEventBus`，作為系統內部高效、非阻塞的通訊中樞。
        *   **非同步 I/O**: `ResultsSaver` 使用 `aiosqlite` 進行非同步資料庫操作，`AppContext` 也被改造成非同步上下文管理器 (`async with`)，確保資源的非阻塞獲取與釋放。
        *   **非同步測試**: 引入 `pytest-asyncio`，並重寫了 `test_final_acceptance.py`，使其能夠在單一事件循環中協調並測試整個非同步流程。
    *   **影響**:
        *   **根本性穩定**: 徹底根除了競爭條件與死鎖問題。
        *   **性能提升**: I/O 密集型操作不再阻塞主事件循環，提升了系統效率。
        *   **簡化邏輯**: 非同步模型使得並發控制邏輯更清晰、更易於維護。

*   **【除錯實錄】鳳凰計畫：從錯誤中浴火重生**
    *   **挑戰一：`ModuleNotFoundError: No module named 'src.core.queue.in_memory_queue'`**
        *   **根本原因**: 在將 `in_memory_queue.py` 重命名為 `async_event_bus.py` 後，`tests/conftest.py` 和 `src/core/context.py` 中仍然存在對舊檔案的引用。
        *   **解決方案**: 系統性地檢查並更新了所有相關的 `import` 語句，確保整個專案都指向新的 `AsyncEventBus`。
    *   **挑戰二：`TypeError: initRepeat() missing 1 required positional argument: 'n'`**
        *   **根本原因**: DEAP 函式庫的 `tools.initRepeat` 函數在其註冊到 `toolbox` 時的語法有其特殊性。直接註冊 `initRepeat` 會導致參數傳遞問題。
        *   **解決方案**: 調整了 DEAP `toolbox` 的註冊邏輯。首先將 `create_rsi_genome` 函數直接註冊為 `individual`，然後再將 `tools.initRepeat` 註冊為 `population`，並指定它使用 `toolbox.individual` 作為生成器。同時，確保 `create_rsi_genome` 返回的是 DEAP 可識別的 `creator.Individual` 實例，而不僅僅是字典。
    *   **挑戰三：`ValueError: task_done() called too many times`**
        *   **根本原因**: 生產者 (`EvolutionChamber`) 和消費者 (`BacktestingWorker`) 都在任務完成後調用了 `task_queue.task_done()`，導致對同一個任務的完成信號被重複發送。
        *   **解決方案**: 重新定義了職責邊界。規定只有消費者（即 `BacktestingWorker`）在完成一個工作單元後，才有責任調用 `task_done()`。生產者則透過 `task_queue.join()` 來等待所有任務完成的信號，從而避免了重複調用。
    *   **挑戰四：`ValueError: empty range in randrange(1, 1)`**
        *   **根本原因**: DEAP 的 `tools.cxTwoPoint` 交叉算子要求被操作的序列長度至少為 2。而我們的基因組中，`params` 字典只有一個 `window` 鍵，長度為 1，導致無法執行兩點交叉。
        *   **解決方案**: 修改了 `mate_genomes` 函數。當基因序列不滿足 `cxTwoPoint` 的長度要求時，採取了更簡單直接的交叉策略——直接交換兩個個體的整個 `params` 字典。這保證了交叉操作的穩健性。

### **v1.0 (磐石協議) - 作戰計畫 042**
*   **【重大架構升級】引入「作戰上下文」與「企業級任務佇列」**
    *   **實作細節**:
        *   **作戰上下文 (`AppContext`)**: 建立了一個中央容器，統一管理所有共享服務的生命週期。
        *   **交易型佇列 (`SQLiteQueue`)**: 實現了一個基於 SQLite 事務的、絕對穩健的任務佇列。
    *   **影響**:
        *   **多進程安全**: 確保了在複雜的多進程操作中，數據不會損壞，任務不會遺失。
        *   **代碼解耦**: 應用程式邏輯與基礎設施服務完全分離，提高了可維護性。

### **v0.6.0 (精準指示器) - 作戰計畫 038**
*   **【重大架構升級】實作統一 CLI 入口與 v82.0 精準指示器日誌系統**
    *   **實作細節**:
        *   **引入 `Typer`**: 在根目錄下建立 `run.py`，將其打造為一個功能強大且易於擴展的命令列介面 (CLI) 應用。
        *   **建立 `LogManager`**: 設計並實作了基於 SQLite 的結構化日誌系統，並在任務結束時自動歸檔。
    *   **影響**:
        *   **開發流程簡化**: 統一了整個專案的執行入口和日誌記錄方式。
        *   **可追溯性增強**: 所有的操作都有了集中化、永久性的日誌記錄。

## **七、 開發者指引**
*   遵循 PEP 8 程式碼風格。
*   所有程式碼註解、日誌訊息和終端機輸出均使用**繁體中文**。
*   嚴禁在程式碼中硬編碼任何 API 金鑰或敏感資訊。所有配置應透過 `config.yml` 管理。
*   在提交程式碼前，請務必運行 `poetry run pytest` 確保沒有引入新的迴歸問題。

歡迎開發者們一同參與【普羅米修斯之火】的建設！
