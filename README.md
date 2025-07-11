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
    *   此目錄是整個系統的心臟。每一個位於 `apps/` 下的子目錄（例如 `apps/factor_engine/`）或獨立腳本（例如 `apps/run_gold_layer.py`）都可以被視為一個「微應用」或一個獨立的執行單元。
    *   每個單元專注於執行一項具體的任務。例如：
        *   `apps/factor_engine/run_factor_etl.py`：可能負責運行特定的因子計算和ETL流程。
        *   `apps/run_gold_layer.py`：負責構建黃金層數據。
        *   更複雜的應用如 `apps/backtesting_engine/` 可能包含完整的回測邏輯。
    *   這種劃分使得各功能單元可以獨立開發、測試、部署和擴展。

*   **`core/` 目錄 - 共享核心模組：**
    *   此目錄存放所有可被不同「微應用」共享的核心組件和工具函式。
    *   例如：
        *   `core/config.py`：提供統一的專案級配置讀取功能。
        *   `core/logger.py`：提供標準化的日誌記錄器 (`get_logger`)，方便各模組和應用統一日誌格式與輸出。
        *   `core/constants.py`：定義專案範圍內的共通常數。
        *   `core/utils/` (目錄)：包含各類通用的輔助函式和工具模組 (例如 `path_utils.py`)。獨立的 `core/utils.py` 檔案已被整合或移除。
        *   未來可能加入 `core/secrets.py` 用於管理敏感憑證。

*   **標準數據流 (Standard Data Flow)：**
    系統遵循經典的 ETL/ELT 模式，將數據處理流程標準化為：
    1.  **數據提取 (Extract)**：由 `apps/` 目錄下的各類 `downloader` 微應用負責。這些應用程式連接外部 API 或數據源，獲取原始情報。
    2.  **數據轉換 (Transform)**：由 `apps/` 目錄下的各類 `transformer` 微應用負責。它們接收原始數據，進行清洗、處理、格式轉換（例如，轉換為標準化的 Parquet 檔案），並可能進行初步的特徵工程。
    3.  **數據裝載 (Load)**：主要由 `apps/database_loader` 這類微應用負責。它們將經過轉換和標準化的數據（通常是 Parquet 檔案），高效且安全地載入到我們的中央數據儲存庫（例如 DuckDB）。

這種微服務化的應用設計，使得我們可以更靈活地組合不同的應用程式來完成複雜的數據管線任務，同時也方便針對特定功能進行優化或替換，而不會影響到系統的其他部分。

## **四、 檔案目錄結構**

以下是反映當前專案狀態的檔案目錄結構：

```
.
├── .gitignore
├── README.md
├── config.yml   # <--- 新增的中央設定檔
├── poetry.lock  # Poetry 依賴鎖定檔案
├── pyproject.toml # Poetry 專案設定與依賴文件
├── apps
│   ├── __init__.py
│   ├── analysis_pipeline # 分析管線應用
│   │   └── run.py
│   ├── backtesting_engine # 回測引擎
│   │   ├── __init__.py
│   │   └── main.py
│   ├── factor_engine # 因子引擎
│   │   ├── engine.py
│   │   └── run_factor_etl.py
│   ├── news_client # 新聞客戶端應用 (已移除本地 config.py)
│   │   └── run.py
│   ├── pipeline_metadata_manager # 管線元數據管理器 (已移除本地 config.py)
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── portfolio_optimizer # 投資組合優化器
│   │   ├── __init__.py
│   │   └── main.py
│   ├── py.typed # PEP 561 類型標記檔案
│   ├── report_generator # 報告生成器
│   │   ├── __init__.py
│   │   ├── generator.py
│   │   └── run.py
│   ├── run_gold_layer.py # 黃金層數據建構腳本 (已使用 core.logger)
│   └── run_stress_index.py # 壓力指數計算腳本
├── core
│   ├── __init__.py
│   ├── analyzers # 分析器模組
│   │   ├── __init__.py
│   │   └── base_analyzer.py
│   ├── clients # API 客戶端模組
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── finmind.py
│   │   ├── fmp.py
│   │   ├── fred.py
│   │   ├── nyfed.py
│   │   └── yfinance.py
│   ├── config.py # 核心配置模組 (讀取 config.yml)
│   ├── constants.py # 核心常數定義
│   ├── db # 資料庫相關模組
│   │   ├── __init__.py
│   │   └── db_manager.py
│   ├── logger.py  # 標準化核心日誌模組
│   ├── pipelines # 數據管線框架
│   │   ├── __init__.py
│   │   ├── base_step.py
│   │   ├── pipeline.py
│   │   └── steps # 管線步驟實現
│   │       ├── __init__.py
│   │       ├── aggregators.py
│   │       ├── financial_steps.py
│   │       └── loaders.py
│   ├── py.typed # PEP 561 類型標記檔案
│   └── utils # 通用工具包 (注意：獨立的 core/utils.py 已被移除)
│       ├── __init__.py
│       └── path_utils.py # 範例：路徑相關工具
# 如果 general_utils.py 被創建在 core/utils/ 下，也應列於此處
├── pytest.ini # Pytest 設定檔
└── tests # 測試代碼
    ├── __init__.py
    ├── conftest.py # Pytest 的共用 fixtures 和 hooks
    ├── integration # 整合測試
    │   ├── __init__.py
    │   ├── apps
    │   │   ├── __init__.py
    │   │   ├── test_analysis_pipeline.py
    │   │   └── test_refactored_apps.py # 包含對 apps 腳本的測試
    │   └── pipelines
    │       ├── __init__.py
    │       ├── test_data_pipeline.py
    │       └── test_example_flow.py
    └── unit # 單元測試
        ├── __init__.py
        ├── core
        │   ├── __init__.py
        │   ├── analyzers
        │   │   ├── __init__.py
        │   │   └── test_base_analyzer.py
        │   └── clients
        │       ├── __init__.py
        │       ├── test_finmind.py
        │       ├── test_fmp.py
        │       ├── test_fred.py
        │       ├── test_nyfed.py
        │       └── test_yfinance.py
        └── test_feature_analyzer.py # (此檔案的具體位置和內容可能需進一步確認)
```

## **五、 環境設定與啟動**

本專案使用 [Poetry](https://python-poetry.org/) 進行依賴管理和環境設定。請遵循以下步驟設定您的作戰環境：

1.  **安裝 Poetry (如果尚未安裝)**：
    請參考 Poetry 官方文檔進行安裝：[Installation - Poetry Documentation](https://python-poetry.org/docs/#installation)

2.  **配置 Poetry 以在專案內創建虛擬環境 (推薦)**：
    執行一次以下指令，讓 Poetry 將虛擬環境創建在專案目錄下的 `.venv` 資料夾中：
    ```bash
    poetry config virtualenvs.in-project true
    ```

3.  **安裝專案依賴與初始化環境**：
    進入專案的根目錄 (包含 `pyproject.toml` 檔案)，執行以下指令來安裝所有必要的作戰套件並建立虛擬環境：
    ```bash
    poetry install
    ```
    此指令會讀取 `pyproject.toml` 和 `poetry.lock` 檔案，解析並安裝所有主要依賴和開發依賴。

4.  **啟動 Poetry 虛擬環境**：
    有兩種主要方式可以啟動並在虛擬環境中工作：

    *   **啟動一個新的 shell 會話 (常用)**：
        ```bash
        poetry shell
        ```
        此指令會啟動一個新的 shell，其中虛擬環境已自動激活。之後在此 shell 中執行的所有 Python 或 pip 指令都將作用於此虛擬環境。

    *   **在現有 shell 中運行單個指令**：
        ```bash
        poetry run <your_command>
        ```
        例如，運行一個 Python 腳本：
        ```bash
        poetry run python apps/run_gold_layer.py
        ```
        或運行 Pytest (詳見下一節)：
        ```bash
        poetry run pytest -v
        ```

完成上述步驟後，您的本地環境即已準備就緒。由於系統已模組化為微服務應用，通常沒有單一的「服務啟動」指令，而是根據需求，使用 `poetry run python <script_path.py>` 的方式直接運行位於 `apps/` 目錄下的特定應用腳本。

## **六、 戰術校準：執行測試**

在成功的環境初始化之後，執行全面的自動化測試是確保所有作戰單元正常運作的關鍵步驟。我們的系統已建立完善的測試框架。

請在專案根目錄下，並確保您的 Poetry 虛擬環境已激活（例如，通過 `poetry shell` 進入新的 shell，或者直接使用 `poetry run`），執行以下指令以運行所有的核心單元測試並檢視詳細輸出：

```bash
poetry run pytest -v
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

