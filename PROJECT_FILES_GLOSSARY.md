# 專案檔案詞彙表 (v2.0 磐石版)

本文件旨在提供一個完整、詳細的專案檔案地圖，說明每一個檔案與目錄在【普羅米修斯之火】框架中的功能與核心職責。

## **一、 技術棧 (Technology Stack)**

本專案使用 [Poetry](https://python-poetry.org/) (v1.8.2+) 進行依賴管理。

*   **核心與框架:**
    *   `python`: `>=3.12,<3.14`
    *   `typer`: `^0.12.3` (命令列介面)
    *   `fastapi`: `^0.111.0` (Web API 框架)
*   **數據處理與分析:**
    *   `pandas`: `^2.2.2`
    *   `numpy`: `<2.0`
    *   `pandas-ta`: `0.3.14b0`
    *   `pandas-ta-openbb`: `^0.4.22`
    *   `vectorbt`: `^0.28.0`
*   **遺傳演算法:**
    *   `deap`: `^1.4.1`
*   **資料庫與 I/O:**
    *   `duckdb`: `^1.0.0`
    *   `aiosqlite`: `^0.21.0` (非同步 SQLite 驅動)
    *   `pyyaml`: `^6.0.1` (YAML 設定檔)
    *   `openpyxl`: `^3.1.5` (Excel 讀寫)
*   **網路與 API 客戶端:**
    *   `requests`: `^2.32.3`
    *   `requests-cache`: `^1.2.1`
    *   `yfinance`: `0.2.40`
    *   `fredapi`: `^0.5.2`
*   **視覺化與報告:**
    *   `plotly`: `^5.22.0`
    *   `rich`: `^14.0.0` (美化終端機輸出)
*   **測試與品質保證:**
    *   `pytest`: `^8.2.2`
    *   `pytest-mock`: `^3.14.0`
    *   `pytest-asyncio`: `^1.0.0`
    *   `ruff`: `^0.4.8` (Linter & Formatter)

## **二、 檔案目錄結構 (v2.0)**

```
.
├── PROJECT_FILES_GLOSSARY.md
├── README.md
├── TEST_REPORT.md
├── config.yml
├── create_dummy_data.py
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
├── run_local_services.py
├── src
│   ├── apps
│   │   ├── __init__.py
│   │   ├── ai_analyst_app.py
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
│   │   ├── results_projector_app.py
│   │   ├── run_evolution.py
│   │   ├── run_rebuild_models.py
│   │   ├── tools
│   │   │   ├── clear_results.py
│   │   │   ├── report_generator_app.py
│   │   │   ├── show_results.py
│   │   │   └── task_adder_app.py
│   │   ├── validation_app.py
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
│       ├── events
│       │   ├── event_store.py
│       │   └── event_types.py
│       ├── logger.py
│       ├── logging
│       │   └── log_manager.py
│       ├── monitoring
│       │   └── dashboard.py
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
│       │   ├── base.py
│       │   └── sqlite_queue.py
│       ├── services
│       │   ├── __init__.py
│       │   ├── backtesting_service.py
│       │   ├── checkpoint_manager.py
│       │   ├── evolution_chamber.py
│       │   └── optimizer_service.py
│       └── utils
│           ├── __init__.py
│           ├── caching.py
│           ├── data_loader.py
│           └── path_utils.py
└── tests
    ├── conftest.py
    ├── fixtures
    │   ├── corrupted.zip
    │   ├── no_data_response.html
    │   └── sample_daily_ohlc_20250711.zip
    ├── ignition_test.py
    ├── integration
    │   ├── analysis
    │   │   └── test_data_engine_cache.py
    │   ├── apps
    │   │   └── test_analysis_pipeline.py
    │   └── pipelines
    │       ├── test_data_pipeline.py
    │       └── test_example_flow.py
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
        │   └── test_queue.py
        └── test_feature_analyzer.py
```

## **三、 根目錄 (Root Directory)**

-   `README.md`: **[文檔]** 開發者手冊，提供專案的整體介紹、技術棧、環境設定、主要功能用法、版本歷史與開發者指引。
-   `PROJECT_FILES_GLOSSARY.md`: **[文檔]** (本檔案) 提供比 `README.md` 更詳細的、針對每一個檔案和目錄的功能說明。
-   `run.py`: **[核心入口]** 專案的統一命令列介面 (CLI)，使用 `Typer` 建立。是執行所有主要任務（如演化、回測、測試、儀表板）的入口點。
-   `run_local_services.py`: **[輔助腳本]** 用於在本機同時啟動多個服務（如演化引擎和回測工作者）的腳本，模擬生產環境的運行方式。
-   `config.yml`: **[設定檔]** 全局設定檔。
-   `pyproject.toml`: **[依賴管理]** `Poetry` 的專案設定檔。
-   `poetry.lock`: **[依賴管理]** `Poetry` 的鎖定檔案。
-   `pytest.ini`, `mypy.ini`: **[工具設定]** `Pytest` 和 `Mypy` 的設定檔。
-   `create_dummy_data.py`: **[輔助腳本]** 用於生成測試或開發所需的虛擬數據。

## **四、 `src/apps/` - 應用程式層**

此目錄包含所有可執行的應用邏輯。

-   `evolution_app.py`: **[核心應用-同步]** 演化流程的主函數。負責初始化並啟動 `EvolutionChamber`，驅動策略演化。它使用 `SQLiteQueue` 來分派回測任務。
-   `backtest_worker_app.py`: **[核心應用-同步]** 背景回測工作者的主函數。它從 `SQLiteQueue` 中獲取任務，使用 `BacktestingService` 執行回測，並將結果放回佇列。
-   `query_gateway.py`: **[核心應用-非同步]** 負責啟動 FastAPI Web 服務，為儀表板提供數據查詢的後端 API。
-   `tools/`: **[工具應用]** 包含一系列用於開發和維護的命令列工具，如清除結果、顯示結果、手動新增任務等。

## **五、 `src/core/` - 核心服務與商業邏輯層**

此目錄是專案的心臟，包含了所有共享的核心商業邏輯、服務與工具。

-   `context.py`: **[核心服務-非同步]** `AppContext` 的實作。一個非同步上下文管理器 (`async with`)，負責初始化並提供所有共享的 **非同步** 服務，如 `aiosqlite` 資料庫連線、`PersistentEventStream` 和 `ResultsSaver`。**注意：此元件目前主要由 `query_gateway.py` 使用，尚未整合至同步的演化流程中。**
-   `services/`:
    -   `evolution_chamber.py`: **[核心服務-同步]** 策略演化室。封裝了 `DEAP` 遺傳演算法的邏輯，負責管理策略的生成、交叉和突變。
    -   `backtesting_service.py`: **[核心服務-同步]** 回測服務。被 `backtest_worker_app` 使用，負責執行實際的回測計算。
-   `queue/`:
    -   `sqlite_queue.py`: **[核心通訊-同步]** 一個基於 `sqlite3` 的、穩健的 **同步** 任務佇列。是 `evolution_app` 和 `backtest_worker_app` 之間進行任務分派和結果回收的主要通訊機制。
-   `events/`:
    -   `event_store.py`: **[核心通訊-非同步]** 一個基於 `aiosqlite` 的持久化 **非同步** 事件流。它實現了事件溯源模式，是系統中正在開發或用於特定非同步場景的元件。
-   `db/`:
    -   `results_saver.py`: **[數據持久化-非同步]** 結果儲存器。使用 `aiosqlite` 以非同步方式將回測結果儲存到資料庫。
-   `logger.py`: **[核心服務]** `LogManager` 的實作，提供結構化的日誌記錄功能。

## **六、 `tests/` - 自動化測試**

此目錄包含所有自動化測試，確保程式碼的品質與穩定性。

-   `conftest.py`: **[測試設定]** `Pytest` 的本地插件檔案，用於定義所有測試共享的 `fixtures`（例如，初始化的 `AppContext`、暫存的資料庫等），簡化測試的編寫。
-   `ignition_test.py`: **[啟動測試]** 一個非常基礎的測試，用於確保 `Pytest` 本身可以正常啟動並發現測試，可視為專案測試環境的「點火測試」。
-   `fixtures/`: **[測試數據]** 存放所有測試案例所需的靜態數據檔案。
    -   `*.zip`, `*.html`: 模擬從外部 API 下載的數據，用於測試數據解析和處理的各種情況（如正常、損壞、無數據等）。
-   `unit/`: **[單元測試]**
    -   專注於測試單一函式、類別或模組的功能是否正確，不涉及外部依賴（如資料庫、網路）。
    -   **`core/`**: 包含對核心服務的單元測試，例如測試 `SQLiteQueue` 的 `put` 和 `get` 是否正常。
    -   **`analysis/`**: 包含對分析相關功能的單元測試。
-   `integration/`: **[整合測試]**
    -   專注於測試多個模組協同工作時是否正確，可能會涉及資料庫或檔案系統等真實的外部依賴。
    -   **`pipelines/`**: 測試數據處理管線（`p0`, `p1`, `p2`）的端到端流程是否順暢。
    -   **`apps/`**: 測試應用程式層的整合，例如，測試 `evolution_app` 是否能成功地將任務放入佇列，以及 `backtest_worker_app` 是否能正確地處理這些任務。
-   `test_p*.py`: 直接放在 `tests/` 目錄下的測試檔案，通常是針對特定 `pipeline` 的高階整合測試。
