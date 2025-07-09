# core/clients/fred.py
# 此模組包含與 FRED (Federal Reserve Economic Data) API 互動的客戶端邏輯。

import os
import requests
import pandas as pd
from typing import Optional, List # 新增 List

# FRED API 基礎 URL
FRED_API_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

class FREDAPIClient:
    """
    用於與 FRED API 互動的客戶端，以獲取經濟數據系列。
    """
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 FREDAPIClient。

        Args:
            api_key (Optional[str]): FRED API Key。如果未提供，
                                       將嘗試從環境變數 FRED_API_KEY 讀取。

        Raises:
            ValueError: 如果 API Key 未提供且環境變數中也未設定。
        """
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        if not self.api_key:
            raise ValueError("FRED API Key 未設定。請設定 FRED_API_KEY 環境變數或在初始化時傳入 api_key。")
        print("資訊：FREDAPIClient 初始化成功。")

    def get_series_observations(self, series_id: str,
                                realtime_start: Optional[str] = None,
                                realtime_end: Optional[str] = None,
                                limit: Optional[int] = None, # FRED API 預設 100,000
                                offset: Optional[int] = None,
                                sort_order: Optional[str] = None, # 'asc', 'desc'
                                observation_start: Optional[str] = None, # YYYY-MM-DD
                                observation_end: Optional[str] = None    # YYYY-MM-DD
                               ) -> Optional[pd.DataFrame]:
        """
        從 FRED API 獲取指定經濟數據系列的觀測值。

        Args:
            series_id (str): 要獲取的 FRED Series ID (例如 "DGS10", "CPIAUCSL")。
            realtime_start (Optional[str]): 即時數據開始日期 (YYYY-MM-DD)。預設為 API 的最早可用日期。
            realtime_end (Optional[str]): 即時數據結束日期 (YYYY-MM-DD)。預設為 API 的最新可用日期。
            limit (Optional[int]): 返回的最大觀測數量。
            offset (Optional[int]): 數據偏移量 (用於分頁)。
            sort_order (Optional[str]): 排序順序 ('asc' 或 'desc')。
            observation_start (Optional[str]): 觀測數據的開始日期 (YYYY-MM-DD)。
            observation_end (Optional[str]): 觀測數據的結束日期 (YYYY-MM-DD)。

        Returns:
            Optional[pd.DataFrame]: 包含觀測數據的 DataFrame (欄位: date, series_id, value)。
                                     如果請求失敗或無數據，則返回 None 或空 DataFrame。
        """
        params = {
            'series_id': series_id,
            'api_key': self.api_key,
            'file_type': 'json',
        }
        # 添加可選參數
        if realtime_start: params['realtime_start'] = realtime_start
        if realtime_end: params['realtime_end'] = realtime_end
        if limit is not None: params['limit'] = str(limit)
        if offset is not None: params['offset'] = str(offset)
        if sort_order: params['sort_order'] = sort_order
        if observation_start: params['observation_start'] = observation_start
        if observation_end: params['observation_end'] = observation_end

        print(f"資訊：正在從 FRED API 獲取數據，Series ID: {series_id}, Params: { {k:v for k,v in params.items() if k not in ['api_key']} }")

        try:
            response = requests.get(FRED_API_BASE_URL, params=params)
            response.raise_for_status()  # 如果 HTTP 狀態碼是 4xx 或 5xx，則引發 HTTPError

            data = response.json()

            if not data.get('observations'):
                print(f"警告：FRED API 未返回 Series ID '{series_id}' 的觀測數據。可能是無效的 ID、日期範圍無數據或 API Key 權限問題。")
                return pd.DataFrame() # 成功請求但無數據，返回空 DataFrame

            df = pd.DataFrame(data['observations'])

            # FRED 返回的 'value' 可能包含 '.' 表示無數據，需要處理
            # 保留 'realtime_start', 'realtime_end', 'date', 'value'
            # 根據遷移的 fetch_fred_data，我們只需要 date 和 value
            df = df[['date', 'value']]
            df['date'] = pd.to_datetime(df['date'])

            # 將 '.' 或其他非數值轉換為 NaN，然後移除這些行
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df.dropna(subset=['value'], inplace=True)

            df['series_id'] = series_id  # 新增 series_id 欄位以標識數據來源

            # 重新排列欄位順序以符合預期
            df = df[['date', 'series_id', 'value']]

            print(f"資訊：成功從 FRED API 獲取 {len(df)} 筆 Series ID '{series_id}' 的有效觀測數據。")
            return df

        except requests.exceptions.HTTPError as http_err:
            print(f"錯誤：FRED API HTTP 錯誤 (Series ID: {series_id})：{http_err} - 回應內容：{response.text if response else '無回應內容'}")
            return None
        except requests.exceptions.RequestException as req_err:
            print(f"錯誤：請求 FRED API 時發生網路或請求配置錯誤 (Series ID: {series_id})：{req_err}")
            return None
        except ValueError as json_err: # requests.json() 可能引發的錯誤
            print(f"錯誤：解析 FRED API JSON 回應時失敗 (Series ID: {series_id})：{json_err}")
            return None
        except Exception as e:
            print(f"錯誤：處理 FRED API 數據時發生未知錯誤 (Series ID: {series_id})：{e}")
            return None

    def get_multiple_series(self, series_ids: List[str], **kwargs) -> Optional[pd.DataFrame]:
        """
        獲取多個 FRED 經濟數據系列的觀測值並將它們合併。

        Args:
            series_ids (List[str]): 要獲取的 FRED Series ID 列表。
            **kwargs: 其他傳遞給 get_series_observations 的參數
                      (例如 observation_start, observation_end)。

        Returns:
            Optional[pd.DataFrame]: 包含所有請求系列數據的合併 DataFrame。
                                     如果所有系列都請求失敗或無數據，則返回 None 或空 DataFrame。
        """
        all_series_data = []
        print(f"資訊：開始批量獲取 FRED Series IDs: {series_ids}")
        for series_id in series_ids:
            print(f"資訊：處理批量請求中的 Series ID: {series_id}")
            series_df = self.get_series_observations(series_id, **kwargs)
            if series_df is not None and not series_df.empty:
                all_series_data.append(series_df)
            elif series_df is None: # 單個系列獲取失敗
                print(f"警告：批量獲取中，Series ID '{series_id}' 數據獲取失敗。")
            # series_df is empty DataFrame: 該系列無數據，不需特別處理，不會被 concat

        if not all_series_data:
            print("警告：批量獲取 FRED 數據未成功獲取任何系列的有效數據。")
            return pd.DataFrame() # 如果所有系列都無數據或失敗，返回空 DataFrame

        combined_df = pd.concat(all_series_data, ignore_index=True)
        print(f"資訊：成功合併 {len(all_series_data)} 個 FRED 系列的數據，總共 {len(combined_df)} 筆記錄。")
        return combined_df


# 範例使用 (主要用於開發時測試)
if __name__ == '__main__':
    print("--- FRED API Client 測試 (直接執行 core/clients/fred.py) ---")
    # 執行此測試前，請確保設定了 FRED_API_KEY 環境變數
    try:
        client = FREDAPIClient() # API Key 從環境變數讀取
        print("FREDAPIClient 初始化成功。")

        # 測試獲取單一系列數據 (例如美國10年期公債殖利率)
        print("\n測試獲取單一系列 DGS10 (美國10年期公債殖利率)...")
        dgs10_data = client.get_series_observations("DGS10", observation_start="2023-01-01", observation_end="2023-01-10")
        if dgs10_data is not None:
            if not dgs10_data.empty:
                print(f"成功獲取 DGS10 數據 (共 {len(dgs10_data)} 筆):")
                print(dgs10_data.head())
            else:
                print("DGS10 數據請求成功，但返回為空 DataFrame (該日期範圍可能無數據)。")
        else:
            print("獲取 DGS10 數據失敗。")

        # 測試獲取一個可能不存在或近期無數據的系列
        print("\n測試獲取不存在的系列 'NONEXISTENTSERIES123'...")
        non_existent_data = client.get_series_observations("NONEXISTENTSERIES123")
        if non_existent_data is not None and non_existent_data.empty:
            print("獲取不存在系列數據返回空 DataFrame (符合預期，API 可能返回錯誤或無觀測)。")
        elif non_existent_data is None:
            print("獲取不存在系列數據失敗 (符合預期)。")
        else:
            print(f"獲取不存在系列數據返回了非預期的數據: {non_existent_data.head()}")

        # 測試批量獲取多個系列
        print("\n測試批量獲取多個系列 (DGS10, CPIAUCSL)...")
        series_to_fetch = ["DGS10", "CPIAUCSL", "UNRATE"] # 美國10年期公債, CPI, 失業率
        multi_series_data = client.get_multiple_series(
            series_ids=series_to_fetch,
            observation_start="2023-10-01",
            observation_end="2023-12-31",
            sort_order="asc" # 要求升序
        )
        if multi_series_data is not None:
            if not multi_series_data.empty:
                print(f"成功批量獲取數據 (共 {len(multi_series_data)} 筆):")
                print(multi_series_data.head())
                print("...")
                print(multi_series_data.tail())
                # 驗證是否包含所有請求的 series_id
                print(f"數據中包含的 Series IDs: {multi_series_data['series_id'].unique()}")
            else:
                print("批量數據請求成功，但所有系列均返回為空 DataFrame。")
        else:
            print("批量獲取數據失敗 (可能部分或全部系列失敗)。")

    except ValueError as ve: # API Key 未設定等初始化問題
        print(f"初始化錯誤: {ve}")
    except Exception as e:
        print(f"執行期間發生未預期錯誤: {e}")

    print("--- FRED API Client 測試結束 ---")
