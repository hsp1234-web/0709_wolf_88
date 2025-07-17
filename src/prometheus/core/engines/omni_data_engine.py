# 檔案路徑: src/prometheus/core/engines/omni_data_engine.py
# --- 全天候數據獲取引擎 ---

import asyncio
from typing import Tuple, Optional

import pandas as pd

from prometheus.core.clients.yfinance import YFinanceClient
from prometheus.core.clients.finmind import FinMindClient
from prometheus.core.logging.log_manager import LogManager

logger = LogManager.get_instance().get_logger("OmniDataEngine")

class OmniDataEngine:
    """
    一個具有韌性的全天候數據獲取引擎，整合了多個數據源和降級策略。
    - 主要數據源: Yahoo Finance (`YFinanceClient`)
    - 備用數據源 (台股): FinMind (`FinMindClient`)
    - 降級策略:
        1. 顆粒度降級: 當分鐘線數據獲取失敗時，自動嘗試獲取日線數據。
        2. 數據源降級: 當主要數據源 (yfinance) 失敗時，自動切換到備用數據源 (finmind)。
    """

    def __init__(self):
        """初始化所有需要的數據客戶端。"""
        self.yf_client = YFinanceClient()
        # 注意：FinMindClient 需要 API Token，假設它已在環境變數中設定
        try:
            self.finmind_client = FinMindClient()
        except ValueError as e:
            logger.warning(f"無法初始化 FinMindClient，備用數據源將不可用: {e}")
            self.finmind_client = None

    async def get_data(
        self, symbol: str, interval: str = "1d", **kwargs
    ) -> Tuple[Optional[pd.DataFrame], str, str]:
        """
        獲取數據的核心方法，內建降級邏輯。

        Args:
            symbol (str): 商品代碼 (例如 "AAPL", "2330.TW")。
            interval (str): 數據顆粒度 (例如 "1d", "1h", "5m")。
            **kwargs: 其他傳遞給客戶端 fetch_data 方法的參數 (例如 period, start_date, end_date)。

        Returns:
            A tuple containing:
            - pd.DataFrame or None: 獲取的數據，如果所有嘗試都失敗則為 None。
            - str: 實際使用的數據源 (例如 "yfinance", "finmind", "none")。
            - str: 實際獲取的數據顆粒度 (例如 "1d", "1h")。
        """
        # --- 1. 主要路徑: 嘗試從 yfinance 獲取數據 ---
        logger.info(f"[{symbol}] 嘗試從主要數據源 (yfinance) 獲取 {interval} 數據...")
        data = await self.yf_client.fetch_data(symbol, interval=interval, **kwargs)

        if data is not None and not data.empty:
            logger.info(f"[{symbol}] 成功從 yfinance 獲取 {interval} 數據。")
            data.columns = [col.lower() for col in data.columns]
            return data, "yfinance", interval

        # --- 2. 獲取失敗，觸發降級邏輯 ---
        logger.warning(f"[{symbol}] yfinance 未能提供 {interval} 數據，啟動降級協議。")

        # --- 2a. 顆粒度降級: 如果請求的是分鐘/小時線，嘗試降級到日線 ---
        is_intraday = any(unit in interval for unit in ["m", "h"])
        if is_intraday:
            logger.info(f"[{symbol}] 顆粒度降級: 嘗試從 yfinance 獲取日線 (1d) 數據...")
            data_daily = await self.yf_client.fetch_data(symbol, interval="1d", **kwargs)
            if data_daily is not None and not data_daily.empty:
                logger.info(f"[{symbol}] 成功透過顆粒度降級從 yfinance 獲取到日線數據。")
                data_daily.columns = [col.lower() for col in data_daily.columns]
                return data_daily, "yfinance", "1d"
            logger.warning(f"[{symbol}] 顆粒度降級失敗，yfinance 同樣未能提供日線數據。")


        # --- 2b. 數據源降級: 嘗試備用數據源 (FinMind) ---
        # 僅對台股 (以 .TW 結尾) 進行數據源降級
        if symbol.upper().endswith(".TW") and self.finmind_client:
            finmind_symbol = symbol.split(".")[0]
            logger.info(f"[{symbol}] 數據源降級: 嘗試從 finmind (ID: {finmind_symbol}) 獲取日線數據...")
            try:
                # FinMind 通常只提供日線數據，這裡我們直接請求日線
                data_finmind = await self.finmind_client.fetch_data(
                    symbol=finmind_symbol,
                    dataset="TaiwanStockPrice",
                    start_date=kwargs.get("start_date", "2020-01-01"), # FinMind 需要一個開始日期
                    end_date=kwargs.get("end_date")
                )
                if data_finmind is not None and not data_finmind.empty:
                    logger.info(f"[{symbol}] 成功透過數據源降級從 finmind 獲取到日線數據。")
                    # FinMind 的欄位名稱可能不同，這裡可以做一個標準化處理
                    # 為了驗證協議，暫時直接返回
                    data_finmind.columns = [col.lower() for col in data_finmind.columns]
                    return data_finmind, "finmind", "1d"
            except Exception as e:
                logger.error(f"[{symbol}] 嘗試從 finmind 獲取數據時發生錯誤: {e}")


        # --- 3. 所有降級路徑均告失敗 ---
        logger.error(f"[{symbol}] 所有降級路徑均告失敗，無法獲取任何數據。")
        return None, "none", "none"
