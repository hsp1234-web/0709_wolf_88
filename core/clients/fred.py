# -*- coding: utf-8 -*-
"""
核心數據客戶端：聯準會經濟數據庫 (FRED) (v2.1 - 快取與金鑰管理升級版)
"""
import pandas as pd
# 使用官方的 fredapi 函式庫，而不是直接操作 requests
from fredapi import Fred as FredAPILib
from typing import List, Dict, Any, Optional

from .base import BaseAPIClient
from core.config import get_fred_api_key # **關鍵改造**：導入金鑰獲取函數

class FredClient(BaseAPIClient):
    """
    用於從 FRED API 獲取經濟數據的客戶端。
    使用官方 fredapi 函式庫進行數據獲取。
    """
    def __init__(self):
        """
        初始化 FredClient。
        金鑰會自動從 config.yml 讀取。
        """
        try:
            # **關鍵改造**: 自動從設定檔獲取金鑰
            api_key = get_fred_api_key()
        except ValueError as e:
            # 如果金鑰未設定，提供清晰的錯誤指引
            print(f"錯誤：無法初始化 FredClient。{e}")
            # 應該重新拋出原始錯誤或一個新的特定錯誤，以阻止客戶端在沒有金鑰的情況下被建立
            raise ValueError(f"FredClient 初始化失敗: {e}") from e

        # BaseAPIClient 的 base_url 在此情境下不是主要用途，
        # 因為 fredapi 函式庫內部管理其 API 端點。
        # 但我們仍需調用 super().__init__ 以設定好 self._session (儘管 fredapi 不直接用它)
        # 和 self.api_key (fredapi 會用到)。
        super().__init__(api_key=api_key, base_url="https://api.stlouisfed.org/fred")

        # 使用獲取的金鑰初始化官方 fredapi 實例
        # self.api_key 是由 super().__init__ 設定的
        self._fred_official_client = FredAPILib(api_key=self.api_key)
        print(f"資訊：FredClient ({self.__class__.__name__}) 初始化成功，已載入 API 金鑰。")

    def fetch_data(self, symbol: str, **kwargs: Any) -> pd.DataFrame:
        """
        從 FRED 獲取單個時間序列數據。

        Args:
            symbol (str): FRED 指標的代碼 (e.g., 'DGS10', 'VIXCLS')。
            **kwargs: 可接受 'force_refresh' (bool) 以建議繞過快取 (主要用於日誌和一致性，
                      因為 fredapi 的快取行為獨立)。
                      其他參數如 'observation_start', 'observation_end' 等會傳遞給 fredapi。

        Returns:
            pd.DataFrame: 包含 'Date' 和指標值的時間序列數據。
                          若獲取失敗或數據無效，則返回包含 'Date' 和 symbol 列的空 DataFrame。
        Raises:
            ValueError: 如果 FRED 回傳的數據無效或全為空值。
        """
        print(f"資訊：{self.__class__.__name__} 正在獲取指標 {symbol}...")
        force_refresh = kwargs.get('force_refresh', False)

        # 提取 fredapi 支援的參數
        fred_params = {k: v for k, v in kwargs.items() if k in [
            'observation_start', 'observation_end',
            'realtime_start', 'realtime_end',
            'limit', 'offset', 'sort_order',
            'aggregation_method', 'frequency', 'units'
        ]}

        # 使用 BaseAPIClient 的快取控制上下文，主要是為了日誌記錄和保持介面一致性
        # 注意：requests-cache 不會直接攔截 fredapi 函式庫的內部請求。
        # fredapi 可能有自己的快取邏輯 (雖然其文件未明確說明客戶端快取)。
        # 我們的快取層主要作用於我們自己發出的 requests 請求。
        # 這裡的 force_refresh 更多是作為一個「意圖」傳遞。
        with self._get_request_context(force_refresh=force_refresh):
            try:
                # 使用官方 fredapi 函式庫獲取數據
                series_data = self._fred_official_client.get_series(series_id=symbol, **fred_params)
            except Exception as e: # 捕獲 fredapi 可能拋出的任何錯誤
                print(f"錯誤：{self.__class__.__name__} 使用 fredapi 獲取 {symbol} 時發生錯誤: {e}")
                # 返回標準化的空 DataFrame
                return pd.DataFrame(columns=['Date', symbol]).set_index('Date')


        if not isinstance(series_data, pd.Series):
            print(f"警告：{self.__class__.__name__} 從 FRED 獲取的指標 {symbol} 數據類型不是 pd.Series，而是 {type(series_data)}。")
            return pd.DataFrame(columns=['Date', symbol]).set_index('Date')

        if series_data.empty:
            print(f"警告：{self.__class__.__name__} 從 FRED 獲取的指標 {symbol} 數據為空。")
            # 返回標準化的空 DataFrame
            return pd.DataFrame(columns=['Date', symbol]).set_index('Date')

        df = series_data.to_frame(name=symbol)
        df.index.name = 'Date'

        # 髒數據防護點: 檢查轉換後的 DataFrame 是否合理
        if df.empty or (symbol in df and df[symbol].isnull().all()):
            # 即使 fredapi 返回了東西，如果全是 NaN，也認為是無效數據
            print(f"警告：{self.__class__.__name__} 獲取的指標 {symbol} 數據轉換後無效或全為空值。")
            # 保險起見，返回標準化的空 DataFrame
            return pd.DataFrame(columns=['Date', symbol]).set_index('Date')

        print(f"資訊：{self.__class__.__name__} 成功獲取 {len(df)} 筆 {symbol} 數據。")
        return df

    def close_session(self):
        """
        關閉由 BaseAPIClient 管理的 requests session。
        fredapi 函式庫不直接暴露其 session 管理，因此這裡只調用父類的方法。
        """
        super().close_session()
        print(f"資訊：{self.__class__.__name__} 的基礎 session (如果已初始化) 已關閉。")


if __name__ == '__main__':
    print("--- FredClient 金鑰與快取升級後測試 ---")
    print("請確保您的 config.yml 中已填寫有效的 FRED API Key。")

    client: Optional[FredClient] = None
    try:
        client = FredClient()

        test_series_id = 'DGS10' # 10年期公債殖利率
        test_params_initial = {'observation_start': '2023-01-01', 'observation_end': '2023-01-10'}

        print(f"\n--- 測試獲取 {test_series_id} (第一次, 應實際請求) ---")
        data_first = client.fetch_data(test_series_id, **test_params_initial)
        if not data_first.empty:
            print(f"{test_series_id} 數據範例 (第一次):")
            print(data_first.tail(3))
        else:
            print(f"無法獲取 {test_series_id} 數據 (第一次)。")

        # 由於 fredapi 不使用我們的 requests-cache，重複請求通常會再次命中 API。
        # BaseAPIClient 的快取上下文在這裡主要是日誌作用和概念上的一致性。
        # 若要測試 fredapi 自身的潛在快取或避免重複 API 呼叫，需更複雜的 mock。
        print(f"\n--- 測試獲取 {test_series_id} (第二次, 參數相同) ---")
        data_second = client.fetch_data(test_series_id, **test_params_initial)
        if not data_second.empty:
            print(f"{test_series_id} 數據範例 (第二次):")
            print(data_second.tail(3))
            if data_first.equals(data_second):
                print("INFO: 第二次獲取數據與第一次一致。")
            else:
                print("WARNING: 第二次獲取數據與第一次不一致。")
        else:
            print(f"無法獲取 {test_series_id} 數據 (第二次)。")

        print(f"\n--- 測試獲取 {test_series_id} (強制刷新, 意圖) ---")
        data_refresh = client.fetch_data(test_series_id, force_refresh=True, **test_params_initial)
        if not data_refresh.empty:
            print(f"{test_series_id} 數據範例 (強制刷新):")
            print(data_refresh.tail(3))
        else:
            print(f"無法獲取 {test_series_id} 數據 (強制刷新)。")

        # 測試一個可能不存在的指標
        print("\n--- 測試獲取不存在的指標 (FAKEID123) ---")
        fake_data = client.fetch_data('FAKEID123')
        if fake_data.empty:
            print("成功處理不存在的指標 FAKEID123，返回空 DataFrame。")
        else:
            print("錯誤：獲取不存在指標 FAKEID123 時未返回空 DataFrame。")


    except ValueError as ve: # 例如金鑰未設定
        print(f"\n測試過程中發生設定錯誤: {ve}")
    except Exception as e:
        print(f"\n測試過程中發生未預期錯誤: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if client:
            client.close_session()

    print("\n--- FredClient 測試結束 ---")
