# 主執行入口: 時間序列聚合器
import os
import sys

# --- 路徑自我校正 ---
# 確保腳本無論從何處執行，都能正確找到專案根目錄並將其添加到 sys.path
current_script_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_script_path)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pandas as pd
import datetime
from apps.time_aggregator.core.aggregator import TimeAggregator

# --- 核心邏輯 ---
def main():
    """
    主函式，執行時間序列聚合流程。
    """
    print("[INFO] Time Aggregator 服務啟動...")
    db_path = "market_data.duckdb"  # 實際應用中可能來自配置
    silver_table_name = "silver_market_ohlcv_1m" # 銀層表名

    # 清理舊的測試數據庫文件 (如果存在)，以便每次運行都是乾淨的狀態
    # 這主要用於本地測試，實際部署時可能不需要
    # 確保只在 __main__ 執行時清理，避免測試時意外刪除
    if __name__ == "__main__":
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"[DEBUG] 已刪除舊的數據庫文件: {db_path}")
        if os.path.exists(f"{db_path}.wal"):
            os.remove(f"{db_path}.wal")
            print(f"[DEBUG] 已刪除舊的 WAL 文件: {db_path}.wal")

    try:
        with TimeAggregator(db_path=db_path) as aggregator:

            # 1. 模擬數據依賴：創建一個包含多筆秒級假數據的 Pandas DataFrame
            #    (模擬從 read_bronze_ticks 讀取到的內容)
            print("[INFO] 步驟 1: 正在創建模擬的秒級 Tick DataFrame...")
            simulated_start_time = datetime.datetime(2023, 11, 1, 9, 0, 0)
            mock_ticks_list = []
            # 標的 A
            mock_ticks_list.extend([
                {'timestamp': simulated_start_time + datetime.timedelta(seconds=5), 'price': 100.0, 'volume': 10, 'instrument': 'INSTRUMENT_A'},
                {'timestamp': simulated_start_time + datetime.timedelta(seconds=15), 'price': 101.0, 'volume': 5, 'instrument': 'INSTRUMENT_A'},
                {'timestamp': simulated_start_time + datetime.timedelta(seconds=30), 'price': 99.0, 'volume': 8, 'instrument': 'INSTRUMENT_A'},
                {'timestamp': simulated_start_time + datetime.timedelta(seconds=50), 'price': 100.5, 'volume': 12, 'instrument': 'INSTRUMENT_A'}, # Min 1 for A
                {'timestamp': simulated_start_time + datetime.timedelta(minutes=1, seconds=10), 'price': 102.0, 'volume': 7, 'instrument': 'INSTRUMENT_A'}, # Min 2 for A
            ])
            # 標的 B
            mock_ticks_list.extend([
                {'timestamp': simulated_start_time + datetime.timedelta(seconds=10), 'price': 2000.0, 'volume': 20, 'instrument': 'INSTRUMENT_B'},
                {'timestamp': simulated_start_time + datetime.timedelta(seconds=40), 'price': 1995.0, 'volume': 15, 'instrument': 'INSTRUMENT_B'}, # Min 1 for B
            ])

            simulated_ticks_df = pd.DataFrame(mock_ticks_list)
            # 確保 'timestamp' 欄位是 datetime 類型
            simulated_ticks_df['timestamp'] = pd.to_datetime(simulated_ticks_df['timestamp'])
            print(f"[INFO] 成功創建 {len(simulated_ticks_df)} 筆模擬 Tick 數據。")
            # print("[DEBUG] 模擬 Tick DataFrame 預覽:")
            # print(simulated_ticks_df.head())

            # 2. 調用 aggregate_to_1m_ohlcv 處理這個假數據 DataFrame
            print(f"\n[INFO] 步驟 2: 正在將 Tick 數據聚合為 1 分鐘 OHLCV...")
            aggregated_ohlcv_df = aggregator.aggregate_to_1m_ohlcv(simulated_ticks_df.copy()) # 傳遞副本以防意外修改

            if aggregated_ohlcv_df.empty:
                print("[WARN] 聚合結果為空，可能沒有有效的 Tick 數據進行聚合。")
            else:
                print(f"[INFO] 成功聚合為 {len(aggregated_ohlcv_df)} 筆 1 分鐘 OHLCV 數據。")
                # print("[DEBUG] 聚合 OHLCV DataFrame 預覽:")
                # print(aggregated_ohlcv_df)

            # 3. 調用 write_silver_ohlcv 將聚合結果寫入數據庫
            if not aggregated_ohlcv_df.empty:
                print(f"\n[INFO] 步驟 3: 正在將聚合後的 OHLCV 數據寫入銀層資料表 '{silver_table_name}'...")
                aggregator.write_silver_ohlcv(aggregated_ohlcv_df, silver_table_name=silver_table_name)
                print(f"[INFO] 數據已成功存入銀層資料表 '{silver_table_name}'。")

                # (可選) 驗證寫入
                # conn_check = duckdb.connect(database=db_path, read_only=True)
                # count_after_write = conn_check.execute(f"SELECT COUNT(*) FROM {silver_table_name}").fetchone()[0]
                # print(f"[DEBUG] 銀層資料表 '{silver_table_name}' 目前包含 {count_after_write} 筆記錄。")
                # conn_check.close()
            else:
                print("[INFO] 步驟 3: 聚合結果為空，無需寫入銀層。")

        print("\n[SUCCESS] Time Aggregator 服務執行完畢。")

    except Exception as e:
        print(f"[ERROR] Time Aggregator 執行過程中發生錯誤: {e}")
        # 在實際應用中，這裡可能需要更複雜的錯誤處理機制

if __name__ == "__main__":
    main()
