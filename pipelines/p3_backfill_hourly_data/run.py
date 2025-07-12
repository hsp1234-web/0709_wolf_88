# In pipelines/p3_backfill_hourly_data/run.py
import sys
from pathlib import Path

import pandas as pd

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

def run_backfill(start_date_str, end_date_str):
    from core.analysis.data_engine import DataEngine
    from core.config import config
    """
    執行歷史數據回填管線。

    核心邏輯:
    1. 初始化 DataEngine (它已具備連接 DuckDB 的能力)。
    2. 產生一個包含所有需要回填的小時級時間戳列表。
    3. 遍歷每一個時間戳，呼叫 data_engine.generate_snapshot()。
       - 如果數據已在快取中，此操作將會非常迅速 (Cache Hit)。
       - 如果數據不在快取中，DataEngine 會自動從 API 獲取並寫入快取 (Cache Miss)。
    """
    print(f"--- 開始執行數據回填作業：從 {start_date_str} 到 {end_date_str} ---")

    # 步驟 1: 初始化
    from core.clients.fred import FredClient
    from core.clients.taifex_db import TaifexDBClient
    from core.clients.yfinance import YFinanceClient

    yf_client = YFinanceClient()
    fred_client = FredClient(api_key=config.get("api_keys.fred"))
    taifex_client = TaifexDBClient()
    data_engine = DataEngine(
        yf_client=yf_client, fred_client=fred_client, taifex_client=taifex_client
    )

    # 步驟 2: 產生時間戳
    hourly_timestamps = pd.date_range(start=start_date_str, end=end_date_str, freq="H")

    # 步驟 3: 遍歷並觸發 DataEngine
    total_tasks = len(hourly_timestamps)
    for i, ts in enumerate(hourly_timestamps):
        print(f"--- 正在處理 ({i + 1}/{total_tasks}): {ts} ---")
        try:
            # 這一步是核心：無論數據是否存在，DataEngine 都會處理
            data_engine.generate_snapshot(ts)
        except Exception as e:
            print(f"❌ 處理 {ts} 時發生錯誤: {e}")

    # 關閉資源
    data_engine.close()
    print("--- 數據回填作業完成 ---")


if __name__ == "__main__":
    # 範例：回填過去三天的數據
    # 實際使用時，可以透過 argparse 等方式傳入參數
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.Timedelta(days=3)
    run_backfill(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
