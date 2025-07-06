# -*- coding: utf-8 -*-
"""
獨立測試腳本：驗證資料庫唯一約束

此腳本用於獨立驗證 DBManager 建立的資料表是否正確實施了唯一約束。
"""
import os
import sys
import duckdb

# 設定專案路徑，以便導入 DBManager
try:
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from apps.daily_market_analyzer.db_manager import DBManager
except ImportError as e:
    print(f"無法導入 DBManager: {e}")
    print("請確保此腳本能夠從專案根目錄正確執行，或者已設定 PYTHONPATH。")
    sys.exit(1)

# 測試配置
TEST_DB_DIR_CONSTRAINT = os.path.join(project_root, "data_workspace", "test_dbs_constraint")
TEST_DB_PATH_CONSTRAINT = os.path.join(TEST_DB_DIR_CONSTRAINT, "constraint_test.duckdb")
TABLE_NAME_CONSTRAINT = "market_data_constraint_test" # 使用一個專用的表名

def main():
    print("--- 開始資料庫唯一約束驗證 ---")

    # 清理並準備環境
    os.makedirs(TEST_DB_DIR_CONSTRAINT, exist_ok=True)
    if os.path.exists(TEST_DB_PATH_CONSTRAINT):
        os.remove(TEST_DB_PATH_CONSTRAINT)
        print(f"已刪除舊的約束測試資料庫: {TEST_DB_PATH_CONSTRAINT}")

    # 1. 初始化 DBManager 並創建表格
    # 注意：DBManager 的 __init__ 會調用 _setup_database，這會創建以
    # self.ohlcv_table_name（即傳入的 target_ohlcv_table_name）命名的表格。
    print(f"初始化 DBManager，目標資料庫: {TEST_DB_PATH_CONSTRAINT}, 目標表格: {TABLE_NAME_CONSTRAINT}")
    try:
        db_man = DBManager(db_path=TEST_DB_PATH_CONSTRAINT, target_ohlcv_table_name=TABLE_NAME_CONSTRAINT)
        print(f"DBManager 初始化成功。表格 '{TABLE_NAME_CONSTRAINT}' 應已創建。")
    except Exception as e:
        print(f"錯誤：DBManager 初始化或表格創建失敗: {e}")
        sys.exit(1)

    # 2. 嘗試第一次插入
    insert_sql = f"""
    INSERT INTO {TABLE_NAME_CONSTRAINT} (ticker, datetime, interval, open, high, low, close, volume)
    VALUES ('TEST_TICKER', '2025-07-07 00:00:00', '1d', 100.0, 101.0, 99.0, 100.5, 1000);
    """
    print(f"\n執行第一次插入:\n{insert_sql.strip()}")
    try:
        with duckdb.connect(TEST_DB_PATH_CONSTRAINT) as con:
            con.execute(insert_sql)
            print("第一次插入成功。")

            # 驗證數據是否存在
            count_result = con.execute(f"SELECT COUNT(*) FROM {TABLE_NAME_CONSTRAINT}").fetchone()
            if count_result and count_result[0] == 1:
                print(f"數據庫中現在有 {count_result[0]} 行數據。")
            else:
                print(f"錯誤：第一次插入後，數據庫中的行數不為 1 (實際: {count_result[0] if count_result else '查詢失敗'})。")
                sys.exit(1)

    except Exception as e:
        print(f"錯誤：第一次插入失敗: {type(e).__name__} - {e}")
        sys.exit(1)

    # 3. 嘗試第二次插入 (相同的數據)
    print(f"\n執行第二次插入 (預期觸發約束錯誤):\n{insert_sql.strip()}")
    constraint_violated = False
    try:
        with duckdb.connect(TEST_DB_PATH_CONSTRAINT) as con:
            con.execute(insert_sql)
        # 如果執行到這裡，表示沒有拋出異常，約束可能未生效
        print("錯誤：第二次插入竟然也成功了！唯一約束可能未正確設定或未生效。")
    except duckdb.ConstraintException as ce:
        print(f"成功：第二次插入按預期拋出了 ConstraintException: {ce}")
        constraint_violated = True
    except Exception as e:
        print(f"錯誤：第二次插入時發生了非預期的錯誤: {type(e).__name__} - {e}")

    # 4. 最終驗證
    if constraint_violated:
        print("\n--- 資料庫唯一約束驗證成功 ---")
        print(f"表格 '{TABLE_NAME_CONSTRAINT}' 的 PRIMARY KEY (ticker, datetime, interval) 成功阻止了重複數據的插入。")
    else:
        print("\n--- 資料庫唯一約束驗證失敗 ---")
        print("未能按預期捕獲到 ConstraintException。請檢查 db_manager.py 中的表格創建邏輯。")
        sys.exit(1)

if __name__ == "__main__":
    main()
