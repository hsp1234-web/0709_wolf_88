# **【普羅米修斯之火】金融數據與分析框架 - 開發者手冊 v2.0**

## **一、 專案概覽與目的**

【普羅米修斯之火】是一個專為進階量化研究與金融市場分析而設計的 Python 框架。本專案旨在提供一個從多樣化數據源獲取金融數據、進行複雜指標計算、透過遺傳演算法進行策略最佳化、回測交易策略、並將結果視覺化的完整解決方案。

**當前架構 (v2.0):**
本專案目前採用一種混合式架構：
*   **同步核心**：核心的策略演化 (`evolution_app`) 與回測 (`backtest_worker_app`) 流程是基於多進程/多線程的同步模型。它們使用一個基於 `SQLite` 的、穩健的任務佇列 (`SQLiteQueue`) 進行通訊，確保了在 CPU 密集型計算中的穩定性與任務的持久性。
*   **非同步服務**：儀表板後端 (`query_gateway`) 等 Web 服務則採用了現代的 `asyncio` 和 `FastAPI` 架構，以實現高效率的 I/O 操作和並發處理。

這種設計允許系統在需要執行大量計算時保持穩健，同時在需要處理網路請求時又能擁有高效能。

## **二、 技術棧 (Technology Stack)**

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

## **三、 完整檔案目錄結構 (v2.0)**

> **[文件化說明]**
> 關於下表中每一個檔案的詳細功能、職責與執行邏輯，請參閱 **[`PROJECT_FILES_GLOSSARY.md`](./PROJECT_FILES_GLOSSARY.md)** 檔案。

```
.
├── PROJECT_FILES_GLOSSARY.md
├── README.md
├── TEST_REPORT.md
├── config.yml
├── create_dummy_data.py
├── mypy.ini
├── pipelines
│   ├── ... (歷史數據管線)
├── poetry.lock
├── pyproject.toml
├── pytest.ini
├── run.py
├── run_local_services.py
├── src
│   ├── ... (應用程式與核心邏輯)
└── tests
    ├── ... (測試相關檔案)
```

## **四、 環境設定與執行**

1.  **安裝 Poetry**: `curl -sSL https://install.python-poetry.org | python -`
2.  **克隆專案**。
3.  **配置 Poetry 虛擬環境** (推薦): `poetry config virtualenvs.in-project true`
4.  **安裝依賴**: `poetry install`
5.  **激活虛擬環境**: `poetry shell`

## **五、 主要功能執行與測試**

本專案提供兩種主要的執行方式：透過統一的 CLI 入口 `run.py`，或使用 `run_local_services.py` 進行模擬部署。

### **5.1 透過 `run.py` CLI 執行單個任務**

`run.py` 是專案的統一命令列介面，你可以用它來執行各種獨立的任務。

*   **查看所有可用指令**:
    ```bash
    poetry run python run.py --help
    ```
*   **執行一次完整的策略演化**:
    ```bash
    poetry run python run.py evolve
    ```
*   **啟動儀表板後端服務**:
    ```bash
    poetry run python run.py dashboard --host 127.0.0.1 --port 8000
    ```
*   **清除所有回測結果**:
    ```bash
    poetry run python run.py clear-results --force
    ```

### **5.2 透過 `run_local_services.py` 模擬生產環境**

為了模擬生產環境中「生產者-消費者」並行工作的場景，我們提供了 `run_local_services.py` 腳本。它會同時啟動一個演化引擎（生產者）和多個回測工作者（消費者）。

*   **啟動本地服務集群**:
    ```bash
    poetry run python run_local_services.py
    ```
    這會啟動一個 `evolution_app` 和預設數量的 `backtest_worker_app`。你將在終端機中看到它們並行工作的日誌。按 `Ctrl+C` 可以優雅地關閉所有服務。

### **5.3 執行自動化測試**

*   **運行所有測試**:
    ```bash
    poetry run pytest -v
    ```
*   **運行測試並生成報告**:
    `run.py` 也整合了測試和報告生成的功能。
    ```bash
    poetry run python run.py run-tests
    ```
    此指令會執行所有測試，並在 `output/reports/` 目錄下生成 `report.xml`，同時在根目錄下生成 `TEST_REPORT.md`。

## **六、 開發者指引**

*   遵循 PEP 8 程式碼風格。
*   所有程式碼註解、日誌訊息和終端機輸出均使用**繁體中文**。
*   嚴禁在程式碼中硬編碼任何 API 金鑰或敏感資訊。所有配置應透過 `config.yml` 管理。
*   在提交程式碼前，請務必運行 `poetry run pytest` 確保沒有引入新的迴歸問題。

---

## **附錄：歷史版本存檔**

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
