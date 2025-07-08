import pytest
import pandas as pd
import pandas_ta as ta
import numpy as np
import shutil
import sqlite3
import json
from pathlib import Path
from fastapi.testclient import TestClient

from core.config import PROJECT_ROOT
# 假設 FastAPI app 實例可以從 main 導入
from prometheus_fire_backend.console_api.main import app

# --- 常數定義 ---
TEST_TICKER = "E2E_TEST_STOCK"
TEST_DATE_STR = "2023-10-26" # 一個特定的日期
NUM_HISTORICAL_DAYS = 30 # 計算因子所需的歷史數據天數 (例如 SMA10, RSI14 需要至少14+天)

GOLDEN_RECORDS_BASE_DIR = PROJECT_ROOT / "data_warehouse" / "golden_records" / "daily"
FACTOR_STORE_BASE_DIR = PROJECT_ROOT / "data_warehouse" / "factor_store" / "daily"
METADATA_DB_PATH = PROJECT_ROOT / "data_warehouse" / "factor_details.db"
RECIPES_CONFIG_PATH = PROJECT_ROOT / "prometheus_fire_backend" / "config" / "factor_recipes.json"

# 預期的黃金紀錄檔案路徑 (包含歷史數據，但以 TEST_DATE_STR 命名，模擬當日觸發分析)
# Orchestrator 的 _execute_factor_calculation_task 會讀取 ticker/date.parquet
# 所以我們準備的黃金紀錄檔案名就是 TEST_DATE_STR.parquet
GOLDEN_RECORD_TICKER_DIR = GOLDEN_RECORDS_BASE_DIR / TEST_TICKER
GOLDEN_RECORD_FILE_PATH = GOLDEN_RECORD_TICKER_DIR / f"{TEST_DATE_STR}.parquet"

# FactorEngine 會為黃金紀錄中的每一天（如果有多天）生成一個因子檔案
# 我們主要關心針對 TEST_DATE_STR 生成的因子檔案
FACTOR_FILE_TICKER_DIR = FACTOR_STORE_BASE_DIR / TEST_TICKER
EXPECTED_FACTOR_FILE_PATH = FACTOR_FILE_TICKER_DIR / f"{TEST_DATE_STR}.parquet"


# --- Pytest Fixtures ---
@pytest.fixture(scope="function") # function scope 表示每個測試函數都會執行一次
def setup_test_environment():
    print("Setting up test environment...")

    # 1. 清理舊的測試檔案和目錄
    if GOLDEN_RECORD_TICKER_DIR.exists():
        shutil.rmtree(GOLDEN_RECORD_TICKER_DIR)
    if FACTOR_FILE_TICKER_DIR.exists():
        shutil.rmtree(FACTOR_FILE_TICKER_DIR)
    if METADATA_DB_PATH.exists():
        METADATA_DB_PATH.unlink()

    GOLDEN_RECORD_TICKER_DIR.mkdir(parents=True, exist_ok=True)
    FACTOR_FILE_TICKER_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


    # 2. 準備因子配方檔案 (如果不存在，則創建一個基本的)
    # 這個檔案應該由之前的步驟創建，但為了測試的獨立性，可以檢查一下
    if not RECIPES_CONFIG_PATH.exists():
        RECIPES_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        default_recipes = {
            "SMA_10_Close": {
                "name": "SMA_10_Close", "type": "trend", "description": "10-day SMA",
                "calculator_type": "pandas_ta", "calculator_function": "sma",
                "params": {"length": 10, "source_column": "Close"},
                "output_column_name": "SMA_10_Close"
            },
            "RSI_14_Close": {
                "name": "RSI_14_Close", "type": "momentum", "description": "14-day RSI",
                "calculator_type": "pandas_ta", "calculator_function": "rsi",
                "params": {"length": 14, "source_column": "Close"},
                "output_column_name": "RSI_14_Close"
            }
        }
        with open(RECIPES_CONFIG_PATH, 'w') as f:
            json.dump(default_recipes, f, indent=2)
        print(f"Created a default recipes file at {RECIPES_CONFIG_PATH} for testing.")


    # 3. 創建包含足夠歷史數據的模擬黃金紀錄 DataFrame
    # TEST_DATE_STR 將是這個序列中的最後一天
    date_index = pd.date_range(end=pd.to_datetime(TEST_DATE_STR), periods=NUM_HISTORICAL_DAYS, freq='B')

    np.random.seed(42)
    open_prices = np.random.uniform(90, 110, NUM_HISTORICAL_DAYS)
    close_prices = open_prices + np.random.normal(0, 2, NUM_HISTORICAL_DAYS)
    high_prices = np.maximum(open_prices, close_prices) + np.random.uniform(0, 5, NUM_HISTORICAL_DAYS)
    low_prices = np.minimum(open_prices, close_prices) - np.random.uniform(0, 5, NUM_HISTORICAL_DAYS)
    volume_data = np.random.randint(100000, 5000000, NUM_HISTORICAL_DAYS)

    mock_ohlcv_df = pd.DataFrame({
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volume_data.astype(float) # pandas_ta 可能偏好 float volume
    }, index=date_index)
    mock_ohlcv_df.index.name = "Date"

    # 儲存這個包含歷史數據的 DataFrame 到預期的黃金紀錄路徑
    # FactorEngine 將會讀取這個檔案，並為其中的每一天（如果 generate_and_store_daily_factors 被這樣調用）
    # 或針對特定日期（如果 calculate_factors 後手動儲存）生成因子。
    # 我們的 Orchestrator._execute_factor_calculation_task 會讀取此檔案，
    # 然後傳給 FactorEngine.generate_and_store_daily_factors。
    # FactorEngine.generate_and_store_daily_factors 會迭代此 DataFrame 的每一行，
    # 為每一行（每一天）生成一個因子檔案。
    mock_ohlcv_df.to_parquet(GOLDEN_RECORD_FILE_PATH)
    print(f"Mock golden record created at: {GOLDEN_RECORD_FILE_PATH} with {len(mock_ohlcv_df)} rows.")
    print("Mock golden record head:")
    print(mock_ohlcv_df.head())
    print("Mock golden record tail:")
    print(mock_ohlcv_df.tail())


    yield mock_ohlcv_df # 讓測試函數可以訪問原始的黃金紀錄 df

    # --- 清理 ---
    print("Tearing down test environment...")
    if GOLDEN_RECORD_TICKER_DIR.exists():
        shutil.rmtree(GOLDEN_RECORD_TICKER_DIR)
    if FACTOR_FILE_TICKER_DIR.exists():
        shutil.rmtree(FACTOR_FILE_TICKER_DIR)
    if METADATA_DB_PATH.exists():
        METADATA_DB_PATH.unlink()
    # recipes file 是共享的，測試不應刪除它，除非是測試專用的臨時 recipes
    print("Test environment teardown complete.")


# --- 測試函數 ---
def test_factor_generation_and_metadata_sync(setup_test_environment):
    """
    端到端測試：
    1. 調用 API 觸發指定日期和股票的因子計算。
    2. 驗證生成的因子數據是否正確 (與手動計算比較)。
    3. 驗證因子元數據是否已同步到資料庫。
    """
    raw_golden_df = setup_test_environment # 從 fixture 獲取原始黃金數據

    # TestClient 會處理 app 的 lifespan 事件，所以 FactorMetadataManager 應該會被調用
    with TestClient(app) as client:
        # --- 1. 觸發因子計算 ---
        print(f"Triggering factor calculation for {TEST_TICKER} on {TEST_DATE_STR} via API...")
        response = client.post(
            "/api/v1/start_factor_mission",
            json={"ticker": TEST_TICKER, "date": TEST_DATE_STR}
        )
        assert response.status_code == 200, f"API call failed: {response.text}"
        response_data = response.json()
        assert response_data["mission_id"] is not None
        mission_id = response_data["mission_id"]
        print(f"Factor calculation mission started. Mission ID: {mission_id}")

        # 簡單輪詢任務狀態，直到成功或失敗 (這裡簡化，假設任務很快完成)
        # 在真實的測試中，可能需要更複雜的輪詢或異步等待機制
        for _ in range(10): # 最多等待約 5 秒 (假設 sleep 0.5s)
            status_response = client.get(f"/api/v1/mission_status/{mission_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                if status_data["status"] == "SUCCESS":
                    print("Factor calculation mission reported SUCCESS.")
                    assert EXPECTED_FACTOR_FILE_PATH.exists(), f"Factor file {EXPECTED_FACTOR_FILE_PATH} was not created."
                    break
                elif status_data["status"] == "failed":
                    pytest.fail(f"Factor calculation mission failed: {status_data.get('message')}")
            else:
                pytest.fail(f"Failed to get mission status: {status_response.text}")
            import time
            time.sleep(0.5)
        else:
            pytest.fail("Factor calculation mission did not complete in time.")

        # --- 2. 驗證因子數據 ---
        print(f"Verifying factor data in {EXPECTED_FACTOR_FILE_PATH}...")
        assert EXPECTED_FACTOR_FILE_PATH.exists(), "Factor Parquet file was not created."

        # FactorEngine 的 generate_and_store_daily_factors 會為黃金記錄 DataFrame 中的每一天創建一個檔案。
        # EXPECTED_FACTOR_FILE_PATH 是針對 TEST_DATE_STR (黃金記錄的最後一天) 的因子檔案。
        generated_factors_df = pd.read_parquet(EXPECTED_FACTOR_FILE_PATH)

        # 期望這個檔案只包含 TEST_DATE_STR 當天的因子值
        assert len(generated_factors_df) == 1, f"Factor file should contain data for a single date, but found {len(generated_factors_df)}"
        assert pd.to_datetime(generated_factors_df.index[0]).strftime('%Y-%m-%d') == TEST_DATE_STR

        # 手動計算預期因子值 (使用完整的 raw_golden_df)
        expected_factors = raw_golden_df.copy()
        expected_factors.ta.sma(length=10, close='Close', append=True, col_names=('SMA_10_Close',))
        expected_factors.ta.rsi(length=14, close='Close', append=True, col_names=('RSI_14_Close',))

        # 選取 TEST_DATE_STR 當天的預期值
        expected_values_for_date = expected_factors.loc[pd.to_datetime(TEST_DATE_STR)]

        print("Generated factors for the target date:")
        print(generated_factors_df)
        print("\nExpected factor values for the target date (manual calculation):")
        print(expected_values_for_date[['SMA_10_Close', 'RSI_14_Close']])

        # 比較 SMA_10_Close
        assert "SMA_10_Close" in generated_factors_df.columns
        # 由於 SMA(10) 需要10天數據，raw_golden_df 的前9天 SMA 會是 NaN
        # 第10天 (索引9) 開始才會有值。
        # TEST_DATE_STR 是序列的最後一天 (第 NUM_HISTORICAL_DAYS-1 天)
        if NUM_HISTORICAL_DAYS >= 10:
            pd.testing.assert_series_equal(
                pd.Series([expected_values_for_date["SMA_10_Close"]], index=generated_factors_df.index, name="SMA_10_Close"),
                generated_factors_df["SMA_10_Close"],
                check_dtype=False, # Parquet 儲存和讀取可能改變 dtype (e.g. int to float if NaNs involved)
                rtol=1e-5
            )
            print("SMA_10_Close verified.")
        else:
            assert pd.isna(generated_factors_df["SMA_10_Close"].iloc[0]), "SMA_10_Close should be NaN due to insufficient history"
            print("SMA_10_Close verified (as NaN due to insufficient history).")


        # 比較 RSI_14_Close
        assert "RSI_14_Close" in generated_factors_df.columns
        if NUM_HISTORICAL_DAYS >= 15: # RSI(14) 通常需要14+1=15天數據開始穩定 (或有值)
            pd.testing.assert_series_equal(
                pd.Series([expected_values_for_date["RSI_14_Close"]], index=generated_factors_df.index, name="RSI_14_Close"),
                generated_factors_df["RSI_14_Close"],
                check_dtype=False,
                rtol=1e-5
            )
            print("RSI_14_Close verified.")
        else:
            assert pd.isna(generated_factors_df["RSI_14_Close"].iloc[0]), "RSI_14_Close should be NaN due to insufficient history"
            print("RSI_14_Close verified (as NaN due to insufficient history).")


        # --- 3. 驗證元數據 ---
        print(f"Verifying metadata in {METADATA_DB_PATH}...")
        assert METADATA_DB_PATH.exists(), "Metadata SQLite DB was not created."

        conn = sqlite3.connect(METADATA_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT factor_id, name, type, description, calculator_function, params_json, output_column_name FROM factor_details")
        db_metadata_rows = cursor.fetchall()
        conn.close()

        db_metadata_map = {row[0]: {
            "name": row[1], "type": row[2], "description": row[3],
            "calculator_function": row[4], "params": json.loads(row[5]),
            "output_column_name": row[6]
        } for row in db_metadata_rows}

        with open(RECIPES_CONFIG_PATH, 'r') as f:
            recipe_metadata = json.load(f)

        assert len(db_metadata_map) >= len(recipe_metadata), "More recipes in JSON than in DB or mismatch."

        for factor_id, recipe_info in recipe_metadata.items():
            assert factor_id in db_metadata_map, f"Factor ID {factor_id} from recipes not found in DB."
            db_info = db_metadata_map[factor_id]

            assert db_info["name"] == recipe_info["name"]
            assert db_info["type"] == recipe_info["type"]
            assert db_info["description"] == recipe_info["description"]
            assert db_info["calculator_function"] == recipe_info["calculator_function"]
            # params 比較時要注意順序和類型，json.loads 後再比較較好
            assert db_info["params"] == recipe_info["params"]
            assert db_info["output_column_name"] == recipe_info["output_column_name"]

        print(f"Metadata for {len(recipe_metadata)} factors verified in the database.")
        print("End-to-end test completed successfully.")

# 如果需要，可以添加更多的測試案例，例如測試邊界條件、錯誤處理等。
# pytest 會自動發現並運行以 test_ 開頭的函數。
# 運行測試: 在專案根目錄執行 pytest prometheus_fire_backend/tests/test_factor_e2e.py
# 或 pytest (如果 pytest.ini 配置正確)
# (需要安裝 pytest: pip install pytest)
# (需要安裝 httpx: pip install httpx) for TestClient
# (需要安裝 pandas-ta: pip install pandas-ta)
# (需要安裝 numpy, pandas, fastapi, uvicorn 等)
# (需要安裝 pyarrow for parquet: pip install pyarrow)
# (需要安裝 pytest-asyncio 如果有 async fixtures/tests: pip install pytest-asyncio) - 目前沒有
