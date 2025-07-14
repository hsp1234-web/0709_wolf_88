# 專案檔案詞彙表 (v1.1 鳳凰版)

本文件旨在提供一個完整、詳細的專案檔案地圖，說明每一個檔案與目錄在【普羅米修斯之火】框架中的功能與核心職責。

---
## **一、 檔案目錄結構 (v1.1.0)**
.
├── PROJECT_FILES_GLOSSARY.md
├── README.md
├── TEST_REPORT.md
├── config.yml
├── mypy.ini
├── pipelines
├── poetry.lock
├── pyproject.toml
├── pytest.ini
├── run.py
├── src
│   ├── apps
│   │   ├── __init__.py
│   │   ├── backtest_worker_app.py
│   │   └── evolution_app.py
│   └── core
│       ├── __init__.py
│       ├── config.py
│       ├── constants.py
│       ├── context.py
│       ├── db
│       │   ├── __init__.py
│       │   └── results_saver.py
│       ├── queue
│       │   ├── __init__.py
│       │   └── async_event_bus.py
│       └── services
│           ├── __init__.py
│           ├── backtesting_service.py
│           └── evolution_chamber.py
└── tests
    ├── __init__.py
    ├── conftest.py
    └── integration
        └── test_final_acceptance.py

---

## **二、 根目錄 (Root Directory)**

專案的起始點，包含核心設定檔、主要執行入口與文檔。

-   `README.md`: **[文檔]** 開發者手冊，提供專案的整體介紹、技術棧、環境設定、主要功能用法、版本歷史與開發者指引。是新成員了解專案的第一站。
-   `PROJECT_FILES_GLOSSARY.md`: **[文檔]** (本檔案) 專案檔案詞彙表，提供比 `README.md` 更詳細的、針對每一個檔案和目錄的功能說明。
-   `run.py`: **[核心入口 (歷史)]** 專案的統一命令列介面 (CLI) 入口。在【鳳凰計畫】重構後，其大部分功能已整合進測試流程，主要用於歷史功能或未來擴展。
-   `config.yml`: **[設定檔]** 全局設定檔，用於配置 API 金鑰、資料庫路徑等。
-   `pyproject.toml`: **[依賴管理]** `Poetry` 的專案設定檔，定義了專案元數據及所有依賴套件。
-   `poetry.lock`: **[依賴管理]** `Poetry` 自動產生的鎖定檔案，確保環境的可複製性。
-   `pytest.ini`: **[測試設定]** `Pytest` 的設定檔。
-   `mypy.ini`: **[靜態分析]** `Mypy` 型別檢查工具的設定檔。

---

## **三、 `src/apps/` - 應用程式層 (非同步)**

此目錄包含所有可執行的非同步應用。每個模組都代表一個獨立的非同步功能單元。

-   `evolution_app.py`: **[核心應用]** 演化流程的非同步主函數 (`main`)。負責初始化並啟動 `EvolutionChamber`，驅動策略演化流程。
-   `backtest_worker_app.py`: **[核心應用]** 背景回測工作者的非同步主函數 (`main`)。啟動一個非同步的背景工作者，持續從事件總線 (`AsyncEventBus`) 的任務佇列中獲取任務，執行回測，並將結果放入結果佇列。

---

## **四、 `src/core/` - 核心服務與商業邏輯層 (非同步)**

此目錄是專案的心臟，包含了所有共享的非同步核心商業邏輯、服務與工具。

-   `context.py`: **[核心服務]** `AppContext` 的實作。一個非同步上下文管理器 (`async with`)，負責初始化並提供所有共享的非同步服務（如 `AsyncEventBus`, `ResultsSaver` 的資料庫連線）。
-   `services/`: **[核心服務]**
    -   `evolution_chamber.py`: **策略演化室 (非同步)**。整合了 `DEAP` 遺傳演算法函式庫。它以非同步方式管理策略族群的生成、評估 (透過向 `AsyncEventBus` 派發回測任務)、選擇、交叉與突變。
    -   `backtesting_service.py`: **回測服務 (非同步)**。被 `backtest_worker_app` 使用，負責執行回測計算，並以非同步方式將結果儲存到資料庫。
-   `queue/`: **[核心通訊]**
    -   `async_event_bus.py`: **非同步事件總線**。基於 `asyncio.Queue` 實現，提供一個任務佇列和一個結果佇列，是系統內所有非同步組件之間通訊的中樞。
-   `db/`: **[數據持久化]**
    -   `results_saver.py`: **結果儲存器 (非同步)**。使用 `aiosqlite`，負責以非同步方式將回測結果、策略參數等數據標準化並儲存到結果資料庫 (`results.sqlite`) 中。

---

## **五、 `tests/` - 自動化測試 (非同步)**

此目錄包含所有自動化測試，以確保程式碼的品質與穩定性。

-   `integration/test_final_acceptance.py`: **[最終驗收測試]** 鳳凰計畫的最終驗收測試。這是一個基於 `pytest-asyncio` 的全系統整合測試，它在一個事件循環中，透過 `asyncio.create_task` 協調 `evolution_app` 和 `backtest_worker_app` 的運行，驗證從演化、任務分派、回測到結果儲存的完整非同步流程。
-   `conftest.py`: **[測試設定]** `Pytest` 的本地插件檔案，為測試提供共享的 fixtures。在鳳凰計畫中，它被簡化，因為 `AppContext` 的 `async with` 機制已能處理大部分設定與清理工作。

---

## **六、 `output/` - 執行輸出**

此目錄用於存放所有由程式執行產生的檔案，已被加入 `.gitignore`。

-   `results.sqlite`: 存放所有回測結果的 SQLite 資料庫檔案。
-   `*.log`: （歷史）日誌檔案。

---

## **七、 `pipelines/` - 歷史數據管線**

此目錄包含專案早期的數據處理管線，在【鳳凰計畫】中未被使用，但為歷史參考保留。
