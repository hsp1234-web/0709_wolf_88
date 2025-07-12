# 【普羅米修斯之火】金融數據與分析框架

**版本：v0.2.0**

## 專案概述

本專案旨在建立一個由 AI 輔助開發的、模組化、可擴展的金融數據分析框架。其核心是透過標準化的數據管線（Pipelines）和應用（Apps），實現從數據獲取、處理、分析到視覺化報告的自動化流程。

## 核心依賴與技術棧

本專案基於 Python 3.12+，並使用 Poetry 進行依賴管理。

### 主要依賴 (`[tool.poetry.dependencies]`)
| 套件             | 版本            | 說明                                       |
| ---------------- | --------------- | ------------------------------------------ |
| `numpy`          | `<2.0`          | 高效能多維陣列運算                         |
| `pandas`         | `^2.3.1`        | 高效能 DataFrame 結構，用於數據操作        |
| `duckdb`         | `^1.3.2`        | 高效能嵌入式分析型數據庫                   |
| `pyyaml`         | `^6.0.2`        | YAML 解析器，用於讀取 `config.yml`         |
| `requests-cache` | `^1.2.1`        | 為 `requests` 提供快取功能                 |
| `yfinance`       | `0.2.60`        | 從 Yahoo Finance 獲取金融市場數據          |
| `requests`       | `^2.32.4`       | 標準 HTTP 函式庫                           |
| `urllib3`        | `<2.0`          | `requests` 的底層依賴，鎖定版本以確保兼容  |
| `pybreaker`      | `^1.4.0`        | 熔斷器模式實現，增加系統穩定性             |
| `plotly`         | `>=5.18.0,<5.19.0` | 強大的互動式圖表函式庫                     |
| `pytz`           | `^2025.2`       | 世界時區資料庫                             |
| `psutil`         | `^6.0.0`        | 跨平台系統監控函式庫                       |
| `fredapi`        | `^0.5.2`        | FRED (Federal Reserve Economic Data) API 客戶端 |
| `vectorbt`       | `^0.28.0`       | 用於投資組合回測與分析                     |
| `pydantic`       | `^2.11.7`       | 數據驗證與設定管理                         |
| `typer`          | `^0.16.0`       | 命令列介面建構工具                         |
| `openpyxl`       | `^3.1.5`        | 讀寫 Excel 檔案                            |

### 開發依賴 (`[tool.poetry.group.dev.dependencies]`)
| 套件             | 版本          | 說明                                       |
| ---------------- | ------------- | ------------------------------------------ |
| `pytest`         | `^8.4.1`      | 核心測試框架                               |
| `pytest-mock`    | `^3.14.1`     | 用於在單元測試中模擬物件                   |
| `types-requests` | `*`           | `requests` 的類型存根                      |
| `types-PyYAML`   | `^6.0.12`     | `PyYAML` 的類型存根                        |
| `types-pytz`     | `^2024.1.0`   | `pytz` 的類型存根                          |
| `deptry`         | `^0.23.0`     | 檢測未使用的依賴項                         |
| `ruff`           | `^0.12.3`     | 高效能 Python Linter                       |
| `pytest-timeout` | `^2.4.0`      | 為 `pytest` 提供超時功能                   |

## 架構核心更新 (v0.2.0)

### 1. 作戰指揮中心 (`run.py`)
專案現在擁有一個基於 `Typer` 的統一命令列入口 `run.py`。所有功能模組都應透過此入口執行，以確保日誌系統等共享資源能被正確初始化。

### 2. 精準指示器日誌系統 (`core/logger.py`)
引入了全新的 `LogManager`，它會將所有任務的日誌即時寫入 `output/logs/session.sqlite`，並在任務結束後歸檔至 `output/logs/archive/` 目錄下的文字檔案中，實現了操作的可追溯性。

## 環境設定

1.  **安裝 Poetry**:
    ```bash
    pip install poetry
    ```
2.  **安裝專案依賴**:
    ```bash
    poetry install
    ```
3.  **設定 API 金鑰**:
    複製 `config.yml.template` (如果存在) 為 `config.yml`，並填入您自己的 API 金鑰。

## 使用方法

所有任務都應透過 `run.py` 啟動。

```bash
# 建議進入 poetry 的虛擬環境
poetry shell

# 查看所有可用命令及其說明
python run.py --help

# 範例：執行壓力指數計算
python run.py stress-index

# 範例：執行 SMA 策略回測
python run.py sma-backtest
```

## 版本歷史

### v0.2.0 (2025-07-13) - 作戰計畫 038
*   **【重大架構升級】實作統一 CLI 入口與 v82.0 精準指示器日誌系統**
    *   **背景**: 隨著專案模組增加，舊有的分散式執行方式 (每個 `app` 都有自己的執行腳本) 導致了代碼重複、日誌分散、難以統一管理等問題。為了建立一個更穩健、可擴展的框架，我們引入了中央指揮與控制系統。
    *   **實作細節**:
        *   **引入 `Typer`**: 在根目錄下建立 `run.py`，利用 `Typer` 函式庫將其打造為一個功能強大且易於擴展的命令列介面 (CLI) 應用。現在，所有核心功能都作為子命令 (如 `stress-index`, `sma-backtest`) 註冊到 `run.py` 中。
        *   **建立 `LogManager`**: 在 `core/logger.py` 中，設計並實作了 `LogManager` 類別。此類別在 `run.py` 啟動時被實例化，並透過 `Typer` 的上下文 (`ctx.obj`) 依賴注入到各個子命令對應的任務函數中。
        *   **日誌持久化與歸檔**: `LogManager` 使用 `SQLite` 作為即時日誌後端 (`output/logs/session.sqlite`)，確保了日誌寫入的高效與安全。在每個任務 (無論成功或失敗) 結束時，`run.py` 的 `finally` 區塊會確保 `LogManager` 的 `archive_to_file` 方法被呼叫，將該次執行的所有日誌轉存為一個帶時間戳的 `.txt` 報告，存放於 `output/logs/archive/`，實現了永久的、人類可讀的作戰紀錄。
    *   **影響**:
        *   **開發流程簡化**: 開發者現在只需關注 `apps/` 下的業務邏輯，並將其主函數註冊到 `run.py` 即可，無需再編寫重複的路徑校正和日誌初始化代碼。
        *   **可追溯性增強**: 所有的操作都有了集中化、永久性的日誌記錄，極大地便利了問題排查和結果審計。

*   **【全專案重構】日誌系統整合**
    *   **背景**: 為了配合全新的 `LogManager`，所有先前使用舊版 `get_logger` 的模組都需要進行重構。
    *   **實作細節**:
        *   系統性地掃描了 `apps/` 目錄下的所有模組。
        *   將模組中的主函數 (如 `main`, `run_etl`) 的簽名進行修改，使其能夠接收一個 `log_manager: LogManager` 參數。
        *   移除了所有 `from core.logger import get_logger` 的引用。
        *   將所有的 `logger.info(...)` 呼叫替換為 `log_manager.log("INFO", ...)`。
        *   更新了 `if __name__ == "__main__":` 區塊，在獨立執行時創建一個備用的 `LogManager` 實例，以保持模組的獨立可測試性。
    *   **影響**:
        *   統一了整個專案的日誌記錄方式。
        *   修復了 `ignition_test.py` 中因無法導入 `get_logger` 而導致的大量測試失敗。

### v0.1.0 (初始版本)
*   建立專案基本結構，包含 `core` 和 `apps` 目錄。
*   實現了多個獨立的數據獲取和分析應用。
*   使用分散的 `get_logger` 進行基本的日誌記錄。
