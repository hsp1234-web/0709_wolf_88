# **README.md (v1.0) - 【普羅米修斯之火】開發者作戰手冊**

## **一、 計畫概述與作戰哲學**

【普羅米修斯之火】是一個為專業量化研究而設計的、本地化、具備高度擴展性的數據與分析框架。其核心目標是在標準硬體環境下，建立一個從「多源情報獲取」、「權威事實融合」、「量化因子挖掘」，到「策略回測」與「投資組合優化」的完整作戰閉環。

**重要更新：【奧林匹斯計畫】已成功完成！** 本專案的基礎架構經歷了一次徹底的清理與重構，舊有的單體後端 (`prometheus_fire_backend`) 已被全新的、基於「微服務應用生態系」的模組化架構所取代。這一轉變旨在提升系統的靈活性、可維護性與擴展性，為未來的作戰任務奠定堅實基礎。

本計畫在新的架構下，將繼續遵循三大核心作戰哲學：

1.  **指揮官主導 (Commander-Led):** 系統的一切行動（數據獲取、融合、計算、回測、優化）皆由終端使用者（指揮官）透過 API 下達指令，AI助理（後端）負責精準執行與匯報。我們反對無法觀測、不受控制的「全自動化」。
2.  **湖倉一體、不可變更 (Immutable Data Lake & Warehouse):** 我們採用業界先進的ELT（先存後整）架構。所有原始情報被完整、不可變更地載入「數據湖」，而後續的分析數據則從湖中提煉至「數據倉儲」，確保了數據的絕對可追溯性。黃金紀錄、因子數據等均以版本化或日期戳的方式管理，鼓勵不可變的數據操作。
3.  **內容感知、精準打擊 (Content-Aware, Surgical Strike):** 系統在數據獲取階段，具備「內容感知」能力，能夠理解已獲取數據的具體欄位與時間範圍，從而將API資源精準地用於「補充」情報缺口，而非「重複」覆蓋，極大地提升了情報獲取的效率。（此哲學在 `DataFetcher` 的 `hydrate_data_range` 等方法中有所體現）。

## **二、 技術棧 (Technology Stack)**

*   **核心數據處理:** Pandas, NumPy
*   **數據持久化格式:** Apache Parquet
*   **技術指標計算:** `pandas-ta`
*   **向量化回測:** `vectorbt`
*   **投資組合優化:** `PyPortfolioOpt`
*   **路徑管理:** `pathlib`
*   **日誌記錄:** Python `logging` 模組 (用於各微應用及核心日誌)
*   **測試框架:** Pytest (確保每個作戰單元的健壯性)
*   **數據庫：**
    *   DuckDB (作為主要的中央數據儲存庫/軍火庫)
    *   SQLite (可選，用於特定微應用的輕量級元數據或日誌存儲)
*   **命令行界面 (部分輔助腳本):** `argparse`

## **三、 系統核心架構：微服務應用生態系 (Micro-App Ecosystem)**

經過【奧林匹斯計畫】的重構，系統現採用「**微服務應用 (Micro-App)**」架構理念。此架構的核心是將原先龐大、單體的後端管線，拆解為一系列獨立、自足、職責單一的作戰單元。這種設計大幅提升了系統的模組化程度、可維護性及擴展性。

*   **`apps/` 目錄 - 微應用中心：**
    *   此目錄是整個系統的心臟。每一個位於 `apps/` 下的子目錄都是一個獨立的「微應用」。
    *   每個微應用專注於執行一項具體的任務。例如：
        *   `apps/yfinance_downloader`：專責從 Yahoo Finance 下載金融數據。
        *   `apps/taifex_data_transformer`：專責轉換台指期貨相關數據格式。
        *   `apps/database_loader`：專責將標準化後的數據（通常為 Parquet 格式）載入中央資料庫（例如 DuckDB）。
    *   這種劃分使得各應用可以獨立開發、測試、部署和擴展。

*   **`core/` 目錄 -共享核心模組：**
    *   此目錄存放所有可被不同「微應用」共享的核心組件和工具函式。
    *   例如：
        *   `core/config.py`：提供統一的專案級配置讀取功能。
        *   `core/constants.py`：定義專案範圍內的共通常數。
        *   `core/utils.py`：包含通用的輔助函式。
        *   未來可能加入 `core/secrets.py` 用於管理敏感憑證。

*   **標準數據流 (Standard Data Flow)：**
    系統遵循經典的 ETL/ELT 模式，將數據處理流程標準化為：
    1.  **數據提取 (Extract)**：由 `apps/` 目錄下的各類 `downloader` 微應用負責。這些應用程式連接外部 API 或數據源，獲取原始情報。
    2.  **數據轉換 (Transform)**：由 `apps/` 目錄下的各類 `transformer` 微應用負責。它們接收原始數據，進行清洗、處理、格式轉換（例如，轉換為標準化的 Parquet 檔案），並可能進行初步的特徵工程。
    3.  **數據裝載 (Load)**：主要由 `apps/database_loader` 這類微應用負責。它們將經過轉換和標準化的數據（通常是 Parquet 檔案），高效且安全地載入到我們的中央數據儲存庫（例如 DuckDB）。

這種微服務化的應用設計，使得我們可以更靈活地組合不同的應用程式來完成複雜的數據管線任務，同時也方便針對特定功能進行優化或替換，而不會影響到系統的其他部分。

## **四、 檔案目錄結構**

以下是經過【奧林匹斯計畫】重構後，我們全新的、潔淨的檔案目錄結構：

```
.
├── .gitignore
├── README.md
├── apps
│   ├── __init__.py
│   ├── backtesting_engine
│   │   ├── __init__.py
│   │   └── main.py
│   ├── daily_market_analyzer
│   │   ├── __init__.py
│   │   ├── analysis_engine.py
│   │   ├── db_manager.py
│   │   ├── report_generator.py
│   │   ├── run.py
│   │   └── yfinance_client.py
│   ├── database_loader
│   │   ├── __init__.py
│   │   └── loader.py
│   ├── dossier_generator
│   │   └── run.py
│   ├── feature_analyzer
│   │   ├── __init__.py
│   │   ├── analyzer.py
│   │   ├── cross_market_analyzer.py
│   │   ├── dealer_position_analyzer.py
│   │   └── run.py
│   ├── finmind_client
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── config.py
│   │   └── run.py
│   ├── fmp_client
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── config.py
│   │   └── run.py
│   ├── institutional_analyzer
│   │   ├── __init__.py
│   │   ├── analyzer.py
│   │   └── run.py
│   ├── news_client
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── config.py
│   │   └── run.py
│   ├── nyfed_client
│   │   ├── __init__.py
│   │   ├── client.py
│   │   └── run.py
│   ├── pipeline_metadata_manager
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── manager.py
│   ├── portfolio_optimizer
│   │   ├── __init__.py
│   │   └── main.py
│   ├── report_generator
│   │   ├── __init__.py
│   │   ├── generator.py
│   │   └── run.py
│   ├── taifex_data_pipeline
│   │   ├── run.py
│   │   └── stream_unzipper.py
│   ├── taifex_data_transformer
│   │   ├── __init__.py
│   │   ├── run.py
│   │   └── transformer.py
│   ├── time_aggregator
│   │   ├── __init__.py
│   │   └── run.py
│   ├── yfinance_client
│   │   ├── __init__.py
│   │   ├── client.py
│   │   └── run.py
│   └── yfinance_downloader
│       └── downloader.py
├── core
│   ├── __init__.py
│   ├── config.py
│   ├── constants.py
│   └── utils.py
├── pytest.ini
└── tests
    ├── __init__.py
    ├── _test_harness_api_failures.py
    ├── _test_harness_config_missing.py
    ├── _test_harness_data_corruption.py
    ├── _test_harness_database_loader.py
    ├── _test_harness_dependency_issues.py
    ├── _test_harness_taifex_live_download.py
    ├── _test_harness_taifex_transformer.py
    ├── _test_harness_yfinance_live.py
    └── unit
        ├── __init__.py
        └── test_feature_analyzer.py
```

## **五、 環境設定與啟動**

為了確保【普羅米修斯之火】計畫的順利運行，請遵循以下步驟設定您的作戰環境：

1.  **建立並啟動 Python 虛擬環境 (建議)**：
    為了維持專案依賴的純淨性，強烈建議您使用虛擬環境。您可以選擇 `venv` 或 `conda`。

    *   使用 `venv`:
        ```bash
        python -m venv .venv
        source .venv/bin/activate  # Linux/macOS
        # 或者
        # .venv\Scripts\activate    # Windows
        ```

    *   使用 `conda`:
        ```bash
        conda create -n prometheus_fire python=3.9  # 可指定 Python 版本
        conda activate prometheus_fire
        ```

2.  **安裝專案依賴 (環境初始化)**：
    在啟動虛擬環境後，進入專案的根目錄，執行以下指令來安裝所有必要的作戰套件：
    ```bash
    pip install .
    ```
    如果專案未來提供 `requirements.txt` 檔案，也可以使用 `pip install -r requirements.txt`。

完成上述步驟後，您的本地環境即已準備就緒，可以開始執行各個微應用或進行測試。由於系統已模組化為微服務應用，通常沒有單一的「服務啟動」指令，而是根據需求直接運行位於 `apps/` 目錄下的特定應用腳本 (例如 `python apps/yfinance_downloader/downloader.py --help`)。

## **六、 戰術校準：執行測試**

在成功的環境初始化之後，執行全面的自動化測試是確保所有作戰單元正常運作的關鍵步驟。我們的系統已建立完善的測試框架。

請在專案根目錄下執行以下指令，以運行所有的核心單元測試並檢視詳細輸出：

```bash
python -m pytest -v
```

所有測試均應通過，以確認系統處於穩定的戰備狀態。

## **七、 未來展望：下一階段作戰目標**

隨著【奧林匹斯計畫】的完成和「微服務應用生態系」的成功部署，我們已為下一階段的宏偉藍圖奠定了堅實的基礎。

**【三階段作戰計畫】 - 第一階段：建立「中央情報骨幹」**

下一階段的核心任務是建立我們系統的「中央情報骨幹」。此階段的重點包括但不限於：

*   **強化數據獲取能力**：擴展和優化現有的 `downloader` 微應用，接入更多元、更高質量的金融數據源。
*   **精煉數據轉換流程**：提升 `transformer` 微應用的處理效率和數據清洗能力，確保數據的準確性與一致性。
*   **構建高效數據倉儲**：圍繞 DuckDB 或其他選定的數據庫技術，打造一個高效、可擴展、易於查詢的中央數據倉儲。
*   **完善元數據管理**：建立全面的元數據管理機制，追蹤數據來源、血緣關係、更新頻率及質量指標。
*   **開發標準化數據接口**：為各分析型微應用（如特徵分析、回測引擎、組合優化等）提供穩定、高效的數據訪問接口。

此「中央情報骨幹」將成為我們整個量化研究框架的神經中樞，為後續更高級的分析與決策支持功能提供動力。

