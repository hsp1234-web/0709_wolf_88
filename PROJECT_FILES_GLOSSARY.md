# 專案檔案詞彙表 (v2.1 萬象引擎版)

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

## **二、 檔案目錄結構 (v2.1)**

```
.
├── PROJECT_FILES_GLOSSARY.md
├── README.md
├── TEST_REPORT.md
├── config.yml
├── create_dummy_data.py
├── mypy.ini
├── ...
├── src
│   └── core
│       ├── ...
│       └── services
│           ├── __init__.py
│           ├── backtesting_service.py
│           ├── checkpoint_manager.py
│           ├── evolution_chamber.py
│           └── optimizer_service.py
└── tests
    ├── ...
    └── unit
        └── services
            └── test_omniverse_engine.py
```

## **三、 根目錄 (Root Directory)**

-   `README.md`: **[文檔]** 開發者手冊，提供專案的整體介紹、技術棧、環境設定、主要功能用法、版本歷史與開發者指引。
-   `PROJECT_FILES_GLOSSARY.md`: **[文檔]** (本檔案) 提供比 `README.md` 更詳細的、針對每一個檔案和目錄的功能說明。
-   `run.py`: **[核心入口]** 專案的統一命令列介面 (CLI)，使用 `Typer` 建立。是執行所有主要任務（如演化、回測、測試、儀表板）的入口點。
-   `run_local_services.py`: **[輔助腳本]** 用於在本機同時啟動多個服務（如演化引擎和回測工作者）的腳本，模擬生產環境的運行方式。
-   `config.yml`: **[設定檔]** 全局設定檔。**在 v2.1 中，新增了 `factor_universe` 區塊，這是萬象引擎的核心設定，用於定義所有可供演化使用的因子、參數範圍與操作，實現了配置驅動的策略擴展。**
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
    -   `evolution_chamber.py`: **[核心服務-同步]** **萬象引擎的大腦**。重構後的演化室不再局限於特定策略，而是成為一個動態的基因體工廠。它讀取 `config.yml` 中的 `factor_universe`，動態地生成由多個「條件」組成的複雜基因體，並負責對這些基因體進行交叉與突變。
    -   `backtesting_service.py`: **[核心服務-同步]** **萬象引擎的執行者**。重構後的回測服務成為一個動態的規則解釋器。它接收複雜的基因體，遍歷其中的每一個條件，動態調用 `pandas-ta` 計算對應的技術指標，並根據條件的運算子將指標序列轉化為交易信號，最終組合所有信號並執行 `vectorbt` 回測。
-   `queue/`:
    -   `sqlite_queue.py`: **[核心通訊-同步]** 一個基於 `sqlite3` 的、穩健的 **同步** 任務佇列。是 `evolution_app` 和 `backtest_worker_app` 之間進行任務分派和結果回收的主要通訊機制。
-   `events/`:
    -   `event_store.py`: **[核心通訊-非同步]** 一個基於 `aiosqlite` 的持久化 **非同步** 事件流。它實現了事件溯源模式，是系統中正在開發或用於特定非同步場景的元件。
-   `db/`:
    -   `results_saver.py`: **[數據持久化-非同步]** 結果儲存器。使用 `aiosqlite` 以非同步方式將回測結果儲存到資料庫。
-   `logger.py`: **[核心服務]** `LogManager` 的實作，提供結構化的日誌記錄功能。

## **六、 `tests/` - 自動化測試**

此目錄包含所有自動化測試，確保程式碼的品質與穩定性。

-   `conftest.py`: **[測試設定]** `Pytest` 的本地插件檔案。
-   `unit/services/test_omniverse_engine.py`: **[單元測試]** **萬象引擎的專屬測試**。此檔案包含針對新架構下 `EvolutionChamber` 和 `BacktestingService` 的單元測試，用於驗證它們能否正確生成、操作和解釋複雜的基因體。
-   `integration/`: **[整合測試]** 專注於測試多個模組協同工作時是否正確。

[end of PROJECT_FILES_GLOSSARY.md]
