# 專案檔案詞彙表 (v0.7.0)

本文件詳細說明專案中每個檔案的功能與用途。

## 檔案結構總覽

```
.
├── README.md
├── PROJECT_FILES_GLOSSARY.md
├── config.yml
├── mypy.ini
├── poetry.lock
├── pyproject.toml
├── pytest.ini
├── run.py
├── apps
│   ├── __init__.py
│   ├── analysis_pipeline
│   ├── backtest_worker_app.py
│   ├── backtesting_engine
│   ├── dashboard
│   ├── db_manager
│   ├── factor_engine
│   ├── pipeline_metadata_manager
│   ├── portfolio_optimizer
│   ├── query_gateway.py
│   ├── report_generator
│   ├── tools
│   └── visualization
├── core
│   ├── __init__.py
│   ├── analysis
│   ├── analyzers
│   ├── clients
│   ├── config.py
│   ├── constants.py
│   ├── db
│   ├── engines
│   ├── logger.py
│   ├── pipelines
│   ├── queue
│   └── services
├── output
│   ├── logs
│   │   └── archive
│   └── task_queue.db
└── tests
    ├── conftest.py
    ├── fixtures
    ├── ignition_test.py
    ├── integration
    └── unit
```

---
## 根目錄

-   `README.md`: 提供專案的整體介紹、安裝說明和使用指南。
-   `PROJECT_FILES_GLOSSARY.md`: 本檔案，提供專案中每個檔案的詳細功能說明。
-   `config.yml`: 全局設定檔，用於配置資料庫連線、API 金鑰等。
-   `mypy.ini`: `mypy` 型別檢查工具的設定檔。
-   `poetry.lock`: `poetry` 用於鎖定專案依賴版本的檔案。
-   `pyproject.toml`: `poetry` 的專案設定檔，定義專案元數據和依賴。
-   `run.py`: 專案執行的主要進入點，提供統一的 CLI 介面。

---
## `core` - 核心模組

此目錄包含專案的核心共用模組。

### `core/analysis`
-   `data_engine.py`: 資料引擎，負責提供和管理分析數據。
-   `stress_index.py`: 壓力指數的計算邏輯。

### `core/analyzers`
-   `base_analyzer.py`: 分析器的基底類別。

### `core/clients` - API 客戶端
-   `base.py`: API 客戶端的基底類別。
-   `finmind.py`: `FinMind` API。
-   `fmp.py`: `Financial Modeling Prep` API。
-   `fred.py`: `FRED` (Federal Reserve Economic Data) API。
-   `nyfed.py`: `New York Fed` API。
-   `taifex_db.py`: 台交所資料庫客戶端。
-   `yfinance.py`: `Yahoo Finance` API。

### `core/db` - 資料庫互動
-   `db_manager.py`: 資料庫管理模組。
-   `results_saver.py`: 提供 `save_result` 函數，專門負責將計算結果寫入 DuckDB 資料庫。

### `core/engines`
-   `robust_acquisition_engine.py`: 提供穩健的數據獲取功能。

### `core/pipelines` - 資料管線
-   `base_step.py`: 管線步驟的基底類別。
-   `pipeline.py`: 管線的核心邏輯。
-   `steps/`: 包含各個管線步驟的實作。

### `core/queue` - 異步任務佇列
-   `base.py`: 定義所有任務佇列都必須遵守的抽象基底類別 `BaseQueue`。
-   `sqlite_queue.py`: 提供一個基於 `SQLite` 的、輕量級且持久化的任務佇列實現 `SQLiteQueue`。

### `core/services` - 核心服務
-   `backtesting_service.py`: 核心的回測服務 `BacktestingService`，負責從佇列中取得任務、執行計算並儲存結果。

### 其他 `core` 檔案
-   `config.py`: 應用程式設定的管理模組。
-   `constants.py`: 定義專案中使用的常數。
-   `logger.py`: 基於 SQLite 的 v82.0「精準指示器」日誌系統。

---
## `apps` - 應用程式

此目錄包含各個獨立的應用程式模組，它們大多被 `run.py` 作為子命令調用。

### `apps/analysis_pipeline`
-   `run.py`: 執行資料分析管線。

### `apps/backtesting_engine`
-   `engine.py`: 回測引擎的核心邏輯。
-   `run.py`: 執行回測。

### `apps/dashboard`
-   `dashboard.html`: 基於 Web 的可視化儀表板前端頁面。

### `apps/db_manager`
-   `setup_database.py`: 設定和初始化資料庫。

### `apps/factor_engine`
-   `engine.py`: 因子計算引擎。
-   `run_factor_etl.py`: 執行因子數據的 ETL (抽取、轉換、載入) 流程。
-   `sma_crossover_factor.py`: 實現簡單移動平均線 (SMA) 交叉策略的因子。

### `apps/pipeline_metadata_manager`
-   `manager.py`: 管理和追蹤管線的元數據。

### `apps/portfolio_optimizer`
-   `main.py`: 投資組合優化器。

### `apps/report_generator`
-   `generator.py`: 產生回測或分析報告。
-   `run.py`: 執行報告產生。

### `apps/tools` - 開發與維護工具
-   `task_adder_app.py`: 用於向任務佇列中新增一批帶有動態參數的測試任務。
-   `show_results.py`: 提供在終端機中以表格形式顯示已儲存結果的功能。
-   `clear_results.py`: 提供一個安全的 CLI 工具，用於清除所有已儲存的回測結果。

### `apps/visualization`
-   `plot_sma_crossover.py`: 將 SMA 交叉策略的結果可視化。

### 其他 `apps` 檔案
-   `backtest_worker_app.py`: 回測服務工作者的應用程式入口，負責初始化佇列與服務。
-   `query_gateway.py`: 基於 `FastAPI` 的查詢網關，為前端儀表板提供 API 端點。

---
## `output` - 輸出

此目錄存放腳本執行後產生的檔案，已被加入 `.gitignore`。

-   `logs/archive/`: 存放每次 `run.py` 執行後歸檔的純文字日誌報告。
-   `task_queue.db`: 用於異步任務佇列的 SQLite 資料庫。

---
## `tests` - 自動化測試

此目錄包含所有單元測試與整合測試。

-   `conftest.py`: `pytest` 的設定檔，用於定義共用的 fixtures。
-   `fixtures/`: 存放測試用的靜態檔案。
-   `ignition_test.py`: 點火測試，快速檢查專案的關鍵部分是否能正常導入和初始化。
-   `integration/`: 整合測試，測試多個模組協同工作的場景。
-   `unit/`: 單元測試，針對單一模組或函數進行測試。
