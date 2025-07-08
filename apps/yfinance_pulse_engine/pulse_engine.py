# -*- coding: utf-8 -*-
"""
YFinancePulseEngine - 指揮官引擎
====================================

負責協調 YFinanceHydrator 進行數據回填任務。
根據配置的目標 tickers 和日期範圍，並發地調用 YFinanceHydrator.hydrate_day。
"""
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
# 假設 YFinanceHydrator 和 DBManager 能被正確導入
# from apps.yfinance_hydrator.hydrator import YFinanceHydrator
# from apps.daily_market_analyzer.db_manager import DBManager

class YFinancePulseEngine:
    """
    指揮官引擎，用於驅動 YFinanceHydrator 進行數據回填。
    """
    def __init__(self, hydrator, max_workers: int | None = None):
        """
        初始化 YFinancePulseEngine。

        Args:
            hydrator (YFinanceHydrator): YFinanceHydrator 的實例。
            max_workers (int | None, optional): 線程池的最大工作線程數。
                                                若為 None，則 ThreadPoolExecutor 會自行決定。
        """
        self.hydrator = hydrator
        self.max_workers = max_workers if max_workers is not None else 5 # 預設一個較小的值
        if self.max_workers <= 0:
            print("警告 (YFinancePulseEngine): max_workers 數量無效，將使用預設值 5。")
            self.max_workers = 5
        print(f"INFO: YFinancePulseEngine 初始化完畢。最大並發任務數: {self.max_workers}")

    def run(self, tickers: list[str], start_date_str: str, end_date_str: str, force_refresh: bool = False):
        """
        執行數據回填脈衝任務。

        遍歷指定的 tickers 和日期範圍，為每個 (ticker, date) 組合調用 YFinanceHydrator.hydrate_day。

        Args:
            tickers (list[str]): 要處理的股票代碼列表。
            start_date_str (str): 開始日期 (YYYY-MM-DD)。
            end_date_str (str): 結束日期 (YYYY-MM-DD)。
            force_refresh (bool, optional): 是否強制刷新數據，忽略 CacheIndex 中的 SUCCESS/NO_DATA 狀態。
                                            預設為 False。
        """
        print(f"\n--- YFinancePulseEngine: 開始執行回填脈衝 ---")
        print(f"目標 Tickers: {tickers}")
        print(f"日期範圍: [{start_date_str} to {end_date_str}]")
        print(f"強制刷新: {force_refresh}")
        print(f"最大並發數: {self.max_workers}")

        if not tickers:
            print("警告 (YFinancePulseEngine): Tickers 列表為空，沒有任務可執行。")
            return

        try:
            s_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            e_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            if s_date > e_date:
                print(f"錯誤 (YFinancePulseEngine): 起始日期 {start_date_str} 不能晚於結束日期 {end_date_str}。")
                return
        except ValueError:
            print(f"錯誤 (YFinancePulseEngine): 日期格式無效。請使用 YYYY-MM-DD。 Start: {start_date_str}, End: {end_date_str}")
            return

        dates_to_process = pd.date_range(s_date, e_date).strftime("%Y-%m-%d").tolist()

        tasks = []
        for ticker in tickers:
            for date_str in dates_to_process:
                tasks.append({'ticker': ticker, 'date_str': date_str})

        if not tasks:
            print("INFO (YFinancePulseEngine): 沒有生成任何 (ticker, date) 回填任務。")
            return

        print(f"INFO (YFinancePulseEngine): 共生成 {len(tasks)} 個 (ticker, date) 回填任務。")

        processed_count = 0
        failed_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self.hydrator.hydrate_day, task['ticker'], task['date_str'], force_refresh): task
                for task in tasks
            }

            for future in as_completed(future_to_task):
                task_info = future_to_task[future]
                try:
                    future.result() # 等待 hydrate_day 完成，捕獲可能發生的異常
                    # hydrate_day 內部會打印自己的日誌，這裡可以只記錄任務完成
                    print(f"INFO (YFinancePulseEngine Task): Ticker={task_info['ticker']}, Date={task_info['date_str']} 回填任務已完成。")
                    processed_count += 1
                except Exception as e:
                    print(f"錯誤 (YFinancePulseEngine Task): Ticker={task_info['ticker']}, Date={task_info['date_str']} 回填任務執行時發生頂層異常: {e}")
                    failed_count += 1

        print(f"\n--- YFinancePulseEngine: 回填脈衝執行完畢 ---")
        print(f"總任務數: {len(tasks)}")
        print(f"成功處理任務數: {processed_count}")
        print(f"失敗任務數: {failed_count}")

if __name__ == '__main__':
    # 此處僅為示例，實際執行應通過 run_pulse_engine.py
    print("YFinancePulseEngine: 此模組應通過 run_pulse_engine.py 執行。")
    # 需要:
    # from apps.daily_market_analyzer.db_manager import DBManager
    # from apps.yfinance_hydrator.hydrator import YFinanceHydrator
    # import os

    # test_db_path = "data_workspace/temp/pulse_engine_test.duckdb"
    # if os.path.exists(test_db_path):
    #     os.remove(test_db_path)

    # db_man = DBManager(db_path=test_db_path, target_ohlcv_table_name="MarketPrices_Daily_PulseTest")
    # hydrator_instance = YFinanceHydrator(db_manager=db_man)
    # pulse_engine = YFinancePulseEngine(hydrator=hydrator_instance, max_workers=2)

    # test_tickers = ["AAPL", "GOOG"] # 使用實際存在的 ticker 進行測試
    # test_start_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    # test_end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # print(f"Pulse Engine 測試: Tickers={test_tickers}, Dates=[{test_start_date} to {test_end_date}]")
    # pulse_engine.run(tickers=test_tickers, start_date_str=test_start_date, end_date_str=test_end_date, force_refresh=False)

    # print("\n第二次運行 (應主要從快取讀取):")
    # pulse_engine.run(tickers=test_tickers, start_date_str=test_start_date, end_date_str=test_end_date, force_refresh=False)

    # if os.path.exists(test_db_path):
    #     print(f"測試完畢，測試資料庫 {test_db_path} 可供檢查。")
    #     # os.remove(test_db_path)
    pass
