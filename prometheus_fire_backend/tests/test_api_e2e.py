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
# DATA_LAKE_PATH 指向 data_lake/raw/taifex，因為這是 TaifexClient 儲存 Parquet 檔案的地方
DATA_LAKE_RAW_TAIFEX_PATH = os.path.join(PROJECT_BASE_PATH, "data_lake", "raw", "taifex")
# MOCK_DATA_PATH 仍然可以保留，以防某些舊的、未被此測試覆蓋的輔助功能可能仍在使用它
MOCK_DATA_PATH = os.path.join(PROJECT_BASE_PATH, "mock_data")

TEST_DATE_STR = "2025-07-08" # 使用與黃金模擬數據一致的日期
TEST_DATETIME_OBJ = datetime.strptime(TEST_DATE_STR, "%Y-%m-%d")

MAX_POLL_ATTEMPTS = 30  # 最多輪詢次數 (例如 30 次)
POLL_INTERVAL = 0.2  # 輪詢間隔秒數 (例如 0.2 秒)
# 引入 pandas 用於讀取 parquet 和比較 dataframe
import pandas as pd
import pandas.testing # 用於比較 DataFrame

# --- 輔助函數 ---
# get_expected_json_output 函數將被移除，因為我們直接比較 Parquet 檔案

def clean_data_lake_for_test(date_str: str, data_type: str, data_lake_base_path: str = DATA_LAKE_RAW_TAIFEX_PATH):
    """清理特定測試在 data_lake 中可能生成的 Parquet 檔案。"""
    # 檔案路徑現在是 data_lake/raw/taifex/<data_type>/<date_str>.parquet
    file_path = os.path.join(data_lake_base_path, data_type, f"{date_str}.parquet")
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"已清理舊檔案: {file_path}")

    # 可選：如果 <data_type> 目錄為空則刪除
    data_type_dir = os.path.join(data_lake_base_path, data_type)
    if os.path.exists(data_type_dir) and not os.listdir(data_type_dir):
        try:
            os.rmdir(data_type_dir)
            print(f"已清理空目錄: {data_type_dir}")
        except OSError as e:
            print(f"清理目錄 {data_type_dir} 失敗: {e}") # 可能因為非空或權限問題

@pytest.fixture(autouse=True)
def ensure_data_lake_path_exists():
    """確保執行測試所需的 data_lake 基本路徑存在。"""
    # 我們需要確保 DATA_LAKE_RAW_TAIFEX_PATH 下的 institutional_investors 和 pc_ratio 子目錄存在
    # 因為 TaifexClient._save_to_data_lake 會預期這些目錄
    os.makedirs(os.path.join(DATA_LAKE_RAW_TAIFEX_PATH, "institutional_investors"), exist_ok=True)
    os.makedirs(os.path.join(DATA_LAKE_RAW_TAIFEX_PATH, "pc_ratio"), exist_ok=True)
    print(f"確保 Data Lake 目錄結構存在於: {DATA_LAKE_RAW_TAIFEX_PATH}")

# --- 定義模擬 CSV 內容 ---
MOCK_INVESTORS_CSV_CONTENT = (
    "日期,身份別,多方交易口數,多方交易契約金額(百萬元),空方交易口數,空方交易契約金額(百萬元),多空交易口數淨額,多空交易契約金額淨額(百萬元),多方未平倉口數,多方未平倉契約金額(百萬元),空方未平倉口數,空方未平倉契約金額(百萬元),多空未平倉口數淨額,多空未平倉契約金額淨額(百萬元)\n"
    f"{TEST_DATE_STR.replace('-', '/')},自營商,266543,51886,240474,51465,26069,421,302016,101867,183199,43319,118817,58548\n"
    f"{TEST_DATE_STR.replace('-', '/')},投信,1357,3511,2647,8580,-1290,-5069,55561,213816,14379,57387,41182,156429\n"
    f"{TEST_DATE_STR.replace('-', '/')},外資及陸資,442679,367852,424911,334839,17768,33013,154210,139387,538032,416068,-383822,-276681\n"
)

MOCK_PC_RATIO_CSV_CONTENT = (
    "日期,賣權成交量,買權成交量,買賣權成交量比率%,賣權未平倉量,買權未平倉量,買賣權未平倉量比率%\n"
    f"{TEST_DATE_STR.replace('-', '/')},341931,385728,88.65,161864,150408,107.62,\n"
)


# --- 端到端測試 ---
@pytest.mark.asyncio
async def test_fetch_taifex_e2e(async_client: httpx.AsyncClient):
    """
    端到端整合測試：
    1. 清理 data_lake (特定檔案)。
    2. 通過 API 觸發 fetch_taifex 任務 (institutional_investors)，使用模擬數據。
    3. 輪詢任務狀態直至成功。
    4. 驗證 data_lake 中的 Parquet 檔案是否已生成且（可選地）內容符合預期。
    5. 對 pc_ratio 重複此過程。
    """
    # 更新測試案例以包含 use_mock 和 mock_data
    test_cases = [
        {
            "data_type": "institutional_investors",
            "params": {
                "type": "fetch_taifex",
                "date": TEST_DATE_STR,
                "data_types": ["institutional_investors"], # 使用列表
                "use_mock": True,
                "mock_data": {"institutional_investors_csv": MOCK_INVESTORS_CSV_CONTENT}
            }
        },
        {
            "data_type": "pc_ratio",
            "params": {
                "type": "fetch_taifex",
                "date": TEST_DATE_STR,
                "data_types": ["pc_ratio"], # 使用列表
                "use_mock": True,
                "mock_data": {"pc_ratio_csv": MOCK_PC_RATIO_CSV_CONTENT}
            }
        },
    ]

    for case in test_cases:
        data_type_to_fetch = case["data_type"]
        mission_api_params = case["params"] # mission_api_params 現在已包含 use_mock 和 mock_data

        # 1. 清理 data_lake 中可能存在的舊檔案
        clean_data_lake_for_test(TEST_DATE_STR, data_type_to_fetch) # 它會清理 .parquet
        print(f"\n[測試案例: {data_type_to_fetch}] 清理完成，準備發送 API 請求: {mission_api_params}")

        # 2. 發送 API 請求以啟動任務
        response = await async_client.post("/api/v1/start_mission", json=mission_api_params)
        assert response.status_code == 200, f"啟動任務 API 請求失敗 ({data_type_to_fetch}): {response.text}"
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

        # 4. 驗證 data_lake 中的 Parquet 檔案與黃金標準檔案是否一致
        generated_file_name = f"{TEST_DATE_STR}.parquet"
        actual_file_path = os.path.join(DATA_LAKE_RAW_TAIFEX_PATH, data_type_to_fetch, generated_file_name)

        golden_fixture_filename = f"golden_{data_type_to_fetch}_{TEST_DATE_STR}.parquet"
        expected_file_path = os.path.join(PROJECT_BASE_PATH, "prometheus_fire_backend", "tests", "fixtures", golden_fixture_filename)

        assert os.path.exists(actual_file_path), f"實際生成的數據檔案 {actual_file_path} 未在 data_lake 中生成。"
        print(f"[測試案例: {data_type_to_fetch}] 實際檔案 {actual_file_path} 已生成。")
        assert os.path.exists(expected_file_path), f"黃金標準檔案 {expected_file_path} 未找到。請先生成。"
        print(f"[測試案例: {data_type_to_fetch}] 黃金標準檔案 {expected_file_path} 已找到。")

        try:
            actual_df = pd.read_parquet(actual_file_path)
            expected_df = pd.read_parquet(expected_file_path)
        except Exception as e:
            pytest.fail(f"讀取 Parquet 檔案時發生錯誤: {e}")

        # 比較 DataFrame
        # check_dtype=False 因為從 CSV轉換過來的類型可能與直接構造的 Parquet 略有差異，但內容應一致
        # 如果TaifexClient內部有嚴格的類型轉換，可以設為True
        # 對於某些浮點數比較，可能需要設定 rtol 或 atol
        pandas.testing.assert_frame_equal(actual_df, expected_df, check_dtype=True) # 先嘗試嚴格比較
        print(f"[測試案例: {data_type_to_fetch}] Parquet 檔案內容驗證成功！")

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
