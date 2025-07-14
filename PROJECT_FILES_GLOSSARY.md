# 專案檔案詞彙表 (v0.8.0)

本文件旨在提供一個完整、詳細的專案檔案地圖，說明每一個檔案與目錄在【普羅米修斯之火】框架中的功能與核心職責。

---

## **一、 根目錄 (Root Directory)**

專案的起始點，包含核心設定檔、主要執行入口與文檔。

-   `README.md`: **[文檔]** 開發者手冊，提供專案的整體介紹、技術棧、環境設定、主要功能用法、版本歷史與開發者指引。是新成員了解專案的第一站。
-   `PROJECT_FILES_GLOSSARY.md`: **[文檔]** (本檔案) 專案檔案詞彙表，提供比 `README.md` 更詳細的、針對每一個檔案和目錄的功能說明。
-   `run.py`: **[核心入口]** 專案的統一命令列介面 (CLI) 入口。使用 `Typer` 函式庫，將所有應用程式 (`apps/`) 的功能整合為子命令 (例如 `run-tests`, `evolve`, `dashboard`)。它還負責初始化 `LogManager` 並將其注入到各個任務中。
-   `config.yml`: **[設定檔]** 全局設定檔，用於配置 API 金鑰 (如 FRED)、資料庫路徑、快取設定等外部參數。**此檔案包含敏感資訊，已被加入 `.gitignore`，絕不應提交至版本控制系統。**
-   `pyproject.toml`: **[依賴管理]** `Poetry` 的專案設定檔，定義了專案的元數據 (名稱、版本、作者等) 以及所有生產環境與開發環境的依賴套件。
-   `poetry.lock`: **[依賴管理]** `Poetry` 自動產生的鎖定檔案，確保在任何環境下都能安裝完全相同版本的依賴套件，實現了環境的可複製性。
-   `pytest.ini`: **[測試設定]** `Pytest` 的設定檔，用於配置測試路徑、標記、預設參數 (如 `--junitxml`) 等。
-   `mypy.ini`: **[靜態分析]** `Mypy` 型別檢查工具的設定檔，用於定義型別檢查的規則與路徑。
-   `run_tests.py`: **[歷史腳本]** 舊版的測試執行腳本，現已被 `run.py run-tests` 命令取代。
-   `run_pipeline.sh`: **[歷史腳本]** 舊版的管線執行腳本，其功能已被 `run.py` 中的特定命令取代。
-   `_test_run.py`, `archive_test.py`, `check_qsize.py`, `read_logs.py`, `run_show_results.py`: **[臨時/偵錯腳本]** 這些是開發過程中用於臨時測試、偵錯或快速驗證特定功能的小型腳本，不屬於核心功能的一部分。

---

## **二、 `apps/` - 應用程式層**

此目錄包含所有使用者可直接透過 `run.py` 執行的具體應用。每個模組都代表一個獨立的功能單元。

-   `evolution_app.py`: **[核心應用]** `evolve` 命令的應用程式入口，負責初始化並啟動 `EvolutionChamber`，執行策略演化流程。
-   `backtest_worker_app.py`: **[核心應用]** `backtest-worker` 命令的應用程式入口，啟動一個背景工作者，專門用於執行由 `EvolutionChamber` 或其他模組派發的回測任務。
-   `query_gateway.py` & `dashboard/dashboard.html`: **[核心應用]** `dashboard` 命令的應用程式入口，使用 `FastAPI` 和 `Uvicorn` 啟動一個網頁伺服器，提供視覺化的儀表板來展示回測結果。
-   `tools/`: **[工具集]**
    -   `report_generator_app.py`: `run-tests` 命令的一部分，負責讀取 `pytest` 產生的 JUnit XML 報告，並將其轉換為人類可讀的 Markdown 戰報 (`TEST_REPORT.md`)。
    -   `task_adder_app.py`: `add-test-tasks` (歷史) 命令的入口，用於向任務佇列中手動添加一批測試任務。
    -   `show_results.py`: `show-results` 命令的入口，用於在終端機中查詢並顯示所有已儲存的回測結果。
    -   `clear_results.py`: `clear-results` 命令的入口，用於清除資料庫中所有已儲存的回測結果。
-   `optimizer_app.py`: **[歷史應用]** `optimize` (歷史) 命令的入口，是演化室的早期原型，現已被 `evolution_app.py` 取代。
-   `backtesting_engine/`: **[歷史引擎]**
    -   `engine.py`: 舊版的回測引擎核心邏輯。
    -   `run.py`: 舊版的回測引擎執行腳本。
-   `factor_engine/`, `analysis_pipeline/`, `portfolio_optimizer/`, `report_generator/`: **[歷史/待整合模組]** 這些是專案早期開發的各種功能模組，部分功能可能已被新架構取代或等待重構整合。

---

## **三、 `core/` - 核心服務與商業邏輯層**

此目錄是專案的心臟，包含了所有共享的核心商業邏輯、服務、客戶端與工具。

-   `logger.py`: **[核心服務]** `LogManager` 的實作。提供基於 `SQLite` 的結構化日誌系統，並能在任務結束時自動將日誌歸檔為文字檔案。
-   `services/`: **[核心服務]**
    -   `evolution_chamber.py`: **策略演化室**。整合了 `DEAP` 遺傳演算法函式庫，是整個系統自我進化的核心。它負責管理策略族群的生成、評估 (透過派發回測任務)、選擇、交叉與突變。
    -   `backtesting_service.py`: **回測服務**。被 `backtest-worker` 使用，負責從任務佇列中獲取回測任務，執行回測，並將結果儲存到資料庫。
    -   `optimizer_service.py`: **單次優化器 (歷史)**。`EvolutionChamber` 的前身，用於概念驗證。
-   `queue/`: **[核心服務]**
    -   `sqlite_queue.py`: 基於 `SQLite` 實現的持久化任務佇列。確保即使在程式中斷後，待處理的回測任務也不會遺失。
    -   `base.py`: 任務佇列的抽象基底類別。
-   `db/`: **[數據持久化]**
    -   `results_saver.py`: 負責將回測結果、策略參數等數據標準化並儲存到結果資料庫中。
    -   `db_manager.py`: 提供資料庫連線與管理功能。
-   `clients/`: **[數據源]**
    -   `finmind.py`, `fmp.py`, `fred.py`, `nyfed.py`, `yfinance.py`: 分別對應不同第三方金融數據 API (FinMind、Financial Modeling Prep、FRED、紐約聯儲、Yahoo Finance) 的客戶端，封裝了數據請求、認證與錯誤處理。
    -   `base.py`: 所有 API 客戶端的抽象基底類別。
-   `pipelines/`: **[數據處理管線]**
    -   定義了數據處理的步驟 (`BaseStep`) 與管線 (`Pipeline`) 的基本架構。
    -   `steps/`: 包含各種可重用的管線步驟，如數據載入 (`loaders.py`)、金融計算 (`financial_steps.py`) 等。
-   `config.py`: **[設定管理]** 提供一個函數 `get_config()`，用於載入並解析 `config.yml`，讓應用程式的其餘部分可以方便地存取設定值。
-   `constants.py`: **[常數]** 定義專案中廣泛使用的常數，例如預設的資料庫名稱、API 端點等，以避免在程式碼中出現硬編碼的 "魔法數字"。
-   `utils/`: **[共用工具]**
    -   `caching.py`: 提供快取裝飾器，用於快取函式結果，減少重複計算或 API 請求。
    -   `path_utils.py`: 提供路徑處理相關的工具函式。

---

## **四、 `tests/` - 自動化測試**

此目錄包含所有自動化測試，以確保程式碼的品質與穩定性。

-   `ignition_test.py`: **[點火測試]** 一種快速的健全檢查測試，它不執行任何邏輯，僅僅嘗試導入專案中的每一個 `.py` 檔案，以確保沒有任何因語法錯誤、循環依賴或環境問題導致的導入失敗。
-   `integration/`: **[整合測試]**
    -   `test_evolution_pipeline.py`: 演化管線的輕量化邏輯驗證測試。透過模擬 (Mocking) 耗時的回測過程，專門驗證 `EvolutionChamber` 的核心演算法邏輯是否正確。
    -   其他檔案: 測試多個模組協同工作時的端到端流程。
-   `unit/`: **[單元測試]** 針對單一函式或類別進行的測試，確保最小的功能單元運作正常。
-   `fixtures/`: 存放測試所需的靜態數據檔案，例如模擬的 API 回應、測試用的 CSV 檔案等。
-   `conftest.py`: `Pytest` 的本地插件檔案，用於定義測試範圍內共享的 Fixtures (例如，一個臨時的資料庫連線)。

---

## **五、 `output/` - 執行輸出**

此目錄用於存放所有由程式執行產生的檔案，已被加入 `.gitignore`。

-   `logs/`:
    -   `session.sqlite`: 當前 `run.py` 工作階段的即時日誌資料庫。
    -   `archive/`: 存放所有歷史工作階段的文字日誌歸檔。
-   `reports/`:
    -   `report.xml`: `pytest` 產生的 JUnit XML 格式的機器可讀測試報告。
-   `*.duckdb`: `DuckDB` 資料庫檔案。
-   `TEST_REPORT.md`: `run.py run-tests` 產生的 Markdown 格式人類可讀測試報告。

---

## **六、 `pipelines/` - 歷史數據管線**

此目錄包含專案早期的數據處理管線，部分可能已被新架構取代。

-   `p0_downloader/`: 下載原始資料。
-   `p1_explorer/`: 探索和初步分析資料。
-   `p2_elt_pipeline/`: 執行 ELT (抽取、載入、轉換) 流程。
-   `p3_backfill_hourly_data/`: 回填每小時的歷史資料。

---
## v0.9.0 新增/修改檔案 (最終驗收)

### `tests/integration` - 整合測試

-   `test_final_acceptance.py`: **[新增]** 最終驗收測試。這是一個全系統的整合測試，它在一個由 `conftest.py` 提供的、乾淨的隔離環境中，自動化地模擬從 `evolve` 命令啟動，到背景 `backtest-worker` 處理完所有任務的完整端到端流程。這是驗證所有核心組件能否完美協同工作的最終品質閘門。

### 根目錄 (Root Directory)

-   `TEST_REPORT.md`: **[自動生成報告]** 由 `run.py run-tests` 命令自動產生的、人類可讀的 Markdown 格式測試報告。它總結了所有自動化測試的執行結果。
