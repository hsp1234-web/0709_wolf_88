# **【普羅米修斯之火】檔案功能詞彙表**

本文件旨在詳細說明專案中各個關鍵檔案的功能與職責，以幫助開發者快速理解專案結構與程式碼邏輯。

---

## **根目錄 (`./`)**

### `_test_run.py`
*   **類型**: 全功能整合測試腳本 (手動執行)。
*   **功能**: 此腳本提供了一個端到端 (End-to-End) 的功能驗證流程，用於測試 `RobustDataAcquisitionEngine` 的核心能力。
*   **執行邏輯**:
    1.  定義一個包含多種金融商品代碼 (包括有效和無效代碼) 的目標列表。
    2.  在執行前，自動清理舊的資料庫 (`prometheus_fire.duckdb`) 和 API 快取檔案，以確保測試環境的純淨性。
    3.  **第一次執行**: 初始化引擎並運行，此時應從網路獲取數據，並將結果寫入永久快取和 DuckDB 資料庫。
    4.  **第二次執行**: 再次運行引擎，此時應直接從快取中讀取數據，執行速度會非常快，用以驗證快取機制是否生效。
    5.  **快取清除測試**: 手動清除特定商品 (如 'AAPL') 的快取，並驗證引擎能否重新從網路獲取該商品的數據。
    6.  **最終驗證**: 從 DuckDB 資料庫中查詢所有數據，匯總並打印，以確認數據已成功且正確地儲存。
*   **目的**: 作為一個比自動化 `pytest` 更全面的手動驗證工具，用於在重大變更後，快速驗證整個數據獲取 -> 快取 -> 存儲的鏈路是否通暢。

---

## **應用層 (`apps/`)**

### `apps/analysis_pipeline/run.py`
*   **類型**: 分析管線執行器 (歷史版本)。
*   **功能**: 作為一個早期的分析任務調度器，主要用於執行特定的因子計算任務。
*   **執行邏輯**:
    1.  使用 `argparse` 解析命令列參數，允許使用者指定要運行的因子名稱 (預設為 `sma_crossover`)。
    2.  根據傳入的因子名稱，呼叫對應的因子計算函式 (例如 `calculate_sma_crossover`)。
    3.  將計算出的因子結果儲存到 `output/` 目錄下的 CSV 檔案中。
*   **現狀 (v0.6.0)**: 此腳本的功能已被整合至根目錄的 `run.py` 中，並由 `sma-backtest` 等子命令觸發其核心邏輯。此檔案本身已不作為主要入口，但其內部的業務邏輯（如呼叫 `calculate_sma_crossover`）仍被複用。

### `apps/backtesting_engine/engine.py`
*   **類型**: 核心回測引擎類別。
*   **功能**: 提供一個簡單的向量化回測器 (`Backtester` 類)，用於評估交易策略的歷史績效。
*   **核心組件 (`Backtester` 類)**:
    *   `__init__`: 初始化函式，接收價格序列 (`price_series`)、信號序列 (`signal_series`) 和初始資金。
    *   `run()`: 核心回測方法。它將價格和信號合併，計算每日的策略報酬率，並最終生成一條資產淨值曲線 (`cumulative_returns`)。
    *   `get_performance_metrics()`: 績效計算方法。在 `run()` 執行完畢後呼叫，用於計算一系列關鍵績效指標 (KPIs)，如總回報率、夏普比率和最大回撤。
*   **目的**: 將回測的複雜計算邏輯封裝起來，使得上層的執行腳本 (如 `apps/backtesting_engine/run.py`) 可以用更簡潔的方式調用回測功能。

### `apps/backtesting_engine/run.py`
*   **類型**: SMA 策略回測應用主執行腳本。
*   **功能**: 完整地執行一個「SMA 簡單移動平均線交叉策略」的回測流程。
*   **執行邏輯**:
    1.  **獲取信號**: 呼叫因子引擎 (`apps/factor_engine/sma_crossover_factor.py`) 中的 `calculate_sma_crossover` 函式，獲取基於 SMA 交叉策略生成的買賣信號。
    2.  **初始化引擎**: 將獲取到的價格序列和信號序列傳入 `Backtester` 類，創建一個回測器實例。
    3.  **執行回測**: 呼叫回測器實例的 `run()` 方法。
    4.  **計算並展示績效**: 呼叫 `get_performance_metrics()` 方法，並將結果打印到終端機。
    5.  **儲存結果**: 將包含價格、信號和回測結果的詳細數據儲存到 `output/sma_crossover_result.csv`，以供後續的視覺化分析使用。
*   **現狀 (v0.6.0)**: 此腳本的 `main` 函式現在由根目錄 `run.py` 的 `sma-backtest` 命令進行調度。

### `apps/db_manager/setup_database.py`
*   **類型**: 資料庫結構 (Schema) 初始化腳本。
*   **功能**: 用於建立和設定專案所需的核心資料庫表格。
*   **執行邏輯**:
    1.  定義一個 DuckDB 資料庫檔案的名稱 (`prometheus_fire.duckdb`)。
    2.  包含一個非常長的 SQL `CREATE TABLE IF NOT EXISTS` 指令，用於定義 `hourly_time_series` 表格的完整結構，該表格旨在儲存所有小時級別的金融時間序列數據。
    3.  包含一個 `COMMENT ON TABLE` 指令，為表格添加註解。
    4.  `setup_database()` 函式會連接到資料庫，執行上述的建表和加註解的 SQL 指令，並在最後驗證表格是否成功建立。
*   **目的**: 提供一個可重複執行的、標準化的方式來初始化專案的數據倉庫，確保所有下游應用都有一個一致的數據庫結構可以使用。

### `apps/factor_engine/run_factor_etl.py`
*   **類型**: 因子計算 ETL (提取、轉換、加載) 流程主執行腳本。
*   **功能**: 作為一個複雜的 ETL 工作流，負責從數據庫中提取原始價格數據，計算多種技術因子和宏觀經濟因子，並將計算結果存回資料庫。
*   **執行邏輯**:
    1.  **提取 (Extract)**: 連接到資料庫，查詢 `MarketPrices_Daily` 表格以獲取所有股票代碼 (`ticker`)。
    2.  **轉換 (Transform)**:
        *   對於每一個 `ticker`，讀取其完整的價格歷史。
        *   呼叫 `FactorEngine` 中的方法，計算多種技術指標，如歷史波動率 (hv_20d)、成交量波動率、RSI 等。
        *   獨立計算宏觀因子，如殖利率曲線利差 (`spread_10y_2y`) 和信用利差代理指標 (`HYG_LQD_price_ratio`)。
        *   將所有計算出的因子數據（無論是個股的還是宏觀的）轉換為標準的「長表」格式 (`ticker`, `date`, `factor_name`, `factor_value`)。
    3.  **加載 (Load)**: 將所有轉換好的因子數據合併成一個大的 DataFrame，並將其寫入到 `FactorStore_Daily` 表格中。
*   **現狀 (v0.6.0)**: 此腳本已被重構，其 `run_etl` 函式會接收一個 `log_manager` 參數，並使用其進行日誌記錄。

### `apps/factor_engine/sma_crossover_factor.py`
*   **類型**: 特定因子計算模組。
*   **功能**: 專門用於計算「簡單移動平均線 (SMA) 交叉」策略所需的交易信號。
*   **執行邏輯**:
    1.  初始化 `DataEngine`。
    2.  使用 `DataEngine` 獲取指定股票 (預設為 'spy') 的小時級收盤價。
    3.  使用 `pandas` 的 `rolling().mean()` 方法計算短期 (預設 20 小時) 和長期 (預設 50 小時) 的移動平均線。
    4.  比較短期和長期 SMA，產生持倉信號 (`position`，1 為多頭，0 為空倉/中性)。
    5.  計算 `position` 的變化，產生交易信號 (`signal`，+1 為黃金交叉買入點，-1 為死亡交叉賣出點)。
    6.  返回一個包含價格、SMA 線、持倉和交易信號的完整 DataFrame。
*   **目的**: 將一個具體的因子計算邏輯封裝成一個獨立、可複用的函式，供其他應用 (如回測引擎) 調用。

### `apps/pipeline_metadata_manager/manager.py`
*   **類型**: 檔案處理元數據管理器。
*   **功能**: 提供了一個 `MetadataManager` 類，用於追蹤哪些檔案已經被處理過，以避免重複處理。
*   **執行邏輯**:
    1.  **指紋計算**: 提供 `calculate_file_fingerprint()` 函式，使用 SHA-256 算法計算檔案的唯一雜湊值。
    2.  **資料庫互動**: `MetadataManager` 類會連接到一個指定的資料庫 (例如 `pipeline_metadata.duckdb`)。
    3.  **檢查與寫入**:
        *   `check_fingerprint_exists()`: 查詢資料庫，檢查某個檔案的指紋是否已經存在。
        *   `write_fingerprint()`: 將新的檔案指紋，連同檔名、大小、處理時間等元數據，寫入到資料庫中。
*   **目的**: 在數據導入或 ETL 流程中，作為一個檢查點，確保同一份原始檔案不會被重複處理多次，保證數據的一致性和處理效率。
*   **現狀 (v0.6.0)**: 已被重構為接收 `log_manager` 參數。

### `apps/portfolio_optimizer/main.py`
*   **類型**: 投資組合優化器 (模擬)。
*   **功能**: 一個模擬的投資組合優化應用。
*   **執行邏輯**: 此檔案目前只包含一個 `run_optimization` 函式，它會記錄開始和結束的日誌訊息，並返回一個成功的狀態。它旨在作為一個佔位符，未來可以整合真正的投資組合優化庫 (如 `pypfopt`)。
*   **現狀 (v0.6.0)**: 已被重構為接收 `log_manager` 參數。

### `apps/report_generator/generator.py`
*   **類型**: 核心報告生成器。
*   **功能**: 提供 `ReportGenerator` 類，負責從資料庫獲取數據，並使用 `Plotly` 生成包含 K 線圖和交易信號的視覺化 HTML 報告。
*   **執行邏輯**:
    1.  `_fetch_data`: 從資料庫中獲取指定股票在特定時間範圍內的 OHLCV 數據、Chimera 信號數據以及 P/C Ratio 數據。
    2.  `_plot_report_plotly`: 使用 `Plotly` 的 `make_subplots` 創建一個多子圖的圖表，包含 K 線圖、成交量圖，並在 K 線圖上標記買賣信號點。如果 P/C Ratio 數據可用，還會繪製其趨勢圖。
    3.  `generate_report`: 作為公開方法，協調以上所有步驟，並將最終生成的圖表儲存為 HTML 檔案。
*   **目的**: 將數據獲取、圖表繪製和檔案儲存的複雜邏輯封裝起來，提供一個簡單的介面來生成標準化的分析報告。
*   **現狀 (v0.6.0)**: 已被重構為接收 `log_manager` 參數。

### `apps/report_generator/run.py`
*   **類型**: 報告生成器應用主執行腳本。
*   **功能**: 提供一個命令列介面，讓使用者可以指定股票代碼、日期範圍等參數來生成報告。
*   **執行邏輯**:
    1.  使用 `argparse` 解析命令列參數。
    2.  根據參數初始化 `ReportGenerator` 類。
    3.  呼叫 `generate_report` 方法來執行報告的生成和儲存。
*   **現狀 (v0.6.0)**: 此腳本的 `main` 函式已被重構為接收 `log_manager` 參數，但尚未整合到根目錄的 `run.py` 中。

### `apps/visualization/plot_sma_crossover.py`
*   **類型**: 特定視覺化腳本。
*   **功能**: 專門用於讀取 `sma_crossover_result.csv` 檔案，並將其內容視覺化為一個互動式的 Plotly 圖表。
*   **執行邏輯**:
    1.  讀取由 `apps/backtesting_engine/run.py` 生成的 CSV 檔案。
    2.  使用 `Plotly` 繪製 SPY 收盤價、短期 SMA 和長期 SMA 的線圖。
    3.  從數據中找出交易信號點 (黃金交叉和死亡交叉)，並在圖表上用三角形標記出來。
    4.  將最終的圖表儲存為 `output/sma_crossover_chart.html`。
*   **目的**: 作為 SMA 策略回測流程的最後一步，提供結果的視覺化驗證。

### `apps/run_finmind_test.py`
*   **類型**: API 客戶端測試腳本 (手動)。
*   **功能**: 用於端到端地驗證 `FinMindClient` 是否能成功連接 FinMind API、傳遞參數並獲取數據。
*   **執行邏輯**:
    1.  從 `config.yml` 讀取 FinMind API Token。
    2.  初始化 `FinMindClient`。
    3.  嘗試獲取台積電 (`2330`) 最近的三大法人買賣超數據。
    4.  驗證返回的數據是否為非空的 DataFrame，並打印預覽。
*   **目的**: 在不運行完整 `pytest` 套件的情況下，快速驗證特定 API 客戶端的功能是否正常。

### `apps/run_fmp_test.py`
*   **類型**: API 客戶端測試腳本 (手動)。
*   **功能**: 用於端到端地驗證 `FMPClient` 是否能成功獲取 Financial Modeling Prep 的數據。
*   **執行邏輯**:
    1.  從 `config.yml` 讀取 FMP API 金鑰。
    2.  初始化 `FMPClient`。
    3.  嘗試獲取蘋果公司 (`AAPL`) 最近 5 筆的歷史日線價格。
    4.  驗證返回結果並打印預覽。
*   **目的**: 快速驗證 FMP API 客戶端的功能。

### `apps/run_gold_layer.py`
*   **類型**: 數據管線應用主執行腳本。
*   **功能**: 執行「黃金層 (Gold Layer)」數據的建構管線。
*   **執行邏輯**:
    1.  初始化一個 `DataPipeline`。
    2.  將 `BuildGoldLayerStep` 作為唯一的步驟傳入管線。
    3.  運行管線。
*   **目的**: 將一個特定的、可能很複雜的數據處理流程 (建立黃金層) 封裝成一個簡單的應用。
*   **現狀 (v0.6.0)**: 已被重構為接收 `log_manager` 參數，但尚未整合到根目錄的 `run.py` 中。

### `apps/run_stress_index.py`
*   **類型**: 核心分析應用主執行腳本。
*   **功能**: 執行「金融壓力指數」的計算管線。
*   **執行邏輯**:
    1.  初始化 `DataPipeline`。
    2.  將 `CalculateStressIndexStep` 作為步驟傳入管線。
    3.  運行管線，觸發壓力指數的完整計算流程。
    4.  打印最終的計算結果。
*   **現狀 (v0.6.0)**: 已被重構並整合到根目錄的 `run.py` 中，可透過 `run.py stress-index` 命令執行。

### `apps/run_taifex_prototype_test.py`
*   **類型**: 原型功能驗證腳本。
*   **功能**: 用於測試一個早期的、基於本地檔案系統的 `TaifexFileReader` 原型。
*   **執行邏輯**:
    1.  初始化 `TaifexFileReader`，並將其指向 `tests/fixtures/taifex_data` 目錄下的模擬數據。
    2.  分別呼叫 `read_put_call_ratio` 和 `read_delta` 方法，測試讀取兩種不同格式 (一個乾淨，一個需要跳過首行) 的 CSV 檔案。
    3.  打印讀取到的數據預覽。
*   **目的**: 在將新功能 (如讀取台期所數據) 正式整合到 `core/clients` 之前，進行快速的原型設計和驗證。

---

## **核心層 (`core/`)**

### `core/config.py`
*   **類型**: 設定管理模組。
*   **功能**: 提供一個單例模式的 `ConfigManager` 類，用於在專案的任何地方安全地讀取 `config.yml` 中的設定。
*   **執行邏輯**:
    1.  `ConfigManager` 類在第一次被實例化時，會讀取 `config.yml` 檔案並將其內容載入到一個類別層級的字典中。
    2.  之後的所有實例化請求都會返回同一個實例，避免重複讀取檔案。
    3.  `get()` 方法允許使用點分法 (`.`) 來安全地獲取巢狀的設定值 (例如 `api_keys.fred`)，並支持設定預設值。
    4.  提供一個專用的 `get_fred_api_key()` 輔助函式，增加了對金鑰是否存在和是否為預留位置的檢查。
*   **目的**: 將設定的讀取和訪問邏輯集中化，避免在程式碼中硬編碼設定值，並提供一個統一、安全的訪問介面。

### `core/logger.py`
*   **類型**: v82.0 精準指示器日誌系統。
*   **功能**: 提供 `LogManager` 類，作為整個專案的日誌記錄與歸檔核心。
*   **執行邏輯**:
    1.  **初始化**: 在 `__init__` 中，連接到指定的 SQLite 資料庫 (`session.sqlite`)，並啟用 WAL (Write-Ahead Logging) 模式以提高併發寫入效能。
    2.  **`log()` 方法**:
        *   接收日誌級別 (`level`) 和訊息 (`message`)。
        *   將帶有時間戳的日誌訊息 `print` 到終端機以供即時查看。
        *   將相同的日誌訊息插入到 SQLite 的 `logs` 表格中。
    3.  **`archive_to_file()` 方法**:
        *   查詢 `logs` 表格中的所有日誌。
        *   建立一個位於 `output/logs/archive/` 目錄下、帶有執行時間戳的 `.txt` 檔案。
        *   將所有日誌寫入該檔案，形成永久的作戰報告。
        *   關閉資料庫連接。
*   **目的**: 為專案提供一個標準化的、持久化的、可追溯的日誌解決方案。

### `core/analysis/data_engine.py`
*   **類型**: 數據引擎核心。
*   **功能**: `DataEngine` 類負責協調多個數據客戶端 (`YFinanceClient`, `FredClient`, `TaifexDBClient`)，並內建一個基於 DuckDB 的快取機制。
*   **執行邏輯**:
    1.  **初始化**: 透過依賴注入接收所有需要的數據客戶端實例，並建立一個到 DuckDB 的持久連接。
    2.  **快取機制**:
        *   `_query_cache`: 在獲取數據前，先查詢 DuckDB 中是否已有該時間點的數據。
        *   `_write_cache`: 如果快取未命中，在從 API 獲取新數據後，會將其寫入 DuckDB。
    3.  `generate_snapshot()`: 作為主要方法，它會先檢查快取，如果未命中，則呼叫其他私有方法從各個客戶端獲取數據、計算指標，然後將結果存入快取並返回。
*   **目的**: 作為一個高階的數據提供者，向上層應用屏蔽了底層數據源的複雜性和快取細節，提供一個統一的數據獲取介面。

### `core/analysis/stress_index.py`
*   **類型**: 核心分析引擎。
*   **功能**: `StressIndexCalculator` 類負責計算綜合的每日金融壓力指數。
*   **執行邏輯**:
    1.  `_fetch_all_data`: 呼叫 `FredClient` 和 `NYFedClient` 獲取所有需要的原始經濟數據 (如 VIX, 利率, 交易商持倉等)。
    2.  `_preprocess_and_align`: 對獲取到的不同頻率的數據進行預處理，包括計算衍生指標 (如殖利率利差)，並使用前向填充 (`ffill`) 將它們對齊到一個統一的每日時間序列上。
    3.  `_normalize_to_zscore`: 使用滾動窗口 (預設為一個交易年) 計算每個指標的 Z-Score，以使其具有可比性。
    4.  `_aggregate_index`: 將所有標準化後的 Z-Score 進行加總平均 (在加總前會反轉某些指標的方向，以確保分數越高代表壓力越大)，從而合成為一個單一的每日壓力指數。
    5.  `calculate()`: 作為公開方法，按順序協調以上所有步驟。
*   **目的**: 封裝計算一個複雜宏觀指標所需的所有步驟，使其易於被上層的數據管線 (`CalculateStressIndexStep`) 調用。

### `core/clients/*`
*   **類型**: API 客戶端模組。
*   **功能**: `core/clients/` 目錄下的每一個檔案都代表一個與特定外部數據源 (如 Yahoo Finance, FRED, FMP) 進行互動的客戶端。
*   **設計模式**:
    *   **`base.py`**: 定義了 `BaseAPIClient`，作為所有其他客戶端的父類。它內建了基於 `requests-cache` 的中央快取引擎和統一的 `_get_request_context` 方法來處理強制刷新。
    *   **子類實現**: 每個特定的客戶端 (如 `fred.py`, `fmp.py`) 都繼承自 `BaseAPIClient`，並實現其 `fetch_data` 方法，以處理該特定 API 的請求 URL、參數和回應格式。
*   **目的**: 將與外部 API 的所有通訊細節 (URL 構建、參數格式化、錯誤處理、數據解析) 封裝起來，為上層應用提供一個乾淨、統一的數據獲取介面。

### `core/pipelines/*`
*   **類型**: 可複用數據處理管線。
*   **功能**: `core/pipelines/` 目錄定義了一個可組合的數據處理管線框架。
*   **設計模式**:
    *   **`base_step.py`**: 定義了 `BaseETLStep` 抽象基礎類，要求所有步驟都必須實現一個 `execute` 方法。
    *   **`pipeline.py`**: `DataPipeline` 類可以接收一個由多個 `BaseETLStep` 實例組成的列表，並按順序依次執行它們，將上一步的輸出作為下一步的輸入。
*   **目的**: 將多步驟的複雜數據處理流程 (如計算壓力指數) 模組化，使其更清晰、更易於維護和測試。

---

## **數據處理管線 (`pipelines/`)**

### `pipelines/p0_downloader/run.py`
*   **類型**: 數據下載器。
*   **功能**: 一個自動化的數據採集腳本，專門用於從台灣期貨交易所 (TAIFEX) 下載每日的交易數據壓縮檔。
*   **執行邏輯**:
    1.  接收開始和結束日期作為參數。
    2.  遍歷日期範圍，為每一天生成一個下載任務。
    3.  使用 `ThreadPoolExecutor` 進行併發下載，以提高效率。
    4.  每個下載任務都包含隨機的 `User-Agent` 和請求延遲，以模擬真實使用者行為。
    5.  具備錯誤處理和重試機制。
*   **目的**: 作為整個 ELT 流程的第一步 (E - Extract)，負責從外部網站獲取原始數據檔案。

### `pipelines/p1_explorer/run.py`
*   **類型**: 數據格式探勘與註冊器。
*   **功能**: 掃描 `p0_downloader` 下載回來的原始檔案，分析其格式 (編碼、標頭)，並將這些格式資訊註冊到一個「格式註冊表」資料庫中。
*   **執行邏輯**:
    1.  遍歷下載目錄下的所有檔案 (支援 `.zip`, `.csv`, `.txt`)。
    2.  對每個檔案的標頭計算一個唯一的「指紋」(SHA-256 雜湊值)。
    3.  將這個指紋，連同檔案的編碼 (`encoding`) 和標頭內容 (`header`)，存入一個 SQLite 資料庫 (`schema_registry.db`)。
    4.  如果某個格式 (指紋) 已經存在，則只增加其計數。
*   **目的**: 自動化地發現和記錄新出現的數據格式，為後續的數據轉換 (Transformer) 提供依據。

### `pipelines/p2_elt_pipeline/run_elt.py`
*   **類型**: ELT (提取、加載、轉換) 主流程。
*   **功能**: 執行一個完整的 ELT 流程，將原始檔案加載到數據倉庫，然後進行轉換。
*   **執行邏輯**:
    1.  **加載 (Load)**: `run_loader` 函式會掃描下載目錄，但**只會**將那些其格式指紋已存在於「格式註冊表」中的檔案，以二進制形式 (BLOB) 原封不動地載入到原始數據倉庫 (`raw_taifex.duckdb`) 中。
    2.  **轉換 (Transform)**: `run_transformer` 函式會讀取原始數據倉庫中的數據，根據「格式註冊表」中的資訊 (如編碼、標頭)，將二進制的數據解析為結構化的表格，並將其寫入到最終的分析數據庫 (`analytics_taifex.duckdb`) 中。
*   **目的**: 實現一個與傳統 ETL 不同的 ELT 流程，即先加載原始數據，再進行轉換，這樣可以保留最原始的數據副本，並在未來可以對其進行不同方式的轉換。

### `pipelines/p3_backfill_hourly_data/run.py`
*   **類型**: 歷史數據回填管線。
*   **功能**: 用於填充或更新 `DataEngine` 的 DuckDB 快取中的歷史小時級數據。
*   **執行邏輯**:
    1.  接收一個開始和結束日期。
    2.  生成該範圍內所有的小時級時間戳。
    3.  遍歷每一個時間戳，並呼叫 `DataEngine` 的 `generate_snapshot()` 方法。
    4.  `DataEngine` 內部會自動處理快取邏輯：如果該小時的數據已存在，則直接跳過；如果不存在，則從 API 獲取並寫入快取。
*   **目的**: 提供一個手動觸發歷史數據填充的機制，確保分析應用所需的所有歷史數據都已存在於本地快取中。
