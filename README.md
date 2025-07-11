# **README.md - 【普羅米修斯之火】開發者手冊**

## **一、 計畫概述**

【普羅米修斯之火】是一個為專業量化研究而設計的、本地化、具備高度擴展性的數據與分析框架。其核心目標是在標準硬體環境下，建立一個從「多源數據獲取」、「數據融合與清洗」、「量化因子挖掘」，到「策略回測」與「投資組合優化」的完整流程。

本專案採用模組化架構，旨在提升系統的靈活性、可維護性與擴展性。

核心設計原則：
1.  **使用者主導 (User-Led):** 系統的關鍵操作由使用者透過 API 或腳本觸發，後端負責執行與反饋。
2.  **數據湖倉一體 (Lakehouse Architecture):** 原始數據完整載入數據湖，分析數據從湖中提煉至數據倉儲，確保數據可追溯性。數據以版本化或日期戳管理。
3.  **內容感知獲取 (Content-Aware Fetching):** 數據獲取階段具備識別已有數據範圍的能力，精準補充數據缺口，提升效率。

## **二、 技術棧 (Technology Stack)**

*   **核心數據處理:** Pandas, NumPy
*   **數據持久化格式:** Apache Parquet
*   **技術指標計算:** `pandas-ta`
*   **非同步網路請求:** `aiohttp`
*   **HTTP請求快取:** `requests-cache`
*   **斷路器模式實現:** `pybreaker`
*   **系統資源監控:** `psutil`
*   **嵌入式分析資料庫:** DuckDB
*   **HTTP客戶端庫:** `requests`, `urllib3` (<2.0)
*   **金融數據獲取:** `yfinance`
*   **路徑管理:** `pathlib`
*   **日誌記錄:** Python `logging` 模組
*   **測試框架:** Pytest
*   **命令行界面 (輔助腳本):** `argparse`

## **三、 系統核心架構**

系統採用「微服務應用 (Micro-App)」架構理念，將後端管線拆解為獨立的作戰單元。

*   **`apps/` 目錄 - 微應用中心：**
    *   每個子目錄或獨立腳本是一個「微應用」，專注於特定任務（如因子計算、黃金層構建、回測）。
*   **`core/` 目錄 - 共享核心模組：**
    *   存放可被不同微應用共享的核心組件，如配置管理 (`core/config.py`)、日誌記錄器 (`core/logger.py`)、API 客戶端 (`core/clients/`)、數據庫管理器 (`core/db/`) 以及核心數據獲取引擎 (`core/engines/`)。
*   **標準數據流 (ETL/ELT)：**
    1.  **數據提取 (Extract)**：由 `downloader` 微應用或核心引擎負責。
    2.  **數據轉換 (Transform)**：由 `transformer` 微應用負責。
    3.  **數據裝載 (Load)**：由 `database_loader` 微應用或核心引擎負責，載入到 DuckDB。

### **核心數據獲取引擎：`RobustDataAcquisitionEngine`**

位於 `core/engines/robust_acquisition_engine.py`，是系統數據獲取的基石。設計目標是實現高效、穩定且具備自我調節能力的數據獲取。

**核心功能：**

1.  **非同步併發獲取 (Asynchronous & Concurrent Fetching)**：
    *   利用 `asyncio` 配合 `yf.Ticker().history()` 在獨立線程中執行，實現多個股票代碼數據的併發獲取，提升I/O密集型任務的效率。
2.  **智慧降級探測 (Intelligent Degradation Probing)**：
    *   在請求詳細歷史數據（如日線）前，先對目標進行一次輕量級的「探測請求」（如月線數據）。
    *   如果探測失敗（如股票代碼無效、無任何數據返回），則跳過對該目標的後續詳細數據請求，避免資源浪費。
3.  **資源感知儲存 (Resource-Aware Storage)**：
    *   使用 `psutil` 監控系統記憶體使用率。
    *   當記憶體使用超過預設閾值 (70%) 時，引擎會將獲取的數據優先寫入永久儲存（DuckDB），而非僅保留在記憶體中。
    *   在當前實現中，無論記憶體使用率如何，數據均會通過 UPSERT 操作寫入 DuckDB 以確保持久化。
4.  **斷路器模式 (Circuit Breaker)**：
    *   使用 `pybreaker` 函式庫包裹單個股票數據的獲取邏輯 (`fetch_single_ticker` 方法)。
    *   當對某一特定股票的請求連續失敗達到預設次數（5次）後，斷路器會「跳閘」，在指定超時時間（60秒）內阻止對該股票的後續請求，防止系統資源被無效請求拖垮，並給予遠端服務恢復的時間。
5.  **HTTP請求快取與重試 (via `requests-cache` & `urllib3.Retry`)**：
    *   引擎內部創建了一個配置了永久快取 (`requests-cache`) 和指數退避重試 (`urllib3.Retry`) 策略的 `requests.Session` 物件。
    *   **重要限制**：由於 `yfinance` (版本 0.2.60 及後續) 內部可能強制使用 `curl_cffi` 並建議不向其傳遞自訂 `session` 物件，因此這個經過強化的 `session` **目前未直接應用於 `yfinance` 的數據下載過程**。`yfinance` 將依賴其自身的請求邏輯和可能的內部快取。
    *   因此，`requests-cache` 提供的持久性HTTP層級快取和基於狀態碼的重試，對 `yfinance` 的請求影響有限。引擎的 `force_recache` 方法目前實現為清除 `requests-cache` 的全局快取。
6.  **數據持久化 (DuckDB Integration)**：
    *   所有成功獲取並處理的數據都會通過 UPSERT（插入或更新）操作存入名為 `permanent_financial_data.duckdb` 的 DuckDB 資料庫文件中。
    *   表結構為 `historical_ohlcv (date TIMESTAMP, symbol VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT, interval VARCHAR, PRIMARY KEY (symbol, interval, date))`。

## **四、 檔案目錄結構**

```
.
├── .gitignore
├── README.md
├── config.yml
├── poetry.lock
├── pyproject.toml
├── _test_run.py # 核心功能與引擎驗證腳本
├── permanent_api_cache.sqlite # requests-cache 快取檔案 (如果運行過引擎)
├── permanent_financial_data.duckdb # DuckDB 資料庫檔案 (如果運行過引擎)
├── apps
│   ├── ... (其他微應用)
├── core
│   ├── __init__.py
│   ├── clients
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── yfinance.py # (及其他特定API客戶端)
│   ├── config.py
│   ├── constants.py
│   ├── db
│   │   ├── __init__.py
│   │   └── db_manager.py
│   ├── engines # <--- 新增引擎目錄
│   │   ├── __init__.py
│   │   └── robust_acquisition_engine.py # <--- 核心數據獲取引擎
│   ├── logger.py
│   └── utils
│       ├── __init__.py
│       └── path_utils.py
├── pytest.ini
└── tests
    ├── ... (測試目錄結構)
```

## **五、 環境設定與啟動**

本專案使用 [Poetry](https://python-poetry.org/) 進行依賴管理。

1.  **安裝 Poetry**：參考 [Poetry 官方文檔](https://python-poetry.org/docs/#installation)。
2.  **配置 Poetry (推薦)**：`poetry config virtualenvs.in-project true`
3.  **安裝依賴**：在專案根目錄執行 `poetry install`。
    *   此操作會安裝 `pyproject.toml` 中定義的所有依賴，包括主依賴和開發依賴。
    *   核心運行時依賴包括：`pandas`, `numpy`, `pandas-ta`, `yfinance=="0.2.60"`, `aiohttp`, `psutil`, `pybreaker`, `duckdb`, `requests-cache`, `urllib3<2.0`, `pyarrow` 等。
4.  **啟動虛擬環境**：
    *   `poetry shell` (推薦，啟動一個已激活虛擬環境的新 shell)
    *   或 `poetry run <command>` (在現有 shell 中運行單個指令)

## **六、 運行核心引擎驗證**

提供了一個驗證腳本 `_test_run.py` 用於測試 `RobustDataAcquisitionEngine` 的核心功能。

**執行驗證：**
確保虛擬環境已激活，然後在專案根目錄運行：
```bash
poetry run python _test_run.py
```

此腳本將執行以下操作：
1.  清理舊的資料庫和API快取檔案（如果存在）。
2.  初始化 `RobustDataAcquisitionEngine` 並執行第一次數據獲取（應從網路）。
3.  再次執行數據獲取（理論上應測試快取，但受限於 `yfinance` 與自訂 `session` 的兼容性，快取效果依賴 `yfinance` 內部機制）。
4.  測試手動清除 `requests-cache` 快取並重新獲取單個股票數據。
5.  從 DuckDB 資料庫中查詢並打印已儲存數據的摘要。

觀察腳本輸出，確認智慧降級、併發獲取、數據處理、錯誤處理及資料庫寫入是否符合預期。

## **七、 注意事項與已知限制**

*   **`requests-cache` 與 `yfinance` 的兼容性**：如前所述，由於 `yfinance` 目前版本 (0.2.60) 的內部改動（可能涉及 `curl_cffi` 的使用）並建議不傳遞自訂 `session`，`requests-cache` 的 HTTP 層級快取和重試策略無法直接應用於 `yfinance` 的數據下載。引擎的快取效果依賴 `yfinance` 自身的（如果存在且啟用）快取行為。
*   **`force_recache` 的實現**：由於上述原因，`force_recache` 方法目前是通過清除 `requests-cache` 的全局快取來實現的。這對於不使用該 `session` 的 `yfinance` 請求，其強制重新獲取的效果有限。

## **八、 未來展望**

此 `RobustDataAcquisitionEngine` 為後續的數據分析、因子計算、策略回測等高級功能奠定了堅實的數據基礎。未來的開發可以集中在：
*   擴展更多數據源的客戶端。
*   完善數據清洗與驗證層。
*   開發更複雜的因子計算模組。
*   整合高效的回測與投資組合優化工具。

```
