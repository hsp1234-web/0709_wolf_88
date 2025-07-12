# 檔案路徑: core/analysis/data_engine.py
import pandas as pd
from datetime import datetime
from typing import Dict, Any

# 假設這些是我們已經存在的客戶端
from core.clients.yfinance import YFinanceClient
from core.clients.fred import FredClient
from core.clients.taifex_db import TaifexDBClient

class DataEngine:
    """
    數據引擎核心。
    負責協調所有數據客戶端，計算多維度指標，
    並生成一份「高密度市場狀態快照」。
    """
    def __init__(self, yf_client: YFinanceClient, fred_client: FredClient, taifex_client: TaifexDBClient):
        """
        透過依賴注入初始化，傳入所有需要的數據客戶端。
        """
        self.yf_client = yf_client
        self.fred_client = fred_client
        self.taifex_client = taifex_client

    def _calculate_technicals(self, ohlcv: pd.DataFrame) -> Dict[str, Any]:
        """
        私有方法：計算基礎技術指標。
        【Jules的任務】: 在此實現 RSI, MACD, BBands 等計算邏輯。
        """
        technicals = {}
        # 範例：計算20日均線
        if 'Close' in ohlcv.columns and len(ohlcv) >= 20:
            technicals['MA20'] = round(ohlcv['Close'].rolling(window=20).mean().iloc[-1], 2)
        else:
            technicals['MA20'] = None

        # TODO: 實現 RSI, MACD, BBands 等指標計算
        technicals['RSI_14D'] = 70 # 暫用假數據
        technicals['RSI_status'] = '超買' # 暫用假數據

        return technicals

    def generate_snapshot(self, ticker: str, as_of_date: str) -> Dict[str, Any]:
        """
        生成指定標的與日期的市場狀態快照。
        """
        print(f"正在為 {ticker} 生成 {as_of_date} 的市場快照...")

        # 1. 獲取基礎行情數據
        ohlcv = self.yf_client.get_history(ticker, period="1y") # 簡化起見，先用一年數據
        if ohlcv.empty:
            return {"error": f"無法獲取 {ticker} 的行情數據。"}

        latest_price = ohlcv['Close'].iloc[-1]

        # 2. 計算技術指標
        technicals_data = self._calculate_technicals(ohlcv)

        # 3. 獲取宏觀數據
        # VIX 指數
        vix_data = self.fred_client.fetch_data('VIXCLS') # 使用正確的方法名 fetch_data
        latest_vix = vix_data['VIXCLS'].iloc[-1] if not vix_data.empty and 'VIXCLS' in vix_data.columns else None # 從 DataFrame 中提取 Series

        # 【升級】直接獲取真實 MOVE 指數，取代代理計算
        # 為了演示，這裡的 start_date 設為固定值，實際應用中可能需要更動態的日期範圍
        move_series = self.yf_client.get_move_index(start_date="2020-01-01", end_date=as_of_date)
        latest_move = move_series.iloc[-1] if not move_series.empty else None

        # 4. 獲取本地期交所數據 (範例)
        # inst_pos = self.taifex_client.get_institutional_positions(start_date=as_of_date, end_date=as_of_date)

        # 5. 組裝快照
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "target": ticker,
            "price_section": {
                "price": latest_price,
            },
            "technicals_section": technicals_data,
            "macro_section": {
                "VIX": latest_vix,
                "MOVE_Index": latest_move, # <--- 使用新指標
            },
            # TODO: 添加期權市場、市場內部結構等部分
        }

        return snapshot
