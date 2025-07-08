# prometheus_fire_backend/tests/test_api_e2e_live.py

import pytest
import time
import os
import pandas as pd
from fastapi.testclient import TestClient
from typing import Dict, Any, List

# 假設 FastAPI app 實例和相關模組可以從以下路徑導入
# 調整此導入路徑以匹配您的專案結構
from prometheus_fire_backend.console_api.main import app as fastapi_app # 引入 FastAPI app
from prometheus_fire_backend.modules.orchestrator import MISSION_STATUS_SUCCESS, MISSION_STATUS_FAILED

# --- 測試設定 ---
# 使用一個通常會有數據的過去日期進行測試，避免依賴當天數據
# 注意：期交所可能只提供最近一段時間的數據查詢。例如，三個月或一年內。
# 選擇一個相對近期的過去日期，例如上一個交易日，或者幾天前。
# 為了讓測試更穩定，可以考慮使用一個非常久遠但確定有數據的日期，
# 但要注意期交所網站的資料保留政策。
# 這裡我們用一個固定的過去日期，假設它通常有數據。
# **重要**: 執行此測試前，請確認此日期在期交所網站上是有數據的。
# 指揮官注意：此日期可能需要根據實際情況調整以確保期交所當日有數據。
TEST_LIVE_DATE = "2024-06-07" # 嘗試一個新的範例日期
TEST_DATA_TYPES = ["institutional_investors"] # 先測試一個數據類型以減少請求負擔

MAX_POLL_ATTEMPTS = 30  # 輪詢次數上限 (例如 30 * 2s = 60s 超時)
POLL_INTERVAL_S = 2     # 輪詢間隔秒數

# Data Lake 的基本路徑 (相對於專案根目錄)
# Orchestrator 內部會處理 project_base_path，TaifexClient 會將數據存到相對於它的路徑
# 我們需要知道 data_lake 的最終絕對路徑才能檢查檔案
# TestClient 運行時的當前目錄通常是專案根目錄

# 獲取專案根目錄 (假設此測試檔案在 project_root/prometheus_fire_backend/tests/ 下)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_LAKE_BASE_PATH = os.path.join(PROJECT_ROOT, "data_lake", "raw", "taifex")


@pytest.fixture(scope="module")
def client():
    """提供 FastAPI TestClient 實例。"""
    with TestClient(fastapi_app) as c:
        yield c

@pytest.mark.live # 標記為實彈測試
def test_start_mission_live_data_fetch_and_verify_file(client: TestClient):
    """
    測試啟動一個真實數據獲取任務 (use_mock: false)，
    輪詢其狀態直至成功，並驗證相應的數據檔案已在 data_lake 中創建且不為空。
    """
    mission_payload = {
        "type": "fetch_taifex",
        "date": TEST_LIVE_DATE,
        "data_types": TEST_DATA_TYPES,
        "use_mock": False  # <<< 設定為 False 以觸發真實數據獲取
    }

    print(f"\n[Live Test] 發送實彈任務請求: {mission_payload}")
    response = client.post("/api/v1/start_mission", json=mission_payload)

    assert response.status_code == 200, f"啟動實彈任務失敗: {response.text}"
    response_data = response.json()
    mission_id = response_data.get("mission_id")
    assert mission_id, "實彈任務啟動後未返回 mission_id"
    print(f"[Live Test] 實彈任務已啟動，Mission ID: {mission_id}")

    # 輪詢任務狀態
    mission_completed_successfully = False
    for attempt in range(MAX_POLL_ATTEMPTS):
        print(f"[Live Test] 輪詢任務狀態 (Attempt {attempt + 1}/{MAX_POLL_ATTEMPTS})...")
        time.sleep(POLL_INTERVAL_S)
        status_response = client.get(f"/api/v1/mission_status/{mission_id}")

        if status_response.status_code == 200:
            status_data = status_response.json()
            current_status = status_data.get("status")
            print(f"[Live Test] Mission ID {mission_id} 當前狀態: {current_status}, 訊息: {status_data.get('message')}")

            if current_status == MISSION_STATUS_SUCCESS:
                mission_completed_successfully = True
                print(f"[Live Test] 任務 {mission_id} 已成功完成。")
                break
            elif current_status == MISSION_STATUS_FAILED:
                pytest.fail(f"實彈任務 {mission_id} 執行失敗。最終狀態: {status_data}")
        else:
            print(f"[Live Test] 查詢任務 {mission_id} 狀態失敗，狀態碼: {status_response.status_code}。回應: {status_response.text}")
            # 即使查詢失敗，也可能繼續輪詢，除非是 404 (任務不存在)

    assert mission_completed_successfully, f"實彈任務 {mission_id} 在 {MAX_POLL_ATTEMPTS * POLL_INTERVAL_S} 秒內未成功完成。"

    # 驗證 data_lake 中已生成檔案
    # 檔案路徑格式來自 TaifexClient._save_to_data_lake
    # 例如: data_lake/raw/taifex/institutional_investors/YYYY-MM-DD.parquet
    for data_type in TEST_DATA_TYPES:
        expected_file_name = f"{TEST_LIVE_DATE}.parquet"
        expected_file_path = os.path.join(DATA_LAKE_BASE_PATH, data_type, expected_file_name)

        print(f"[Live Test] 驗證檔案是否存在且不為空: {expected_file_path}")
        assert os.path.exists(expected_file_path), f"預期的數據檔案 {expected_file_path} 未找到。"

        file_size = os.path.getsize(expected_file_path)
        assert file_size > 0, f"數據檔案 {expected_file_path} 為空。"
        print(f"[Live Test] 檔案 {expected_file_path} 存在且大小為 {file_size} bytes。")

        # 可選：嘗試讀取 Parquet 檔案的 metadata 或少量數據以進一步驗證
        try:
            df = pd.read_parquet(expected_file_path)
            assert not df.empty, f"Parquet 檔案 {expected_file_path} 讀取後為空。"
            print(f"[Live Test] Parquet 檔案 {expected_file_path} 成功讀取，包含 {len(df)} 行數據。")
        except Exception as e:
            pytest.fail(f"讀取 Parquet 檔案 {expected_file_path} 失敗: {e}")

    print(f"[Live Test] 實彈數據獲取與檔案驗證測試 ({TEST_LIVE_DATE}, {', '.join(TEST_DATA_TYPES)}) 通過。")

# 可選：添加更多實彈測試案例，例如測試不同數據類型或日期
# 但要注意請求頻率，避免對期交所造成負擔。

# python -m pytest -m live prometheus_fire_backend/tests/test_api_e2e_live.py
# 上述命令可以只運行標記為 'live' 的測試
