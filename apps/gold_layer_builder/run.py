# --- 路徑自我校正 (必須在所有 import 之前) ---
import sys
import os
current_script_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_script_path)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --- 以上為路徑校正 ---
import datetime
import numpy as np
import pandas as pd
from apps.gold_layer_builder.core.builder import GoldLayerBuilder

# 主執行入口: 金層決策引擎

# --- 核心邏輯 ---
def main():
    """
    主函式，執行金層數據生成流程。
    """
    print("[INFO] Gold Layer Builder 服務啟動...")
    db_path = "market_data.duckdb"  # 實際應用中可能來自配置
    gold_ohlcv_table = "gold_market_ohlcv_daily"
    gold_features_table = "gold_market_features_daily"

    # 清理舊的測試數據庫文件 (如果存在)，以便每次運行都是乾淨的狀態
    if __name__ == "__main__":
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"[DEBUG] 已刪除舊的數據庫文件: {db_path}")
        if os.path.exists(f"{db_path}.wal"):
            os.remove(f"{db_path}.wal")
            print(f"[DEBUG] 已刪除舊的 WAL 文件: {db_path}.wal")

    try:
        with GoldLayerBuilder(db_path=db_path) as builder:

            # 1. 模擬數據依賴：創建一個包含多日分鐘級假數據的 Pandas DataFrame
            #    (模擬從銀層 silver_market_ohlcv_1m 讀取到的內容)
            print("\n[INFO] 步驟 1: 正在創建模擬的銀層分鐘級 OHLCV DataFrame...")
            num_days_sim = 25  # 模擬約一個月的數據以便計算 MA20
            base_start_datetime = datetime.datetime(2023, 1, 1, 9, 0, 0)
            all_silver_ticks = []
            instruments = ["INSTR_X", "INSTR_Y"]

            for day_offset in range(num_days_sim):
                current_date_base = base_start_datetime + datetime.timedelta(
                    days=day_offset
                )
                for instrument in instruments:
                    # 每天模擬幾條分鐘線數據
                    price_seed = (
                        100 + day_offset * 0.5 + (5 if instrument == "INSTR_Y" else 0)
                    )  # 不同的基價和趨勢
                    for min_offset in range(0, 60 * 3, 15):  # 模擬三小時的15分鐘線
                        ts = current_date_base + datetime.timedelta(minutes=min_offset)
                        o = price_seed + np.random.uniform(-0.5, 0.5)
                        h = o + np.random.uniform(0, 0.3)
                        low_val = o - np.random.uniform(0, 0.3) # Renamed l to low_val
                        c = low_val + np.random.uniform(0, h - low_val)  # 確保 c 在 l 和 h 之間
                        v = np.random.randint(50, 200)
                        all_silver_ticks.append(
                            {
                                "timestamp": ts,
                                "instrument": instrument,
                                "open": o,
                                "high": h,
                                "low": low_val,
                                "close": c,
                                "volume": v,
                            }
                        )

            simulated_silver_df = pd.DataFrame(all_silver_ticks)
            simulated_silver_df["timestamp"] = pd.to_datetime(
                simulated_silver_df["timestamp"]
            )
            print(
                f"[INFO] 成功創建 {len(simulated_silver_df)} 筆模擬銀層分鐘數據 (涵蓋 {num_days_sim} 天, {len(instruments)} 個標的)。"
            )
            # print("[DEBUG] 模擬銀層 DataFrame (部分):")
            # print(simulated_silver_df.sample(5))

            # 2. 調用 aggregate_to_daily_ohlcv
            print("\n[INFO] 步驟 2: 正在將分鐘數據聚合為日線 OHLCV...")
            daily_ohlcv_df = builder.aggregate_to_daily_ohlcv(
                simulated_silver_df.copy()
            )
            if daily_ohlcv_df.empty:
                print("[WARN] 日線聚合結果為空。")
                return  # 後續步驟依賴此結果
            print(f"[INFO] 成功聚合得到 {len(daily_ohlcv_df)} 筆日線 OHLCV 數據。")
            # print("[DEBUG] 日線 OHLCV DataFrame (部分):")
            # print(daily_ohlcv_df.sample(min(5, len(daily_ohlcv_df))))

            # 3. 調用 calculate_features
            print("\n[INFO] 步驟 3: 正在計算日線技術特徵...")
            features_inclusive_df = builder.calculate_features(daily_ohlcv_df.copy())
            if features_inclusive_df.empty:  # 應該不會發生，因為 daily_ohlcv_df 非空
                print("[WARN] 特徵計算結果為空。")
                return
            print(
                f"[INFO] 成功計算技術特徵，最終 DataFrame 包含 {len(features_inclusive_df)} 筆記錄。"
            )
            # print("[DEBUG] 包含特徵的 DataFrame (部分, INSTR_X):")
            # print(features_inclusive_df[features_inclusive_df['instrument'] == 'INSTR_X'].tail())

            # 4. 調用 write_gold_tables
            print("\n[INFO] 步驟 4: 正在將日線 OHLCV 和特徵數據寫入金層資料表...")
            builder.write_gold_tables(
                features_inclusive_df,
                ohlcv_table_name=gold_ohlcv_table,
                features_table_name=gold_features_table,
            )
            print(
                f"[INFO] 數據已成功存入金層資料表: '{gold_ohlcv_table}' 和 '{gold_features_table}'。"
            )

            # (可選) 驗證寫入
            # conn_check = duckdb.connect(database=db_path, read_only=True)
            # count_ohlcv = conn_check.execute(f"SELECT COUNT(*) FROM {gold_ohlcv_table}").fetchone()[0]
            # count_features = conn_check.execute(f"SELECT COUNT(*) FROM {gold_features_table}").fetchone()[0]
            # print(f"[DEBUG] 金層 OHLCV 表 '{gold_ohlcv_table}' 目前包含 {count_ohlcv} 筆記錄。")
            # print(f"[DEBUG] 金層特徵表 '{gold_features_table}' 目前包含 {count_features} 筆記錄。")
            # conn_check.close()

        print(
            "\n[SUCCESS] Gold Layer Builder 服務執行完畢。 【蒼穹之眼】數據架構已成功建立！"
        )

    except Exception as e:
        print(f"[ERROR] Gold Layer Builder 執行過程中發生錯誤: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
