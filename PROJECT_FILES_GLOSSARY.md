# **【普羅米修斯之火】專案檔案詞彙表 (v0.7.0)**

本文件旨在提供一份專案的內部解剖圖，詳細說明每個關鍵檔案與目錄的功能、職責與它們之間的協同工作關係。

## **一、 根目錄 (Root Directory)**

-   `README.md`: **專案的門戶**。提供專案的整體介紹、核心能力、快速上手指南和開發規範。是新成員了解專案的第一站。
-   `run.py`: **統一作戰指揮中心**。使用 `Typer` 建立的命令列介面 (CLI) 入口。所有核心的數據管線與應用程式，都應註冊於此，由它統一調度與執行。
-   `config.yml`: **專案的中央神經系統**。集中管理所有需要靈活配置的參數，如 API 金鑰、資料庫路徑等。嚴禁包含任何敏感資訊的版本被提交。
-   `pyproject.toml`: **專案的身份證與依賴清單**。使用 `Poetry` 管理，定義了專案的元數據、核心依賴與開發依賴。是專案環境可重複性的唯一真理來源。
-   `poetry.lock`: **依賴的精確藍圖**。由 `Poetry` 自動生成，鎖定了每個依賴包的精確版本，確保所有開發者環境的一致性。
-   `pytest.ini`: `pytest` 測試框架的設定檔。
-   `mypy.ini`: `mypy` 型別檢查工具的設定檔。
-   `run_tests.py`: 執行自動化測試的腳本。
-   `run_pipeline.sh`: 執行資料管線的腳本。
-   `_test_run.py`: 用於執行臨時測試的腳本。

## **二、 `core/` - 核心引擎與共享工具**

此目錄是專案的心臟，提供了所有上層應用與管線所需的底層能力。

-   `core/clients/`: **外交使團**。
    -   **職責**: 負責與所有外部第三方 API 進行通訊。每個客戶端都封裝了特定數據源（如 YFinance, FRED）的請求、認證和數據解析邏輯。
    -   **數據流**: 將從外部 API 獲取的原始數據（通常是 JSON 或 DataFrame）傳遞給調用它的模組（主要是 `extract.py`）。
-   `core/db/db_manager.py`: **中央數據庫管理員**。
    -   **職責**: 封裝了所有與 `DuckDB` 數據庫的互動邏輯。提供了如 `write_dataframe` 等標準化接口，簡化了數據的讀寫操作。
    -   **數據流**: 接收來自 `load.py` 模組的 DataFrame 並將其寫入磁碟上的數據庫檔案；或被 `run.py` 中的應用讀取數據。
-   `core/utils/caching.py`: **高效的記憶體**。
    -   **職責**: 提供基於 `requests-cache` 的網路請求快取機制。
    -   **數據流**: 在 `extract.py` 模組中被用於快取來自 API 的原始數據，避免在開發和測試中重複下載，大幅提高效率。
-   `core/config.py`: **設定檔的管理模組**。
-   `core/constants.py`: **定義專案中使用的常數**。
-   `core/logger.py`: **日誌記錄模組**。
-   `core/analysis/`: **分析工具**。
    -   `data_engine.py`: **資料引擎**，負責提供和管理分析數據。
    -   `stress_index.py`: **壓力指數的計算邏輯**。
-   `core/analyzers/`: **分析器**。
    -   `base_analyzer.py`: **分析器的基底類別**。
-   `core/engines/`: **引擎**。
    -   `robust_acquisition_engine.py`: **提供穩健的數據獲取功能**。
-   `core/pipelines/`: **資料管線的核心組件**。
    -   `base_step.py`: **管線步驟的基底類別**。
    -   `pipeline.py`: **管線的核心邏輯**。
    -   `steps/`: **包含各個管線步驟的實作**。
-   `core/utils/`: **共用的工具函式**。
    -   `path_utils.py`: **路徑處理工具**。

## **三、 `pipelines/` - 數據處理與轉化管線**

此目錄是專案的工業區，負責將原始數據轉化為高價值的結構化資訊。

### **`pipelines/p0_downloader/` - 原始資料下載管線**
-   `run.py`: **執行原始資料的下載**。

### **`pipelines/p1_explorer/` - 資料探索管線**
-   `run.py`: **執行資料的探索與初步分析**。

### **`pipelines/p2_elt_pipeline/` - ELT 管線**
-   `run_elt.py`: **執行 ELT (抽取、載入、轉換) 流程**。

### **`pipelines/p3_backfill_hourly_data/` - 小時級歷史資料回填管線**
-   `run.py`: **執行小時級歷史資料的回填**。

### **`pipelines/p4_daily_macro_etl/` - 日線宏觀數據管線**
-   **戰術角色**: 負責建立宏觀經濟的背景視圖。
-   `run_etl.py`: **管線總指揮**。協調下屬三個模組，執行完整的 ETL 流程。
-   `extract.py`: **宏觀情報蒐集官**。
    -   **輸入**: 無。
    -   **輸出**: 一個包含多個來自 FRED 的原始宏觀經濟數據 DataFrame 的字典。
    -   **依賴**: `core/clients/fred.py`。
-   `transform.py`: **數據標準化處理廠**。
    -   **輸入**: `extract.py` 輸出的原始數據字典。
    -   **輸出**: 一個以日期為索引、經過整合與清洗的單一 DataFrame。
-   `load.py`: **宏觀數據庫管理員**。
    -   **輸入**: `transform.py` 輸出的 DataFrame。
    -   **輸出**: 將數據寫入名為 `daily_macro_market_data` 的數據表。

### **`pipelines/p5_hourly_price_etl/` - 小時級市場數據管線**
-   **戰術角色**: 專案的核心數據引擎，負責構建高精度、多維度的市場數據。
-   `run_etl.py`: **管線總指揮**。
    -   **職責**: 根據 `--mode` 參數（`backfill` 或 `update`）協調下屬模組，執行小時級數據的獲取與存儲。
    -   **數據流**: 依序調用 `extract`, `transform`, `load` 模組。
-   `extract.py`: **高頻行情接收器**。
    -   **角色定位**: 情報蒐集官，負責從市場前線獲取最即時的價格情報。
    -   **輸入**: `mode` 參數（`backfill` 或 `update`）。
    -   **輸出**: 一個字典，鍵為資產代號，值為其對應的原始小時線 OHLCV DataFrame。
    -   **外部依賴**: `core/clients/yfinance.py`, `core/utils/caching.py`。
-   `transform.py`: **數據精煉與特徵工程中心**。
    -   **角色定位**: 數據精煉廠與軍工廠，不僅清洗數據，還負責生產高價值的衍生指標。
    -   `run_transformation()`:
        -   **輸入**: `extract.py` 輸出的原始數據字典。
        -   **輸出**: 一個扁平化、以時間為索引的單一 DataFrame，包含所有資產的基礎價格數據。
    -   `calculate_technical_indicators()`:
        -   **輸入**: 包含基礎價格數據的 DataFrame。
        -   **輸出**: 一個欄位極大豐富的 DataFrame，新增了數十種技術指標。
    -   `calculate_options_derived_metrics()`:
        -   **輸入**: 包含價格與技術指標的 DataFrame。
        -   **輸出**: 一個僅包含 SPY 選擇權衍生指標的 DataFrame。
-   `load.py`: **軍火庫管理員**。
    -   **角色定位**: 負責將精煉後的數據資產，安全、準確地存入我們的中央軍火庫（數據庫）。
    -   `run_load()`:
        -   **輸入**: `transform.run_transformation()` 輸出的 DataFrame 和 `mode` 參數。
        -   **輸出**: 將基礎價格數據以「替換」或「附加」模式寫入 `hourly_market_data` 表。
    -   `overwrite_data_with_indicators()`:
        -   **輸入**: `transform.calculate_technical_indicators()` 輸出的 DataFrame。
        -   **輸出**: 以「替換」模式，用包含技術指標的數據覆蓋 `hourly_market_data` 表。
    -   `merge_and_overwrite_with_options_metrics()`:
        -   **輸入**: 原始的數據 DataFrame 和選擇權指標 DataFrame。
        -   **輸出**: 將兩者合併後，以「替換」模式覆蓋 `hourly_market_data` 表。

## **四、 `apps/` - 終端應用程式**

此目錄是我們數據價值的最終體現，將後端的複雜計算轉化為可用的產品。

### **`apps/dashboard/` - 互動式市場儀表板**
-   **戰術角色**: **作戰情報中心 (CIC)**，將所有關鍵數據以最直觀的方式呈現給指揮官。
-   `run_app.py`: **儀表板生成引擎**。
    -   **職責**: 負責整個儀表板的生成與顯示。
    -   **數據流**:
        1.  **讀取**: 從 `hourly_market_data` 數據庫讀取最完整的數據。
        2.  **轉換**: 使用 `Plotly` 將數據轉換為多個聯動的互動式圖表。
        3.  **輸出**: 生成一個名為 `market_dashboard.html` 的獨立 HTML 檔案到 `output/` 目錄，並自動在瀏覽器中打開。
    -   **外部依賴**: `core/db/db_manager.py`。

### **其他應用**
-   `apps/analysis_pipeline/run.py`: **執行資料分析管線**。
-   `apps/backtesting_engine/`: **回測引擎**。
    -   `engine.py`: **回測引擎的核心邏輯**。
    -   `run.py`: **執行回測**。
-   `apps/db_manager/setup_database.py`: **設定和初始化資料庫**。
-   `apps/factor_engine/`: **因子計算引擎**。
    -   `engine.py`: **因子計算引擎**。
    -   `run_factor_etl.py`: **執行因子數據的 ETL (抽取、轉換、載入) 流程**。
    -   `sma_crossover_factor.py`: **實現簡單移動平均線 (SMA) 交叉策略的因子**。
-   `apps/pipeline_metadata_manager/manager.py`: **管理和追蹤管線的元數據**。
-   `apps/portfolio_optimizer/main.py`: **投資組合優化器**。
-   `apps/report_generator/`: **報告產生器**。
    -   `generator.py`: **產生回測或分析報告**。
    -   `run.py`: **執行報告產生**。
-   `apps/visualization/plot_sma_crossover.py`: **將 SMA 交叉策略的結果可視化**。
-   `apps/run_finmind_test.py`: **測試 `FinMind` API 客戶端**。
-   `apps/run_fmp_test.py`: **測試 `FMP` API 客戶端**。
-   `apps/run_gold_layer.py`: **執行黃金層數據處理**。
-   `apps/run_stress_index.py`: **計算和分析壓力指數**。
-   `apps/run_taifex_prototype_test.py`: **測試台交所數據原型**。

## **五、 `data/` - 數據儲存**
-   `financial_data.db`: **DuckDB 數據庫檔案**。

## **六、 `output/` - 輸出**
-   `market_dashboard.html`: **互動式市場儀表板的 HTML 檔案**。
-   `logs/`: **存放日誌檔案**。
    -   `archive/`: **歸檔的作戰報告**。
    -   `session.sqlite`: **當前工作階段的日誌數據庫**。
    -   `standalone_test.sqlite`: **獨立測試的日誌數據庫**。

## **七、 `tests/` - 自動化測試**
-   `conftest.py`: **`pytest` 的設定檔，用於定義 fixtures**。
-   `fixtures/`: **存放測試用的靜態檔案**。
-   `ignition_test.py`: **點火測試，確保專案的基本設定正確**。
-   `integration/`: **整合測試**。
-   `unit/`: **單元測試**。
-   `test_p0_downloader.py`: **測試 `p0_downloader` 管線**。
-   `test_p1_explorer.py`: **測試 `p1_explorer` 管線**。
-   `test_p2_elt_pipeline.py`: **測試 `p2_elt_pipeline` 管線**。
-   `unit/test_feature_analyzer.py`: **測試特徵分析器**。
