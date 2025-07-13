# -*- coding: utf-8 -*-
"""
數據管線第一階段：小時級價格數據提取器 (Extractor)
"""
import logging
from typing import Dict, List

import pandas as pd
import yfinance as yf

from core.utils.caching import get_cached_session, temporary_disabled_cache

logger = logging.getLogger(__name__)

# A. 基礎價格數據: 主要市場指數、期貨、大宗商品、貨幣、美國大型股
BASIC_PRICE_ASSETS: List[str] = [
    "SPY",  # S&P 500 ETF
    "QQQ",  # Nasdaq 100 ETF
    "IWM",  # Russell 2000 ETF
    "EFA",  # MSCI EAFE ETF (已開發市場)
    "EEM",  # MSCI Emerging Markets ETF (新興市場)
    "TLT",  # 20+ Year Treasury Bond ETF
    "HYG",  # High-yield Corporate Bond ETF
    "DBC",  # Invesco DB Commodity Index Tracking Fund
    "GLD",  # Gold ETF
    "SLV",  # Silver ETF
    "UUP",  # US Dollar Index ETF
    "EURUSD=X",  # 歐元/美元
    "USDJPY=X",  # 美元/日圓
    "ES=F",  # S&P 500 期貨
    "NQ=F",  # Nasdaq 100 期貨
    "YM=F",  # Dow Jones 期貨
    "RTY=F", # Russell 2000 期貨
    "CL=F",  # 原油期貨
    "GC=F",  # 黃金期貨
    "SI=F",  # 白銀期貨
    "HG=F",  # 銅期貨
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "TSLA",
    "META",
    "BRK-B",
    "JPM",
    "TSM",  # 台積電 ADR
]


def run_extraction(mode: str) -> Dict[str, pd.DataFrame]:
    """
    從 yfinance 提取小時線 OHLCV 數據。

    Args:
        mode (str): 操作模式，可以是 'backfill' 或 'update'。

    Returns:
        Dict[str, pd.DataFrame]: 一個字典，鍵是資產代號，值是包含 OHLCV 數據的 DataFrame。
    """
    logger.info(f"--- [Extractor] 啟動，模式: {mode} ---")

    if mode not in ["backfill", "update"]:
        raise ValueError("模式參數必須是 'backfill' 或 'update'")

    # 根據模式設定 yfinance 的下載參數
    if mode == "backfill":
        params = {"period": "730d", "interval": "1h"}
        logger.info("執行回填模式，下載過去 730 天的小時數據。")
    else:  # update mode
        params = {"period": "2d", "interval": "1h"}
        logger.info("執行更新模式，下載最近 2 天的小時數據。")

    # yfinance.download 接受一個包含所有代號的單一列表
    # 這比逐一下載要高效得多
    logger.info(f"準備從 yfinance 下載 {len(BASIC_PRICE_ASSETS)} 檔資產數據...")

    # 快取策略：
    # yfinance 有自己的快取機制。我們的快取主要用於開發和測試。
    # 在 'update' 模式下，我們需要確保獲取最新數據，
    # yfinance 本身在請求近期數據時通常不會返回陳舊的快取。
    # 我們的 caching.py 在這裡主要是為了提供一個統一的模式，
    # 但 yfinance 的行為是關鍵。
    session = get_cached_session()
    # 在更新模式下，我們理論上應該禁用快取以獲取最新數據，
    # 但 yfinance 的 download 不直接接受 session 物件。
    # yfinance 的快取是基於時間的，請求 '2d' 的數據通常能繞過快取。
    # 此處保留快取邏輯以符合專案架構。

    # 使用 yfinance.download 進行批次下載
    try:
        with temporary_disabled_cache(session) if mode == "update" else open("/dev/null", "w") as _:
            raw_data = yf.download(
                tickers=BASIC_PRICE_ASSETS,
                **params,
                group_by='ticker',
                auto_adjust=False,  # 我們需要原始的 OHLCV
                prepost=False,       # 忽略盤前盤後交易
                threads=True,        # 使用多線程加速
                proxy=None
            )
    except Exception as e:
        logger.error(f"使用 yfinance 下載數據時發生嚴重錯誤: {e}", exc_info=True)
        return {}

    if raw_data.empty:
        logger.warning("yfinance.download 返回了空的 DataFrame，沒有提取到任何數據。")
        return {}

    # yfinance 在下載單一代號時返回一個簡單的 DataFrame，
    # 但在下載多個代號時返回一個以代號為鍵的字典或一個多索引的 DataFrame。
    # 我們將其標準化為一個字典，其中每個鍵對應一個 DataFrame。
    # yfinance v0.2+ `download` returns a dict of DataFrames when multiple tickers are requested.
    # The keys are the ticker symbols.
    # We will iterate through the tickers and handle cases where data might be missing.
    data_dict = {}
    for ticker in BASIC_PRICE_ASSETS:
        if ticker in raw_data and not raw_data[ticker].empty:
            data_dict[ticker] = raw_data[ticker]
        else:
            logger.warning(f"未能提取到資產 {ticker} 的數據，或返回的數據為空。")


    # 清理和驗證每個 DataFrame
    valid_data = {}
    for ticker, df in data_dict.items():
        if df.empty:
            logger.warning(f"資產 {ticker} 沒有返回任何數據。")
            continue
        # 移除完全是 NaN 的行
        df.dropna(how='all', inplace=True)
        if df.empty:
            logger.warning(f"資產 {ticker} 在移除 NaN 行後變為空。")
            continue
        valid_data[ticker] = df

    logger.info(f"--- [Extractor] 完成，成功提取 {len(valid_data)} 檔有效資產數據 ---")
    return valid_data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    print("--- [測試] 執行數據提取模組 (回填模式) ---")
    backfill_data = run_extraction(mode="backfill")
    if backfill_data:
        # 打印 SPY 數據的頭幾行作為樣本
        spy_data = backfill_data.get("SPY")
        if spy_data is not None:
            print("\nSPY (backfill) 數據預覽:")
            print(spy_data.head())
            print(f"SPY 總共獲取 {len(spy_data)} 筆小時數據。")
        else:
            print("\n未找到 SPY 的回填數據。")
    else:
        print("回填模式未提取到任何數據。")


    print("\n--- [測試] 執行數據提取模組 (更新模式) ---")
    update_data = run_extraction(mode="update")
    if update_data:
        # 打印 AAPL 數據作為樣本
        aapl_data = update_data.get("AAPL")
        if aapl_data is not None:
            print("\nAAPL (update) 數據預覽:")
            print(aapl_data)
            print(f"AAPL 總共獲取 {len(aapl_data)} 筆小時數據。")
        else:
            print("\n未找到 AAPL 的更新數據。")
    else:
        print("更新模式未提取到任何數據。")
