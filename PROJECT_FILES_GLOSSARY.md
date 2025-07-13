# **【普羅米修斯之火】專案檔案詞彙表 (v0.7.0)**

本文件旨在提供一份專案的內部解剖圖，詳細說明每個關鍵檔案與目錄的功能、職責與它們之間的協同工作關係。

## **一、 根目錄 (Root Directory)**

-   `README.md`: **專案的門戶**。提供專案的整體介紹、核心能力、快速上手指南和開發規範。是新成員了解專案的第一站。
-   `run.py`: **統一作戰指揮中心**。使用 `Typer` 建立的命令列介面 (CLI) 入口。所有核心的數據管線與應用程式，都應註冊於此，由它統一調度與執行。
-   `config.yml`: **專案的中央神經系統**。集中管理所有需要靈活配置的參數，如 API 金鑰、資料庫路徑等。嚴禁包含任何敏感資訊的版本被提交。
-   `pyproject.toml`: **專案的身份證與依賴清單**。使用 `Poetry` 管理，定義了專案的元數據、核心依賴與開發依賴。是專案環境可重複性的唯一真理來源。
-   `poetry.lock`: **依賴的精確藍圖**。由 `Poetry` 自動生成，鎖定了每個依賴包的精確版本，確保所有開發者環境的一致性。

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

## **三、 `pipelines/` - 數據處理與轉化管線**

此目錄是專案的工業區，負責將原始數據轉化為高價值的結構化資訊。

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
