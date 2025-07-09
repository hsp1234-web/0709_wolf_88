# 寫入檔案: apps/stress_index_calculator/run.py
import os
import sys
import argparse
import duckdb
import pandas as pd

# --- 路徑自我校正樣板碼 ---
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    apps_dir = os.path.dirname(current_dir)
    project_root = os.path.dirname(apps_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
except Exception as e:
    print(f"專案路徑校正時發生錯誤: {e}", file=sys.stderr)
# --- 路徑自我校正樣板碼結束 ---

# 從本機模組導入計算函式
from apps.stress_index_calculator.calculator import calculate_derived_indicators, calculate_stress_index

# --- 常數定義 ---
SOURCE_DB_PATH = os.path.join(project_root, 'market_data.duckdb')
TARGET_DB_PATH = os.path.join(project_root, 'analytics_mart.duckdb')
STRESS_INDEX_TABLE = 'dealer_stress_index'

def fetch_source_data(db_path: str, use_simulated_data_if_db_missing: bool = True) -> pd.DataFrame:
    """從來源資料庫提取所有需要的數據並合併。
    如果資料庫檔案不存在且 use_simulated_data_if_db_missing 為 True，則返回模擬數據。
    """
    print(f"正在檢查來源數據庫: {db_path}...")

    simulated_data_used = False
    if not os.path.exists(db_path) and use_simulated_data_if_db_missing:
        print(f"警告：來源資料庫 {db_path} 不存在。將使用模擬數據進行測試。")
        simulated_data = {
            'date': pd.to_datetime(['2025-07-01', '2025-07-02', '2025-07-03', '2025-07-04', '2025-07-05']),
            'SOFR': [5.3, 5.31, 5.32, 5.30, 5.31],
            'DGS10': [4.25, 4.26, 4.27, 4.28, 4.27],
            'DGS2': [4.75, 4.76, 4.75, 4.77, 4.76],
            'Total_Gross_Positions_Millions': [600000, 600000, 610000, 605000, 615000],
            'Reserves': [3400, 3400, 3450, 3420, 3460],
            'Volatility_Index': [60, 61, 62, 60, 63], # MOVE
            'VIX': [12, 13, 12.5, 12.8, 13.1]
        }
        df = pd.DataFrame(simulated_data).set_index('date')
        simulated_data_used = True
        print("模擬數據已加載。")
        return df

    if simulated_data_used: # 如果已經用了模擬數據，就不再嘗試讀取DB
        # 理論上，上面的 return df 已經跳出函式了，但為了邏輯清晰
        return df

    print(f"正在從 {db_path} 提取來源數據...")
    try:
        with duckdb.connect(database=db_path, read_only=True) as con:
            # 這裡需要一個更複雜的 SQL 查詢來合併 nyfed_data, fred_data, daily_ohlcv
            # 作為第一步，我們先模擬一個合併後的 DataFrame 結構
            # 實際查詢範例：
            # SELECT d.date, d.close as MOVE, f.value as SOFR ...
            # FROM daily_ohlcv d
            # LEFT JOIN fred_data f ON d.date = f.date AND f.series_id = 'SOFR' ...
            # WHERE d.symbol = '^MOVE'

            # 為了簡化，我們先假設一個已合併的 df
            # 在後續步驟中，我們將構建完整的 SQL 查詢
            # 現階段如果 DB 存在，但我們仍想用模擬數據進行測試，可以取消下面這行的註解
            # print("警告：目前使用模擬數據結構。下一步將實現完整的 SQL 數據提取邏輯。")
            # return pd.DataFrame(simulated_data).set_index('date') # 返回模擬數據

            # TODO: 替換為實際的 SQL 查詢
            print("錯誤：尚未實現從實際資料庫提取數據的 SQL 查詢。請在後續步驟中完成。")
            print("為通過初步測試，暫時返回空的 DataFrame。")
            return pd.DataFrame() # 或者拋出 NotImplementedError

    except Exception as e:
        print(f"提取數據時發生錯誤: {e}")
        return pd.DataFrame()

def save_results(df: pd.DataFrame, db_path: str, table_name: str):
    """將計算結果儲存到目標資料庫"""
    if df.empty:
        print("沒有計算結果可以儲存。")
        return

    print(f"正在將結果儲存至 {db_path} 的 {table_name} 表...")
    try:
        with duckdb.connect(database=db_path, read_only=False) as con:
            con.register('result_df', df.reset_index()) # 儲存時重置索引以包含日期欄位
            con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM result_df")
        print("儲存成功。")
    except Exception as e:
        print(f"儲存結果時發生錯誤: {e}")

def main():
    parser = argparse.ArgumentParser(description="計算交易商壓力指數。")
    # 未來可以添加日期範圍等參數
    parser.add_argument('--run', action='store_true', help="執行計算流程。")
    args = parser.parse_args()

    if not args.run:
        parser.print_help()
        sys.exit(0)

    # 1. 提取數據
    merged_df = fetch_source_data(SOURCE_DB_PATH)
    if merged_df.empty:
        print("無法獲取來源數據，任務中止。")
        return

    # 2. 執行計算
    # 這裡需要一個 config 字典，我們先用一個簡單的範例
    config = {
        'rolling_window_days': 252, # 在模擬數據中，這個值可能過大，導致排名結果為NaN
        'weights': {
            'sofr_dev': 0.2,
            'spread_inv': 0.2,
            'gross_pos': 0.15,
            'move': 0.2,
            'vix': 0.15,
            'pos_res_ratio': 0.1
        },
        'smoothing_window_stress_index': 5, # 同樣，對於少量數據點，平滑可能意義不大
        'threshold_ratio_color': 90, # 用於 Pos/Res Ratio 的條件權重
        'enable_macd_momentum_plot': False # 根據 calculator.py，MACD 相關參數在此層級
    }

    # 由於模擬數據點很少，調整滾動窗口以避免全為 NaN
    # 實際應用中應使用 config 中的值
    if len(merged_df) < 30 : # 如果數據點過少
        print("警告：模擬數據點過少，臨時調整滾動窗口為3天，最小期數為1天，以進行初步測試。")
        config['rolling_window_days'] = 3
        config['smoothing_window_stress_index'] = 1 # 關閉平滑
        # 注意：calculator.py 內部 min_periods_rank = window * 0.6
        # 如果 window = 3, min_periods_rank = 1 (取整)

    df_derived = calculate_derived_indicators(merged_df)
    final_df = calculate_stress_index(df_derived, config)

    # calculate_macd_momentum 是 calculator.py 中的一個獨立函式
    # 但目前的 run.py 結構是直接調用 calculate_stress_index
    # 為了與 calculator.py 中的 calculate_all_indicators 保持一致性，
    # 這裡可以選擇性地調用 calculate_macd_momentum，或者假設 calculate_stress_index 內部處理了
    # 根據提供的 calculator.py，MACD 是獨立的，所以我們也應該獨立調用 (如果需要)
    # 不過，您提供的 run.py 範本沒有調用 MACD，我們暫時遵循此範本。
    # 如果需要 MACD，應從 calculator 導入並調用 calculate_macd_momentum(final_df, config)

    # 3. 儲存結果
    save_results(final_df, TARGET_DB_PATH, STRESS_INDEX_TABLE)

    print("壓力指數計算流程執行完畢。")

if __name__ == "__main__":
    main()
