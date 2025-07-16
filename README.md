# **【普羅米修斯之火】金融數據與分析框架 - 開發者手冊 v2.1**

## **一、 專案概覽與目的**

【普羅米修斯之火】是一個專為進階量化研究與金融市場分析而設計的 Python 框架。本專案旨在提供一個從多樣化數據源獲取金融數據、進行複雜指標計算、透過遺傳演算法進行策略最佳化、回測交易策略、並將結果視覺化的完整解決方案。

**核心理念演進 (v2.1 - 萬象引擎):**
本作戰計畫旨在將策略演化系統從單一的「均線策略」升級為可處理多元因子組合的「萬象引擎」。我們重構了基因體 (Genome) 的數據結構與核心服務，讓 AI 能夠在一個更廣闊、由 `config.yml` 動態定義的「因子宇宙」中，探索與創新更複雜的交易策略。

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

## **三、 完整檔案目錄結構 (v3.0 - 終極整合)**

> **[文件化說明]**
> 關於下表中每一個檔案的詳細功能、職責與執行邏輯，請參閱 **[`PROJECT_FILES_GLOSSARY.md`](./PROJECT_FILES_GLOSSARY.md)** 檔案。

```
.
├── PROJECT_FILES_GLOSSARY.md
├── README.md
├── TEST_REPORT.md
├── config.yml
├── mypy.ini
├── poetry.lock
├── pyproject.toml
├── pytest.ini
├── run.py
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

本專案的所有功能，皆透過統一的 CLI 入口 `run.py` 進行操作。

### **5.1 透過 `run.py` CLI 執行任務**

`run.py` 是專案的唯一命令列介面，你可以用它來執行各種獨立的任務。

*   **查看所有可用指令**:
    ```bash
    poetry run python run.py --help
    ```

*   **數據管理 (`data`)**:
    ```bash
    # 建立虛構數據
    poetry run python run.py data create-dummy
    ```

*   **數據管線 (`pipelines`)**:
    ```bash
    # 執行數據下載
    poetry run python run.py pipelines run-downloader --start-date 2023-01-01 --end-date 2023-01-31

    # 執行格式探勘
    poetry run python run.py pipelines run-explorer

    # 執行 ELT 流程
    poetry run python run.py pipelines run-elt

    # 執行歷史數據回填
    poetry run python run.py pipelines run-backfill --start-date 2023-01-01 --end-date 2023-01-31
    ```

*   **結果管理 (`results`)**:
    ```bash
    # 清除所有結果
    poetry run python run.py results clear

    # 顯示回測結果
    poetry run python run.py results show

    # 添加回測任務
    poetry run python run.py results add-tasks --num-tasks 50

    # 生成測試報告
    poetry run python run.py results generate-report
    ```

*   **核心應用**:
    ```bash
    # 啟動儀表板後端服務
    poetry run python run.py dashboard --host 127.0.0.1 --port 8000

    # 執行一次完整的策略演化
    poetry run python run.py analyze
    ```

### **5.2 執行自動化測試**

*   **運行所有測試**:
    ```bash
    poetry run pytest -v
    ```
*   **運行測試並生成報告**:
    `run.py` 也整合了測試和報告生成的功能。
    ```bash
    poetry run python run.py results generate-report
    ```

## **六、 開發者指引**

*   遵循 PEP 8 程式碼風格。
*   所有程式碼註解、日誌訊息和終端機輸出均使用**繁體中文**。
*   嚴禁在程式碼中硬編碼任何 API 金鑰或敏感資訊。所有配置應透過 `config.yml` 管理。
*   在提交程式碼前，請務必運行 `poetry run pytest` 確保沒有引入新的迴歸問題。

## **七、 日誌系統 (雅典娜之鏡)**

本專案實現了一個集中式的結構化日誌系統，以取代所有分散的 `print()` 語句，提供清晰、可追蹤的系統活動記錄。

*   **核心元件**: `src/prometheus/core/logging/log_manager.py`
*   **日誌格式**: `[時間戳] [日誌級別] [來源模組] - 訊息`
    *   例如: `[2025-07-16 06:20:00] [INFO] [Evolution-Engine] - 正在處理第 1 代...`
*   **日誌輸出**:
    *   **控制台**: 所有日誌都會即時輸出到控制台。
    *   **檔案**: 所有日誌都會被寫入到 `data/logs/prometheus.log`。該檔案會根據大小自動輪替。
*   **如何使用**:
    在任何需要日誌記錄的模組中，透過以下方式獲取 logger 實例：
    ```python
    from src.prometheus.core.logging.log_manager import LogManager
    logger = LogManager.get_instance().get_logger("你的模組名稱")

    logger.info("這是一條資訊日誌。")
    logger.error("這是一條錯誤日誌。", exc_info=True) # exc_info=True 會附帶堆疊追蹤
    ```

---

## **附錄：歷史版本存檔**

### **v2.2 (雅典娜之鏡) - 作戰計畫 107**
*   **【重大基礎設施升級】實施集中式結構化日誌系統**
    *   **背景**: 舊有版本大量使用 `print()` 語句，導致輸出混亂、難以追蹤，且無法進行分級或持久化。
    *   **實作細節**:
        *   **強化 `LogManager`**: 將 `log_manager.py` 重構為一個採用單例模式的中央日誌服務，確保全專案使用統一的日誌配置。
        *   **統一格式與輸出**: 設定了標準的日誌格式 `[時間戳] [級別] [模組] - 訊息`，並能同時輸出到控制台和可輪替的日誌檔案 (`data/logs/prometheus.log`)。
        *   **全面替換 `print()`**: 在整個 `src` 目錄下，系統性地將 `print()` 語句替換為 `logger.info()`, `logger.error()`, `logger.debug()` 等呼叫。
        *   **建立單元測試**: 為 `LogManager` 新增了單元測試，驗證其單例行為、檔案寫入和格式的正確性。
    *   **影響**:
        *   **可追蹤性**: 所有系統活動都有了統一、帶時間戳和來源的記錄，極大地方便了問題排查和行為分析。
        *   **可維護性**: 程式碼變得更加乾淨，移除了混亂的 `print()` 語句，提高了可讀性和專業性。
        *   **持久化**: 所有日誌都被保存到檔案中，便於事後審計和分析。

### **v2.1 (萬象引擎) - 作戰計畫 106**
*   **【重大架構升級】從「單一策略」到「多元因子宇宙」**
    *   **背景**: 舊有的演化引擎只能處理固定的「雙均線交叉」策略，其基因體只是一個包含兩個數字的簡單列表，極大地限制了 AI 探索策略空間的能力。
    *   **實作細節**:
        *   **廢棄簡單基因**: 完全廢棄了 `[fast, slow]` 的基因結構。
        *   **引入複雜基因體**: 將「基因體 (Genome)」重新設計為一個 **條件列表**。每個條件都是一個包含 `factor` (因子名稱), `params` (參數), `operator` (運算子) 和 `value` (比較值) 的字典，允許可擴展、可組合的複雜策略。
        *   **因子宇宙 (`factor_universe`)**: 在 `config.yml` 中新增了 `factor_universe` 區塊，允許開發者在不修改程式碼的情況下，透過設定檔來定義所有可供 AI 使用的因子、參數範圍、運算子等。
        *   **動態演化室 (`EvolutionChamber`)**: 重構了 `EvolutionChamber`，使其能夠讀取 `factor_universe` 設定，並動態地生成、突變和交叉新的複雜基因體。
        *   **動態回測引擎 (`BacktestingService`)**: 重構了 `BacktestingService`，將其從一個寫死均線邏輯的服務，改造為一個 **動態規則解釋器**。它能遍歷基因體中的每個條件，使用 `pandas-ta` 動態計算指標，並根據運算子將其轉換為交易信號，最終組合所有信號進行回測。
        *   **建立專屬單元測試**: 新增了 `tests/unit/services/test_omniverse_engine.py` 來專門驗證新架構下兩個核心服務的正確性與穩健性。
    *   **影響**:
        *   **策略空間擴展**: AI 不再局限於單一策略，可以在一個廣闊的因子宇宙中進行探索與創新。
        *   **配置驅動開發**: 新增或修改可用因子不再需要修改 Python 程式碼，只需維護 `config.yml`，極大提高了擴展性與靈活性。
        *   **架構解耦**: 演化邏輯與具體的策略計算被完全解耦，使系統更加清晰和可維護。

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
