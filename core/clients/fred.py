# core/clients/fred.py
# 此模組包含與 FRED (Federal Reserve Economic Data) API 互動的客戶端邏輯。

import os
import requests
import pandas as pd
from typing import Optional, List, Dict, Any

from .base import BaseAPIClient

# FRED API 的主機 URL
FRED_API_HOST = "https://api.stlouisfed.org"
# FRED 獲取觀測數據的特定端點路徑
FRED_OBSERVATIONS_ENDPOINT = "/fred/series/observations"


class FREDClient(BaseAPIClient):  # 類名從 FREDAPIClient 改為 FREDClient 以求簡潔
    """
    用於與 FRED API 互動的客戶端，以獲取經濟數據系列。
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 FREDClient。

        Args:
            api_key (Optional[str]): FRED API Key。如果未提供，
                                       將嘗試從環境變數 FRED_API_KEY 讀取。
        Raises:
            ValueError: 如果 API Key 未提供且環境變數中也未設定。
        """
        fred_api_key = api_key or os.getenv("FRED_API_KEY")
        if not fred_api_key:
            raise ValueError(
                "FRED API Key 未設定。請設定 FRED_API_KEY 環境變數或在初始化時傳入 api_key。"
            )

        super().__init__(api_key=fred_api_key, base_url=FRED_API_HOST)
        print("資訊：FREDClient 初始化成功。")

    def _prepare_params(self, series_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        準備請求 FRED API 所需的參數。
        """
        request_params: Dict[str, Any] = params.copy()
        request_params["series_id"] = series_id
        request_params["api_key"] = self.api_key
        request_params["file_type"] = "json"  # FRED API 要求指定 file_type

        # 將 limit 和 offset (如果存在) 轉換為字串，因為 API 可能期望它們是字串
        if "limit" in request_params and request_params["limit"] is not None:
            request_params["limit"] = str(request_params["limit"])
        if "offset" in request_params and request_params["offset"] is not None:
            request_params["offset"] = str(request_params["offset"])

        return request_params

    def fetch_data(self, symbol: str, **kwargs) -> pd.DataFrame:
        """
        從 FRED API 獲取指定經濟數據系列的觀測值。

        Args:
            symbol (str): 要獲取的 FRED Series ID (例如 "DGS10", "CPIAUCSL")。
                          在 FRED 中，這對應 'series_id'。
            **kwargs: 其他可選的 FRED API 參數，例如:
                realtime_start (str, optional): YYYY-MM-DD
                realtime_end (str, optional): YYYY-MM-DD
                limit (int, optional): 返回的最大觀測數量。
                offset (int, optional): 數據偏移量。
                sort_order (str, optional): 'asc' 或 'desc'。
                observation_start (str, optional): YYYY-MM-DD
                observation_end (str, optional): YYYY-MM-DD

        Returns:
            pd.DataFrame: 包含觀測數據的 DataFrame (欄位: date, series_id, value)。
                          如果請求失敗或無數據，則返回空的 DataFrame。
        Raises:
            requests.exceptions.HTTPError: 如果 API 請求遭遇 HTTP 錯誤。
        """
        # 從 kwargs 提取 FRED API 參數
        # 注意：BaseAPIClient 的 fetch_data 簽名是 (self, symbol: str, **kwargs)
        # symbol 在此處即為 series_id

        api_params = {}
        allowed_fred_params = [
            "realtime_start",
            "realtime_end",
            "limit",
            "offset",
            "sort_order",
            "observation_start",
            "observation_end",
            # "units", "frequency", "aggregation_method", "output_type" 等其他參數可按需添加
        ]
        for key, value in kwargs.items():
            if key in allowed_fred_params and value is not None:
                api_params[key] = value

        # 準備最終參數 (包括 series_id, api_key, file_type)
        final_params = self._prepare_params(series_id=symbol, params=api_params)

        print(
            f"資訊：FREDClient 正在獲取 Series ID: {symbol}, Params (不含apikey): { {k:v for k,v in final_params.items() if k != 'api_key'} }"
        )

        try:
            # 從 kwargs 中提取 force_refresh，預設為 False
            force_refresh = kwargs.get('force_refresh', False)

            # **關鍵變更**: 使用 self._get_request_context 控制快取行為
            with self._get_request_context(force_refresh=force_refresh):
                # 直接使用 self._session 進行請求，並拼接 base_url 和 endpoint
                request_url = f"{self.base_url}{FRED_OBSERVATIONS_ENDPOINT}"
                response = self._session.get(request_url, params=final_params)
                response.raise_for_status()  # 檢查 HTTP 錯誤
                json_response = response.json() # 解析 JSON

            if not json_response or not json_response.get("observations"): # 檢查 json_response 是否為 None
                print(
                    f"警告：FRED API 未返回 Series ID '{symbol}' 的觀測數據或請求失敗。可能是無效的 ID、日期範圍無數據、API Key 權限問題或網路問題。"
                )
                return pd.DataFrame()

            df = pd.DataFrame(json_response["observations"])

            # FRED 返回的 'value' 可能包含 '.' 表示無數據，需要處理
            # 我們只需要 date 和 value
            if "date" not in df.columns or "value" not in df.columns:
                print(
                    f"警告：FRED API 返回的數據缺少 'date' 或 'value' 欄位。Series ID: {symbol}"
                )
                return pd.DataFrame()

            df = df[["date", "value"]]
            df["date"] = pd.to_datetime(df["date"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df.dropna(subset=["value"], inplace=True)

            if df.empty:
                print(f"資訊：FRED API Series ID '{symbol}' 在處理後無有效觀測數據。")
                return pd.DataFrame()

            df["series_id"] = symbol  # 新增 series_id 欄位以標識數據來源
            df = df[["date", "series_id", "value"]]  # 重新排列欄位順序

            print(
                f"資訊：FREDClient 成功獲取並處理了 {len(df)} 筆 Series ID '{symbol}' 的有效觀測數據。"
            )
            return df

        except (
            requests.exceptions.HTTPError
        ) as http_err:  # 由 BaseClient 的 _request 引發
            print(
                f"錯誤：FREDClient 請求遭遇 HTTP 錯誤 (Series ID: {symbol}): {http_err}"
            )
            raise  # 允許 HTTPError 向上傳播，以便調用者可以根據狀態碼做不同處理
        except (
            requests.exceptions.RequestException
        ) as req_err:  # 其他請求相關錯誤，例如超時、連接錯誤
            print(
                f"錯誤：FREDClient 請求遭遇網路或請求配置錯誤 (Series ID: {symbol}): {req_err}"
            )
            return pd.DataFrame()  # 對於這類錯誤，返回空 DataFrame
        except (
            ValueError
        ) as json_err:  # super()._request() 中的 response.json() 可能引發的錯誤
            print(
                f"錯誤：FREDClient 解析 JSON 回應失敗 (Series ID: {symbol})：{json_err}"
            )
            return pd.DataFrame()
        except Exception as e:  # 其他所有未知錯誤
            print(f"錯誤：FREDClient 處理數據時發生未知錯誤 (Series ID: {symbol})：{e}")
            return pd.DataFrame()

    def get_multiple_series(self, series_ids: List[str], **kwargs) -> pd.DataFrame:
        """
        獲取多個 FRED 經濟數據系列的觀測值並將它們合併。
        這是一個便捷方法，內部多次調用 fetch_data。

        Args:
            series_ids (List[str]): 要獲取的 FRED Series ID 列表。
            **kwargs: 其他傳遞給 fetch_data 的參數 (例如 observation_start)。

        Returns:
            pd.DataFrame: 包含所有成功請求系列數據的合併 DataFrame。
                          如果所有系列都請求失敗或無數據，則返回空的 DataFrame。
        """
        all_series_data = []
        print(f"資訊：FREDClient 開始批量獲取 Series IDs: {series_ids}")
        for series_id in series_ids:
            print(f"資訊：FREDClient 處理批量請求中的 Series ID: {series_id}")
            try:
                series_df = self.fetch_data(symbol=series_id, **kwargs)
                if not series_df.empty:
                    all_series_data.append(series_df)
            except requests.exceptions.HTTPError:
                # fetch_data 會打印錯誤，這裡可以選擇性地記錄 series_id 失敗
                print(
                    f"警告：FREDClient 批量獲取中，Series ID '{series_id}' 數據獲取遭遇 HTTP 錯誤，已跳過。"
                )
            # 其他異常由 fetch_data 內部處理並可能返回空 DataFrame

        if not all_series_data:
            print("警告：FREDClient 批量獲取未成功獲取任何系列的有效數據。")
            return pd.DataFrame()

        combined_df = pd.concat(all_series_data, ignore_index=True)
        print(
            f"資訊：FREDClient 成功合併 {len(all_series_data)} 個 FRED 系列的數據，總共 {len(combined_df)} 筆記錄。"
        )
        return combined_df


# 範例使用 (主要用於開發時測試)
if __name__ == "__main__":
    print("--- FREDClient 重構後測試 (直接執行 core/clients/fred.py) ---")
    # 執行此測試前，請確保設定了 FRED_API_KEY 環境變數
    try:
        client = FREDClient()
        print("FREDClient 初始化成功。")

        # 測試獲取單一系列數據 (DGS10) 並測試快取
        print("\n--- 測試 FREDClient 快取功能 (Series: DGS10) ---")
        series_id_test = "DGS10"
        test_params = {"observation_start": "2024-01-01", "observation_end": "2024-01-05"}

        print(f"\n[DGS10] 執行第一次 (應會下載, URL 包含 {test_params})...")
        data_dgs10_first = client.fetch_data(symbol=series_id_test, **test_params)
        if not data_dgs10_first.empty:
            print(f"成功獲取 DGS10 數據 (第一次): {len(data_dgs10_first)} 筆")
            print(data_dgs10_first.head())
        else:
            print(f"DGS10 (第一次) 返回空 DataFrame。請檢查 API Key 或 FRED 服務狀態。")

        print(f"\n[DGS10] 執行第二次 (應從快取讀取, URL 包含 {test_params})...")
        data_dgs10_second = client.fetch_data(symbol=series_id_test, **test_params)
        if not data_dgs10_second.empty:
            print(f"成功獲取 DGS10 數據 (第二次): {len(data_dgs10_second)} 筆")
            # 這裡可以加入對 response.from_cache 的檢查 (如果 BaseClient._request 返回 response 物件)
            # 目前 BaseAPIClient._request 直接返回 json，所以依賴 print 訊息判斷
        else:
            print(f"DGS10 (第二次) 返回空 DataFrame。")

        if not data_dgs10_first.empty and not data_dgs10_second.empty:
            if data_dgs10_first.equals(data_dgs10_second):
                print("[DGS10] 快取驗證：第一次和第二次獲取的數據一致。")
            else:
                print("警告：[DGS10] 快取驗證失敗：第一次和第二次獲取的數據不一致！")

        print(f"\n[DGS10] 執行第三次 (強制刷新, URL 包含 {test_params})...")
        data_dgs10_third = client.fetch_data(symbol=series_id_test, force_refresh=True, **test_params)
        if not data_dgs10_third.empty:
            print(f"成功獲取 DGS10 數據 (強制刷新): {len(data_dgs10_third)} 筆")
        else:
            print(f"DGS10 (強制刷新) 返回空 DataFrame。")

        if not data_dgs10_first.empty and not data_dgs10_third.empty:
            if data_dgs10_first.equals(data_dgs10_third):
                print("[DGS10] 強制刷新驗證：第一次和強制刷新獲取的數據一致。")
            else:
                print("警告：[DGS10] 強制刷新驗證失敗：第一次和強制刷新獲取的數據不一致！")

        # 測試 get_multiple_series 是否也受益於快取 (間接測試)
        # 注意：get_multiple_series 本身不直接處理 force_refresh，它會傳遞 kwargs 給 fetch_data
        # 所以如果 fetch_data 的快取邏輯正確，這裡應該也能體現
        print("\n--- 測試 get_multiple_series 是否間接受益於快取 (Series: DGS10, UNRATE) ---")
        series_list_test = ["DGS10", "UNRATE"] # DGS10 應該已經快取了 (如果參數相同)
        multi_params = {"observation_start": "2024-01-01", "observation_end": "2024-01-05"}

        print(f"\n[批量] 第一次執行 (DGS10 可能從快取讀取, UNRATE 應下載, URL 包含 {multi_params})...")
        multi_data_first = client.get_multiple_series(series_ids=series_list_test, **multi_params)
        if not multi_data_first.empty:
            print(f"成功批量獲取數據 (第一次): {len(multi_data_first)} 筆")
            print(f"Series IDs: {multi_data_first['series_id'].unique()}")

        print(f"\n[批量] 第二次執行 (DGS10, UNRATE 均應從快取讀取, URL 包含 {multi_params})...")
        multi_data_second = client.get_multiple_series(series_ids=series_list_test, **multi_params)
        if not multi_data_second.empty:
            print(f"成功批量獲取數據 (第二次): {len(multi_data_second)} 筆")

        if not multi_data_first.empty and not multi_data_second.empty:
            if multi_data_first.equals(multi_data_second):
                print("[批量] 快取驗證：批量獲取的數據一致。")
            else:
                 print("警告：[批量] 快取驗證失敗：批量獲取的數據不一致！")

        print(f"\n[批量] 第三次執行 (強制刷新 DGS10, UNRATE, URL 包含 {multi_params})...")
        multi_data_third = client.get_multiple_series(series_ids=series_list_test, force_refresh=True, **multi_params)
        if not multi_data_third.empty:
            print(f"成功批量獲取數據 (強制刷新): {len(multi_data_third)} 筆")

        if not multi_data_first.empty and not multi_data_third.empty:
            if multi_data_first.equals(multi_data_third):
                print("[批量] 強制刷新驗證：批量獲取的數據一致。")
            else:
                print("警告：[批量] 強制刷新驗證失敗：批量獲取的數據不一致！")


        # 測試獲取一個可能不存在的系列 (確保錯誤處理仍然正常)
        print("\n--- 測試獲取不存在的系列 'NONEXISTENTSERIES123' (應不使用快取) ---")
        try:
            non_existent_data = client.fetch_data("NONEXISTENTSERIES123", force_refresh=False) # 快取無關緊要
            if non_existent_data.empty:
                print("獲取不存在系列數據返回空 DataFrame (API 可能返回錯誤或無觀測，已被處理)。")
        except requests.exceptions.HTTPError as e:
            print(f"成功捕獲到 HTTP 錯誤 (符合預期，因為系列不存在): {e.response.status_code if e.response else 'N/A'}")
            # print(f"詳細錯誤: {e.response.text if e.response else 'N/A'}") # 可能過於詳細

    except ValueError as ve_init:  # API Key 未設定等初始化問題
        print(f"初始化錯誤: {ve_init}")
    except Exception as e:
        print(f"執行 FREDClient 測試期間發生未預期錯誤: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close_session() # 確保關閉 session

    print("\n--- FREDClient 快取整合後測試結束 ---")
