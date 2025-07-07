# apps/report_generator/_test_argus_harness.py
import subprocess
import os
import sys
from pathlib import Path
import duckdb # 測試腳本需要 duckdb 來準備數據
from datetime import date, datetime # 需要 datetime 來準備 ohlcv_1d 的 timestamp

# --- 路徑設定 ---
try:
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent
    # 測試時，我們會創建一個臨時的資料庫和輸出目錄
    TEST_DB_PATH = current_dir / "temp_argus_test_analytics_mart.duckdb"
    TEST_OUTPUT_DIR = current_dir / "temp_argus_test_output"
    RUN_PY_PATH = current_dir / "run.py"

    # 將專案根目錄添加到 sys.path，以便 run.py 中的導入能正常工作
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

except Exception as e:
    print(f"路徑設定時發生錯誤 (_test_argus_harness.py): {e}", file=sys.stderr)
    sys.exit(1)

def _prepare_test_environment():
    """準備測試環境：創建臨時輸出目錄，刪除舊的臨時資料庫。"""
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
        print(f"已刪除舊的臨時測試資料庫: {TEST_DB_PATH}")

    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"已確保臨時測試輸出目錄存在: {TEST_OUTPUT_DIR}")

def _create_test_input_data(con: duckdb.DuckDBPyConnection):
    """在臨時資料庫中創建 ohlcv_1d 和 chimera_daily_signals 並插入數據。"""
    try:
        # 1. ohlcv_1d
        con.execute("""
        CREATE TABLE ohlcv_1d (
            timestamp TIMESTAMP, product_id VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT
        );""")
        # 使用 datetime 物件作為 timestamp
        ohlcv_data = [
            (datetime(2023,1,1,0,0,0), 'ARGUS_STOCK', 10.0,12.0,9.8,11.5,1000),
            (datetime(2023,1,2,0,0,0), 'ARGUS_STOCK', 11.5,13.0,11.0,12.8,1500),
            (datetime(2023,1,3,0,0,0), 'ARGUS_STOCK', 12.8,12.8,10.5,11.0,2000), # 價跌量增
            (datetime(2023,1,4,0,0,0), 'ARGUS_STOCK', 11.0,11.5,10.8,11.2,800),
            (datetime(2023,1,5,0,0,0), 'ARGUS_STOCK', 11.2,12.5,11.1,12.0,1200)  # 價漲量增
        ]
        con.executemany("INSERT INTO ohlcv_1d VALUES (?,?,?,?,?,?,?)", ohlcv_data)
        print("已插入測試 OHLCV 數據。")

        # 2. chimera_daily_signals
        con.execute("""
        CREATE TABLE chimera_daily_signals (
            date DATE, stock_id VARCHAR, price_volume_label VARCHAR,
            institutional_flow_label VARCHAR, composite_signal VARCHAR
            -- 測試腳本不需要所有欄位，僅需 generator.py 中 _fetch_data 會讀取的
        );""")
        chimera_data = [
            # 讓 2023-01-02 成為 價漲量增_法人買超
            (date(2023,1,2), 'ARGUS_STOCK', '價漲量增', '法人買超', '價漲量增_法人買超'),
            # 讓 2023-01-03 成為 價跌量增_法人賣超
            (date(2023,1,3), 'ARGUS_STOCK', '價跌量增', '法人賣超', '價跌量增_法人賣超'),
            # 讓 2023-01-05 成為 其他類型，例如 價漲量增_法人中性
            (date(2023,1,5), 'ARGUS_STOCK', '價漲量增', '法人中性', '價漲量增_法人中性'),
        ]
        con.executemany("INSERT INTO chimera_daily_signals VALUES (?,?,?,?,?)", chimera_data)
        print("已插入測試 Chimera 信號數據。")
        con.commit()

    except Exception as e:
        print(f"在臨時資料庫中創建測試數據時發生錯誤: {e}")
        raise

def _run_report_generator_script(stock_id: str, start_date: str, end_date: str) -> Path:
    """通過 subprocess 調用 report_generator 的 run.py。"""
    output_filename = f"{stock_id}_{start_date.replace('-', '')}_{end_date.replace('-', '')}_report.png"
    expected_report_path = TEST_OUTPUT_DIR / output_filename

    command = [
        sys.executable, str(RUN_PY_PATH),
        "--stock-id", stock_id,
        "--start-date", start_date,
        "--end-date", end_date,
        "--db-path", str(TEST_DB_PATH),
        "--output-dir", str(TEST_OUTPUT_DIR)
    ]
    print(f"執行指令: {' '.join(command)}")
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True, cwd=project_root, encoding='utf-8')
        print("report_generator run.py 標準輸出:")
        print(process.stdout)
        if process.stderr:
            print("report_generator run.py 標準錯誤 (如有):")
            print(process.stderr)

        if not expected_report_path.exists():
            raise FileNotFoundError(f"預期的報告檔案未生成: {expected_report_path}")
        if expected_report_path.stat().st_size == 0:
            raise ValueError(f"生成的報告檔案為空: {expected_report_path}")

        print(f"報告檔案似乎已成功生成: {expected_report_path}")
        return expected_report_path

    except subprocess.CalledProcessError as e:
        print(f"report_generator run.py 執行失敗，返回碼: {e.returncode}")
        print("標準輸出:")
        print(e.stdout)
        print("標準錯誤:")
        print(e.stderr)
        raise
    except Exception as e:
        print(f"執行或驗證報告生成時發生錯誤: {e}")
        raise


def main():
    print("=== 【百眼巨人計畫】整合驗收測試 ===")
    _prepare_test_environment()

    db_conn = None
    try:
        db_conn = duckdb.connect(database=str(TEST_DB_PATH))
        _create_test_input_data(db_conn)
        db_conn.close() # 關閉連接，以便子進程可以訪問
        db_conn = None
        print("臨時資料庫準備完畢，連接已關閉。")

        test_stock = "ARGUS_STOCK"
        test_start = "2023-01-01"
        test_end = "2023-01-05"

        generated_file = _run_report_generator_script(test_stock, test_start, test_end)

        print(f"\n整合測試成功！報告已生成於: {generated_file}")
        print("請手動檢查生成的圖片內容是否符合預期標記。")

    except Exception as e:
        print(f"\n整合驗收測試過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if db_conn: # 如果上面 try 塊中出錯導致連接未關閉
            db_conn.close()
        # 清理臨時檔案和目錄 (可選，方便調試時保留)
        # if TEST_DB_PATH.exists():
        #     TEST_DB_PATH.unlink()
        # if TEST_OUTPUT_DIR.exists():
        #     import shutil
        #     shutil.rmtree(TEST_OUTPUT_DIR)
        print(f"提醒：臨時測試檔案 ({TEST_DB_PATH}, {TEST_OUTPUT_DIR}) 可能未被自動刪除，方便手動檢查。")

if __name__ == "__main__":
    main()
