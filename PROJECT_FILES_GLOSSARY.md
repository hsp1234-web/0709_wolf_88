# 專案檔案詞彙表 (v3.0 終極整合版)

本文件旨在提供一個完整、詳細的專案檔案地圖，說明每一個檔案與目錄在【普羅米修斯之火】框架中的功能與核心職責。

## **一、 技術棧 (Technology Stack)**

本專案使用 [Poetry](https://python-poetry.org/) (v1.8.2+) 進行依賴管理。

*   **核心與框架:**
    *   `python`: `>=3.12,<3.14`
    *   `typer`: `^0.12.3` (命令列介面)
    *   `fastapi`: `^0.111.0` (Web API 框架)
    *   `setuptools`: `^80.9.0` (建構工具)
*   **數據處理與分析:**
    *   `pandas`: `^2.2.2`
    *   `numpy`: `<2.0`
    *   `pandas-ta`: `^0.3.14b0`
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

## **二、 檔案目錄結構 (v4.0 - 簡化後)**

```
.
├── PROJECT_FILES_GLOSSARY.md
├── README.md
├── TEST_REPORT.md
├── config.yml
├── data/
├── mypy.ini
├── poetry.lock
├── pyproject.toml
├── pytest.ini
├── run.py
├── scripts/
│   ├── verify_db.py
│   ├── verify_factor_accuracy.py
│   └── verify_fred_client.py
├── src/
│   ├── __init__.py
│   └── prometheus
│       ├── cli/
│       │   └── main.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── analysis/
│       │   ├── clients/
│       │   ├── config.py
│       │   ├── constants.py
│       │   ├── context.py
│       │   ├── db/
│       │   │   ├── __init__.py
│       │   │   ├── data_warehouse.py
│       │   │   ├── db_manager.py
│       │   │   ├── evolution_logger.py
│       │   │   ├── schema_registry.py
│       │   │   └── transactional_writer.py
│       │   ├── engines/
│       │   │   ├── __init__.py
│       │   │   ├── bond_factor_engine.py
│       │   │   ├── crypto_factor_engine.py
│       │   │   ├── index_factor_engine.py
│       │   │   └── stock_factor_engine.py
│       │   ├── logging/
│       │   └── queue/
│       ├── pipelines/
│       │   ├── p4_stock_factor_generation.py
│       │   ├── p5_crypto_factor_generation.py
│       │   ├── p6_simulation_training.py
│       │   └── steps/
│       └── services/
└── tests/
    ├── conftest.py
    ├── fixtures/
    ├── ignition_test.py
    ├── integration/
    │   ├── analysis/
    │   ├── apps/
    │   └── pipelines/
    └── unit/
        ├── analysis/
        └── core/
            ├── analyzers/
            ├── clients/
            └── logging/
```

## **三、 根目錄 (Root Directory)**

-   `README.md`: **[文檔]** 開發者手冊，提供專案的整體介紹、技術棧、環境設定、主要功能用法、版本歷史與開發者指引。
-   `PROJECT_FILES_GLOSSARY.md`: **[文檔]** (本檔案) 提供比 `README.md` 更詳細的、針對每一個檔案和目錄的功能說明。
-   `run.py`: **[核心入口]** 專案的統一命令列介面 (CLI)，使用 `Typer` 建立。是執行所有主要任務的唯一入口點。
-   `config.yml`: **[設定檔]** 全局設定檔。包含了 API 金鑰、資料庫路徑以及因子定義。
-   `pyproject.toml`: **[依賴管理]** `Poetry` 的專案設定檔。
-   `poetry.lock`: **[依賴管理]** `Poetry` 的鎖定檔案。
-   `pytest.ini`, `mypy.ini`: **[工具設定]** `Pytest` 和 `Mypy` 的設定檔。
-   `data/`: **[數據目錄]** 存放所有數據相關檔案，包括日誌、檢查點和資料庫。
-   `scripts/`: **[輔助腳本]** 包含用於驗證、報告和診斷的輔助工具。

## **四、 `src/prometheus/` - 原始碼主目錄**

-   `cli/main.py`: **[命令列介面]** `Typer` 應用的主要實作，定義了所有可用的命令列指令，如 `build-feature-store` 和 `run-simulation-training`。
-   `core/`: **[核心服務與商業邏輯層]**
    -   `clients/`: 包含所有與外部 API 互動的客戶端，如 `YFinanceClient`, `FredClient` 等。
    -   `db/`: 包含了資料庫管理、數據倉庫 (`DataWarehouse`) 和 schema 定義。
    -   `engines/`: 包含針對不同資產類別的因子計算引擎，如 `StockFactorEngine`, `CryptoFactorEngine` 等。
    -   `logging/log_manager.py`: **[核心服務]** 中央日誌管理器。
    -   `queue/sqlite_queue.py`: 一個基於 `sqlite3` 的、穩健的同步任務佇列。
-   `pipelines/`: **[數據處理管線]**
    -   `p4_stock_factor_generation.py`: **[管線]** 生成股票相關因子的生產線。
    -   `p5_crypto_factor_generation.py`: **[管線]** 生成加密貨幣相關因子的生產線。
    -   `p6_simulation_training.py`: **[管線]** 訓練因子模擬器的管線。
    -   `steps/`: 包含管線中每個具體步驟的實現。
-   `services/`: **[應用服務]** 包含應用程式級別的服務，如 `FactorSimulator`。

## **五、 `tests/` - 自動化測試**

此目錄包含所有自動化測試，確保程式碼的品質與穩定性。

-   `conftest.py`: **[測試設定]** `Pytest` 的本地插件檔案，用於定義所有測試共享的 `fixtures`。
-   `unit/`: **[單元測試]** 專注於測試單一函式、類別或模組的功能是否正確。
-   `integration/`: **[整合測試]** 專注於測試多個模組協同工作時是否正確。
-   `fixtures/`: **[測試數據]** 存放所有測試案例所需的靜態數據檔案。
