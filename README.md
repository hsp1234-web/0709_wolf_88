# 【普羅米修斯之火】金融數據與分析框架

**版本 v0.6.0**

---

## 1. 專案概覽與目的

**【普羅米修斯之火】(Prometheus Fire)** 是一個模組化、可擴展的金融數據與分析框架。其核心設計理念是將複雜的金融分析任務分解為一系列獨立、可複用的應用模組 (`apps`)，並透過一個統一的命令列介面（CLI）作戰指揮中心 (`run.py`) 進行調度。

本框架旨在解決金融數據專案中常見的挑戰：
*   **流程標準化**：提供一個標準化的方式來執行從數據獲取、分析、回測到生成報告的完整流程。
*   **日誌與可追溯性**：內建強健的「精準指示器」日誌系統，確保每一次執行的結果都有詳細、可追溯的作戰紀錄。
*   **快速擴展**：開發者可以專注於單一功能的開發，並輕鬆地將其作為一個新的應用整合到現有框架中。

## 2. 核心組件詳解

### 2.1. 作戰指揮中心 (`run.py`)

`run.py` 是整個專案的單一入口點 (Single Entry Point)，基於 `Typer` 函式庫建構。它負責：
*   **命令解析**：將使用者的命令 (如 `stress-index`) 對應到具體的應用模組。
*   **資源初始化**：在任何任務開始前，初始化共享資源，最核心的就是 `LogManager`。
*   **任務分派**：透過 `execute_task` 函式，將 `LogManager` 實例注入到被呼叫的應用模組中，並標準化任務的啟動與結束日誌。
*   **全域異常捕獲與歸檔**：無論任務成功或失敗，`run.py` 的頂層 `try...finally` 結構確保日誌總能被成功歸檔。

### 2.2. 精準指示器系統 (`core/logger.py`)

`LogManager` 是專案的日誌與歸檔核心，其運作機制如下：
1.  **即時寫入 SQLite**：所有日誌訊息 (包含時間戳、日誌級別、訊息內容) 都會被即時寫入到 `output/logs/session.sqlite` 資料庫中。使用 `SQLite` 和 `WAL` (Write-Ahead Logging) 模式確保了高效能和進程安全的寫入。
2.  **終端機即時輸出**：為了方便開發者即時監控，所有日誌也會同時 `print` 到終端機。
3.  **任務結束時歸檔**：當一個任務透過 `run.py` 執行完畢後，`LogManager` 的 `archive_to_file` 方法會被觸發。此方法會讀取 `session.sqlite` 中的所有日誌，並將其格式化後寫入一個帶有時間戳的文字檔案中，存放於 `output/logs/archive/`，形成永久的「作戰報告」。

## 3. 技術棧 (Technology Stack)

*   **核心語言**: Python 3.12+
*   **依賴管理與建構**: Poetry
*   **命令列介面**: Typer
*   **核心數據處理**: Pandas, NumPy
*   **數據獲取客戶端**: `yfinance`, `requests`, `fredapi` 等，統一存放於 `core/clients/`
*   **日誌系統**: 自定義 `LogManager` (基於 `sqlite3`, `pytz`)

## 4. 檔案目錄結構

```
.
├── README.md                # 本文件
├── pyproject.toml           # 專案依賴與設定 (Poetry)
├── run.py                   # ✨ 專案統一作戰指揮中心 (CLI 入口)
├── config.yml               # 專案設定檔 (API 金鑰、路徑等)
│
├── core/                    # 專案核心共用模組
│   ├── clients/             # 外部 API 客戶端 (e.g., FMP, Fred)
│   ├── pipelines/           # 可複用的數據處理管線與步驟
│   └── logger.py            # v82.0 精準指示器日誌系統
│
├── apps/                    # 各個獨立的功能性應用
│   ├── run_stress_index.py  # 壓力指數計算應用
│   ├── backtesting_engine/  # 回測引擎應用
│   └── ...                  # 其他獨立應用模組
│
├── output/                  # 所有任務的產出檔案目錄
│   ├── logs/
│   │   ├── session.sqlite   # 當前執行的即時日誌數據庫
│   │   └── archive/         # 歷史作戰報告歸檔
│   └── ...                  # 其他任務產出的數據或圖表
│
└── tests/                   # 自動化測試案例
    ├── unit/                # 單元測試
    └── integration/         # 整合測試
```

## 5. 環境設定與執行

### 步驟 1：安裝依賴

本專案使用 Poetry 進行依賴管理。請先確保您已安裝 Poetry。

```bash
# 安裝所有定義在 pyproject.toml 中的核心與開發依賴
poetry install
```

### 步驟 2：設定 API 金鑰

將 `config.yml` 中的 API 金鑰預留位置 (例如 `YOUR_REAL_FMP_API_KEY_HERE`) 替換為您自己的有效金鑰。

### 步驟 3：執行任務

所有任務都應透過根目錄的 `run.py` 來啟動。這確保了日誌系統能正確初始化。

```bash
# 建議進入 poetry 的虛擬環境後再執行
poetry shell

# 查看所有可用的命令
python run.py --help

# 執行壓力指數計算任務
python run.py stress-index
```

## 6. 開發者指南：如何新增應用

若要為專案新增一個名為 `new_feature` 的功能，請遵循以下步驟：

1.  **建立應用腳本**：在 `apps/` 目錄下建立 `run_new_feature.py`。
2.  **撰寫核心邏輯**：在 `run_new_feature.py` 中，建立一個 `main(log_manager: LogManager)` 函式。`log_manager` 參數將由 `run.py` 自動注入。
3.  **使用日誌**：在您的函式中，使用 `log_manager.log("INFO", "你的日誌訊息")` 來記錄進度。
4.  **整合至 `run.py`**：
    *   在 `run.py` 頂部，匯入您的新函式：`from apps.run_new_feature import main as run_new_feature`。
    *   在 `run.py` 底部，新增一個新的 Typer 命令：
        ```python
        @app.command()
        def new_feature(ctx: typer.Context):
            """這裡寫下新功能的簡短說明"""
            execute_task(ctx.obj, "新功能描述性名稱", run_new_feature)
        ```
5.  **完成**！現在您可以透過 `python run.py new-feature` 來執行您的新功能。

## 7. 版本歷史與變更日誌

### **v0.6.0 (作戰計畫 036-038)**
*   **架構升級**
    *   **統一 CLI 入口**: 引入 `Typer`，建立 `run.py` 作為唯一的任務調度中心，標準化所有應用的執行方式。
    *   **v82.0 日誌歸檔系統**: 實作了基於 SQLite 和文字檔案歸檔的 `LogManager`，為所有任務提供標準化、可追溯的「精準指示器」日誌記錄。
    *   **日誌系統重構**: 將專案中所有使用舊版 `get_logger` 的模組，全部重構為接收 `LogManager` 實例的新架構。
*   **功能調整**
    *   **正規化 `TaifexFileReader`**: (作戰計畫 036) 將原型程式碼重構為符合專案架構的標準化客戶端。
*   **測試**
    *   修復了因日誌系統變更而導致的整合測試失敗。

---
*本文件由 AI 助理 Jules 根據專案狀態自動生成與修訂。*
