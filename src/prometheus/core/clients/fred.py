# -*- coding: utf-8 -*-
"""
核心數據客戶端：聯準會經濟數據庫 (FRED) (v2.1 - 快取與金鑰管理升級版)
"""

from typing import Any, Optional

import pandas as pd

from fredapi import Fred as FredAPILib

from prometheus.core.config import get_fred_api_key
from prometheus.core.logging.log_manager import LogManager

from .base import BaseAPIClient

logger = LogManager.get_instance().get_logger("FredClient")


class FredClient(BaseAPIClient):
    """
    用於從 FRED API 獲取經濟數據的客戶端。
    使用官方 fredapi 函式庫進行數據獲取。
    """

    def __init__(
        self, api_key: Optional[str] = None, session: Optional[Any] = None
    ):  # 添加 session 以便測試時傳入
        """
        初始化 FredClient。

        Args:
            api_key (Optional[str]): 要使用的 FRED API 金鑰。
                                     如果提供，則使用此金鑰。
                                     如果為 None，則嘗試從 config.yml 讀取。
            session (Optional[Any]): requests session 物件，主要用於測試時注入 mock session。
                                     fredapi 函式庫本身不直接使用此 session，但 BaseAPIClient 可能會。
        """
        final_api_key: Optional[str] = None
        if api_key:
            final_api_key = api_key
            logger.info("初始化時偵測到直接傳入的 API 金鑰。")
        else:
            try:
                logger.debug("初始化時未直接傳入 API 金鑰，嘗試從設定檔獲取...")
                final_api_key = get_fred_api_key()
            except ValueError as e:
                logger.error(f"無法初始化 FredClient: {e}", exc_info=True)
                raise ValueError(f"FredClient 初始化失敗: {e}") from e

        if not final_api_key:
            error_msg = "FredClient 初始化失敗：API 金鑰既未直接提供，也無法從設定檔中獲取。"
            logger.error(error_msg)
            raise ValueError(error_msg)

        super().__init__(
            api_key=final_api_key, base_url="https://api.stlouisfed.org/fred"
        )

        if session:
            self._session = session
            logger.info("已使用傳入的 session 物件。")

        self._fred_official_client = FredAPILib(api_key=self.api_key)
        self._emergency_cache = {}
        logger.info(f"{self.__class__.__name__} 初始化成功。FredAPILib 將自行管理其網路請求。已啟用應急快取。")

    def fetch_data(self, symbol: str, **kwargs: Any) -> pd.DataFrame:
        """
        從 FRED 獲取單個時間序列數據。
        """
        logger.info(f"正在獲取指標 {symbol}...")
        force_refresh = kwargs.get("force_refresh", False)
        cache_key_params = tuple(
            sorted((k, v) for k, v in kwargs.items() if k != "force_refresh")
        )
        cache_key = (symbol, cache_key_params)

        if not force_refresh and cache_key in self._emergency_cache:
            logger.debug(f"使用應急快取獲取指標 {symbol} 及參數 {cache_key_params}...")
            return self._emergency_cache[cache_key].copy()

        fred_params = {
            k: v
            for k, v in kwargs.items()
            if k in ["observation_start", "observation_end", "realtime_start", "realtime_end", "limit", "offset", "sort_order", "aggregation_method", "frequency", "units"]
        }

        with self._get_request_context(force_refresh=force_refresh):
            if force_refresh and cache_key in self._emergency_cache:
                logger.debug(f"應急快取因 force_refresh 而清除 {symbol} / {cache_key_params}。")
                del self._emergency_cache[cache_key]

            try:
                logger.debug(f"正在透過 FredAPILib 請求 {symbol}...")
                series_data = self._fred_official_client.get_series(series_id=symbol, **fred_params)
            except Exception as e:
                logger.error(f"使用 fredapi 獲取 {symbol} 時發生錯誤: {e}", exc_info=True)
                return pd.DataFrame(columns=["Date", symbol]).set_index("Date")

        if not isinstance(series_data, pd.Series):
            logger.warning(f"從 FRED 獲取的指標 {symbol} 數據類型不是 pd.Series，而是 {type(series_data)}。")
            return pd.DataFrame(columns=["Date", symbol]).set_index("Date")

        if series_data.empty:
            logger.warning(f"從 FRED 獲取的指標 {symbol} 數據為空。")
            return pd.DataFrame(columns=["Date", symbol]).set_index("Date")

        df = series_data.to_frame(name=symbol)
        df.index.name = "Date"

        if df.empty or (symbol in df and df[symbol].isnull().all()):
            logger.warning(f"獲取的指標 {symbol} 數據轉換後無效或全為空值。")
            return pd.DataFrame(columns=["Date", symbol]).set_index("Date")

        self._emergency_cache[cache_key] = df.copy()
        logger.debug(f"成功獲取並已存入應急快取 {len(df)} 筆 {symbol} / {cache_key_params} 數據。")
        return df

    def close_session(self):
        """
        關閉由 BaseAPIClient 管理的 requests session。
        """
        super().close_session()
        logger.info("基礎 session (如果已初始化) 已關閉。")


if __name__ == "__main__":
    print("--- FredClient 金鑰與快取升級後測試 ---")
    print("請確保您的 config.yml 中已填寫有效的 FRED API Key。")

    client: Optional[FredClient] = None
    try:
        client = FredClient()

        test_series_id = "DGS10"  # 10年期公債殖利率
        test_params_initial = {
            "observation_start": "2023-01-01",
            "observation_end": "2023-01-10",
        }

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
        data_refresh = client.fetch_data(
            test_series_id, force_refresh=True, **test_params_initial
        )
        if not data_refresh.empty:
            print(f"{test_series_id} 數據範例 (強制刷新):")
            print(data_refresh.tail(3))
        else:
            print(f"無法獲取 {test_series_id} 數據 (強制刷新)。")

        # 測試一個可能不存在的指標
        print("\n--- 測試獲取不存在的指標 (FAKEID123) ---")
        fake_data = client.fetch_data("FAKEID123")
        if fake_data.empty:
            print("成功處理不存在的指標 FAKEID123，返回空 DataFrame。")
        else:
            print("錯誤：獲取不存在指標 FAKEID123 時未返回空 DataFrame。")

    except ValueError as ve:  # 例如金鑰未設定
        print(f"\n測試過程中發生設定錯誤: {ve}")
    except Exception as e:
        print(f"\n測試過程中發生未預期錯誤: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if client:
            client.close_session()

    print("\n--- FredClient 測試結束 ---")
