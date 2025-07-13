# **【普羅米修斯之火】金融數據與分析框架 - 開發者手冊 v0.7.0**

## **一、 專案概覽與目的**

【普羅米修斯之火】是一個模組化、多層次的金融數據分析框架，旨在為量化研究提供從數據獲取、指標計算到視覺化洞察的全鏈路解決方案。本專案的核心是建立一個穩健、可擴展的自動化系統，能夠處理從日線級別的宏觀經濟數據到高頻的小時級市場數據，並將其轉化為可操作的洞察。

## **二、 核心能力**

本框架目前已具備以下三大核心能力：

### **1. 雙軌數據管線**
*   **日線級宏觀數據管線 (`p4_daily_macro_etl`)**: 自動化獲取並存儲來自 FRED 等來源的關鍵宏觀經濟指標，為市場分析提供宏觀背景。
*   **小時級市場數據管線 (`p5_hourly_price_etl`)**: 專注於獲取全球主要資產（指數、期貨、股票等）的小時線 OHLCV 數據，並具備「回填」與「更新」兩種模式，確保持續累積高精度的數據資產。

### **2. 三層數據維度**
在小時級數據管線的基礎上，我們成功地對數據進行了三層維度的深化：
*   **第一層 (價格)**: 獲取並儲存了最基礎的 OHLCV 數據。
*   **第二層 (動能)**: 計算並附加了數十種核心技術指標（如 RSI, MACD, 布林帶等），為市場動能分析提供了豐富的量化依據。
*   **第三層 (結構)**: 攻克了複雜的選擇權衍生數據，將 GEX（總 Gamma 曝險）、最大痛點等高階指標納入我們的數據庫，為理解市場結構與潛在轉折點提供了獨特的視角。

### **3. 互動式儀表板**
*   **數據洞察的最終出口 (`view-dashboard`)**: 我們開發了一個獨立的互動式視覺化儀表板，將龐大、抽象的數據庫，轉化為一個直觀、多圖表聯動的市場儀表板。這實現了從數據到洞察的閉環，讓研究者可以快速地檢視市場的價格行為、動能狀態與結構性風險。

## **三、 技術棧 (Technology Stack)**

*   **核心程式語言:** Python (>=3.12, <3.14)
*   **依賴管理:** Poetry
*   **命令列介面**: Typer
*   **數據處理:**
    *   Pandas, NumPy
    *   Pandas-TA-OpenBB (用於技術指標計算)
*   **API 客戶端與網路請求:**
    *   Requests, Requests-Cache
    *   FredAPI, YFinance
*   **資料庫**: DuckDB, SQLite3 (用於日誌系統)
*   **設定檔管理:** PyYAML
*   **視覺化**: Plotly
*   **測試與品質保證:** Pytest, Pytest-Mock, Ruff

## **四、 架構概覽**

本專案採用一個清晰、模組化的架構，其核心思想如下：

**統一指揮入口 (`run.py`) -> 模組化管線 (`pipelines/`) -> 核心客戶端與工具 (`core/`) -> 終端應用 (`apps/`)**

```
.
├── README.md
├── PROJECT_FILES_GLOSSARY.md
├── apps
│   ├── dashboard
│   │   └── run_app.py  # 儀表板生成邏輯
│   └── ... (其他應用)
├── config.yml
├── core
│   ├── clients       # 所有第三方 API 客戶端
│   ├── db            # 數據庫管理
│   └── ... (其他核心工具)
├── output
│   ├── market_dashboard.html # 儀表板輸出
│   └── logs
│       └── archive     # 作戰報告歸檔
├── pipelines
│   ├── p4_daily_macro_etl    # 日線宏觀數據管線
│   └── p5_hourly_price_etl   # 小時級市場數據管線
├── pyproject.toml
├── run.py  # 專案統一指揮入口
└── tests
    └── ...
```

## **五、 快速上手指南**

### **1. 環境設定**
本專案使用 [Poetry](https://python-poetry.org/) 進行依賴管理。
1.  **安裝 Poetry** (如果尚未安裝)。
2.  **克隆專案**。
3.  **配置 Poetry 虛擬環境** (推薦 `poetry config virtualenvs.in-project true`)。
4.  **安裝依賴**: `poetry install`。
5.  **激活虛擬環境**: `poetry shell`。

### **2. 金鑰配置**
*   **FRED API 金鑰**: 為了運行日線宏觀數據管線，您**必須**在 `config.yml` 中提供一個有效的 FRED API 金鑰。
    ```yaml
    # In config.yml
    api_keys:
      fred: "YOUR_REAL_FRED_API_KEY_HERE"
    ```
*   ⚠️ **安全警告**：`config.yml` 檔案包含敏感金鑰，**絕對不可**提交到任何版本控制系統（如 Git）。請確保它已被列在 `.gitignore` 檔案中。

### **3. 主要指令**
所有核心功能都已整合至根目錄的 `run.py` 中，透過子命令進行呼叫。

*   **查看所有可用命令**:
    ```bash
    poetry run python run.py --help
    ```

*   **數據管線指令**:
    *   `poetry run python run.py build-daily-data`: 執行日線宏觀數據的 ETL 流程。
    *   `poetry run python run.py build-hourly-data --mode backfill`: 首次執行，回填過去兩年的小時級市場數據。
    *   `poetry run python run.py build-hourly-data --mode update`: 每日執行，僅更新最新的小時級市場數據。

*   **數據深化指令**:
    *   `poetry run python run.py calculate-hourly-indicators`: 在小時級數據基礎上，計算並附加技術指標。
    *   `poetry run python run.py calculate-options-metrics`: 在已包含技術指標的數據上，計算並附加選擇權衍生數據。

*   **視覺化指令**:
    *   `poetry run python run.py view-dashboard`: 生成並自動開啟互動式市場儀表板。

### **4. 測試**
*   **運行所有測試**:
    ```bash
    poetry run pytest
    ```

## **六、 歷史用法與變更**

<!--
### **5.1 主要功能執行 (v0.6.0 新版 CLI 用法)**
**[舊版說明]** 以下為 v0.6.0 版本的說明，部分指令已被新的數據管線指令取代或擴充。

*   **執行 SMA 策略回測**:
    ```bash
    poetry run python run.py sma-backtest
    ```
*   **執行壓力指數計算**:
    ```bash
    poetry run python run.py stress-index
    ```
*   **執行 FMP 數據獲取驗證**:
    ```bash
    poetry run python run.py fmp-fetch
    ```
-->

<!--
### **5.2 (歷史用法 - v0.5.0 及更早版本)**

#### **5.2.1 數據回填與快取 (歷史)**
*   **執行數據回填**:
    ```bash
    # [舊命令] 此功能已由 build-hourly-data 指令取代。
    poetry run python pipelines/p3_backfill_hourly_data/run.py
    ```
-->

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
