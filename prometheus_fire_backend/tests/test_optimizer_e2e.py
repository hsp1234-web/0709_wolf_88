import pytest
import pandas as pd
import numpy as np
import shutil
import json
from pathlib import Path
from fastapi.testclient import TestClient
import time # 用於輪詢等待

from core.config import PROJECT_ROOT
from prometheus_fire_backend.console_api.main import app # FastAPI app 實例
from prometheus_fire_backend.modules.optimizer import PortfolioOptimizer # 直接使用進行本地比較

# --- 常數定義 ---
OPTIMIZER_TEST_ASSETS = {
    "ASSET_A": "price_history_A.parquet",
    "ASSET_B": "price_history_B.parquet",
    "ASSET_C": "price_history_C.parquet"
}
OPTIMIZATION_TARGET_MAX_SHARPE = "max_sharpe"
OPTIMIZATION_TARGET_MIN_VOL = "min_volatility"
OPTIMIZATION_TARGET_HRP = "hrp"

# 基礎目錄
DATA_WAREHOUSE_BASE_DIR = PROJECT_ROOT / "data_warehouse"
OPTIMIZER_TEST_DATA_BASE_DIR = DATA_WAREHOUSE_BASE_DIR / "golden_records" / "daily" # 模擬價格數據存放處

RISK_FREE_RATE_FOR_TEST = 0.01

# --- Pytest Fixtures ---
@pytest.fixture(scope="function")
def setup_optimizer_environment():
    print("Setting up optimizer E2E test environment...")

    asset_data_paths_dict = {}
    asset_dfs_dict = {}

    for asset_id, filename in OPTIMIZER_TEST_ASSETS.items():
        asset_dir = OPTIMIZER_TEST_DATA_BASE_DIR / asset_id
        if asset_dir.exists():
            shutil.rmtree(asset_dir)
        asset_dir.mkdir(parents=True, exist_ok=True)

        asset_file_path = asset_dir / filename
        asset_data_paths_dict[asset_id] = str(asset_file_path)

        # 創建模擬價格數據
        num_days = 252 * 2 # 2 年的日數據
        np.random.seed(abs(hash(asset_id)) % (2**32 - 1)) # 不同的種子以產生不同行為的資產
        dates = pd.date_range(start="2021-01-01", periods=num_days, freq="B")

        base_price = np.random.uniform(80, 120)
        # 讓資產有不同的趨勢和波動性
        drift = np.random.uniform(-0.0001, 0.0005) if asset_id != "ASSET_A" else np.random.uniform(0.0001, 0.0008) # A 稍強勢
        volatility = np.random.uniform(0.01, 0.03) if asset_id != "ASSET_B" else np.random.uniform(0.005, 0.015) # B 稍低波動

        # 生成價格序列，確保所有價格為正
        prices = np.zeros(num_days)
        prices[0] = base_price
        for i in range(1, num_days):
            prices[i] = prices[i-1] * (1 + drift + volatility * np.random.randn())
            if prices[i] <= 0: # 避免價格變為0或負數
                prices[i] = prices[i-1] * (1 + abs(drift) + abs(volatility * np.random.randn())) # 強制正向
                if prices[i] <=0 : prices[i] = 0.01 # 最後防線

        asset_df = pd.DataFrame({"Close": prices}, index=dates)
        asset_df.index.name = "Date"
        asset_df.to_parquet(asset_file_path)
        asset_dfs_dict[asset_id] = asset_df # 保存 DataFrame 用於本地比較
        print(f"Mock price data for {asset_id} created at: {asset_file_path}")

    yield asset_data_paths_dict, asset_dfs_dict # API路徑字典, 本地DataFrame字典

    # --- 清理 ---
    print("Tearing down optimizer E2E test environment...")
    for asset_id in OPTIMIZER_TEST_ASSETS:
        asset_dir = OPTIMIZER_TEST_DATA_BASE_DIR / asset_id
        if asset_dir.exists():
            shutil.rmtree(asset_dir)
    print("Optimizer E2E test environment teardown complete.")

def _poll_mission_status(client: TestClient, mission_id: str, timeout_seconds: int = 20) -> dict:
    """輔助函數，用於輪詢任務狀態直到完成或超時。"""
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        status_response = client.get(f"/api/v1/mission_status/{mission_id}")
        if status_response.status_code == 200:
            status_data = status_response.json()
            if status_data["status"] == "SUCCESS":
                print(f"Mission {mission_id} reported SUCCESS.")
                results = status_data.get("details", {}).get("optimized_weights") # Optimizer返回的權重在 optimized_weights
                if results is None: # Fallback for other mission types if needed
                     results = status_data.get("details", {}).get("backtest_results") # Backtester用這個
                if results is None:
                    results = status_data.get("details", {}) # 最通用的

                assert results is not None, "Results missing in successful mission details."
                return status_data["details"] # 返回整個 details 字典
            elif status_data["status"] == "failed":
                pytest.fail(f"Mission {mission_id} failed: {status_data.get('message')}")
        else:
            pytest.fail(f"Failed to get mission status for {mission_id}: {status_response.text}")
        time.sleep(0.5)
    pytest.fail(f"Mission {mission_id} did not complete in {timeout_seconds} seconds.")
    return {}


def _compare_optimization_results(api_results: dict, local_results: tuple, target_desc: str):
    """比較 API 和本地優化結果的輔助函數。"""
    api_weights = api_results.get("optimized_weights")
    api_performance = api_results.get("expected_performance")

    local_weights, local_performance, local_error = local_results
    assert local_error is None, f"Local optimization for {target_desc} failed: {local_error}"

    print(f"\nComparing results for {target_desc}:")
    print(f"  API Weights    : {api_weights}")
    print(f"  Local Weights  : {local_weights}")
    print(f"  API Performance: {api_performance}")
    print(f"  Local Performance: {local_performance}")

    assert api_weights is not None and isinstance(api_weights, dict)
    assert local_weights is not None and isinstance(local_weights, dict)
    assert len(api_weights) == len(local_weights)
    for asset_id in api_weights:
        assert asset_id in local_weights
        assert np.isclose(api_weights[asset_id], local_weights[asset_id], rtol=1e-3, atol=1e-4), \
            f"Weight mismatch for {asset_id} in {target_desc}: API={api_weights[asset_id]}, Local={local_weights[asset_id]}"

    if api_performance and local_performance: # HRP 可能沒有完整的績效數據從 optimizer 直接返回
        for key in ["expected_annual_return", "annual_volatility", "sharpe_ratio"]:
            if key in api_performance and key in local_performance:
                api_val = api_performance[key]
                local_val = local_performance[key]
                if api_val is None and local_val is None: continue
                assert api_val is not None and local_val is not None, f"Performance key {key} has None value mismatch"
                assert np.isclose(float(api_val), float(local_val), rtol=1e-3, atol=1e-4), \
                    f"Performance mismatch for {key} in {target_desc}: API={api_val}, Local={local_val}"
    print(f"Result comparison for {target_desc} passed.")


# --- 測試函數 ---
@pytest.mark.parametrize("optimization_target_param", [
    OPTIMIZATION_TARGET_MAX_SHARPE,
    OPTIMIZATION_TARGET_MIN_VOL,
    # OPTIMIZATION_TARGET_HRP # HRP 的績效比較可能需要額外處理，暫時先不加入自動比較
])
def test_portfolio_optimization_e2e(setup_optimizer_environment, optimization_target_param):
    """
    端到端測試投資組合優化流程。
    """
    asset_paths_for_api, local_asset_dfs = setup_optimizer_environment

    with TestClient(app) as client:
        # --- 1. 透過 API 啟動優化任務 ---
        api_payload = {
            "asset_price_paths_dict": asset_paths_for_api,
            "optimization_target": optimization_target_param,
            "risk_free_rate": RISK_FREE_RATE_FOR_TEST,
            "weight_bounds": [0, 1], # 允許做空可設为 (-1, 1) 或 None
            "covariance_method": "ledoit_wolf", # 使用較穩健的方法
            "expected_returns_method": "mean_historical_return"
        }
        if optimization_target_param == "efficient_risk": # 假設的，未在 parametrize 中
            api_payload["target_volatility"] = 0.10

        print(f"\nTriggering optimization mission ({optimization_target_param}) via API...")
        response = client.post("/api/v1/start_optimization_mission", json=api_payload)
        assert response.status_code == 200, f"API call failed for {optimization_target_param}: {response.text}"
        response_data = response.json()
        mission_id = response_data["mission_id"]
        print(f"Optimization mission ({optimization_target_param}) started. Mission ID: {mission_id}")

        # --- 2. 輪詢任務狀態並獲取結果 ---
        api_mission_details = _poll_mission_status(client, mission_id)

        # --- 3. 本地直接執行優化以供比較 ---
        print(f"Executing local optimization for {optimization_target_param}...")
        # 3a. 合併本地價格數據
        local_prices_df_combined = pd.concat(
            [df["Close"].rename(asset_id) for asset_id, df in local_asset_dfs.items()],
            axis=1
        ).ffill().bfill().dropna()

        local_optimizer = PortfolioOptimizer()
        local_weights, local_performance, local_error = local_optimizer.optimize_portfolio(
            prices_df=local_prices_df_combined,
            optimization_target=optimization_target_param,
            risk_free_rate=RISK_FREE_RATE_FOR_TEST,
            weight_bounds=tuple(api_payload["weight_bounds"]),
            covariance_method=api_payload["covariance_method"],
            expected_returns_method=api_payload["expected_returns_method"],
            target_volatility=api_payload.get("target_volatility") # 如果有
        )

        # --- 4. 比較結果 ---
        _compare_optimization_results(
            api_mission_details,
            (local_weights, local_performance, local_error),
            optimization_target_param
        )

# 單獨測試 HRP，因為其績效計算和返回可能略有不同
def test_hrp_optimization_e2e(setup_optimizer_environment):
    asset_paths_for_api, local_asset_dfs = setup_optimizer_environment
    optimization_target_hrp = OPTIMIZATION_TARGET_HRP

    with TestClient(app) as client:
        api_payload = {
            "asset_price_paths_dict": asset_paths_for_api,
            "optimization_target": optimization_target_hrp,
            "risk_free_rate": RISK_FREE_RATE_FOR_TEST, # HRP本身不直接用，但Orchestrator可能傳遞
             "weight_bounds": [0, 1] # HRP 通常不接受傳統 weight_bounds, PyPortfolioOpt 會忽略
        }
        print(f"\nTriggering optimization mission ({optimization_target_hrp}) via API...")
        response = client.post("/api/v1/start_optimization_mission", json=api_payload)
        assert response.status_code == 200, f"API call failed for HRP: {response.text}"
        mission_id = response.json()["mission_id"]

        api_mission_details_hrp = _poll_mission_status(client, mission_id)

        print(f"Executing local optimization for {optimization_target_hrp}...")
        local_prices_df_combined_hrp = pd.concat(
            [df["Close"].rename(asset_id) for asset_id, df in local_asset_dfs.items()],
            axis=1
        ).ffill().bfill().dropna()

        local_optimizer_hrp = PortfolioOptimizer()
        local_weights_hrp, local_performance_hrp, local_error_hrp = local_optimizer_hrp.optimize_portfolio(
            prices_df=local_prices_df_combined_hrp,
            optimization_target=optimization_target_hrp
            # risk_free_rate 和 weight_bounds 對 HRP 不是主要參數
        )
        # HRP 在 PortfolioOptimizer 中返回的 performance 是基於 mu, S 計算的，與 EF 類似
        _compare_optimization_results(
            api_mission_details_hrp,
            (local_weights_hrp, local_performance_hrp, local_error_hrp),
            optimization_target_hrp
        )

# 運行: python -m pytest prometheus_fire_backend/tests/test_optimizer_e2e.py
# (需要安裝 PyPortfolioOpt, pandas, numpy, pytest, httpx, fastapi, uvicorn, pyarrow)
# pip install PyPortfolioOpt
