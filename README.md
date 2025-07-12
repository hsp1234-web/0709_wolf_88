# **【普羅米修斯之火】金融數據與分析框架 - 開發者手冊 v0.7.0**

## **一、 專案概覽與目的**

【普羅米修斯之火】是一個專為進階量化研究與金融市場分析而設計的 Python 框架。本專案旨在提供一個從多樣化數據源獲取金融數據、進行複雜指標計算、回測交易策略、並將結果視覺化的完整解決方案。其核心設計強調模組化、可擴展性以及數據處理的穩健性。

**最近更新 (作戰計畫 032 & 033):**
*   **FMPClient 實戰驗證**: 成功整合並執行了 `FMPClient` 的端到端測試，驗證了獲取真實市場數據（如歷史股價）的能力。
*   **FinMindClient 實戰驗證**: 成功整合並執行了 `FinMindClient` 的端到端測試，驗證了獲取台灣市場特定數據（如三大法人買賣超）的能力。
*   **配置與腳本標準化**: 建立了標準化的 API 金鑰配置與驗證腳本執行流程，為未來新增數據客戶端奠定了基礎。

## **二、 技術棧 (Technology Stack)**

*   **核心程式語言:** Python (>=3.12, <3.14)
*   **依賴管理:** Poetry (v1.8.2 或相容版本)
*   **數據處理:**
    *   Pandas (`^2.3.1`)
    *   NumPy (`<2.0`)
    *   Pandas-TA (`0.3.14b0`)
*   **API 客戶端與網路請求:**
    *   Requests (`^2.32.4`)
    *   Requests-Cache (`^1.2.1`)
    *   FredAPI (`^0.5.2`)
    *   YFinance (`0.2.60`)
*   **資料庫**:
    *   DuckDB (`^1.3.2`)
*   **設定檔管理:**
    *   PyYAML (`^6.0.2`)
*   **視覺化**:
    *   Plotly (`^6.2.0`)
*   **測試與品質保證:**
    *   Pytest (`^8.4.1`)
    *   Pytest-Mock (`^3.14.1`)
    *   Ruff (用於程式碼檢查與格式化)

## **三、 檔案目錄結構**

以下為專案目前的檔案目錄結構 (已移除 `__pycache__` 和臨時檔案)：

```
.
├── apps
│   ├── analysis_pipeline
│   │   └── run.py
│   ├── backtesting_engine
│   │   ├── engine.py
│   │   └── run.py
│   ├── db_manager
│   │   └── setup_database.py
│   ├── factor_engine
│   │   ├── engine.py
│   │   ├── run_factor_etl.py
│   │   └── sma_crossover_factor.py
│   ├── pipeline_metadata_manager
│   │   └── manager.py
│   ├── portfolio_optimizer
│   │   └── main.py
│   ├── report_generator
│   │   ├── generator.py
│   │   └── run.py
│   ├── visualization
│   │   └── plot_sma_crossover.py
│   ├── run_fmp_test.py
│   ├── run_finmind_test.py
│   ├── run_gold_layer.py
│   └── run_stress_index.py
├── core
│   ├── analysis
│   │   ├── data_engine.py
│   │   └── stress_index.py
│   ├── analyzers
│   │   └── base_analyzer.py
│   ├── clients
│   │   ├── base.py
│   │   ├── finmind.py
│   │   ├── fmp.py
│   │   ├── fred.py
│   │   ├── nyfed.py
│   │   ├── taifex_db.py
│   │   └── yfinance.py
│   ├── db
│   │   └── db_manager.py
│   ├── engines
│   │   └── robust_acquisition_engine.py
│   ├── pipelines
│   │   ├── base_step.py
│   │   ├── pipeline.py
│   │   └── steps
│   ├── config.py
│   ├── constants.py
│   └── logger.py
├── output
│   ├── sma_crossover_chart.html
│   └── sma_crossover_result.csv
├── pipelines
│   ├── p0_downloader
│   │   └── run.py
│   ├── p1_explorer
│   │   └── run.py
│   ├── p2_elt_pipeline
│   │   └── run_elt.py
│   └── p3_backfill_hourly_data
│       └── run.py
├── tests
│   ├── fixtures
│   │   ├── corrupted.zip
│   │   ├── no_data_response.html
│   │   └── sample_daily_ohlc_20250711.zip
│   ├── integration
│   │   ├── analysis
│   │   ├── apps
│   │   └── pipelines
│   └── unit
│       ├── analysis
│       └── core
├── config.yml
├── poetry.lock
├── pyproject.toml
└── README.md
```

## **四、 環境設定與執行**

本專案使用 [Poetry](https://python-poetry.org/) 進行依賴管理。

1.  **安裝 Poetry** (如果尚未安裝)。
2.  **克隆專案**。
3.  **配置 Poetry 虛擬環境** (推薦 `poetry config virtualenvs.in-project true`)。
4.  **安裝依賴**: `poetry install`。
5.  **激活虛擬環境**: `poetry shell` (或使用 `poetry run <command>`)。
6.  **設定 API 金鑰**:
    *   為了運行所有數據獲取功能，您**必須**在 `config.yml` 中提供有效的 API 金鑰/Token。
        ```yaml
        # In config.yml
        api_keys:
          fred: "YOUR_REAL_FRED_API_KEY_HERE"
          fmp: "YOUR_REAL_FMP_API_KEY_HERE"
          finmind: "YOUR_REAL_FINMIND_API_TOKEN_HERE"
        ```
    *   ⚠️ **安全警告**：`config.yml` 檔案包含敏感金鑰，**絕對不可**提交到任何版本控制系統（如 Git）。請確保它已被列在 `.gitignore` 檔案中。

## **五、 主要功能執行與測試**

### **5.1 數據客戶端實戰驗證**

這些腳本用於驗證各個數據客戶端與真實 API 的連通性。請確保已在 `config.yml` 中設定對應的金鑰。

1.  **驗證 FRED & NYFED (壓力指數)**:
    ```bash
    poetry run python apps/run_stress_index.py
    ```
2.  **驗證 FMP (以獲取 Apple 股價為例)**:
    ```bash
    poetry run python apps/run_fmp_test.py
    ```
3.  **驗證 FinMind (以獲取台積電三大法人買賣超為例)**:
    ```bash
    poetry run python apps/run_finmind_test.py
    ```

### **5.2 數據回填與快取**

此管線用於填充 DuckDB 資料庫，供其他模組使用。

*   **執行數據回填**:
    ```bash
    poetry run python pipelines/p3_backfill_hourly_data/run.py
    ```
*   **說明**: 此腳本會使用 `YFinanceClient` (無需金鑰) 獲取 SPY 的小時級數據，並存儲在根目錄的 `prometheus_fire.duckdb` 檔案中。

### **5.3 執行 SMA 策略回測與視覺化**

這是一個完整的無金鑰工作流程，用於驗證因子計算、回測和視覺化功能。

1.  **計算因子並執行回測**:
    ```bash
    poetry run python apps/backtesting_engine/run.py
    ```
    *   **說明**: 此腳本會從 DuckDB 讀取數據，計算 SMA 交叉信號，執行回測，打印績效報告，並將詳細結果儲存到 `output/sma_crossover_result.csv`。

2.  **生成視覺化圖表**:
    ```bash
    poetry run python apps/visualization/plot_sma_crossover.py
    ```
    *   **說明**: 此腳本會讀取上一步生成的 CSV 檔案，並在 `output` 目錄下創建一個名為 `sma_crossover_chart.html` 的互動式圖表。

### **5.4 測試**
*   **運行所有測試**:
    ```bash
    poetry run pytest
    ```
*   **目前測試狀態**: 109 個通過, 16 個跳過 (基於最近一次完整測試運行)。

## **六、 版本歷史與變更日誌**

### **v0.7.0 (對應作戰計畫 033)**
*   **功能驗證**:
    *   **FinMindClient**: 成功執行了端到端的實戰驗證，確認可獲取台灣市場數據。
*   **新增功能**:
    *   新增 `apps/run_finmind_test.py` 作為 FinMindClient 的標準驗證腳本。
*   **配置**:
    *   在 `config.yml` 中新增 `finmind` API Token 的配置項。

### **v0.6.0 (對應作戰計畫 032)**
*   **功能驗證**:
    *   **FMPClient**: 成功執行了端到端的實戰驗證，確認可獲取美國市場股價數據。
*   **新增功能**:
    *   新增 `apps/run_fmp_test.py` 作為 FMPClient 的標準驗證腳本。
*   **配置**:
    *   在 `config.yml` 中新增 `fmp` API Key 的配置項。
*   **修復**:
    *   修正了驗證腳本中 `config` 模組的導入方式，從 `load_config` 函數改為直接使用 `config` 實例。

### **v0.5.0 (對應作戰計畫 031)**
*   **功能驗證**:
    *   **壓力指數**: 成功執行了端到端的壓力指數計算，驗證了 `FredClient` 和 `NYFedClient` 在真實 API 環境下的功能。
*   **修復與改進**:
    *   `apps/run_stress_index.py`: 添加了路徑校正樣板碼，解決了模組導入錯誤。
    *   `core/pipelines/steps/financial_steps.py`: 重構了 `CalculateStressIndexStep`，使其能夠調用 `StressIndexCalculator` 並返回真實的計算結果。
    *   `apps/run_stress_index.py`: 更新了主函數以正確解析和打印計算出的壓力指數值。

### **v0.4.0 (先前版本)**
*   引入了回測引擎，建立了 SMA 交叉策略的回測管線，並修復了多個測試問題。

## **七、 已知限制與技術債務**

*   **Fixture 檔案遺失**: `tests/fixtures/sample_options_delta_20250711.csv` 檔案缺失，導致依賴此檔案的兩個整合測試被暫時跳過。
*   **`FredClient` 應急快取**: `core/clients/fred.py` 中的 `_emergency_cache` 是一個臨時解決方案，用以確保整合測試的通過。
*   **測試覆蓋率**: 雖然進行了大量修復，但整體測試覆蓋率仍有提升空間。

## **八、 開發者指引**
*   遵循 PEP 8 程式碼風格。
*   所有程式碼註解、日誌訊息和終端機輸出均使用**繁體中文**。
*   嚴禁在程式碼中硬編碼任何 API 金鑰或敏感資訊。所有配置應透過 `config.yml` 管理。
*   在提交程式碼前，請務必運行 `poetry run pytest` 確保沒有引入新的迴歸問題。

歡迎開發者們一同參與【普羅米修斯之火】的建設！
