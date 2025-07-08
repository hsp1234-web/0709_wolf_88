import pytest
import httpx # httpx 將由 async_client fixture 提供
import asyncio
import os
import json
import shutil
from datetime import datetime, timedelta

# 從 src 導入 TaifexClient 以便能夠調用其內部方法來生成預期結果
# 這假設 PYTHONPATH 包含專案根目錄
from src.taifex_data_fetcher.client import TaifexClient
from prometheus_fire_backend.modules.orchestrator import MISSION_STATUS_SUCCESS # 匯入任務成功狀態

# --- 設定與常量 ---
# 假設專案根目錄是此測試檔案的再上兩層 (tests -> prometheus_fire_backend -> project_root)
PROJECT_BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_LAKE_PATH = os.path.join(PROJECT_BASE_PATH, "data_lake")
MOCK_DATA_PATH = os.path.join(PROJECT_BASE_PATH, "mock_data") # TaifexClient 會用到此路徑的模擬數據

TEST_DATE_STR = "2025-07-08" # 使用與黃金模擬數據一致的日期
TEST_DATETIME_OBJ = datetime.strptime(TEST_DATE_STR, "%Y-%m-%d")

MAX_POLL_ATTEMPTS = 30  # 最多輪詢次數 (例如 30 次)
POLL_INTERVAL = 0.2  # 輪詢間隔秒數 (例如 0.2 秒)

# --- 輔助函數 ---
def get_expected_json_output(data_type: str, date_obj: datetime) -> list:
    """
    從 mock_data CSV 檔案生成預期的 JSON 輸出內容。
    這模擬了 TaifexClient 獲取、解析和轉換數據後的結果。
    """
    # 實例化一個臨時的 TaifexClient 來使用其解析邏輯
    # 注意：這裡的 data_lake_path 對生成預期結果不重要，但 mock_data_path 很重要
    temp_client = TaifexClient(use_mock_data=True, mock_data_path=MOCK_DATA_PATH, data_lake_path="temp_test_lake")

    if data_type == "institutional_investors":
        expected_data = temp_client.fetch_institutional_investors(date_obj)
    elif data_type == "pc_ratio":
        expected_data = temp_client.fetch_pc_ratio(date_obj)
    else:
        raise ValueError(f"未知的測試數據類型: {data_type}")

    if expected_data is None:
        pytest.fail(f"無法從模擬數據為 {data_type} 生成預期輸出。檢查模擬檔案是否存在且 TaifexClient 解析是否正常。")
    return expected_data

def clean_data_lake_for_test(date_str: str, data_type: str):
    """清理特定測試在 data_lake 中可能生成的檔案。"""
    file_path = os.path.join(DATA_LAKE_PATH, date_str, f"{data_type}.json")
    if os.path.exists(file_path):
        os.remove(file_path)
    # 可選：如果目錄為空則刪除目錄
    dir_path = os.path.join(DATA_LAKE_PATH, date_str)
    if os.path.exists(dir_path) and not os.listdir(dir_path):
        os.rmdir(dir_path)

@pytest.fixture(autouse=True)
def ensure_mock_data_exists():
    """確保執行測試所需的模擬數據檔案存在。"""
    if not os.path.exists(MOCK_DATA_PATH):
        pytest.fail(f"測試前置失敗：模擬數據目錄 {MOCK_DATA_PATH} 不存在。請先運行之前的步驟生成模擬數據。")
    if not os.path.exists(os.path.join(MOCK_DATA_PATH, "institutional_investors.csv")):
        pytest.fail(f"測試前置失敗：{MOCK_DATA_PATH}/institutional_investors.csv 不存在。")
    if not os.path.exists(os.path.join(MOCK_DATA_PATH, "pc_ratio.csv")):
        pytest.fail(f"測試前置失敗：{MOCK_DATA_PATH}/pc_ratio.csv 不存在。")
    # 確保 data_lake 目錄存在，因為 Orchestrator 和 TaifexClient 會嘗試寫入
    os.makedirs(DATA_LAKE_PATH, exist_ok=True)


# --- 端到端測試 ---
@pytest.mark.asyncio
async def test_fetch_taifex_e2e(async_client: httpx.AsyncClient):
    """
    端到端整合測試：
    1. 清理 data_lake (特定檔案)。
    2. 通過 API 觸發 fetch_taifex 任務 (institutional_investors)。
    3. 輪詢任務狀態直至成功。
    4. 驗證 data_lake 中的 JSON 檔案是否已生成且內容正確。
    5. 對 pc_ratio 重複此過程。
    """
    test_cases = [
        {"data_type": "institutional_investors", "params": {"type": "fetch_taifex", "data_type": "institutional_investors", "date": TEST_DATE_STR}},
        {"data_type": "pc_ratio", "params": {"type": "fetch_taifex", "data_type": "pc_ratio", "date": TEST_DATE_STR}},
    ]

    for case in test_cases:
        data_type_to_fetch = case["data_type"]
        mission_api_params = case["params"]

        # 1. 清理 data_lake 中可能存在的舊檔案
        clean_data_lake_for_test(TEST_DATE_STR, data_type_to_fetch)
        print(f"\n[測試案例: {data_type_to_fetch}] 清理完成，準備發送 API 請求...")

        # 2. 發送 API 請求以啟動任務
        response = await async_client.post("/api/v1/start_mission", json=mission_api_params)
        assert response.status_code == 200, f"啟動任務 API 請求失敗: {response.text}"
        response_json = response.json()
        mission_id = response_json.get("mission_id")
        assert mission_id, "API 回應中未找到 mission_id"
        print(f"[測試案例: {data_type_to_fetch}] 任務已啟動，Mission ID: {mission_id}")

        # 3. 輪詢任務狀態
        mission_completed_successfully = False
        for attempt in range(MAX_POLL_ATTEMPTS):
            await asyncio.sleep(POLL_INTERVAL) # 等待一段時間再查詢
            status_response = await async_client.get(f"/api/v1/mission_status/{mission_id}")

            if status_response.status_code == 404: # 任務可能尚未在 Orchestrator 中註冊
                 print(f"[測試案例: {data_type_to_fetch}] 輪詢嘗試 {attempt + 1}/{MAX_POLL_ATTEMPTS}: 任務 {mission_id} 狀態 404 (可能尚未創建)，繼續輪詢...")
                 continue

            assert status_response.status_code == 200, f"查詢任務狀態 API 請求失敗: {status_response.text}"
            status_json = status_response.json()
            current_status = status_json.get("status")
            print(f"[測試案例: {data_type_to_fetch}] 輪詢嘗試 {attempt + 1}/{MAX_POLL_ATTEMPTS}: 任務 {mission_id} 狀態: {current_status}, 訊息: {status_json.get('message')}")

            if current_status == MISSION_STATUS_SUCCESS:
                mission_completed_successfully = True
                break
            elif current_status == "failed": # Orchestrator 中定義的失敗狀態
                pytest.fail(f"任務 {mission_id} 執行失敗: {status_json.get('message')}. Details: {status_json.get('details')}")

        assert mission_completed_successfully, f"任務 {mission_id} 在 {MAX_POLL_ATTEMPTS * POLL_INTERVAL} 秒內未完成。"
        print(f"[測試案例: {data_type_to_fetch}] 任務 {mission_id} 已成功完成。")

        # 4. 驗證 data_lake 中的檔案和內容
        expected_file_path = os.path.join(DATA_LAKE_PATH, TEST_DATE_STR, f"{data_type_to_fetch}.json")
        assert os.path.exists(expected_file_path), f"預期的數據檔案 {expected_file_path} 未在 data_lake 中生成。"
        print(f"[測試案例: {data_type_to_fetch}] 預期檔案 {expected_file_path} 已生成。")

        with open(expected_file_path, "r", encoding="utf-8") as f:
            generated_json_content = json.load(f)

        expected_json_content = get_expected_json_output(data_type_to_fetch, TEST_DATETIME_OBJ)

        # 比較生成的 JSON 和預期的 JSON
        # 注意：順序可能重要，取決於 TaifexClient 如何生成列表。
        # 如果 TaifexClient 的輸出順序是固定的，直接比較列表即可。
        assert generated_json_content == expected_json_content, \
            f"生成的 JSON 內容與預期不符。\n預期: {expected_json_content}\n實際: {generated_json_content}"
        print(f"[測試案例: {data_type_to_fetch}] 檔案內容驗證成功！")

        # 可選：測試後清理
        # clean_data_lake_for_test(TEST_DATE_STR, data_type_to_fetch)
        # print(f"[測試案例: {data_type_to_fetch}] 測試後清理完成。")

    print("\n所有端到端測試案例執行完畢。")

# 如果需要手動運行 (通常通過 pytest 執行):
# if __name__ == "__main__":
#     # 這裡需要一個方法來啟動 FastAPI 伺服器並運行 pytest 測試
#     # 例如: pytest.main([__file__])
#     # 但通常不這樣做，而是直接在命令列使用 pytest
    pass
