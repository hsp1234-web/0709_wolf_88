# 專案檔案詞彙表

本文件詳細說明專案中每個檔案的功能與用途。

## 根目錄

-   `README.md`: 提供專案的整體介紹、安裝說明和使用指南。
-   `_test_run.py`: 用於執行臨時測試的腳本。
-   `config.yml`: 全局設定檔，用於配置資料庫連線、API 金鑰等。
-   `mypy.ini`: `mypy` 型別檢查工具的設定檔。
-   `poetry.lock`: `poetry` 用於鎖定專案依賴版本的檔案。
-   `pyproject.toml`: `poetry` 的專案設定檔，定義專案元數據和依賴。
-   `run.py`: 專案執行的主要進入點。
-   `run_pipeline.sh`: 執行資料管線的腳本。
-   `run_tests.py`: 執行自動化測試的腳本。

## `apps` - 應用程式

此目錄包含各個獨立的應用程式模組。

-   `analysis_pipeline/run.py`: 執行資料分析管線。
-   `backtesting_engine/engine.py`: 回測引擎的核心邏輯。
-   `backtesting_engine/run.py`: 執行回測。
-   `db_manager/setup_database.py`: 設定和初始化資料庫。
-   `factor_engine/engine.py`: 因子計算引擎。
-   `factor_engine/run_factor_etl.py`: 執行因子數據的 ETL (抽取、轉換、載入) 流程。
-   `factor_engine/sma_crossover_factor.py`: 實現簡單移動平均線 (SMA) 交叉策略的因子。
-   `pipeline_metadata_manager/manager.py`: 管理和追蹤管線的元數據。
-   `portfolio_optimizer/main.py`: 投資組合優化器。
-   `report_generator/generator.py`: 產生回測或分析報告。
-   `report_generator/run.py`: 執行報告產生。
-   `visualization/plot_sma_crossover.py`: 將 SMA 交叉策略的結果可視化。
-   `run_finmind_test.py`: 測試 `FinMind` API 客戶端。
-   `run_fmp_test.py`: 測試 `FMP` API 客戶端。
-   `run_gold_layer.py`: 執行黃金層數據處理。
-   `run_stress_index.py`: 計算和分析壓力指數。
-   `run_taifex_prototype_test.py`: 測試台交所數據原型。

## `core` - 核心模組

此目錄包含專案的核心共用模組。

-   `analysis/data_engine.py`: 資料引擎，負責提供和管理分析數據。
-   `analysis/stress_index.py`: 壓力指數的計算邏輯。
-   `analyzers/base_analyzer.py`: 分析器的基底類別。
-   `clients/`: 包含所有第三方 API 的客戶端。
    -   `base.py`: API 客戶端的基底類別。
    -   `finmind.py`: `FinMind` API。
    -   `fmp.py`: `Financial Modeling Prep` API。
    -   `fred.py`: `FRED` (Federal Reserve Economic Data) API。
    -   `nyfed.py`: `New York Fed` API。
    -   `taifex_db.py`: 台交所資料庫客戶端。
    -   `yfinance.py`: `Yahoo Finance` API。
-   `config.py`: 應用程式設定的管理模組。
-   `constants.py`: 定義專案中使用的常數。
-   `db/db_manager.py`: 資料庫管理模組。
-   `engines/robust_acquisition_engine.py`: 提供穩健的數據獲取功能。
-   `logger.py`: 日誌記錄模組。
-   `pipelines/`: 資料管線的核心組件。
    -   `base_step.py`: 管線步驟的基底類別。
    -   `pipeline.py`: 管線的核心邏輯。
    -   `steps/`: 包含各個管線步驟的實作。
-   `utils/`: 共用的工具函式。
    -   `caching.py`: 快取機制。
    -   `path_utils.py`: 路徑處理工具。

## `output` - 輸出

此目錄存放腳本執行後產生的檔案。

-   `logs/`: 存放日誌檔案。

## `pipelines` - 資料管線

此目錄包含主要的資料處理管線。

-   `p0_downloader/run.py`: 下載原始資料。
-   `p1_explorer/run.py`: 探索和初步分析資料。
-   `p2_elt_pipeline/run_elt.py`: 執行 ELT (抽取、載入、轉換) 流程。
-   `p3_backfill_hourly_data/run.py`: 回填每小時的歷史資料。
