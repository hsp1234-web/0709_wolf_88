# **【普羅米修斯之火】金融數據與分析框架 - 開發者手冊 v0.6.0**

## **一、 專案概覽與目的**

【普羅米修斯之火】是一個專為進階量化研究與金融市場分析而設計的 Python 框架。本專案旨在提供一個從多樣化數據源獲取金融數據、進行複雜指標計算、回測交易策略、並將結果視覺化的完整解決方案。其核心設計強調模組化、可擴展性以及數據處理的穩健性。

**最近更新（作戰計畫 038：「精準指示器系統」實作）：**
*   **架構升級**: 引入了基於 `Typer` 的統一命令列介面 (`run.py`)，標準化所有應用的執行流程。
*   **日誌系統**: 實作了 v82.0「精準指示器」日誌系統 (`core/logger.py`)，提供基於 SQLite 的即時日誌記錄與任務結束後的自動歸檔功能。
*   **全專案重構**: 將所有模組的日誌記錄方式重構為依賴注入模型，以適應新的日誌系統，並修復了相關的所有測試。

## **二、 技術棧 (Technology Stack)**

*   **核心程式語言:** Python (>=3.12, <3.14)
*   **依賴管理:** Poetry (v1.8.2 或相容版本)
*   **命令列介面**: Typer (`^0.16.0`)
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
    *   SQLite3 (內建，用於日誌系統)
*   **設定檔管理:**
    *   PyYAML (`^6.0.2`)
*   **視覺化**:
    *   Plotly (`^6.2.0`)
*   **測試與品質保證:**
    *   Pytest (`^8.4.1`)
    *   Pytest-Mock (`^3.14.1`)
    *   Ruff (用於程式碼檢查與格式化)

## **三、 檔案目錄結構 (v0.8.0)**

以下為專案目前的完整檔案目錄結構 (已移除 `__pycache__` 和 `.pyc` 檔案)。

> **[文件化說明]**
> 關於下表中每一個檔案的詳細功能、職責與執行邏輯，請參閱 **[`PROJECT_FILES_GLOSSARY.md`](./PROJECT_FILES_GLOSSARY.md)** 檔案。

```
.:
PROJECT_FILES_GLOSSARY.md
README.md
TEST_REPORT.md
_test_run.py
apps
archive_test.py
check_qsize.py
config.yml
core
file_structure.txt
latest_structure.txt
mypy.ini
output
pipeline_test_loader.duckdb
pipelines
poetry.lock
prometheus_fire.duckdb
pyproject.toml
pytest.ini
read_logs.py
run.py
run_pipeline.sh
run_show_results.py
run_tests.py
tests


./apps:
__init__.py
analysis_pipeline
backtest_worker_app.py
backtesting_engine
dashboard
db_manager
evolution_app.py
factor_engine
optimizer_app.py
pipeline_metadata_manager
portfolio_optimizer
py.typed
query_gateway.py
report_generator
run_finmind_test.py
run_fmp_test.py
run_gold_layer.py
run_stress_index.py
run_taifex_prototype_test.py
tools
visualization


./apps/analysis_pipeline:
run.py


./apps/backtesting_engine:
__init__.py
engine.py
run.py


./apps/dashboard:
dashboard.html

./apps/db_manager:
setup_database.py


./apps/factor_engine:
engine.py
run_factor_etl.py
sma_crossover_factor.py


./apps/pipeline_metadata_manager:
__init__.py
manager.py


./apps/portfolio_optimizer:
__init__.py
main.py


./apps/report_generator:
__init__.py
generator.py
run.py


./apps/tools:
clear_results.py
report_generator_app.py
show_results.py
task_adder_app.py


./apps/visualization:
plot_sma_crossover.py


./core:
__init__.py
analysis
analyzers
clients
config.py
constants.py
db
engines
logger.py
pipelines
py.typed
queue
services
utils


./core/analysis:
data_engine.py
stress_index.py


./core/analyzers:
__init__.py
base_analyzer.py


./core/clients:
__init__.py
base.py
finmind.py
fmp.py
fred.py
nyfed.py
taifex_db.py
yfinance.py


./core/db:
__init__.py
db_manager.py
results_saver.py


./core/engines:
__init__.py
robust_acquisition_engine.py


./core/pipelines:
__init__.py
base_step.py
pipeline.py
steps


./core/pipelines/steps:
__init__.py
aggregators.py
financial_steps.py
loaders.py


./core/queue:
__init__.py
base.py
sqlite_queue.py


./core/services:
__init__.py
backtesting_service.py
evolution_chamber.py
optimizer_service.py


./core/utils:
__init__.py
caching.py
path_utils.py


./output:
logs
reports
test_integration_log.db
test_log_archive

./output/logs:
archive
session.sqlite
standalone_test.sqlite
test_evolution_pipeline.sqlite

./output/logs/archive:
battle_report_20250714_082411.txt
battle_report_20250714_082414.txt
battle_report_20250714_082423.txt
battle_report_20250714_082445.txt
battle_report_20250714_082513.txt
battle_report_20250714_082515.txt
battle_report_20250714_082521.txt
battle_report_20250714_082542.txt
battle_report_20250714_082558.txt
battle_report_20250714_082559.txt
battle_report_20250714_082605.txt
battle_report_20250714_082627.txt
battle_report_20250714_082653.txt
battle_report_20250714_082655.txt
battle_report_20250714_082701.txt
battle_report_20250714_082723.txt
battle_report_20250714_082805.txt
battle_report_20250714_082806.txt
battle_report_20250714_082813.txt
battle_report_20250714_082834.txt

./output/reports:
report.xml

./output/test_log_archive:

./pipelines:
__init__.py
p0_downloader
p1_explorer
p2_elt_pipeline
p3_backfill_hourly_data


./pipelines/p0_downloader:
run.py


./pipelines/p1_explorer:
__init__.py
run.py


./pipelines/p2_elt_pipeline:
run_elt.py


./pipelines/p3_backfill_hourly_data:
run.py

./tests:
conftest.py
fixtures
ignition_test.py
integration
test_p0_downloader.py
test_p1_explorer.py
test_p2_elt_pipeline.py
unit


./tests/fixtures:
corrupted.zip
no_data_response.html
sample_daily_ohlc_20250711.zip

./tests/integration:
analysis
apps
pipelines
test_evolution_pipeline.py
test_full_pipeline.py


./tests/integration/analysis:
test_data_engine_cache.py


./tests/integration/apps:
test_analysis_pipeline.py
test_refactored_apps.py


./tests/integration/pipelines:
test_data_pipeline.py
test_example_flow.py


./tests/unit:
analysis
core
test_feature_analyzer.py


./tests/unit/analysis:
test_data_engine.py


./tests/unit/core:
analyzers
clients
test_queue.py


./tests/unit/core/analyzers:
test_base_analyzer.py


./tests/unit/core/clients:
test_finmind.py
test_fmp.py
test_fred.py
test_nyfed.py
test_yfinance.py
```

## **四、 環境設定與執行**

本專案使用 [Poetry](https://python-poetry.org/) 進行依賴管理。

1.  **安裝 Poetry** (如果尚未安裝)。
2.  **克隆專案**。
3.  **配置 Poetry 虛擬環境** (推薦 `poetry config virtualenvs.in-project true`)。
4.  **安裝依賴**: `poetry install`。
5.  **激活虛擬環境**: `poetry shell` (或使用 `poetry run <command>`)。
6.  **設定 API 金鑰**:
    *   **FRED API 金鑰**: 為了運行壓力指數計算，您**必須**在 `config.yml` 中提供一個有效的 FRED API 金鑰。
        ```yaml
        # In config.yml
        api_keys:
          fred: "YOUR_REAL_FRED_API_KEY_HERE"
        ```
    *   ⚠️ **安全警告**：`config.yml` 檔案包含敏感金鑰，**絕對不可**提交到任何版本控制系統（如 Git）。請確保它已被列在 `.gitignore` 檔案中。

## **五、 主要功能執行與測試**

### **5.1 主要功能執行 (v0.6.0 新版 CLI 用法)**
**[重要]** 從 v0.6.0 開始，所有獨立的應用腳本都已整合至根目錄的 `run.py` 中，透過子命令進行呼叫。

*   **查看所有可用命令**:
    ```bash
    poetry run python run.py --help
    ```
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

### **5.2 (歷史用法 - v0.5.0 及更早版本)**

#### **5.2.1 數據回填與快取 (歷史)**
*   **執行數據回填**:
    ```bash
    # [舊命令，v0.6.0 後不推薦]
    poetry run python pipelines/p3_backfill_hourly_data/run.py
    ```
*   **說明**: 此腳本會使用 `YFinanceClient` (無需金鑰) 獲取 SPY 的小時級數據，並存儲在根目錄的 `prometheus_fire.duckdb` 檔案中。

#### **5.2.2 執行 SMA 策略回測與視覺化 (歷史)**
1.  **計算因子並執行回測**:
    ```bash
    # [舊命令，v0.6.0 後請使用 run.py sma-backtest]
    poetry run python apps/backtesting_engine/run.py
    ```
2.  **生成視覺化圖表**:
    ```bash
    # [此腳本暫未整合至 run.py]
    poetry run python apps/visualization/plot_sma_crossover.py
    ```

#### **5.2.3 執行壓力指數計算 (歷史)**
*   **執行計算**:
    ```bash
    # [舊命令，v0.6.0 後請使用 run.py stress-index]
    poetry run python apps/run_stress_index.py
    ```

### **5.3 測試**
*   **運行所有測試**:
    ```bash
    poetry run pytest
    ```
*   **目前測試狀態**: 112 個通過, 16 個跳過 (基於最近一次完整測試運行)。

## **六、 版本歷史與變更日誌**

### **v0.6.0 (2025-07-13) - 作戰計畫 038**
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

---
## 核心功能：策略演化 (v0.8.0 新增)

本專案的核心現已升級為一個具備自我進化能力的策略探索引擎。您可以透過 `evolve` 命令，驅動系統自動探索並優化策略參數。

**主要工作流程:**

1.  **(可選) 清理環境:**
    ```bash
    # 徹底清除所有先前的回測結果，確保演化從一張白紙開始
    poetry run python run.py clear-results --force
    ```

2.  **啟動運算工作者 (Worker):**
    * 在**一個終端機**中，啟動服務以待命。此進程將作為演化所需的回測算力。
    ```bash
    # 工作者將持續運行，監聽並執行由演化室派發的計算任務
    poetry run python run.py backtest-worker
    ```

3.  **啟動策略演化:**
    * 在**另一個終端機**中，啟動演化流程。
    ```bash
    # 演化室將自動產生、評估、並迭代策略族群
    poetry run python run.py evolve
    ```

4.  **可視化與驗證結果:**
    * 演化完成後，您可以透過儀表板或 CLI 查看最終產出的所有策略表現。
    ```bash
    # 啟動網頁儀表板，查看所有策略的表現分佈
    poetry run python run.py dashboard

    # 或，在終端機中直接查看詳細數據
    poetry run python run.py show-results
    ```

---
### 基礎功能 (歷史用法)
* **手動新增任務 (`add-test-tasks`)**: 此命令用於基礎的管線功能驗證，現已被 `evolve` 的自動化流程所取代。
* **單次優化 (`optimize`)**: 此命令是演化室的前身，用於概念驗證，現已被功能更強大的 `evolve` 命令所取代。

---
## **測試與品質保證 (v0.9.0 新增)**

本專案採用一個多層次的自動化測試與品質保證體系，以確保框架的絕對穩定。

### **1. 靜態防線**
-   **`Ruff` (靜態掃描器)**：第一道防線，捕獲語法錯誤與風格問題。
-   **`deptry` (依賴檢查器)**：第二道防線，確保 `pyproject.toml` 的依賴聲明完整且無冗餘。

### **2. 動態防線**
-   **`ignition_test.py` (導入測試器)**：第三道防線，確保專案所有模組均可被成功導入，不存在循環依賴。
-   **單元測試 (`tests/unit`)**: 針對核心組件（如 `SQLiteQueue`）的精細測試。
-   **整合測試 (`tests/integration`)**:
    -   `test_evolution_pipeline.py`: **輕量化邏輯驗證**。透過模擬(Mocking)回測，專門、快速地驗證演化室的核心演算法。
    -   `test_final_acceptance.py`: **全系統整合驗證**。在隔離環境中，自動化執行從 `evolve` 命令到背景工作者完成計算的完整流程。

### **3. 自動化戰報系統**
透過以下命令，可一鍵執行所有測試，並自動產生一份詳細的 Markdown 格式作戰報告 (`TEST_REPORT.md`)。
```bash
poetry run python run.py run-tests
