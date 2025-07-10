# **README.md (v1.1) - 【普羅米修斯之火】開發者作戰手冊**

## **一、 計畫概述與作戰哲學**

【普羅米修斯之火】是一個為專業量化研究而設計的、本地化、具備高度擴展性的數據與分析框架。其核心目標是在標準硬體環境下，建立一個從「多源情報獲取」、「權威事實融合」、「量化因子挖掘」，到「策略回測」與「投資組合優化」的完整作戰閉環。

**重要更新：【蒼穹之心計畫 - 第一階段進行中】** 本專案正逐步從「腳本聯邦」架構重構為「中央指揮部 (CLI)」架構，旨在統一應用程式的啟動與管理方式，提升易用性與可維護性。

本計畫在新的架構下，將繼續遵循三大核心作戰哲學：

1.  **指揮官主導 (Commander-Led):** 系統的一切行動（數據獲取、融合、計算、回測、優化）皆由終端使用者（指揮官）透過 API 或 CLI 下達指令，AI助理（後端）負責精準執行與匯報。我們反對無法觀測、不受控制的「全自動化」。
2.  **湖倉一體、不可變更 (Immutable Data Lake & Warehouse):** 我們採用業界先進的ELT（先存後整）架構。所有原始情報被完整、不可變更地載入「數據湖」，而後續的分析數據則從湖中提煉至「數據倉儲」，確保了數據的絕對可追溯性。黃金紀錄、因子數據等均以版本化或日期戳的方式管理，鼓勵不可變的數據操作。
3.  **內容感知、精準打擊 (Content-Aware, Surgical Strike):** 系統在數據獲取階段，具備「內容感知」能力，能夠理解已獲取數據的具體欄位與時間範圍，從而將API資源精準地用於「補充」情報缺口，而非「重複」覆蓋，極大地提升了情報獲取的效率。

## **二、 技術棧 (Technology Stack)**

*   **核心數據處理:** Pandas, NumPy
*   **數據持久化格式:** Apache Parquet
*   **技術指標計算:** `pandas-ta`
*   **向量化回測:** `vectorbt`
*   **投資組合優化:** `PyPortfolioOpt`
*   **路徑管理:** `pathlib`
*   **日誌記錄:** Python `logging` 模組 (用於各應用及核心日誌)
*   **測試框架:** Pytest (確保每個作戰單元的健壯性)
*   **數據庫：**
    *   DuckDB (作為主要的中央數據儲存庫/軍火庫)
    *   SQLite (可選，用於特定應用的輕量級元數據或日誌存儲)
*   **命令行界面:** `typer`, `rich` (新的中央指揮部架構)

## **三、 系統核心架構：中央指揮部與微應用生態系 (CLI & Micro-App Ecosystem)**

隨著【蒼穹之心計畫】的推進，系統正轉向以一個位於專案根目錄的 `main.py`（使用 Typer 和 Rich 构建）作為「**中央指揮部 (CLI)**」。此 CLI 將統一管理和調度原有的「**微服務應用 (Micro-App)**」。

*   **`main.py` - 中央指揮部：**
    *   所有應用程式的核心功能將被重構並註冊為 `main.py` 下的子命令。
    *   使用者將透過 `python main.py <command> [options]` 的方式與系統互動。

*   **`apps/` 目錄 - 微應用中心：**
    *   此目錄是整個系統的心臟。每一個位於 `apps/` 下的子目錄都是一個獨立的「微應用」。
    *   每個微應用專注於執行一項具體的任務。其核心邏輯將被 CLI 調用。
        *   例如：`apps/daily_market_analyzer`：提供每日市場分析與報告功能。

*   **`core/` 目錄 -共享核心模組：**
    *   此目錄存放所有可被不同「微應用」共享的核心組件和工具函式。

*   **標準數據流 (Standard Data Flow)：**
    系統遵循經典的 ETL/ELT 模式，將數據處理流程標準化。各提取、轉換、裝載的邏輯單元將逐步整合到新的 CLI 架構中。

## **四、 檔案目錄結構**

以下是經過【奧林匹斯計畫】重構後，我們全新的、潔淨的檔案目錄結構：
*(註：此處目錄結構尚未完全反映【蒼穹之心計畫】的最終狀態，例如 `apps/daily_market_analyzer/run.py` 已被移除，並新增了 `logic.py`。此部分將在重構完成後統一更新。)*
```
.
├── .gitignore
├── README.md
├── main.py  # 新增的中央指揮部
├── apps
│   ├── __init__.py
│   ├── backtesting_engine
│   │   ├── __init__.py
│   │   └── main.py
│   ├── daily_market_analyzer # 已部分重構
│   │   ├── __init__.py
│   │   ├── analysis_engine.py
│   │   ├── db_manager.py
│   │   ├── logic.py # 新增的邏輯模組
│   │   ├── report_generator.py
│   │    # ├── run.py (此檔案已被移除)
│   │   └── yfinance_client.py
│   # ... 其他 apps 目錄結構 ...
├── core
│   # ... core 目錄結構 ...
├── pytest.ini
└── tests
    ├── __init__.py
    ├── apps # 新增的 CLI 應用測試目錄
    │   └── test_daily_market_analyzer.py # 新增的測試檔案
    # ... 其他 tests 目錄結構 ...
```

## **五、 環境設定與啟動**

為了確保【普羅米修斯之火】計畫的順利運行，請遵循以下步驟設定您的作戰環境：

1.  **建立並啟動 Python 虛擬環境 (建議)**：
    為了維持專案依賴的純淨性，強烈建議您使用虛擬環境。您可以選擇 `venv` 或 `conda`。

    *   使用 `venv`:
        ```bash
        python3 -m venv .venv  # 建議使用 python3
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
    # 確保 uv 已安裝 (若在環境設定腳本中未自動安裝)
    # pip install uv
    uv pip install -r requirements.lock.txt # 或 requirements.in
    ```
    如果專案提供了 `pyproject.toml` 且使用如 Poetry 或 PDM 等工具，請遵循其安裝指令。

完成上述步驟後，您的本地環境即已準備就緒。

### **啟動應用功能（透過中央指揮部）**

系統的功能將逐步整合到位於專案根目錄的 `main.py` 中央指揮部。您可以通過以下方式獲取可用命令列表：

```bash
python main.py --help
```

**範例：執行每日市場分析儀 (`daily-market-analyzer`)**

`daily-market_analyzer` 功能已被整合。以下是一些使用範例：

*   **獲取特定標的在指定日期範圍內的數據並生成報告（完整流程）：**
    ```bash
    python main.py daily-market-analyzer --tickers "AAPL,MSFT" --start-date "YYYY-MM-DD" --end-date "YYYY-MM-DD"
    ```

*   **僅獲取數據：**
    ```bash
    python main.py daily-market-analyzer --tickers "AAPL,MSFT" --start-date "YYYY-MM-DD" --end-date "YYYY-MM-DD" --data-only
    ```

*   **僅基於已有數據生成報告：**
    ```bash
    python main.py daily-market-analyzer --tickers "AAPL,MSFT" --report-start-date "YYYY-MM-DD" --report-end-date "YYYY-MM-DD" --report-only
    ```

*   **查看 `daily-market-analyzer` 的所有可用選項：**
    ```bash
    python main.py daily-market-analyzer --help
    ```

隨著更多應用被整合，新的命令和選項將會添加到 `main.py` 中。請隨時使用 `--help` 選項查閱最新的使用方法。

## **六、 戰術校準：執行測試**

在成功的環境初始化之後，執行全面的自動化測試是確保所有作戰單元正常運作的關鍵步驟。我們的系統已建立完善的測試框架。

請在專案根目錄下執行以下指令，以運行所有的核心單元測試並檢視詳細輸出：

```bash
pytest -v
# 或者，如果 pytest.ini 中已配置好 addopts:
# pytest
```

所有測試均應通過，以確認系統處於穩定的戰備狀態。

## **七、 未來展望：下一階段作戰目標**

隨著【奧林匹斯計畫】的完成和「微服務應用生態系」的成功部署，以及【蒼穹之心計畫】的持續推進，我們已為下一階段的宏偉藍圖奠定了堅實的基礎。

**【三階段作戰計畫】 - 第一階段：建立「中央情報骨幹」**

下一階段的核心任務是建立我們系統的「中央情報骨幹」。此階段的重點包括但不限於：

*   **全面遷移至 CLI 架構**：將所有 `apps/` 目錄下的應用程式整合到 `main.py` 中央指揮部。
*   **強化數據獲取能力**：擴展和優化現有的 `downloader` 應用邏輯，接入更多元、更高質量的金融數據源。
*   **精煉數據轉換流程**：提升 `transformer` 應用邏輯的處理效率和數據清洗能力，確保數據的準確性與一致性。
*   **構建高效數據倉儲**：圍繞 DuckDB 或其他選定的數據庫技術，打造一個高效、可擴展、易於查詢的中央數據倉儲。
*   **完善元數據管理**：建立全面的元數據管理機制，追蹤數據來源、血緣關係、更新頻率及質量指標。
*   **開發標準化數據接口**：為各分析型應用（如特徵分析、回測引擎、組合優化等）提供穩定、高效的數據訪問接口。

此「中央情報骨幹」將成為我們整個量化研究框架的神經中樞，為後續更高級的分析與決策支持功能提供動力。
