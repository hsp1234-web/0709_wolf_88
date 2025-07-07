# apps/feature_analyzer/_test_chimera_harness.py
import subprocess
import duckdb
import os
import sys
import pandas as pd
from pathlib import Path
from datetime import date, timedelta

# --- 路徑設定 ---
try:
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent
    DB_PATH = project_root / "analytics_mart.duckdb" # 主分析資料庫
    RUN_PY_PATH = current_dir / "run.py" # feature_analyzer 的 run.py
    # 假設 ohlcv_1d 和 institutional_trades 表格存在於 DB_PATH
    OHLCV_1D_TABLE = "ohlcv_1d"
    INSTITUTIONAL_TRADES_TABLE = "institutional_trades"
    CHIMERA_RESULTS_TABLE = "chimera_daily_signals" # ChimeraAnalyzer 產生的結果表
except Exception as e:
    print(f"路徑設定時發生錯誤: {e}", file=sys.stderr)
    sys.exit(1)

def _prepare_test_db_connection(db_path: Path) -> duckdb.DuckDBPyConnection:
    """建立與測試資料庫的連接，如果檔案已存在則刪除重建。"""
    if db_path.exists():
        db_path.unlink()
        print(f"已刪除舊的測試資料庫: {db_path}")
    con = duckdb.connect(database=str(db_path), read_only=False)
    print(f"已建立並連接到新的測試資料庫: {db_path}")
    return con

def _create_input_tables_and_insert_data(con: duckdb.DuckDBPyConnection):
    """創建輸入表格 (ohlcv_1d, institutional_trades) 並插入測試數據。"""
    try:
        # 1. 創建 ohlcv_1d 表並插入數據
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {OHLCV_1D_TABLE} (
            timestamp TIMESTAMP,
            product_id VARCHAR,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT,
            PRIMARY KEY (timestamp, product_id)
        );""")
        # 準備一些能產生不同價量象限的數據
        # 日期轉換為 datetime.date 物件
        ohlcv_data = [
            # Stock A: 價漲量增 -> 價跌量增 -> 價跌量縮 -> 價漲量縮
            (date(2023, 1, 1), 'STOCK_A', 10.0, 11.0, 9.8, 10.8, 1000), # 基線
            (date(2023, 1, 2), 'STOCK_A', 10.8, 12.0, 10.7, 11.5, 1500), # Q1: 價漲(6.48%) 量增(50%)
            (date(2023, 1, 3), 'STOCK_A', 11.5, 11.6, 10.0, 10.5, 1800), # Q2: 價跌(-8.7%) 量增(20%)
            (date(2023, 1, 4), 'STOCK_A', 10.5, 10.6, 9.5, 9.8, 1200),   # Q3: 價跌(-6.6%) 量縮(-33%)
            (date(2023, 1, 5), 'STOCK_A', 9.8, 10.5, 9.7, 10.2, 1000),  # Q4: 價漲(4.08%) 量縮(-16.6%)
            # Stock B: 只有部分法人數據
            (date(2023, 1, 1), 'STOCK_B', 20.0, 21.0, 19.8, 20.5, 5000), # 基線
            (date(2023, 1, 2), 'STOCK_B', 20.5, 22.0, 20.3, 21.8, 6000), # Q1: 價漲(6.34%) 量增(20%)
        ]
        con.executemany(f"INSERT INTO {OHLCV_1D_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?)", ohlcv_data)
        print(f"已插入測試數據到 {OHLCV_1D_TABLE}")

        # 2. 創建 institutional_trades 表並插入數據
        con.execute(f"""
        CREATE TABLE IF NOT EXISTS {INSTITUTIONAL_TRADES_TABLE} (
            date DATE, stock_id VARCHAR, investor_type VARCHAR,
            buy_shares BIGINT, sell_shares BIGINT, net_shares BIGINT,
            PRIMARY KEY (date, stock_id, investor_type)
        );""")
        institutional_data = [
            # STOCK_A
            (date(2023, 1, 2), 'STOCK_A', 'Foreign_Dealer', 1000, 100, 900), # 總買超 900
            (date(2023, 1, 3), 'STOCK_A', 'Investment_Trust', 50, 850, -800),# 總賣超 -800
            (date(2023, 1, 4), 'STOCK_A', 'Dealer_Self', 200, 200, 0),    # 總中性 0
            # STOCK_A 2023-01-05 無法人數據 -> 籌碼未知
            # STOCK_B
            (date(2023, 1, 1), 'STOCK_B', 'Foreign_Dealer', 500, 0, 500),   # 總買超 500 (配合STOCK_B基線日)
            # STOCK_B 2023-01-02 無法人數據 -> 籌碼未知
        ]
        con.executemany(f"INSERT INTO {INSTITUTIONAL_TRADES_TABLE} VALUES (?, ?, ?, ?, ?, ?)", institutional_data)
        print(f"已插入測試數據到 {INSTITUTIONAL_TRADES_TABLE}")
        con.commit()
    except Exception as e:
        print(f"準備測試數據時發生錯誤: {e}")
        raise

def _run_feature_analyzer_chimera(start_date_str: str, end_date_str: str, stock_ids_list: list[str]):
    """通過 subprocess 調用 apps/feature_analyzer/run.py 執行奇美拉分析。"""
    command = [
        sys.executable, # 使用目前的 python 解釋器
        str(RUN_PY_PATH),
        "--run_chimera_analysis",
        "--analytics_mart_db", str(DB_PATH), # 確保指向測試資料庫
        "--start_date", start_date_str,
        "--end_date", end_date_str,
    ]
    if stock_ids_list:
        command.append("--stock_ids")
        command.extend(stock_ids_list)

    print(f"執行指令: {' '.join(command)}")
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True, cwd=project_root, encoding='utf-8')
        print("feature_analyzer (Chimera) 標準輸出:")
        print(process.stdout)
        if process.stderr:
            print("feature_analyzer (Chimera) 標準錯誤 (如有):")
            print(process.stderr)
    except subprocess.CalledProcessError as e:
        print(f"feature_analyzer (Chimera) 執行失敗，返回碼: {e.returncode}")
        print("標準輸出:")
        print(e.stdout)
        print("標準錯誤:")
        print(e.stderr)
        raise

def _verify_chimera_results(con: duckdb.DuckDBPyConnection, expected_results: list[dict]):
    """驗證 chimera_daily_signals 表格中的數據。"""
    print(f"開始驗證 {CHIMERA_RESULTS_TABLE} 表格...")
    try:
        result_df = con.execute(f"SELECT * FROM {CHIMERA_RESULTS_TABLE} ORDER BY date, stock_id").fetchdf()

        # 將 date 欄位轉換為 datetime.date (如果它是 datetime.datetime)
        if not result_df.empty and isinstance(result_df['date'][0], pd.Timestamp):
             result_df['date'] = result_df['date'].dt.date

        expected_df = pd.DataFrame(expected_results)
        # 對 expected_df 也進行相同的 date 類型轉換
        if not expected_df.empty and 'date' in expected_df.columns:
            expected_df['date'] = pd.to_datetime(expected_df['date']).dt.date


        print(f"\n從資料庫讀取的實際結果 ({len(result_df)} 筆):")
        print(result_df[['date', 'stock_id', 'price_volume_label', 'institutional_flow_label', 'composite_signal', 'total_net_shares']])
        print(f"\n預期結果 ({len(expected_df)} 筆):")
        print(expected_df[['date', 'stock_id', 'price_volume_label', 'institutional_flow_label', 'composite_signal', 'total_net_shares']])

        # 比較時忽略索引，並可能需要處理浮點數精度和 NaN
        # 為了簡化，這裡直接比較選定的欄位，並填充 NaN
        # total_net_shares 可能為 NaN，Pandas 比較時 NaN != NaN，所以需要 fillna
        # 確保比較的欄位順序一致
        cols_to_compare = ['date', 'stock_id', 'price_volume_label', 'institutional_flow_label', 'composite_signal']

        # 處理 total_net_shares 的 NaN 和類型
        result_df['total_net_shares'] = result_df['total_net_shares'].fillna(0).astype(float) # 用0填充NaN以便比較，或選擇其他策略
        expected_df['total_net_shares'] = expected_df['total_net_shares'].fillna(0).astype(float)

        # 如果 price_volume_quadrant 也需要比較，加入到 cols_to_compare
        # result_df['price_volume_quadrant'] = result_df['price_volume_quadrant'].astype(int)
        # expected_df['price_volume_quadrant'] = expected_df['price_volume_quadrant'].astype(int)


        # 進行比較
        pd.testing.assert_frame_equal(
            result_df[cols_to_compare + ['total_net_shares']].sort_values(by=['date', 'stock_id']).reset_index(drop=True),
            expected_df[cols_to_compare + ['total_net_shares']].sort_values(by=['date', 'stock_id']).reset_index(drop=True),
            check_dtype=False, # 稍微放寬類型檢查，因為 DuckDB 和 Pandas 之間可能有細微差異
            check_like=True # 忽略欄位順序，但我們已經手動對齊了
        )
        print(f"\n驗證成功！{CHIMERA_RESULTS_TABLE} 中的數據符合預期。")

    except AssertionError as ae:
        print(f"\n驗證失敗: {ae}")
        raise
    except Exception as e:
        print(f"驗證 {CHIMERA_RESULTS_TABLE} 時發生錯誤: {e}")
        raise

def main():
    print(f"=== 【奇美拉計畫】整合驗收測試 ===")
    print(f"使用資料庫: {DB_PATH}")
    print(f"將執行的 run.py: {RUN_PY_PATH}")

    db_connection = None
    try:
        db_connection = _prepare_test_db_connection(DB_PATH)
        _create_input_tables_and_insert_data(db_connection)

        # 關閉由 harness 維護的連接，以便 subprocess 中的 ChimeraAnalyzer 可以獨占訪問
        db_connection.close()
        db_connection = None
        print("測試腳本的資料庫連接已關閉，準備執行 feature_analyzer。")

        # 定義測試範圍
        test_start_date = "2023-01-01" # 包含基線日，但分析是從第二天開始
        test_end_date = "2023-01-05"
        test_stock_ids = ["STOCK_A", "STOCK_B"]

        _run_feature_analyzer_chimera(test_start_date, test_end_date, test_stock_ids)

        # 重新連接以驗證結果
        db_connection = duckdb.connect(database=str(DB_PATH), read_only=True)
        print("重新連接到資料庫以進行驗證。")

        # 定義預期結果 (注意：價量分析從第二天開始，因為需要前一天的數據計算變化)
        # STOCK_A:
        # 2023-01-02: Q1 (價漲量增), total_net_shares=900 (法人買超) -> 價漲量增_法人買超
        # 2023-01-03: Q2 (價跌量增), total_net_shares=-800 (法人賣超) -> 價跌量增_法人賣超
        # 2023-01-04: Q3 (價跌量縮), total_net_shares=0 (法人中性) -> 價跌量縮_法人中性
        # 2023-01-05: Q4 (價漲量縮), total_net_shares=NaN (籌碼未知) -> 價漲量縮_籌碼未知
        # STOCK_B:
        # 2023-01-02: Q1 (價漲量增), total_net_shares=NaN (籌碼未知) -> 價漲量增_籌碼未知

        # 注意：ChimeraAnalyzer 內部的 pct_change().fillna(0) 會導致第一筆記錄 (2023-01-01) 的 price_change_pct 和 volume_change_pct 為 0。
        # 這使得 2023-01-01 的 price_volume_quadrant 也為 0 (價量平移)。
        # 我們應該只驗證從 2023-01-02 開始的記錄，或者調整預期結果以包含 2023-01-01。
        # 這裡我們假設分析結果是從有變化的第一天開始有意義，即 2023-01-02。
        # ChimeraAnalyzer 的 run_composite_analysis 會處理所有傳入日期的數據，包括第一筆。

        expected_output = [
            {'date': date(2023,1,1), 'stock_id': 'STOCK_A', 'price_volume_label': '價量平移', 'total_net_shares': None,    'institutional_flow_label': '籌碼未知', 'composite_signal': '價量平移_籌碼未知'},
            {'date': date(2023,1,2), 'stock_id': 'STOCK_A', 'price_volume_label': '價漲量增', 'total_net_shares': 900.0,  'institutional_flow_label': '法人買超', 'composite_signal': '價漲量增_法人買超'},
            {'date': date(2023,1,3), 'stock_id': 'STOCK_A', 'price_volume_label': '價跌量增', 'total_net_shares': -800.0, 'institutional_flow_label': '法人賣超', 'composite_signal': '價跌量增_法人賣超'},
            {'date': date(2023,1,4), 'stock_id': 'STOCK_A', 'price_volume_label': '價跌量縮', 'total_net_shares': 0.0,    'institutional_flow_label': '法人中性', 'composite_signal': '價跌量縮_法人中性'},
            {'date': date(2023,1,5), 'stock_id': 'STOCK_A', 'price_volume_label': '價漲量縮', 'total_net_shares': None,    'institutional_flow_label': '籌碼未知', 'composite_signal': '價漲量縮_籌碼未知'},
            {'date': date(2023,1,1), 'stock_id': 'STOCK_B', 'price_volume_label': '價量平移', 'total_net_shares': 500.0,  'institutional_flow_label': '法人買超', 'composite_signal': '價量平移_法人買超'}, # 注意：STOCK_B 1/1 有法人數據
            {'date': date(2023,1,2), 'stock_id': 'STOCK_B', 'price_volume_label': '價漲量增', 'total_net_shares': None,    'institutional_flow_label': '籌碼未知', 'composite_signal': '價漲量增_籌碼未知'},
        ]
        _verify_chimera_results(db_connection, expected_output)

        print(f"\n=== 【奇美拉計畫】整合驗收測試順利完成 ===")

    except Exception as e:
        print(f"\n整合驗收測試過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if db_connection:
            db_connection.close()
            print("測試驗證的資料庫連接已關閉。")
        # 考慮是否在測試結束後刪除測試資料庫 DB_PATH
        # if DB_PATH.exists():
        #     DB_PATH.unlink()
        #     print(f"已清理測試資料庫: {DB_PATH}")

if __name__ == "__main__":
    main()
