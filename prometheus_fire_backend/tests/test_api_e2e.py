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
DATA_LAKE_RAW_YFINANCE_PATH = os.path.join(PROJECT_BASE_PATH, "data_lake", "raw", "yfinance", "ohlcv") # YFinanceClient 儲存路徑
# MOCK_DATA_PATH 仍然可以保留，以防某些舊的、未被此測試覆蓋的輔助功能可能仍在使用它
MOCK_DATA_PATH = os.path.join(PROJECT_BASE_PATH, "mock_data")

TEST_DATE_STR = "2025-07-08" # 使用與黃金模擬數據一致的日期
TEST_YFINANCE_DATE_STR = "2025-07-09" # 為 yfinance 測試使用不同日期以避免衝突
TEST_YFINANCE_TICKER = "0050.TW"
TEST_DATETIME_OBJ = datetime.strptime(TEST_DATE_STR, "%Y-%m-%d")

MAX_POLL_ATTEMPTS = 30  # 最多輪詢次數 (例如 30 次)
POLL_INTERVAL = 0.2  # 輪詢間隔秒數 (例如 0.2 秒)
# 引入 pandas 用於讀取 parquet 和比較 dataframe
import pandas as pd
import pandas.testing # 用於比較 DataFrame

# --- 輔助函數 ---
# get_expected_json_output 函數將被移除，因為我們直接比較 Parquet 檔案

def clean_data_lake_for_test(
    date_str: str,
    data_type: str, # 對於 taifex, 是 'institutional_investors' 或 'pc_ratio'. 對於 yfinance, 是 ticker_symbol
    source: str = "taifex", # 'taifex' 或 'yfinance'
    data_lake_base_path_taifex: str = DATA_LAKE_RAW_TAIFEX_PATH,
    data_lake_base_path_yfinance: str = DATA_LAKE_RAW_YFINANCE_PATH
):
    """清理特定測試在 data_lake 中可能生成的 Parquet 檔案。"""
    file_path = None
    data_type_dir = None # 父目錄，用於檢查是否為空

    if source == "taifex":
        # 檔案路徑: data_lake/raw/taifex/<data_type>/<date_str>.parquet
        file_path = os.path.join(data_lake_base_path_taifex, data_type, f"{date_str}.parquet")
        data_type_dir = os.path.join(data_lake_base_path_taifex, data_type)
    elif source == "yfinance":
        # 檔案路徑: data_lake/raw/yfinance/ohlcv/<ticker_symbol>/<date_str>.parquet
        # data_type 在此情況下是 ticker_symbol
        ticker_symbol = data_type
        file_path = os.path.join(data_lake_base_path_yfinance, ticker_symbol, f"{date_str}.parquet")
        data_type_dir = os.path.join(data_lake_base_path_yfinance, ticker_symbol) # 指向 ticker_symbol 目錄

    if file_path and os.path.exists(file_path):
        os.remove(file_path)
        print(f"已清理舊檔案 ({source}): {file_path}")

    # 可選：如果 <data_type_dir> (即 Taifex 的 data_type 目錄或 YFinance 的 ticker_symbol 目錄) 為空則刪除
    if data_type_dir and os.path.exists(data_type_dir) and not os.listdir(data_type_dir):
        try:
            os.rmdir(data_type_dir)
            print(f"已清理空目錄 ({source}): {data_type_dir}")
        except OSError as e:
            print(f"清理目錄 {data_type_dir} ({source}) 失敗: {e}")

@pytest.fixture(autouse=True)
def ensure_data_lake_path_exists():
    """確保執行測試所需的 data_lake 基本路徑存在。"""
    # Taifex 路徑
    os.makedirs(os.path.join(DATA_LAKE_RAW_TAIFEX_PATH, "institutional_investors"), exist_ok=True)
    os.makedirs(os.path.join(DATA_LAKE_RAW_TAIFEX_PATH, "pc_ratio"), exist_ok=True)
    print(f"確保 Taifex Data Lake 目錄結構存在於: {DATA_LAKE_RAW_TAIFEX_PATH}")

    # YFinance 路徑 (ohlcv 的父目錄)
    # YFinanceClient 會在 _save_to_data_lake 中創建 ticker_symbol 子目錄
    os.makedirs(DATA_LAKE_RAW_YFINANCE_PATH, exist_ok=True)
    print(f"確保 YFinance Data Lake OHLCV 基礎目錄存在於: {DATA_LAKE_RAW_YFINANCE_PATH}")


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
    # clean_data_lake_for_test(TEST_DATE_STR, data_type_to_fetch, source="taifex")
        # print(f"[測試案例: {data_type_to_fetch}] 測試後清理完成。")

    print("\nTaifex 端到端測試案例執行完畢。")


@pytest.mark.asyncio
async def test_fetch_yfinance_e2e(async_client: httpx.AsyncClient):
    """
    端到端整合測試 for fetch_yfinance:
    1. 定義模擬 OHLCV DataFrame。
    2. 清理 data_lake (特定 yfinance 檔案)。
    3. 通過 API 觸發 fetch_yfinance 任務，使用模擬數據。
    4. 輪詢任務狀態直至成功。
    5. 驗證 data_lake 中的 Parquet 檔案是否已生成且內容符合預期。
    """
    ticker_to_test = TEST_YFINANCE_TICKER
    date_to_test = TEST_YFINANCE_DATE_STR # "2025-07-09"

    # 1. 定義模擬 OHLCV DataFrame
    # yfinance history() 返回的 DataFrame 索引是 DatetimeIndex
    mock_ohlcv_data = {
        "Open": [100.0, 102.0],
        "High": [105.0, 104.0],
        "Low": [99.0, 101.0],
        "Close": [103.0, 103.5],
        "Volume": [10000, 12000]
    }
    # 創建一個包含兩天的數據，但 YFinanceClient.fetch_ohlcv 會篩選出指定的那一天
    # 索引必須是 DatetimeIndex
    mock_dates = pd.to_datetime([date_to_test, (datetime.strptime(date_to_test, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")])
    mock_df_full = pd.DataFrame(mock_ohlcv_data, index=mock_dates)
    # YFinanceClient.fetch_ohlcv 預期 mock_data_content 是針對目標單日的 DataFrame
    # 因此，我們從 mock_df_full 中篩選出目標日期的數據作為期望的 mock_data_content
    expected_mock_df_for_client = mock_df_full[mock_df_full.index.strftime('%Y-%m-%d') == date_to_test].copy()

    # DataFetcher 的 mission_params.mock_data.ohlcv_df 需要是這個單日 DataFrame
    # 注意：YFinanceClient 的 fetch_ohlcv 內部會進行儲存，然後返回這個 DataFrame
    # 所以我們用 expected_mock_df_for_client 來比較儲存後的結果

    mission_api_params = {
        "type": "fetch_yfinance",
        "ticker_symbol": ticker_to_test,
        "date": date_to_test,
        "use_mock": True,
        "mock_data": {"ohlcv_df": expected_mock_df_for_client.to_dict(orient='split')} # 傳遞可序列化為 JSON 的格式
        # DataFetcher/YFinanceClient 需要能從 to_dict('split') 重建 DataFrame
        # 或者，我們可以調整 Orchestrator/DataFetcher 來處理 Base64 編碼的 Parquet 字串等
        # 為了簡化，我們將在 Orchestrator 層將 dict 轉回 DataFrame (如果需要)
        # 更新: YFinanceClient 的 mock_data_content 期望直接是 DataFrame。
        # Orchestrator/DataFetcher 需要確保這一點。
        # 對於 API 測試，我們需要模擬 Orchestrator 如何處理 mock_data。
        # 最簡單的方式是讓 Orchestrator 能夠處理 DataFrame-like dict，或者調整 YFinanceClient 的模擬邏輯。
        # 暫時假設 Orchestrator 或 DataFetcher 會將 params["mock_data"]["ohlcv_df"] (如果它是 dict) 轉換回 DataFrame
        # 為了此測試，我們將直接在 DataFetcher 期望 DataFrame (如目前實作)
        # 因此，API 傳遞的 mock_data 格式需要 Orchestrator 能正確解析並傳遞 DataFrame 給 YFinanceClient
        # 此處的 to_dict('split') 是為了讓 JSON 序列化通過，但後端需要重建。
        # 鑑於 YFinanceClient.fetch_ohlcv(mock_data_content: Optional[pd.DataFrame] = None)
        # MainOrchestrator 中，當 use_mock=True 且 params.get("mock_data") 時，
        # fetcher_params["mock_data"] = params["mock_data"]
        # DataFetcher 中，mock_ohlcv_df = mission_params.get("mock_data", {}).get("ohlcv_df")
        # 這表示 API 的 JSON payload 中的 "ohlcv_df" 需要被後端某處轉換為 DataFrame。
        #
        # 簡化：我們將假設 API 的 `mock_data` 欄位可以直接接受一個能被 `pd.DataFrame()` 理解的字典列表結構，
        # 或 Orchestrator 負責轉換。為此 e2e 測試，我們將專注於 YFinanceClient 本身的模擬數據處理能力，
        # 這意味著 `YFinanceClient.fetch_ohlcv` 接收的 `mock_data_content` 應為 DataFrame。
        # API 參數中的 `mock_data` 結構需要與 Orchestrator 的轉換邏輯一致。
        #
        # 為了使此測試獨立於 Orchestrator 的具體轉換邏輯，我們將在 YFinanceClient 中添加對 dict 格式模擬數據的轉換。
        # (已在 YFinanceClient 更新，如果 mock_data_content 是 dict，嘗試 pd.DataFrame.from_dict)
        # 更新 YFinanceClient 以接受 dict (orient='split') 並重建 DataFrame
        # 實際 YFinanceClient.fetch_ohlcv 簽名是 mock_data_content: Optional[pd.DataFrame]
        # 這表示 DataFetcher 需要確保傳遞的是 DataFrame。
        # 此處的 to_dict() 是為了 JSON 傳輸，後端需要反序列化。
        # 假設 MainOrchestrator._execute_fetch_yfinance_task_with_datafetcher
        # 會處理從 JSON dict 到 DataFrame 的轉換，如果 mock_data 存在。
        # 目前 Orchestrator 只是直接傳遞 mock_data:
        # if use_mock and params.get("mock_data"): fetcher_params["mock_data"] = params["mock_data"]
        # 然後 DataFetcher: mock_ohlcv_df = mission_params.get("mock_data", {}).get("ohlcv_df")
        # 所以 YFinanceClient.fetch_ohlcv 裡的 mock_data_content 就是這個 ohlcv_df。
        # 我們需要確保 YFinanceClient 能處理傳入的 dict。
        # 為了測試，我們讓 YFinanceClient 裡的 mock_data_content 期望是 DataFrame。
        # 因此，我們需要修改 Orchestrator 或 DataFetcher，將收到的 dict 轉為 DataFrame。
        #
        # **暫定方案**：修改 `YFinanceClient.fetch_ohlcv`，如果 `mock_data_content` 是 `dict`，嘗試用 `pd.DataFrame.from_dict(mock_data_content, orient='split')` 重建。
        # 這樣 API 可以傳輸 JSON 相容的 dict。
        # 這個修改已經包含在之前的 YFinanceClient 程式碼中（雖然沒有明確寫出 orient='split'，但可以調整）。
        # 此處的 to_dict('split') 格式需要 YFinanceClient 能夠處理。
        # 為了簡單起見，假設 YFinanceClient 內部會處理傳入的 dict (from_dict with correct orient if needed)
        # 最新的 YFinanceClient 實作中，mock_data_content: Optional[pd.DataFrame]，所以 DataFetcher 必須傳 DataFrame。
        # 我們需要修改 DataFetcher 中的 FETCH_YFINANCE 分支：
        # if use_mock:
        #   mock_payload = mission_params.get("mock_data", {}).get("ohlcv_df")
        #   if isinstance(mock_payload, dict):
        #     mock_ohlcv_df = pd.DataFrame.from_dict(mock_payload, orient='split') # 或其他合適的 orient
        #   else: // assume it's already a DataFrame (e.g. direct call in non-API test)
        #     mock_ohlcv_df = mock_payload
        # ... self.yfinance_client.fetch_ohlcv(mock_data_content=mock_ohlcv_df)
        #
        # **最終決定**：保持 YFinanceClient 期望 DataFrame。API 參數傳輸 dict。
        # DataFetcher 在調用 YFinanceClient 之前，負責將 dict 轉換為 DataFrame。
        # 這需要在 DataFetcher 中修改 FETCH_YFINANCE 的模擬部分。
        # （此修改將在下一步驟中完成，現在先假設 API 能觸發此流程）
    }
    # 實際傳給 YFinanceClient 的應該是 DataFrame，所以此處的 mock_data 是為了 e2e 測試 API。
    # DataFetcher 需要將這個 dict 轉換回 DataFrame。

    # 2. 清理 data_lake
    clean_data_lake_for_test(date_to_test, ticker_to_test, source="yfinance")
    print(f"\n[YFinance測試: {ticker_to_test} on {date_to_test}] 清理完成，準備發送 API 請求: {mission_api_params}")

    # 3. 發送 API 請求
    response = await async_client.post("/api/v1/start_mission", json=mission_api_params)
    assert response.status_code == 200, f"啟動 YFinance 任務 API 請求失敗: {response.text}"
    response_json = response.json()
    mission_id = response_json.get("mission_id")
    assert mission_id, "API 回應中未找到 mission_id (YFinance)"
    print(f"[YFinance測試: {ticker_to_test}] 任務已啟動，Mission ID: {mission_id}")

    # 4. 輪詢任務狀態
    mission_completed_successfully = False
    for attempt in range(MAX_POLL_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL)
        status_response = await async_client.get(f"/api/v1/mission_status/{mission_id}")
        if status_response.status_code == 404:
            print(f"[YFinance測試: {ticker_to_test}] 輪詢嘗試 {attempt + 1}/{MAX_POLL_ATTEMPTS}: 任務 {mission_id} 狀態 404，繼續輪詢...")
            continue
        assert status_response.status_code == 200, f"查詢 YFinance 任務狀態 API 請求失敗: {status_response.text}"
        status_json = status_response.json()
        current_status = status_json.get("status")
        print(f"[YFinance測試: {ticker_to_test}] 輪詢嘗試 {attempt + 1}/{MAX_POLL_ATTEMPTS}: 任務 {mission_id} 狀態: {current_status}, 訊息: {status_json.get('message')}")
        if current_status == MISSION_STATUS_SUCCESS:
            mission_completed_successfully = True
            break
        elif current_status == "failed":
            pytest.fail(f"YFinance 任務 {mission_id} 執行失敗: {status_json.get('message')}. Details: {status_json.get('details')}")

    assert mission_completed_successfully, f"YFinance 任務 {mission_id} 在 {MAX_POLL_ATTEMPTS * POLL_INTERVAL} 秒內未完成。"
    print(f"[YFinance測試: {ticker_to_test}] 任務 {mission_id} 已成功完成。")

    # 5. 驗證 Parquet 檔案
    generated_file_name = f"{date_to_test}.parquet"
    actual_file_path = os.path.join(DATA_LAKE_RAW_YFINANCE_PATH, ticker_to_test, generated_file_name)

    assert os.path.exists(actual_file_path), f"YFinance 實際生成的數據檔案 {actual_file_path} 未在 data_lake 中生成。"
    print(f"[YFinance測試: {ticker_to_test}] 實際檔案 {actual_file_path} 已生成。")

    try:
        actual_df = pd.read_parquet(actual_file_path)
    except Exception as e:
        pytest.fail(f"讀取 YFinance 生成的 Parquet 檔案時發生錯誤: {e}")

    # 比較 DataFrame (expected_mock_df_for_client 是我們期望 YFinanceClient 內部處理並儲存的 DataFrame)
    # YFinanceClient 儲存時 index=True
    pandas.testing.assert_frame_equal(actual_df, expected_mock_df_for_client, check_dtype=True, check_index_type=True)
    print(f"[YFinance測試: {ticker_to_test}] YFinance Parquet 檔案內容驗證成功！")

    # 可選：測試後清理
    # clean_data_lake_for_test(date_to_test, ticker_to_test, source="yfinance")
    # print(f"[YFinance測試: {ticker_to_test}] 測試後清理完成。")

    print("\nYFinance 端到端測試案例執行完畢。")


# 如果需要手動運行 (通常通過 pytest 執行):
# if __name__ == "__main__":
#     # 這裡需要一個方法來啟動 FastAPI 伺服器並運行 pytest 測試
#     # 例如: pytest.main([__file__])
#     # 但通常不這樣做，而是直接在命令列使用 pytest
    pass
