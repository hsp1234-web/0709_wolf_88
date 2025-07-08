# tests/test_data_population.py
"""
此腳本用於將 mock_data_utils.py 生成的模擬數據填充到測試用的 DuckDB 資料庫中。
主要用於第一階段模擬演練的數據準備。
"""
import duckdb
import pandas as pd
from pathlib import Path

# --- 標準化「路徑自我校正」樣板碼 START ---
# 由於此腳本預期從專案根目錄使用 pytest 執行，或者直接執行，
# 需要確保 apps 和 tests 目錄在 Python 的搜尋路徑中。
import sys
import os
try:
    current_script_path = Path(__file__).resolve()
    # tests/test_data_population.py -> tests -> project_root
    project_root = current_script_path.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    # 確保 tests 目錄也在 sys.path 中，以便導入 mock_data_utils
    tests_dir = current_script_path.parent
    if str(tests_dir) not in sys.path:
        sys.path.insert(0, str(tests_dir))
except NameError:
    project_root = Path(os.getcwd())
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    tests_dir = project_root / "tests"
    if str(tests_dir) not in sys.path:
         sys.path.insert(0, str(tests_dir))
    print(f"警告：__file__ 未定義，專案路徑校正可能不準確 (test_data_population.py)。")
except Exception as e:
    print(f"專案路徑校正時發生錯誤 (test_data_population.py): {e}", file=sys.stderr)
# --- 標準化「路徑自我校正」樣板碼 END ---

# 延後導入，確保 sys.path 已設定
# from tests.mock_data_utils import ( # pytest 可能無法直接這樣導入，用下面的方式
try:
    from mock_data_utils import (
        generate_mock_taifex_ticks_data,
        generate_mock_treasury_yields_data,
        generate_mock_taifex_pc_ratios_data,
        generate_mock_chimera_signals_data
    )
except ImportError:
    print("無法直接導入 mock_data_utils，請確認 Python 路徑或執行方式。")
    print(f"目前的 sys.path: {sys.path}")
    raise


# 定義模擬資料庫檔案的路徑 (相對於專案根目錄)
MOCK_TAIFEX_TICKS_DB = project_root / "mock_taifex_ticks.duckdb"
MOCK_ANALYTICS_MART_DB = project_root / "mock_analytics_mart.duckdb"
# MOCK_MARKET_DATA_DB = project_root / "mock_market_data.duckdb" # 這個由 yfinance_client 模擬填充

def populate_mock_taifex_ticks_db():
    """填充 mock_taifex_ticks.duckdb"""
    if MOCK_TAIFEX_TICKS_DB.exists():
        MOCK_TAIFEX_TICKS_DB.unlink() # 刪除舊的以確保清潔
        print(f"已刪除舊的 {MOCK_TAIFEX_TICKS_DB}")

    ticks_df = generate_mock_taifex_ticks_data()
    if ticks_df.empty:
        print("警告：生成的模擬 Taifex ticks 數據為空。")
        return

    try:
        with duckdb.connect(str(MOCK_TAIFEX_TICKS_DB)) as con:
            # 根據 apps/time_aggregator/run.py 中的 _create_dummy_source_db_if_needed
            # 它創建的表是 ticks (timestamp TIMESTAMP, product_id VARCHAR, price DOUBLE, qty BIGINT)
            # 而 mock_data_utils 生成的是 timestamp, product_id, price, volume, qty
            # 我們將創建與 dummy_db 相同的 schema，並從 df 中選擇相應欄位
            con.execute("""
                CREATE TABLE ticks (
                    timestamp TIMESTAMP,
                    product_id VARCHAR,
                    price DOUBLE,
                    qty BIGINT  -- 注意這裡用 qty
                );
            """)
            # 選擇需要的欄位進行插入
            # 如果 TimeAggregator 的查詢是 SELECT ... volume ...，那模擬數據的 volume 欄位會被使用 (如果該欄位存在於 select list)。
            # 但為了匹配 dummy db 的 schema，這裡插入 qty
            con.register('ticks_df_temp', ticks_df[['timestamp', 'product_id', 'price', 'qty']])
            con.execute("INSERT INTO ticks SELECT * FROM ticks_df_temp")
            print(f"已成功填充 {len(ticks_df)} 筆數據到 {MOCK_TAIFEX_TICKS_DB} 的 'ticks' 表。")
    except Exception as e:
        print(f"填充 {MOCK_TAIFEX_TICKS_DB} 時發生錯誤: {e}")
        raise

def populate_mock_analytics_mart_db():
    """填充 mock_analytics_mart.duckdb"""
    if MOCK_ANALYTICS_MART_DB.exists():
        MOCK_ANALYTICS_MART_DB.unlink()
        print(f"已刪除舊的 {MOCK_ANALYTICS_MART_DB}")

    treasury_df = generate_mock_treasury_yields_data()
    pc_ratios_df = generate_mock_taifex_pc_ratios_data()
    # 為 chimera signals 準備 stock_ids，應與 yfinance 模擬數據的 stock_ids 一致
    # yfinance 模擬數據使用 "MOCK_AAPL", "MOCK_TSLA", "0050"
    # ReportGenerator 查詢 chimera 時使用原始 stock_id (e.g., "0050.TW") 或處理過的 (e.g. "0050")
    # generate_mock_ohlcv_data 中的 symbol 是 "0050", "MOCK_AAPL", "MOCK_TSLA"
    # ReportGenerator 的 _fetch_data 中 internal_stock_id_for_ohlcv = stock_id.replace(".TW", "")
    # 而 chimera 和 pc_ratio 是用原始 stock_id 查詢
    # 因此 chimera 的 stock_id 需要是 "0050" (如果 ReportGenerator 傳入 "0050") 或 "0050.TW" (如果傳入 "0050.TW")
    # 我們假設 ReportGenerator 會傳入 "0050", "MOCK_AAPL", "MOCK_TSLA" 等ID
    chimera_stock_ids = ["MOCK_AAPL", "MOCK_TSLA", "0050"]
    chimera_df = generate_mock_chimera_signals_data(stock_ids=chimera_stock_ids)

    try:
        with duckdb.connect(str(MOCK_ANALYTICS_MART_DB)) as con:
            # TreasuryYields_Daily table (schema based on FactorEngine)
            if not treasury_df.empty:
                # FactorEngine.get_treasury_yields 查詢 date, term, yield
                # 預期 term 是 'X Yr', 'X Mo'
                con.execute("""
                    CREATE TABLE TreasuryYields_Daily (
                        date TIMESTAMP,
                        term VARCHAR,
                        yield DOUBLE
                    );
                """)
                # 確保 treasury_df['date'] 是 datetime64[ns, UTC]
                # mock_data_utils 已處理
                con.register('treasury_df_temp', treasury_df)
                con.execute("INSERT INTO TreasuryYields_Daily SELECT * FROM treasury_df_temp")
                print(f"已成功填充 {len(treasury_df)} 筆數據到 {MOCK_ANALYTICS_MART_DB} 的 'TreasuryYields_Daily' 表。")
            else:
                print("警告：生成的模擬公債殖利率數據為空。")

            # taifex_pc_ratios table (schema based on ReportGenerator query)
            if not pc_ratios_df.empty:
                # ReportGenerator 查詢 trading_date, product_id, pc_volume_ratio, pc_oi_ratio
                con.execute("""
                    CREATE TABLE taifex_pc_ratios (
                        trading_date DATE,
                        product_id VARCHAR,
                        pc_volume_ratio DOUBLE,
                        pc_oi_ratio DOUBLE
                        -- 其他欄位在 mock data 中未生成，但 ReportGenerator 也不查詢
                    );
                """)
                # mock_data_utils 已處理 trading_date 為 date 物件
                con.register('pc_ratios_df_temp', pc_ratios_df)
                con.execute("INSERT INTO taifex_pc_ratios SELECT * FROM pc_ratios_df_temp")
                print(f"已成功填充 {len(pc_ratios_df)} 筆數據到 {MOCK_ANALYTICS_MART_DB} 的 'taifex_pc_ratios' 表。")
            else:
                print("警告：生成的模擬 P/C ratio 數據為空。")

            # chimera_daily_signals table (schema based on ReportGenerator query)
            if not chimera_df.empty:
                # ReportGenerator 查詢 date, stock_id, price_volume_label, institutional_flow_label, composite_signal
                con.execute("""
                    CREATE TABLE chimera_daily_signals (
                        date DATE,
                        stock_id VARCHAR,
                        price_volume_label VARCHAR,
                        institutional_flow_label VARCHAR,
                        composite_signal VARCHAR
                    );
                """)
                # mock_data_utils 已處理 date 為 date 物件
                # 明確轉換字串欄位為 Pandas 'string' dtype
                string_cols = ['stock_id', 'price_volume_label', 'institutional_flow_label', 'composite_signal']
                for col in string_cols:
                    if col in chimera_df.columns:
                        chimera_df[col] = chimera_df[col].astype("string") # 保持轉換，以防萬一

                # 改用 executemany 插入
                chimera_data_tuples = [tuple(x) for x in chimera_df.to_numpy()]
                con.executemany("""
                    INSERT INTO chimera_daily_signals (date, stock_id, price_volume_label, institutional_flow_label, composite_signal)
                    VALUES (?, ?, ?, ?, ?)
                """, chimera_data_tuples)
                print(f"已成功使用 executemany 填充 {len(chimera_df)} 筆數據到 {MOCK_ANALYTICS_MART_DB} 的 'chimera_daily_signals' 表。")
            else:
                print("警告：生成的模擬 Chimera signals 數據為空。")

            # 為 ohlcv_{timeframe} 創建空表結構 (這些表將由模擬的 yfinance ETL 或 TimeAggregator 填充)
            # ReportGenerator 查詢 timestamp, open, high, low, close, volume, product_id
            timeframes_to_create = ["1d", "1h", "5min"] # 根據普蘭可能用到的
            for tf in timeframes_to_create:
                table_name = f"ohlcv_{tf}"
                con.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        timestamp TIMESTAMP,
                        product_id VARCHAR,
                        open DOUBLE,
                        high DOUBLE,
                        low DOUBLE,
                        close DOUBLE,
                        volume BIGINT,
                        PRIMARY KEY (timestamp, product_id)
                    );
                """)
                print(f"已創建空表 '{table_name}' 於 {MOCK_ANALYTICS_MART_DB}。")

    except Exception as e:
        print(f"填充 {MOCK_ANALYTICS_MART_DB} 時發生錯誤: {e}")
        raise

def main():
    print("開始填充模擬資料庫...")
    populate_mock_taifex_ticks_db()
    populate_mock_analytics_mart_db()
    print("模擬資料庫填充完成。")

if __name__ == "__main__":
    # 為了讓此腳本可以獨立執行 (python tests/test_data_population.py)
    # 以及被 pytest 偵測並執行 (如果包含 test_ 前綴的函數)
    main()

# Pytest 會自動偵測名為 test_* 的函數，如果需要作為 pytest 的一部分，
# 可以將 main() 中的邏輯包裝在一個 test_populate_databases() 函數中。
# 目前，我們將其作為一個獨立的準備步驟，由 main() 觸發。
def test_run_population():
    """此函數讓 pytest 可以執行數據填充。"""
    print("從 pytest 執行數據填充...")
    main()
    # 可以加入 assert 來驗證檔案是否創建等
    assert MOCK_TAIFEX_TICKS_DB.exists(), f"{MOCK_TAIFEX_TICKS_DB} 未創建"
    assert MOCK_ANALYTICS_MART_DB.exists(), f"{MOCK_ANALYTICS_MART_DB} 未創建"
    print("從 pytest 執行數據填充完成。")
