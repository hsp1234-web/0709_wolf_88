# apps/institutional_analyzer/_test_garuda_harness.py
import subprocess
import duckdb
import os
import sys # 導入 sys 模組
import pandas as pd
from datetime import datetime, timedelta

# --- 路徑自我校正樣板碼 START ---
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
    DB_PATH = os.path.join(project_root, "analytics_mart.duckdb")
    RUN_PY_PATH = os.path.join(current_dir, "run.py")
except Exception as e:
    print(f"專案路徑校正時發生錯誤 (_test_garuda_harness.py): {e}", file=sys.stderr)
    DB_PATH = "analytics_mart.duckdb"
    RUN_PY_PATH = "apps/institutional_analyzer/run.py"
# --- 路徑自我校正樣板碼 END ---

TEST_API_TOKEN = os.getenv("TEST_FINMIND_API_TOKEN", "DUMMY_TOKEN_FOR_HARNESS_TEST")

def ensure_table_exists_for_test(db_path: str):
    """
    確保 institutional_trades 表格在 DuckDB 中存在。
    這是一個輔助函數，模仿 analyzer.py 中的 _ensure_table_exists，
    但在測試腳本控制下執行，以避免鎖問題。
    """
    try:
        con = duckdb.connect(db_path)
        con.execute("""
        CREATE TABLE IF NOT EXISTS institutional_trades (
            date DATE,
            stock_id VARCHAR,
            investor_type VARCHAR,
            buy_shares BIGINT,
            sell_shares BIGINT,
            net_shares BIGINT,
            PRIMARY KEY (date, stock_id, investor_type)
        );
        """)
        con.commit()
        con.close()
        print(f"測試前置作業：資料庫 {db_path} 中的 institutional_trades 表格已確認/創建。")
    except Exception as e:
        print(f"測試前置作業：檢查或創建 institutional_trades 表格時發生錯誤: {e}")
        # 如果這裡失敗，後續測試可能無意義，所以向上拋出
        raise

def clear_test_data_from_db(db_path: str, stock_id: str, start_date: str, end_date: str):
    """從 institutional_trades 表格中清除指定股票和日期範圍的數據"""
    try:
        con = duckdb.connect(db_path)
        # 先確保表格存在，再執行刪除
        # 注意：這裡的 ensure_table_exists_for_test 是由測試腳本的 main 函數調用的，
        # clear_test_data_from_db 假設表格已由 main 中的 ensure_table_exists_for_test 創建。
        # 或者，更保險的做法是在這裡也調用一次，但可能會重複打印訊息。
        # 考慮到 main 函數的流程，此處直接嘗試刪除。
        print(f"清除資料庫中股票 {stock_id} 從 {start_date} 到 {end_date} 的舊數據...")
        delete_query = f"""
            DELETE FROM institutional_trades
            WHERE stock_id = '{stock_id}' AND date >= '{start_date}' AND date <= '{end_date}'
        """
        con.execute(delete_query)
        con.commit()
        # DuckDB Python API 獲取影響行數的方式是 connection.execute(...).fetchall() 後，
        # 如果是 DML，返回的 relation 通常有一個 rowcount 屬性，但更可靠的是用 pragma。
        # 不過，pragma_last_rows_affected() 似乎也不是標準 SQL，且可能依賴版本。
        # 最簡單的方式是執行一個 SELECT COUNT(*) afterwards or rely on the fact that no error means success.
        # 這裡我們選擇不獲取精確的 deleted_count 以簡化，因為其主要目的是清除。
        # 如果需要計數，可以再執行一個 SELECT COUNT(*) 比較前後差異，但會增加複雜度。
        # deleted_count = con.execute("SELECT last_rows_affected()").fetchone()[0] # 這是假設的，不一定對
        # 或者，使用 DuckDB 的一個特性，如果 DELETE 有返回結果
        # result = con.execute(delete_query).fetchall() # 檢查 result
        con.close()
        print(f"已執行清除股票 {stock_id} 從 {start_date} 到 {end_date} 的舊數據操作。")
    except duckdb.CatalogException as ce: # 更精確地捕捉表格不存在的錯誤
        print(f"清除舊數據時注意: {ce} (可能表格剛被創建，尚無數據，此為正常現象，或 SQL 語句中的表/函數名錯誤)")
        # 如果錯誤是 "Scalar Function with name changes does not exist!" 則關閉連接
        if "changes does not exist" in str(ce) and con:
             con.close()
    except Exception as e:
        print(f"清除舊數據時發生非預期錯誤: {e}")
        if con: # 確保連接被關閉
            con.close()
        # 不向上拋出異常，讓測試繼續

def run_analyzer_script(stock_id: str, start_date: str, end_date: str, api_token: str | None):
    """執行主分析腳本 apps/institutional_analyzer/run.py"""
    command = [
        "python", RUN_PY_PATH,
        "--stock-id", stock_id,
        "--start-date", start_date,
        "--end-date", end_date
    ]
    if api_token:
        command.extend(["--api-token", api_token])

    print(f"執行指令: {' '.join(command)}")
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True, cwd=project_root, encoding='utf-8')
        print("分析腳本標準輸出:")
        print(process.stdout)
        if process.stderr:
            print("分析腳本標準錯誤 (如果有):")
            print(process.stderr)
    except subprocess.CalledProcessError as e:
        print(f"分析腳本執行失敗，返回碼: {e.returncode}")
        print("標準輸出:")
        print(e.stdout)
        print("標準錯誤:")
        print(e.stderr)
        raise

def verify_data_in_duckdb(db_path: str, stock_id: str, start_date: str, end_date: str, expect_data: bool = True):
    """連接 DuckDB 並驗證數據"""
    print(f"開始驗證資料庫中股票 {stock_id} 從 {start_date} 到 {end_date} 的數據...")
    try:
        con = duckdb.connect(db_path, read_only=True) # 以唯讀模式打開以避免鎖問題
        query = f"""
        SELECT date, stock_id, investor_type, buy_shares, sell_shares, net_shares
        FROM institutional_trades
        WHERE stock_id = '{stock_id}' AND date >= '{start_date}' AND date <= '{end_date}'
        ORDER BY date, investor_type;
        """
        print(f"執行查詢: {query}")
        result_df = con.execute(query).fetchdf()
        con.close()

        print(f"查詢結果 (共 {len(result_df)} 筆記錄):")
        if not result_df.empty:
            print(result_df.head())
        else:
            print("未查詢到任何記錄。")

        if expect_data:
            if result_df.empty:
                raise AssertionError(f"驗證失敗：預期在 institutional_trades 表中找到股票 {stock_id} 的數據，但未找到。")

            expected_columns = ['date', 'stock_id', 'investor_type', 'buy_shares', 'sell_shares', 'net_shares']
            for col in expected_columns:
                if col not in result_df.columns:
                    raise AssertionError(f"驗證失敗：結果中缺少欄位 {col}。")

            valid_investor_types = {'Foreign_Dealer', 'Investment_Trust', 'Dealer_Self', 'Dealer_Hedging'}
            if not result_df['investor_type'].isin(valid_investor_types).all():
                invalid_types = result_df[~result_df['investor_type'].isin(valid_investor_types)]['investor_type'].unique()
                raise AssertionError(f"驗證失敗：發現無效的 investor_type: {invalid_types}")

            if not (result_df['net_shares'] == result_df['buy_shares'] - result_df['sell_shares']).all():
                raise AssertionError("驗證失敗：部分記錄的 net_shares 不等於 buy_shares - sell_shares。")

            print(f"驗證成功：在 institutional_trades 表中找到了 {len(result_df)} 筆股票 {stock_id} 的數據，且基本結構正確。")
        else:
            if not result_df.empty:
                print(f"警告：預期資料庫中沒有股票 {stock_id} 的數據（因使用虛擬Token），但查詢到了 {len(result_df)} 筆。")
            else:
                print(f"驗證成功：如預期（因使用虛擬Token），institutional_trades 表中沒有股票 {stock_id} 的數據。")

    except duckdb.CatalogException as ce: # 表格不存在的錯誤
        if expect_data: # 如果預期有數據但表格不存在，這是個錯誤
            raise AssertionError(f"驗證失敗：預期找到 institutional_trades 表格，但表格不存在 ({ce})")
        else: # 如果不預期有數據，表格不存在也算通過
            print(f"驗證成功：如預期（因使用虛擬Token），institutional_trades 表格不存在或無相關數據 ({ce})。")
    except Exception as e:
        print(f"驗證 DuckDB 數據時發生錯誤: {e}")
        raise

def main():
    test_stock_id = "2884"
    test_end_date_dt = datetime.now() - timedelta(days=1)
    test_start_date_dt = test_end_date_dt - timedelta(days=6)
    test_start_date = test_start_date_dt.strftime("%Y-%m-%d")
    test_end_date = test_end_date_dt.strftime("%Y-%m-%d")

    print(f"=== 【迦樓羅計畫】整合驗收測試 ===")
    print(f"資料庫路徑: {DB_PATH}")
    print(f"測試目標股票: {test_stock_id}")
    print(f"測試日期範圍: {test_start_date} 至 {test_end_date}")
    is_dummy_token = TEST_API_TOKEN == "DUMMY_TOKEN_FOR_HARNESS_TEST"
    if is_dummy_token:
        print("警告：將使用虛擬 API Token (DUMMY_TOKEN_FOR_HARNESS_TEST)。預期不會從 API 獲取真實數據。")
    else:
        print(f"將使用環境變數 TEST_FINMIND_API_TOKEN (長度: {len(TEST_API_TOKEN)})。")

    try:
        # 0. 確保表格存在 (由測試腳本控制，避免 analyzer.py 初始化時的鎖競爭)
        # analyzer.py 中的 _ensure_table_exists 仍然保留，用於非測試腳本調用時的獨立性
        print(f"\n--- 步驟 0: 確保測試用表格存在 ---")
        ensure_table_exists_for_test(DB_PATH)

        # 1. 清除測試期間的舊數據
        print(f"\n--- 步驟 1: 清除舊數據 (股票: {test_stock_id}, 日期: {test_start_date} 至 {test_end_date}) ---")
        clear_test_data_from_db(DB_PATH, test_stock_id, test_start_date, test_end_date)

        # 2. 執行分析腳本
        # 此時 analyzer.py 中的 _ensure_table_exists 應該能正常執行 (因為表格已存在，不會有寫入衝突)
        # 或者即使它嘗試 CREATE IF NOT EXISTS，由於表格已經存在，也不會導致鎖問題。
        print(f"\n--- 步驟 2: 執行分析腳本 (apps/institutional_analyzer/run.py) ---")
        run_analyzer_script(test_stock_id, test_start_date, test_end_date, TEST_API_TOKEN)
        print("分析腳本執行完畢。")

        # 3. 驗證數據
        print(f"\n--- 步驟 3: 驗證 DuckDB 中的數據 ---")
        verify_data_in_duckdb(DB_PATH, test_stock_id, test_start_date, test_end_date, expect_data=not is_dummy_token)

        print(f"\n=== 【迦樓羅計畫】整合驗收測試 ({test_stock_id}) 順利完成 ===")

    except AssertionError as ae:
        print(f"\n整合驗收測試失敗 (AssertionError): {ae}")
        print("請檢查錯誤訊息並修正相關模組。")
        sys.exit(1)
    except Exception as e:
        print(f"\n整合驗收測試過程中發生未預期錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    # finally 不需要了，因為 DuckDB 連接是在每個函數內部臨時建立和關閉的

if __name__ == "__main__":
    main()
