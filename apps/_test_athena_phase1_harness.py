# apps/_test_athena_phase1_harness.py

import subprocess
import sys
import os
import shutil
from pathlib import Path
import duckdb
import pandas as pd
import random

# --- 路徑自我校正樣板碼 START ---
# 取得目前腳本的絕對路徑
current_script_path = Path(__file__).resolve()
# 假設此腳本位於 apps 目錄下，專案根目錄是其再上一層
project_root = current_script_path.parent.parent
# 將專案根目錄加入 sys.path，以便導入 apps 目錄下的模組
sys.path.insert(0, str(project_root))
# --- 路徑自我校正樣板碼 END ---

# 設定微服務的路徑 (相對於 project_root)
TIME_AGGREGATOR_RUN_PY = project_root / "apps" / "time_aggregator" / "run.py"
FEATURE_ANALYZER_RUN_PY = project_root / "apps" / "feature_analyzer" / "run.py"

# 設定測試用的資料庫路徑 (將在測試開始時刪除並重建)
TEST_DATA_DIR = project_root / "data_test_harness" # 使用獨立的測試數據目錄
ANALYTICS_DB_NAME = "analytics_mart.duckdb"
SOURCE_DB_NAME = "taifex_historical_sample.duckdb" # 測試用的樣本源數據庫
ANALYTICS_DB_PATH = TEST_DATA_DIR / ANALYTICS_DB_NAME
SOURCE_DB_PATH = TEST_DATA_DIR / SOURCE_DB_NAME

# 測試參數
TEST_PRODUCT_ID = "MXF1_TEST"
TEST_START_DATE = "2023-01-01"
TEST_END_DATE = "2023-01-03" # 聚合器處理到此日期之前，即 2023-01-01 和 2023-01-02

# 與 time_aggregator 中定義的時間週期保持一致
TIME_PERIODS_FOR_TEST = ["1min", "5min", "15min", "1h", "4h", "1d"]


def create_sample_source_db():
    """創建一個包含少量測試數據的 DuckDB 檔案"""
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SOURCE_DB_PATH.exists():
        SOURCE_DB_PATH.unlink()

    with duckdb.connect(database=str(SOURCE_DB_PATH), read_only=False) as con:
        con.execute("""
            CREATE TABLE ticks (
                timestamp TIMESTAMP,
                product_id VARCHAR,
                price DOUBLE,
                qty BIGINT
            );
        """)
        # 插入一些跨越幾分鐘、幾小時和幾天的數據
        sample_data = [
            # Day 1: 2023-01-01
            (f'{TEST_START_DATE} 08:45:00', TEST_PRODUCT_ID, 14000.0, 10),
            (f'{TEST_START_DATE} 08:45:30', TEST_PRODUCT_ID, 14001.0, 5), # 1min
            (f'{TEST_START_DATE} 08:46:00', TEST_PRODUCT_ID, 14000.5, 8),
            (f'{TEST_START_DATE} 08:50:00', TEST_PRODUCT_ID, 14002.0, 12), # 5min
            (f'{TEST_START_DATE} 09:00:00', TEST_PRODUCT_ID, 14010.0, 20), # 15min
            (f'{TEST_START_DATE} 09:05:00', TEST_PRODUCT_ID, 14011.0, 15),
            (f'{TEST_START_DATE} 09:16:00', TEST_PRODUCT_ID, 14020.0, 20),
            (f'{TEST_START_DATE} 10:00:00', TEST_PRODUCT_ID, 14050.0, 30), # 1h
            (f'{TEST_START_DATE} 10:30:00', TEST_PRODUCT_ID, 14055.0, 25),
            (f'{TEST_START_DATE} 11:00:00', TEST_PRODUCT_ID, 14060.0, 10),
            (f'{TEST_START_DATE} 13:00:00', TEST_PRODUCT_ID, 14000.0, 50), # 4h
            (f'{TEST_START_DATE} 13:30:00', TEST_PRODUCT_ID, 14005.0, 10),
            # Day 2: 2023-01-02
            (f'2023-01-02 08:45:00', TEST_PRODUCT_ID, 14100.0, 10), # 1d
            (f'2023-01-02 08:47:00', TEST_PRODUCT_ID, 14105.0, 15),
            (f'2023-01-02 09:20:00', TEST_PRODUCT_ID, 14120.0, 22),
            (f'2023-01-02 11:50:00', TEST_PRODUCT_ID, 14150.0, 33),
            (f'2023-01-02 13:15:00', TEST_PRODUCT_ID, 14130.0, 28),
        ]
        for row in sample_data:
            con.execute("INSERT INTO ticks VALUES (?, ?, ?, ?)", row)
        print(f"測試用的來源資料庫 {SOURCE_DB_PATH} 已創建並填充數據。")

def run_script(script_path: Path, args: list) -> subprocess.CompletedProcess:
    """執行指定的 Python 腳本並返回結果"""
    cmd = [sys.executable, str(script_path)] + args
    print(f"\n[執行中] {' '.join(cmd)}")
    # 將 PYTHONPATH 設置為包含專案根目錄，以確保子進程可以找到模組
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")

    process = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    if process.returncode != 0:
        print(f"腳本執行失敗，返回碼: {process.returncode}")
        print("標準輸出:")
        print(process.stdout)
        print("標準錯誤:")
        print(process.stderr)
        process.check_returncode() # 如果失敗則拋出例外
    else:
        print("腳本執行成功。")
        # print("標準輸出:") # 可選：通常成功時不需要完整輸出
        # print(process.stdout)
    return process

def manual_calculate_quadrant(price_change_pct: float, volume_change_pct: float) -> int:
    """手動計算象限的邏輯 (與 feature_analyzer 中的一致)"""
    if price_change_pct > 0 and volume_change_pct > 0: return 1
    elif price_change_pct < 0 and volume_change_pct > 0: return 2
    elif price_change_pct < 0 and volume_change_pct < 0: return 3
    elif price_change_pct > 0 and volume_change_pct < 0: return 4
    elif price_change_pct == 0 or volume_change_pct == 0:
        if price_change_pct > 0: return 1
        if price_change_pct < 0: return 2
        if volume_change_pct > 0: return 1
        if volume_change_pct < 0: return 3
    return 0

def main():
    print("=====【雅典娜計畫 - 第一階段】強制整合驗收測試開始 =====")

    # 1. 清理與準備
    print("\n--- 1. 清理與準備 ---")
    if TEST_DATA_DIR.exists():
        print(f"正在刪除舊的測試數據目錄: {TEST_DATA_DIR}")
        shutil.rmtree(TEST_DATA_DIR)
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"已創建空的測試數據目錄: {TEST_DATA_DIR}")
    assert not ANALYTICS_DB_PATH.exists(), f"測試開始前 {ANALYTICS_DB_NAME} 不應存在。"

    create_sample_source_db() # 創建測試用的源數據庫

    # 2. 觸發聚合器
    print("\n--- 2. 觸發時間序列聚合器 (time_aggregator) ---")
    aggregator_args = [
        TEST_PRODUCT_ID,
        TEST_START_DATE,
        TEST_END_DATE,
        "--source_db", str(SOURCE_DB_PATH),
        "--analytics_db", str(ANALYTICS_DB_PATH)
    ]
    run_script(TIME_AGGREGATOR_RUN_PY, aggregator_args)

    # 3. 驗證聚合結果
    print("\n--- 3. 驗證聚合結果 ---")
    assert ANALYTICS_DB_PATH.exists(), f"{ANALYTICS_DB_NAME} 未被創建。"
    print(f"分析資料庫 {ANALYTICS_DB_NAME} 已成功創建。")

    with duckdb.connect(database=str(ANALYTICS_DB_PATH), read_only=True) as con:
        for period in TIME_PERIODS_FOR_TEST:
            table_name = f"ohlcv_{period}"
            print(f"驗證資料表: {table_name}")
            try:
                df = con.execute(f"SELECT * FROM {table_name} WHERE product_id = '{TEST_PRODUCT_ID}'").fetchdf()
            except duckdb.CatalogException:
                assert False, f"資料表 {table_name} 未在 {ANALYTICS_DB_NAME} 中創建。"

            assert not df.empty, f"資料表 {table_name} 為空。"
            print(f"資料表 {table_name} 包含 {len(df)} 行數據。")

            # 簡單檢查 OHLCV 值是否合理 (例如 Open, High, Low, Close > 0, Volume >= 0)
            assert (df['open'] > 0).all(), f"{table_name}: open 值不合理"
            assert (df['high'] > 0).all(), f"{table_name}: high 值不合理"
            assert (df['low'] > 0).all(), f"{table_name}: low 值不合理"
            assert (df['close'] > 0).all(), f"{table_name}: close 值不合理"
            assert (df['volume'] >= 0).all(), f"{table_name}: volume 值不合理"
            assert (df['high'] >= df['open']).all(), f"{table_name}: high 應 >= open"
            assert (df['high'] >= df['low']).all(), f"{table_name}: high 應 >= low"
            assert (df['high'] >= df['close']).all(), f"{table_name}: high 應 >= close"
            assert (df['low'] <= df['open']).all(), f"{table_name}: low 應 <= open"
            assert (df['low'] <= df['close']).all(), f"{table_name}: low 應 <= close"
            print(f"資料表 {table_name} 的 OHLCV 值在合理範圍內。")

    # 4. 觸發分析儀
    print("\n--- 4. 觸發特徵分析儀 (feature_analyzer) ---")
    analyzer_args = ["--analytics_db", str(ANALYTICS_DB_PATH)]
    run_script(FEATURE_ANALYZER_RUN_PY, analyzer_args)

    # 5. 驗證分析結果
    print("\n--- 5. 驗證分析結果 ---")
    with duckdb.connect(database=str(ANALYTICS_DB_PATH), read_only=True) as con:
        for period in TIME_PERIODS_FOR_TEST:
            ohlcv_table_name = f"ohlcv_{period}"
            quadrant_table_name = f"quadrant_analysis_{period}"
            print(f"驗證資料表: {quadrant_table_name} (基於 {ohlcv_table_name})")

            try:
                ohlcv_df = con.execute(f"SELECT * FROM {ohlcv_table_name} WHERE product_id = '{TEST_PRODUCT_ID}' ORDER BY timestamp").fetchdf()
                quadrant_df = con.execute(f"SELECT * FROM {quadrant_table_name} WHERE product_id = '{TEST_PRODUCT_ID}' ORDER BY timestamp").fetchdf()
            except duckdb.CatalogException as e:
                assert False, f"讀取資料表 {ohlcv_table_name} 或 {quadrant_table_name} 失敗: {e}"

            assert not ohlcv_df.empty, f"用於驗證的來源資料表 {ohlcv_table_name} 為空。"
            assert not quadrant_df.empty, f"分析結果資料表 {quadrant_table_name} 為空。"

            # 行數應該一致 (除了第一個K棒，因為它沒有前期數據可以比較，但 feature_analyzer 內部已處理)
            # feature_analyzer 對於第一個K棒會產生 price_change_pct=0, volume_change_pct=0，並賦予一個象限
            assert len(ohlcv_df) == len(quadrant_df), \
                f"{quadrant_table_name} 的行數 ({len(quadrant_df)}) 與 {ohlcv_table_name} ({len(ohlcv_df)}) 不一致。"
            print(f"資料表 {quadrant_table_name} 的行數 ({len(quadrant_df)}) 與輸入一致。")

            # 隨機抽樣幾筆結果進行手動計算驗證
            # 至少需要兩筆數據才能計算變化
            if len(quadrant_df) > 1:
                # 排除第一行，因為它的變化百分比通常是0 (除非 feature_analyzer 有特殊處理)
                # 我們的 feature_analyzer 計算變化時，第一筆的 price_change_pct 和 volume_change_pct 都是 0
                # 因此 quadrant 也會基於此計算。
                sample_indices = random.sample(range(len(quadrant_df)), min(3, len(quadrant_df)))

                for i in sample_indices:
                    # 獲取 ohlcv_df 中對應的當前和前一筆數據 (如果存在)
                    current_ohlcv = ohlcv_df.iloc[i]

                    # 從 quadrant_df 中獲取由 feature_analyzer 計算出的結果
                    analyzed_quadrant_row = quadrant_df.iloc[i]
                    analyzed_price_change_pct = analyzed_quadrant_row['price_change_pct']
                    analyzed_volume_change_pct = analyzed_quadrant_row['volume_change_pct']
                    analyzed_quadrant = analyzed_quadrant_row['quadrant']

                    # 手動計算 price_change_pct 和 volume_change_pct
                    manual_price_change_pct = 0.0
                    manual_volume_change_pct = 0.0

                    if i > 0: # 只有非第一筆數據才有前期數據
                        prev_ohlcv = ohlcv_df.iloc[i-1]
                        if prev_ohlcv['close'] != 0: # 避免除以零
                            manual_price_change_pct = (current_ohlcv['close'] - prev_ohlcv['close']) / prev_ohlcv['close'] * 100

                        if prev_ohlcv['volume'] == 0 and current_ohlcv['volume'] > 0:
                            manual_volume_change_pct = 100.0
                        elif prev_ohlcv['volume'] == 0 and current_ohlcv['volume'] == 0:
                            manual_volume_change_pct = 0.0
                        elif prev_ohlcv['volume'] > 0 : # 避免除以零
                            manual_volume_change_pct = (current_ohlcv['volume'] - prev_ohlcv['volume']) / prev_ohlcv['volume'] * 100
                        else: # prev_ohlcv['volume'] < 0 (不應該發生) or other unhandled
                             manual_volume_change_pct = 0.0 # 或其他錯誤標記

                    # 驗證 feature_analyzer 計算的百分比是否與手動計算的接近 (允許小的浮點誤差)
                    np.testing.assert_allclose(analyzed_price_change_pct, manual_price_change_pct, rtol=1e-5, atol=1e-5,
                                               err_msg=f"[{quadrant_table_name} row {i}] Price change % 不符")
                    np.testing.assert_allclose(analyzed_volume_change_pct, manual_volume_change_pct, rtol=1e-5, atol=1e-5,
                                               err_msg=f"[{quadrant_table_name} row {i}] Volume change % 不符")

                    # 手動計算象限
                    expected_quadrant = manual_calculate_quadrant(analyzed_price_change_pct, analyzed_volume_change_pct)

                    assert analyzed_quadrant == expected_quadrant, \
                        f"[{quadrant_table_name} row {i}] 象限分類不正確。Timestamp: {current_ohlcv['timestamp']}, " \
                        f"P%: {analyzed_price_change_pct:.2f} (calc) vs {manual_price_change_pct:.2f} (manual), " \
                        f"V%: {analyzed_volume_change_pct:.2f} (calc) vs {manual_volume_change_pct:.2f} (manual), " \
                        f"預期象限: {expected_quadrant}, 實際象限: {analyzed_quadrant}"
                print(f"資料表 {quadrant_table_name} 的抽樣數據象限分類已通過手動計算驗證。")
            elif len(quadrant_df) == 1:
                 # 如果只有一筆數據，驗證其百分比變化是否為0，象限是否符合預期
                analyzed_quadrant_row = quadrant_df.iloc[0]
                assert analyzed_quadrant_row['price_change_pct'] == 0, f"[{quadrant_table_name} row 0] Price change % 應為 0"
                assert analyzed_quadrant_row['volume_change_pct'] == 0, f"[{quadrant_table_name} row 0] Volume change % 應為 0"
                expected_quadrant_for_first_row = manual_calculate_quadrant(0,0) # 應該是 0
                assert analyzed_quadrant_row['quadrant'] == expected_quadrant_for_first_row, f"[{quadrant_table_name} row 0] 象限分類不正確"
                print(f"資料表 {quadrant_table_name} 只有一行數據，已驗證其初始狀態。")
            else:
                print(f"資料表 {quadrant_table_name} 為空或只有一行，跳過抽樣驗證。")


    print("\n=====【雅典娜計畫 - 第一階段】強制整合驗收測試成功！ =====")
    print("\n測試日誌:")
    # 這裡可以捕獲上面所有的 print 輸出作為日誌。
    # 在實際執行中，可以重定向 stdout 到一個檔案，或者在 run_script 中收集輸出。
    # 為了簡化，這裡只打印一條成功訊息。
    # 最終交付時，我會提供實際執行此腳本時產生的完整控制台輸出。
    print("所有測試步驟已通過。")

if __name__ == "__main__":
    # 為了讓 pd.testing.assert_approx_equal 能運作
    import numpy as np
    main()
