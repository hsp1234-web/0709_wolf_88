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
            # 調用父類的 _request 方法，它會處理 URL 拼接和 GET 請求
            # FRED_OBSERVATIONS_ENDPOINT 是 "/fred/series/observations"
            json_response = super()._request(
                endpoint=FRED_OBSERVATIONS_ENDPOINT, params=final_params
            )

            if not json_response.get("observations"):
                print(
                    f"警告：FRED API 未返回 Series ID '{symbol}' 的觀測數據。可能是無效的 ID、日期範圍無數據或 API Key 權限問題。"
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

        # 測試獲取單一系列數據
        print("\n測試獲取單一系列 DGS10 (美國10年期公債殖利率)...")
        dgs10_data = client.fetch_data(
            symbol="DGS10", observation_start="2023-10-01", observation_end="2023-10-05"
        )
        if not dgs10_data.empty:
            print(f"成功獲取 DGS10 數據 (共 {len(dgs10_data)} 筆):")
            print(dgs10_data.head())
        else:
            print(
                "DGS10 數據請求成功，但返回為空 DataFrame (請檢查 API Key, 日期範圍或日誌)。"
            )

        # 測試獲取一個可能不存在的系列
        print("\n測試獲取不存在的系列 'NONEXISTENTSERIES123'...")
        try:
            non_existent_data = client.fetch_data("NONEXISTENTSERIES123")
            if non_existent_data.empty:
                print(
                    "獲取不存在系列數據返回空 DataFrame (API 可能返回錯誤或無觀測，已被處理)。"
                )
            else:
                print(
                    f"獲取不存在系列數據返回了非預期的數據: {non_existent_data.head()}"
                )
        except requests.exceptions.HTTPError as e:
            print(
                f"成功捕獲到 HTTP 錯誤 (符合預期，因為系列不存在): {e.response.status_code} - {e.response.text}"
            )

        # 測試批量獲取多個系列
        print("\n測試批量獲取多個系列 (DGS10, CPIAUCSL)...")
        series_to_fetch = ["DGS10", "CPIAUCSL", "UNRATE", "INVALIDSERIES99"]
        multi_series_data = client.get_multiple_series(
            series_ids=series_to_fetch,
            observation_start="2023-12-01",
            observation_end="2023-12-15",
            sort_order="asc",
        )
        if not multi_series_data.empty:
            print(f"成功批量獲取數據 (共 {len(multi_series_data)} 筆):")
            print(multi_series_data.head())
            print("...")
            print(multi_series_data.tail())
            print(f"數據中包含的 Series IDs: {multi_series_data['series_id'].unique()}")
        else:
            print("批量數據請求成功，但所有請求的系列均返回為空 DataFrame或獲取失敗。")

    except ValueError as ve_init:  # API Key 未設定等初始化問題
        print(f"初始化錯誤: {ve_init}")
    except Exception as e:
        print(f"執行期間發生未預期錯誤: {e}")

    print("--- FREDClient 重構後測試結束 ---")
