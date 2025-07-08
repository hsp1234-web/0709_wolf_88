import pytest
import httpx
import asyncio
import os
import pandas as pd
import pandas.testing
from datetime import datetime, timedelta
from pathlib import Path
import shutil # 用於清理目錄

from prometheus_fire_backend.modules.orchestrator import MISSION_STATUS_SUCCESS
from core.config import PROJECT_ROOT

# --- 測試常量 ---
# Data Lake 和 Data Warehouse 的基礎路徑
DATA_LAKE_BASE_PATH = PROJECT_ROOT / "data_lake" / "raw"
DATA_LAKE_RAW_TAIFEX_PATH = DATA_LAKE_BASE_PATH / "taifex"
DATA_LAKE_RAW_YFINANCE_PATH = DATA_LAKE_BASE_PATH / "yfinance" / "ohlcv" # YFinanceClient 儲存 OHLCV 的特定路徑

DATA_WAREHOUSE_BASE_PATH = PROJECT_ROOT / "data_warehouse" / "golden_records"
DATA_WAREHOUSE_DAILY_OHLCV_PATH = DATA_WAREHOUSE_BASE_PATH / "daily_ohlcv"

# 測試用的股票代號和日期
TEST_FUSION_TICKER = "2330.TW" # 台積電
TEST_FUSION_DATE_STR = "2024-03-15" # 假設的測試日期
TEST_FUSION_DATETIME = pd.to_datetime(TEST_FUSION_DATE_STR)

# API 輪詢參數
MAX_POLL_ATTEMPTS = 45  # 增加輪詢次數以應對可能的延遲
POLL_INTERVAL = 0.5  # 輪詢間隔秒數

# --- 輔助函數 ---

def clean_directory(dir_path: Path):
    """如果目錄存在，則遞歸刪除該目錄及其所有內容。"""
    if dir_path.exists() and dir_path.is_dir():
        try:
            shutil.rmtree(dir_path)
            print(f"已清理目錄: {dir_path}")
        except Exception as e:
            print(f"清理目錄 {dir_path} 失敗: {e}")

@pytest.fixture(scope="function", autouse=True)
def manage_test_data_directories():
    """
    在每個測試函數執行前後管理 (清理和創建) Data Lake 和 Data Warehouse 中的測試數據目錄。
    """
    # 定義本次測試可能影響的特定股票和日期的路徑
    # Taifex (假設未來有 OHLCV 數據，或為其他數據類型預留)
    # 由於目前 TaifexClient 不處理 OHLCV，我們主要關注其模擬數據檔案的清理 (如果測試生成了的話)
    # 為了簡化，我們將手動創建模擬的 Taifex OHLCV Parquet 檔案，所以清理也針對它
    taifex_ohlcv_ticker_path = DATA_LAKE_RAW_TAIFEX_PATH / "ohlcv" / TEST_FUSION_TICKER

    yfinance_ticker_path = DATA_LAKE_RAW_YFINANCE_PATH / TEST_FUSION_TICKER
    golden_record_ticker_path = DATA_WAREHOUSE_DAILY_OHLCV_PATH / TEST_FUSION_TICKER

    # 測試前清理
    print("\n--- Test Setup: Cleaning directories ---")
    clean_directory(taifex_ohlcv_ticker_path)
    clean_directory(yfinance_ticker_path)
    clean_directory(golden_record_ticker_path)

    # 確保基礎目錄存在 (通常由應用程式邏輯或 fixture `ensure_data_lake_path_exists` 處理)
    # 此處我們確保測試所需的特定 ticker 目錄的父目錄存在
    (DATA_LAKE_RAW_TAIFEX_PATH / "ohlcv").mkdir(parents=True, exist_ok=True)
    DATA_LAKE_RAW_YFINANCE_PATH.mkdir(parents=True, exist_ok=True)
    DATA_WAREHOUSE_DAILY_OHLCV_PATH.mkdir(parents=True, exist_ok=True)
    print("--- Test Setup: Base directories ensured ---")

    yield # 執行測試

    # 測試後可選擇再次清理，但通常 fixture 的 scope="function" 已確保隔離
    # print("\n--- Test Teardown: Cleaning directories again (optional) ---")
    # clean_directory(taifex_ohlcv_ticker_path)
    # clean_directory(yfinance_ticker_path)
    # clean_directory(golden_record_ticker_path)

async def poll_mission_status(async_client: httpx.AsyncClient, mission_id: str, task_name: str) -> bool:
    """輪詢任務狀態直到成功或失敗。"""
    for attempt in range(MAX_POLL_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL)
        status_response = await async_client.get(f"/api/v1/mission_status/{mission_id}")
        if status_response.status_code == 404:
            print(f"[{task_name}] 輪詢嘗試 {attempt + 1}/{MAX_POLL_ATTEMPTS}: 任務 {mission_id} 狀態 404，繼續輪詢...")
            continue

        assert status_response.status_code == 200, f"[{task_name}] 查詢任務 {mission_id} 狀態 API 請求失敗: {status_response.text}"
        status_json = status_response.json()
        current_status = status_json.get("status")
        print(f"[{task_name}] 輪詢嘗試 {attempt + 1}/{MAX_POLL_ATTEMPTS}: 任務 {mission_id} 狀態: {current_status}, 訊息: {status_json.get('message')}")

        if current_status == MISSION_STATUS_SUCCESS:
            return True
        elif current_status == "failed":
            pytest.fail(f"[{task_name}] 任務 {mission_id} 執行失敗: {status_json.get('message')}. Details: {status_json.get('details')}")

    pytest.fail(f"[{task_name}] 任務 {mission_id} 在 {MAX_POLL_ATTEMPTS * POLL_INTERVAL} 秒內未完成。")
    return False # 理論上不會執行到這裡

# --- 端到端融合測試 ---
@pytest.mark.asyncio
async def test_full_fusion_pipeline_e2e(async_client: httpx.AsyncClient):
    """
    測試完整的數據獲取（模擬）到數據融合的端到端流程。
    """
    # --- 1. 準備：定義模擬數據 ---
    # 模擬 YFinance 數據 (來源 yfinance)
    df_yfinance_mock = pd.DataFrame({
        'Open': [150.0], 'High': [152.5], 'Low': [149.0], 'Close': [151.0], 'Volume': [2000000]
    }, index=[TEST_FUSION_DATETIME])
    df_yfinance_mock.index.name = "Date"

    # 模擬 Taifex 數據 (來源 taifex) - 假設未來 TaifexClient 能獲取個股 OHLCV
    # 為了測試融合邏輯，這裡的數據應與 yfinance 的部分重疊但有差異
    # 例如，Taifex 的 Close 價格不同，且 Volume 數據質量較差或不存在
    df_taifex_mock = pd.DataFrame({
        'Open': [150.2], 'High': [152.8], 'Low': [148.8], 'Close': [150.5], 'Volume': [100] # Volume 較低
    }, index=[TEST_FUSION_DATETIME])
    df_taifex_mock.index.name = "Date"

    # --- 2. 執行：情報佈局 (生成模擬原始數據) ---

    # 2a. 生成模擬 YFinance 數據到 Data Lake
    yfinance_mission_params = {
        "type": "fetch_yfinance",
        "ticker_symbol": TEST_FUSION_TICKER,
        "date": TEST_FUSION_DATE_STR,
        "use_mock": True,
        "mock_data": {"ohlcv_df": df_yfinance_mock.to_dict(orient='split')}
    }
    print(f"\n啟動 YFinance 模擬數據獲取任務 for {TEST_FUSION_TICKER} on {TEST_FUSION_DATE_STR}...")
    response_yfinance = await async_client.post("/api/v1/start_mission", json=yfinance_mission_params)
    assert response_yfinance.status_code == 200, f"啟動 YFinance 獲取任務失敗: {response_yfinance.text}"
    mission_id_yfinance = response_yfinance.json()["mission_id"]
    assert await poll_mission_status(async_client, mission_id_yfinance, "YFinance Fetch"), "YFinance 模擬數據獲取任務未成功。"
    print(f"YFinance 模擬數據獲取任務 {mission_id_yfinance} 完成。")

    # 驗證 YFinance Parquet 檔案已生成 (可選，但有助於調試)
    yfinance_parquet_path = DATA_LAKE_RAW_YFINANCE_PATH / TEST_FUSION_TICKER / f"{TEST_FUSION_DATE_STR}.parquet"
    assert yfinance_parquet_path.exists(), f"YFinance 的模擬 Parquet 檔案未生成於: {yfinance_parquet_path}"
    print(f"YFinance 模擬 Parquet 檔案已確認生成: {yfinance_parquet_path}")

    # 2b. 手動創建模擬 Taifex OHLCV Parquet 檔案到 Data Lake
    # (因為 TaifexClient 目前不直接支持 OHLCV 獲取和對應的 DataFrame 模擬注入)
    taifex_ohlcv_dir = DATA_LAKE_RAW_TAIFEX_PATH / "ohlcv" / TEST_FUSION_TICKER
    taifex_ohlcv_dir.mkdir(parents=True, exist_ok=True)
    taifex_parquet_path = taifex_ohlcv_dir / f"{TEST_FUSION_DATE_STR}.parquet"
    try:
        df_taifex_mock.to_parquet(taifex_parquet_path, index=True)
        print(f"手動創建模擬 Taifex OHLCV Parquet 檔案於: {taifex_parquet_path}")
    except Exception as e:
        pytest.fail(f"手動創建 Taifex 模擬 Parquet 檔案失敗: {e}")
    assert taifex_parquet_path.exists(), "Taifex 的模擬 Parquet 檔案未能手動創建。"


    # --- 3. 執行：啟動熔爐 (數據融合任務) ---
    fusion_mission_params = {
        "ticker_symbol": TEST_FUSION_TICKER,
        "date": TEST_FUSION_DATE_STR,
        "data_type_to_fuse": "daily_ohlcv" # 與 source_priority.json 中的鍵匹配
    }
    print(f"\n啟動數據融合任務 for {TEST_FUSION_TICKER} on {TEST_FUSION_DATE_STR}...")
    response_fusion = await async_client.post("/api/v1/start_fusion_mission", json=fusion_mission_params)
    assert response_fusion.status_code == 200, f"啟動數據融合任務失敗: {response_fusion.text}"
    mission_id_fusion = response_fusion.json()["mission_id"]
    assert await poll_mission_status(async_client, mission_id_fusion, "Data Fusion"), "數據融合任務未成功。"
    print(f"數據融合任務 {mission_id_fusion} 完成。")

    # --- 4. 驗證：黃金紀錄 ---
    golden_record_file_path = DATA_WAREHOUSE_DAILY_OHLCV_PATH / TEST_FUSION_TICKER / f"{TEST_FUSION_DATE_STR}.parquet"
    assert golden_record_file_path.exists(), f"黃金紀錄 Parquet 檔案未生成於: {golden_record_file_path}"
    print(f"黃金紀錄 Parquet 檔案已確認生成: {golden_record_file_path}")

    df_golden_actual = pd.read_parquet(golden_record_file_path)
    print("\實際生成的黃金記錄內容:")
    print(df_golden_actual)

    # 根據 source_priority.json:
    # "Open": ["taifex", "yfinance"], "High": ["taifex", "yfinance"],
    # "Low": ["taifex", "yfinance"], "Close": ["taifex", "yfinance"],
    # "Volume": ["yfinance", "taifex"]
    expected_golden_data = {
        'Open': [df_taifex_mock['Open'].iloc[0]],       # 預期來自 taifex
        'High': [df_taifex_mock['High'].iloc[0]],       # 預期來自 taifex
        'Low': [df_taifex_mock['Low'].iloc[0]],         # 預期來自 taifex
        'Close': [df_taifex_mock['Close'].iloc[0]],     # 預期來自 taifex
        'Volume': [df_yfinance_mock['Volume'].iloc[0]]  # 預期來自 yfinance
    }
    df_golden_expected = pd.DataFrame(expected_golden_data, index=[TEST_FUSION_DATETIME])
    df_golden_expected.index.name = "Date"

    print("\n預期的黃金記錄內容:")
    print(df_golden_expected)

    pandas.testing.assert_frame_equal(df_golden_actual, df_golden_expected, check_dtype=True, check_index_type=True)
    print("\n端到端融合測試成功！黃金記錄內容符合預期。")

    # 注意: @pytest.fixture(autouse=True) manage_test_data_directories 已處理清理
    # 無需在此處再次手動清理
```
