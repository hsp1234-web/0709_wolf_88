# **README.md (v1.0) - 【普羅米修斯之火】開發者作戰手冊**

## **一、 計畫概述與作戰哲學**

【普羅米修斯之火】是一個為專業量化研究而設計的、本地化、具備高度擴展性的數據與分析框架。其核心目標是在標準硬體環境下，建立一個從「多源情報獲取」、「權威事實融合」、「量化因子挖掘」，到「策略回測」與「投資組合優化」的完整作戰閉環。

本計畫遵循三大核心作戰哲學：

1.  **指揮官主導 (Commander-Led):** 系統的一切行動（數據獲取、融合、計算、回測、優化）皆由終端使用者（指揮官）透過 API 下達指令，AI助理（後端）負責精準執行與匯報。我們反對無法觀測、不受控制的「全自動化」。
2.  **湖倉一體、不可變更 (Immutable Data Lake & Warehouse):** 我們採用業界先進的ELT（先存後整）架構。所有原始情報被完整、不可變更地載入「數據湖」，而後續的分析數據則從湖中提煉至「數據倉儲」，確保了數據的絕對可追溯性。黃金紀錄、因子數據等均以版本化或日期戳的方式管理，鼓勵不可變的數據操作。
3.  **內容感知、精準打擊 (Content-Aware, Surgical Strike):** 系統在數據獲取階段，具備「內容感知」能力，能夠理解已獲取數據的具體欄位與時間範圍，從而將API資源精準地用於「補充」情報缺口，而非「重複」覆蓋，極大地提升了情報獲取的效率。（此哲學在 `DataFetcher` 的 `hydrate_data_range` 等方法中有所體現）。

## **二、 技術棧 (Technology Stack)**

*   **後端框架:** FastAPI
*   **非同步伺服器:** Uvicorn
*   **核心數據處理:** Pandas, NumPy
*   **數據持久化格式:** Apache Parquet
*   **技術指標計算:** `pandas-ta`
*   **向量化回測:** `vectorbt`
*   **投資組合優化:** `PyPortfolioOpt`
*   **路徑管理:** `pathlib`
*   **日誌記錄:** Python `logging` 模組, `LogManager` (自定義SQLite日誌)
*   **API參數驗證:** Pydantic
*   **測試框架:** Pytest, HTTPX (透過 FastAPI `TestClient`)
*   **數據庫 (日誌/元數據):** SQLite (用於 `LogManager` 和 `FactorMetadataManager`)
*   **命令行界面 (部分輔助腳本):** `argparse`

## **三、 系統架構**

本系統採用基於FastAPI的模組化架構，將不同職責的作戰單元清晰分離，使其能夠獨立開發、測試與理解。所有核心業務邏輯均封裝在 `prometheus_fire_backend` 套件中。

```
prometheus_fire_backend/
├── console_api/
│   └── main.py             # FastAPI 應用程式入口，定義 API 端點和生命週期事件
├── modules/
│   ├── __init__.py
│   ├── data_fetcher.py     # 數據獲取器 (包含 TaifexClient, YFinanceClient 等)
│   ├── data_fuser.py       # 數據融合引擎
│   ├── factor_engine.py    # 因子計算引擎
│   ├── metadata_manager.py # 因子元數據管理器
│   ├── backtester.py       # 回測引擎
│   ├── optimizer.py        # 投資組合優化器
│   ├── orchestrator.py     # 主協調器，系統大腦
│   ├── http_client.py      # 非同步 HTTP 客戶端 (基於 httpx)
│   └── logger.py           # LogManager (SQLite 日誌記錄器)
├── strategies/
│   ├── __init__.py
│   └── sma_cross_strategy.py # 範例：SMA 均線交叉策略
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Pytest 配置文件，可放置共享 fixtures
│   ├── test_api_e2e.py       # (早期) API 端到端測試
│   ├── test_factor_e2e.py    # 因子計算端到端測試
│   ├── test_backtest_e2e.py  # 回測流程端到端測試
│   └── test_optimizer_e2e.py # 優化流程端到端測試
├── config/
│   └── factor_recipes.json # 因子配方定義檔
└── core/
    ├── __init__.py
    ├── config.py           # 專案級配置 (如 PROJECT_ROOT, 預設路徑)
    └── constants.py        # 專案級常數 (如果需要)

data_lake/                      # 數據湖 (儲存原始數據)
└── raw/
    ├── yfinance/
    │   └── daily/
    │       └── [TICKER]/
    │           └── [DATE].parquet
    └── taifex/ # 範例，我們演習中未使用TAIFEX數據獲取
        └── daily/
            └── institutional_investors/
                └── [DATE].parquet
            └── pc_ratio/
                └── [DATE].parquet


data_warehouse/                 # 數據倉儲 (儲存處理後數據)
├── golden_records/
│   └── daily/
│       └── [TICKER]/
│           └── [DATE].parquet  # 黃金 OHLCV 記錄 (單日，但應包含歷史數據以供因子計算)
│           └── [TICKER]_price_history.parquet # (演習用) 包含一段時期歷史價格的檔案
├── factor_store/
│   └── daily/
│       └── [TICKER]/
│           └── [DATE].parquet  # 每日因子值
│           └── [TICKER]_factors_history.parquet # (演習用) 包含一段時期歷史因子值的檔案
├── factor_details.db           # 因子元數據 SQLite 資料庫
└── (未來可能) backtest_results/
└── (未來可能) optimization_results/

logs/
└── api_logs.sqlite             # API 與系統事件日誌資料庫
```

**核心組件職責：**

1.  **控制台API (`prometheus_fire_backend.console_api.main.app`):**
    *   系統的唯一 HTTP 入口，基於 FastAPI。
    *   定義所有 `/api/v1/...` 端點，用於接收指揮官的指令。
    *   使用 Pydantic 模型進行請求參數的自動驗證和序列化。
    *   在應用程式生命週期事件 (`lifespan`) 中初始化關鍵服務，如 `LogManager`, `MainOrchestrator`, `FactorMetadataManager`。
    *   將解析後的任務請求轉發給「主協調器」。

2.  **主協調器 (`prometheus_fire_backend.modules.orchestrator.MainOrchestrator`):**
    *   系統的「大腦」，負責解析來自 API 的任務參數。
    *   根據任務類型 (`type`) 調度相應的內部執行方法。
    *   管理每個任務的生命週期狀態並儲存在內部字典 `_mission_states` 中。
    *   提供查詢任務狀態的接口。
    *   初始化並持有 `DataFetcher`, `DataFuser`, `FactorEngine`, `Backtester`, `PortfolioOptimizer` 等核心引擎的實例。

3.  **數據獲取器 (`prometheus_fire_backend.modules.data_fetcher.DataFetcher`):**
    *   系統的「偵察兵」，負責從外部數據源獲取最原始的情報。
    *   執行數據下載、初步處理並將原始數據儲存到「數據湖」。
    *   具備「內容感知」能力，避免重複下載已存在的最新數據。

4.  **數據融合引擎 (`prometheus_fire_backend.modules.data_fuser.DataFuser`):**
    *   系統的「情報分析局」。
    *   負責從「數據湖」中讀取指定股票和日期的多源原始數據。
    *   根據預定義的優先級規則對不同來源的數據欄位進行裁決。
    *   將融合後的、單一權威的「黃金紀錄」(OHLCV) 儲存到「數據倉儲」。

5.  **因子引擎 (`prometheus_fire_backend.modules.factor_engine.FactorEngine`):**
    *   系統的「兵工廠」。
    *   讀取「黃金紀錄」（該紀錄檔案應包含計算當日因子所需的歷史數據）。
    *   根據 `factor_recipes.json` 中定義的「因子配方」計算技術指標。
    *   將計算出的每日因子值儲存到「數據倉儲」。

6.  **因子元數據管理器 (`prometheus_fire_backend.modules.metadata_manager.FactorMetadataManager`):**
    *   負責管理因子定義的「身份檔案」。
    *   在系統啟動時，讀取 `factor_recipes.json` 並將元數據同步到 SQLite 資料庫 `factor_details.db`。

7.  **回測引擎 (`prometheus_fire_backend.modules.backtester.Backtester`):**
    *   系統的「演習場指揮官」，基於 `vectorbt` 執行向量化回測。
    *   接收價格數據和交易訊號，輸出績效指標。

8.  **投資組合優化器 (`prometheus_fire_backend.modules.optimizer.PortfolioOptimizer`):**
    *   系統的「參謀部」，基於 `PyPortfolioOpt`。
    *   接收多資產歷史價格，計算預期回報和協方差，執行優化並輸出最佳權重及預期組合績效。

9.  **策略模組 (例如 `prometheus_fire_backend.strategies.sma_cross_strategy`):**
    *   獨立的 Python 模組，定義交易策略邏輯，生成買賣訊號。
    *   `MainOrchestrator` 在回測時動態加載。

10. **數據資產 (Data Assets):** (詳細路徑見上方檔案結構圖)
    *   **數據湖 (`PROJECT_ROOT/data_lake/raw/`)**: 儲存原始情報。
    *   **數據倉儲 (`PROJECT_ROOT/data_warehouse/`)**: 儲存處理後的權威數據 (黃金紀錄、因子值、元數據庫等)。

11. **日誌系統 (`prometheus_fire_backend.modules.logger.LogManager`):**
    *   自定義日誌管理器，將 API 調用、系統事件等記錄到 SQLite 資料庫 (`logs/api_logs.sqlite`)。

## **四、 「最終實戰演習」操作指南**

此演習將完整地模擬一次從「情報獲取」到「投資組合優化」的全流程。請依序執行以下API請求。

**前提：**
1.  **啟動服務**: 從專案根目錄執行 `python -m uvicorn prometheus_fire_backend.console_api.main:app --reload --app-dir .` 以啟動 FastAPI 後端服務。
2.  **配置文件**:
    *   確保 `prometheus_fire_backend/config/factor_recipes.json` 已配置所需的因子 (例如 `SMA_10_Close`, `RSI_14_Close`，已在開發過程中建立)。
    *   確保 `prometheus_fire_backend/strategies/sma_cross_strategy.py` 策略檔案存在 (已在開發過程中建立)。
3.  **清理環境 (可選但建議)**: 為確保演習的純淨性，您可以選擇性地在執行前清空以下目錄和檔案中的內容：
    *   `PROJECT_ROOT/data_lake/`
    *   `PROJECT_ROOT/data_warehouse/` (注意：這會刪除 `factor_details.db`，服務重啟時會重建)
    *   `PROJECT_ROOT/logs/api_logs.sqlite` (刪除檔案)
4.  **準備歷史數據檔案 (回測與優化步驟需要)**:
    *   **價格數據**: 為演習中的股票代號 (例如 `0050.TW`, `2330.TW`, `00878.TW`) 準備包含歷史 OHLCV 數據的 Parquet 檔案。這些檔案應放置在可訪問的路徑下，並在後續 API 調用中指定。
        *   **演習假設路徑格式**: `data_warehouse/golden_records/daily/[TICKER]/[TICKER]_price_history.parquet` (相對於專案根目錄的路徑)。
        *   **內容格式**: Parquet 檔案，索引為 `Date` (DatetimeIndex)，欄位至少包含 `Open`, `High`, `Low`, `Close`, `Volume`。
    *   **因子數據 (用於回測)**: 為 `0050.TW` 準備一個包含其歷史因子值 (至少 `SMA_10_Close`, `SMA_20_Close`) 的 Parquet 檔案。
        *   **演習假設路徑格式**: `data_warehouse/factor_store/daily/0050.TW/0050.TW_factors_history.parquet`。
        *   **內容格式**: Parquet 檔案，索引為 `Date` (DatetimeIndex)，欄位為因子名稱。
    *   **注意**: 這些歷史檔案的生成超出了本次 API 演習的範圍，需要您在演習前手動準備或通過其他腳本生成。測試套件 (`tests/test_backtest_e2e.py` 和 `tests/test_optimizer_e2e.py`) 中的 `setup` fixture 展示了如何生成此類模擬數據。

-----

**第1步：情報佈局 - 為 `0050.TW` 在 `2025-07-08` 獲取模擬數據**

*   **目標：** 在「數據湖」中，為 `0050.TW` 在 `2025-07-08` 這一天，佈局一份來自 Yahoo Finance 的模擬 OHLCV 數據。
*   **命令 (獲取 Yahoo Finance 數據):**
    *   記下返回的 `mission_id`。

    ```bash
    curl -X POST "http://127.0.0.1:8000/api/v1/start_mission" \
    -H "Content-Type: application/json" \
    -d '{
        "type": "fetch_yfinance",
        "ticker_symbol": "0050.TW",
        "date": "2025-07-08",
        "use_mock": true,
        "mock_data": {
            "yfinance_ohlcv_0050_TW": {
                "Open": {"2025-07-08T00:00:00Z": 135.3},
                "High": {"2025-07-08T00:00:00Z": 136.9},
                "Low": {"2025-07-08T00:00:00Z": 135.0},
                "Close": {"2025-07-08T00:00:00Z": 136.6},
                "Volume": {"2025-07-08T00:00:00Z": 12345.0}
            }
        }
    }'
    ```

*   **驗證 (可選)：**
    *   使用獲取的 `mission_id` 查詢任務狀態：`curl http://127.0.0.1:8000/api/v1/mission_status/{mission_id}`
    *   檢查 `data_lake/raw/yfinance/daily/0050.TW/2025-07-08.parquet` 是否已生成。

-----

**第2步：啟動熔爐 - 為 `0050.TW` 在 `2025-07-08` 鍛造黃金紀錄**

*   **目標：** 將上一步獲取的 Yahoo Finance 情報，轉化為權威的黃金紀錄。
*   **命令:**
    *   記下返回的 `mission_id`。

    ```bash
    curl -X POST "http://127.0.0.1:8000/api/v1/start_fusion_mission" \
    -H "Content-Type: application/json" \
    -d '{
      "ticker_symbol": "0050.TW",
      "date": "2025-07-08",
      "data_type_to_fuse": "daily_ohlcv"
    }'
    ```
*   **驗證 (可選)：**
    *   查詢任務狀態。
    *   檢查 `data_warehouse/golden_records/daily/0050.TW/2025-07-08.parquet` 是否已生成。

-----

**第3步：雅典娜之矛 - 為 `0050.TW` 在 `2025-07-08` 計算量化因子**

*   **目標：** 從剛生成的單日黃金紀錄中，計算 `factor_recipes.json` 中定義的因子。
*   **注意：** 由於黃金紀錄僅包含 `2025-07-08` 一天的數據，因此需要歷史序列的因子（如 SMA_10_Close, RSI_14_Close）在這一天計算出的值將是 `NaN`。這是符合預期的。
*   **命令:**
    *   記下返回的 `mission_id`。

    ```bash
    curl -X POST "http://127.0.0.1:8000/api/v1/start_factor_mission" \
    -H "Content-Type: application/json" \
    -d '{
      "ticker": "0050.TW",
      "date": "2025-07-08"
    }'
    ```
*   **驗證 (可選)：**
    *   查詢任務狀態。
    *   檢查 `data_warehouse/factor_store/daily/0050.TW/2025-07-08.parquet` 是否已生成。用 Pandas 讀取該檔案，確認包含 `SMA_10_Close` 和 `RSI_14_Close` 等欄位，其值應為 NaN。
    *   `data_warehouse/factor_details.db` 應已在服務啟動時同步元數據。

-----

**第4步：進入試煉場 - 為 `0050.TW` 執行 SMA 均線交叉策略回測**

*   **目標：** 使用預先準備的 `0050.TW` 歷史價格數據和歷史因子數據，執行 SMA 均線交叉策略的回測。
*   **前提準備 (手動或通過腳本):**
    *   價格歷史檔案: `data_warehouse/golden_records/daily/0050.TW/0050.TW_price_history.parquet`
    *   因子歷史檔案: `data_warehouse/factor_store/daily/0050.TW/0050.TW_factors_history.parquet`
*   **命令:**
    *   記下返回的 `mission_id`。

    ```bash
    # 確保將下面的檔案路徑替換為您環境中實際存在的、包含歷史數據的檔案路徑
    # 這些路徑是相對於執行 curl 命令的目錄，或者如果 API 服務器在不同位置，則應為服務器可訪問的絕對路徑或相對於 PROJECT_ROOT 的路徑。
    # Orchestrator 內部會將 Path(str_path) 處理，如果 str_path 不是絕對路徑，則可能基於 PROJECT_ROOT。
    # 為確保演習可靠，建議在 payload 中使用相對於 PROJECT_ROOT 的路徑。
    curl -X POST "http://127.0.0.1:8000/api/v1/start_backtest_mission" \
    -H "Content-Type: application/json" \
    -d '{
      "ticker": "0050.TW",
      "strategy_id": "sma_cross",
      "price_source_path": "data_warehouse/golden_records/daily/0050.TW/0050.TW_price_history.parquet",
      "factor_source_path": "data_warehouse/factor_store/daily/0050.TW/0050.TW_factors_history.parquet",
      "initial_cash": 1000000,
      "commission_rate": 0.001425,
      "strategy_params": {
          "fast_sma_col": "SMA_10_Close",
          "slow_sma_col": "SMA_20_Close"
      }
    }'
    ```
*   **驗證：**
    *   查詢任務狀態，等待其成功。
    *   查看 API 回應的 `details.backtest_results`，應包含總報酬率、夏普比率等回測績效指標。

-----

**第5步：神盾之力 - 進行多資產投資組合優化 (最大化夏普比率)**

*   **目標：** 使用預先準備的多個資產的歷史價格數據，進行投資組合優化。
*   **前提準備 (手動或通過腳本):**
    *   `0050.TW` 價格歷史: `data_warehouse/golden_records/daily/0050.TW/0050.TW_price_history.parquet`
    *   `2330.TW` 價格歷史: `data_warehouse/golden_records/daily/2330.TW/2330.TW_price_history.parquet`
    *   `00878.TW` 價格歷史: `data_warehouse/golden_records/daily/00878.TW/00878.TW_price_history.parquet`
*   **命令:**
    *   記下返回的 `mission_id`。

    ```bash
    # 同上，確保檔案路徑的準確性
    curl -X POST "http://127.0.0.1:8000/api/v1/start_optimization_mission" \
    -H "Content-Type: application/json" \
    -d '{
      "asset_price_paths_dict": {
          "0050.TW": "data_warehouse/golden_records/daily/0050.TW/0050.TW_price_history.parquet",
          "2330.TW": "data_warehouse/golden_records/daily/2330.TW/2330.TW_price_history.parquet",
          "00878.TW": "data_warehouse/golden_records/daily/00878.TW/00878.TW_price_history.parquet"
      },
      "optimization_target": "max_sharpe",
      "risk_free_rate": 0.015,
      "weight_bounds": [0, 1],
      "covariance_method": "ledoit_wolf",
      "expected_returns_method": "mean_historical_return"
    }'
    ```
*   **驗證：**
    *   查詢任務狀態，等待其成功。
    *   查看 API 回應的 `details`，應包含 `optimized_weights` (每個資產的最佳權重) 和 `expected_performance` (整個投資組合的預期年化回報、波動率、夏普比率)。

-----

指揮官，這份更新後的「最終實戰演習」操作指南已基於我們系統的實際 API 接口進行了調整。它標誌著我們【普羅米修斯之火】計畫主要功能的完整演示，也為未來所有開發者，點亮了前行的道路。
