# -*- coding: utf-8 -*-
"""
數據管線第一階段：數據提取器 (Extractor)
"""

import logging
from typing import Any, Dict, Optional

import pandas as pd

from core.clients.finmind import FinMindClient
from core.clients.fred import FredClient
from core.clients.yfinance import YFinanceClient
from core.config import get_fred_api_key
from core.utils.caching import get_cached_session, temporary_disabled_cache

# 設定日誌
logger = logging.getLogger(__name__)


def run_extraction(
    force_download: bool = False,
    fred_api_key: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    """
    核心數據提取函式。

    負責從所有必要的數據源（FRED, yfinance, FinMind等）提取原始數據，
    並應用統一的快取策略。

    Args:
        force_download (bool): 若為 True，則強制從網路重新下載所有數據，忽略快取。
        fred_api_key (Optional[str]): 用於認證 FRED API 的金鑰。如果未提供，
                                     會嘗試從 `core.config` 獲取。
        start_date (Optional[str]): 數據提取的開始日期 (YYYY-MM-DD)。
        end_date (Optional[str]): 數據提取的結束日期 (YYYY-MM-DD)。

    Returns:
        Dict[str, pd.DataFrame]: 一個字典，鍵為數據源或指標的描述性名稱，
                                 值為對應的 Pandas DataFrame。
                                 如果某個數據源提取失敗，將不會包含在字典中。
    """
    logger.info(f"數據提取流程開始。強制下載模式: {'啟用' if force_download else '停用'}")

    # 統一的快取 Session
    session = get_cached_session()

    # 數據容器
    raw_data: Dict[str, pd.DataFrame] = {}

    # --------------------------------------------------------------------------
    # 數據源 1: FRED (聯準會經濟數據)
    # --------------------------------------------------------------------------
    try:
        logger.info("正在初始化 FRED 客戶端...")
        # 如果未傳入 key，FredClient 會自動從 config 加載
        fred_client = FredClient(api_key=fred_api_key, session=session)
        fred_series_to_fetch = {
            "DGS10": "美國10年期公債殖利率",
            "VIXCLS": "CBOE 波動率指數 (VIX)",
        }
        with temporary_disabled_cache(session) if force_download else open("/dev/null", "w") as _:
            for series_id, description in fred_series_to_fetch.items():
                try:
                    logger.info(f"正在從 FRED 提取: {description} ({series_id})")
                    df = fred_client.fetch_data(
                        symbol=series_id,
                        observation_start=start_date,
                        observation_end=end_date,
                    )
                    if not df.empty:
                        raw_data[f"FRED_{series_id}"] = df
                        logger.info(f"成功提取並儲存 {len(df)} 筆 {series_id} 數據。")
                    else:
                        logger.warning(f"從 FRED 提取 {series_id} 時返回了空的 DataFrame。")
                except Exception as e:
                    logger.error(f"從 FRED 提取 {series_id} 失敗: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"初始化 FRED 客戶端失敗: {e}", exc_info=True)

    # --------------------------------------------------------------------------
    # 數據源 2: Yahoo Finance (市場指數)
    # --------------------------------------------------------------------------
    try:
        logger.info("正在初始化 yfinance 客戶端...")
        yfinance_client = YFinanceClient() # yfinance 客戶端不直接使用 session
        yfinance_symbols_to_fetch = {
            "^GSPC": "S&P 500 指數",
            "^IXIC": "NASDAQ 綜合指數",
            "^MOVE": "MOVE 恐慌指數",
            "GC=F": "黃金期貨",
            "HG=F": "銅期貨",
        }
        # yfinance 的快取由其內部處理，但我們的 force_download 邏輯可以應用
        # yfinance client 的 fetch_data 不直接支援 force_download，但我們可以透過不使用快取版本的 session 來模擬
        # 不過 yfinance client 是獨立的，所以我們這裡的快取控制是概念性的
        for symbol, description in yfinance_symbols_to_fetch.items():
            try:
                logger.info(f"正在從 yfinance 提取: {description} ({symbol})")

                # 決定 yfinance 的提取參數
                fetch_params = {"symbol": symbol}
                if start_date and end_date:
                    fetch_params["start_date"] = start_date
                    fetch_params["end_date"] = end_date
                else:
                    fetch_params["period"] = "max"

                df = yfinance_client.fetch_data(**fetch_params)
                if not df.empty:
                    raw_data[f"YFINANCE_{symbol}"] = df
                    logger.info(f"成功提取並儲存 {len(df)} 筆 {symbol} 數據。")
                else:
                    logger.warning(f"在指定期間內從 yfinance 提取 {symbol} 時返回了空的 DataFrame。")
            except Exception as e:
                logger.error(f"從 yfinance 提取 {symbol} 失敗: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"初始化 yfinance 客戶端失敗: {e}", exc_info=True)

    # --------------------------------------------------------------------------
    # 數據源 3: FinMind (台灣市場數據)
    # --------------------------------------------------------------------------
    try:
        logger.info("正在初始化 FinMind 客戶端...")
        finmind_client = FinMindClient()
        try:
            logger.info("正在從 FinMind 提取: 台灣加權指數")
            # FinMindClient 不受外部快取控制，force_download 概念上適用但無直接作用
            df = finmind_client.fetch_data(
                symbol="TAIEX",
                dataset="TaiwanStockPrice",
                start_date="2000-01-01",
            )
            if not df.empty:
                raw_data["FINMIND_TAIEX"] = df
                logger.info(f"成功提取並儲存 {len(df)} 筆 TAIEX 數據。")
            else:
                logger.warning("從 FinMind 提取 TAIEX 時返回了空的 DataFrame。")
        except Exception as e:
            logger.error(f"從 FinMind 提取 TAIEX 失敗: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"初始化 FinMind 客戶端失敗: {e}", exc_info=True)


    logger.info(f"數據提取流程結束。成功提取 {len(raw_data)} 個數據集。")
    return raw_data


if __name__ == "__main__":
    # 配置基本的日誌記錄器以進行本地測試
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
    )

    print("--- [測試] 執行數據提取模組 ---")

    # 測試 1: 正常執行 (應使用快取)
    print("\n--- 執行第一次 (應從網路下載並快取) ---")
    extracted_data_cache = run_extraction()
    for name, df in extracted_data_cache.items():
        print(f"  - 獲取到數據集 '{name}', 共 {len(df)} 筆記錄。")
        print(df.head(2))
        print("-" * 20)

    # 測試 2: 再次執行 (應快速完成，從快取加載)
    print("\n--- 執行第二次 (應從快取加載) ---")
    extracted_data_cache_2 = run_extraction()
    print(f"第二次提取完成，共 {len(extracted_data_cache_2)} 個數據集。")


    # 測試 3: 強制重新下載
    print("\n--- 執行第三次 (強制重新下載) ---")
    extracted_data_force = run_extraction(force_download=True)
    print(f"強制下載完成，共 {len(extracted_data_force)} 個數據集。")

    print("\n--- [測試] 數據提取模組執行完畢 ---")
