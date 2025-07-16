import duckdb
import os

def main():
    db_path = "data/analytics_warehouse/factors.duckdb"
    table_name = "factors"

    if not os.path.exists(db_path):
        print(f"錯誤：找不到數據庫檔案 '{db_path}'")
        return

    try:
        with duckdb.connect(db_path) as con:
            count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            print(f"'{table_name}' 表中的數據筆數為: {count}")
            if count > 0:
                print("[數據庫驗證通過]")
            else:
                print("[數據庫驗證失敗]")
    except Exception as e:
        print(f"查詢數據庫時發生錯誤: {e}")

if __name__ == "__main__":
    main()
