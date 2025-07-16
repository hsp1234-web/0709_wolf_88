# scripts/debug_db_writer.py

import pandas as pd
import duckdb
import os
import numpy as np

def get_table_columns(con, table_name):
    """查詢並返回資料庫表的欄位列表。"""
    try:
        table_info = con.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        return [info[1] for info in table_info]
    except duckdb.CatalogException:
        # 表格不存在
        return []

def robust_db_writer(con, df, table_name):
    """
    一個穩健的寫入函數，能夠自動偵察、演進並寫入數據。
    """
    # 1. 準備數據
    # 確保 'Date' 欄位存在並且是字串格式
    data_to_write = df.copy()
    if 'Date' in data_to_write.columns:
        data_to_write['Date'] = pd.to_datetime(data_to_write['Date']).dt.strftime('%Y-%m-%d %H:%M:%S')

    # 2. 偵察現有結構
    db_columns = get_table_columns(con, table_name)

    # 3. 演進結構
    if not db_columns:
        # 表格不存在，直接創建
        print(f"表格 '{table_name}' 不存在，將根據 DataFrame 結構創建。")
        con.register('df_to_create', data_to_write)
        con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df_to_create")
        db_columns = get_table_columns(con, table_name)
    else:
        # 表格存在，比較欄位
        df_columns = data_to_write.columns.tolist()
        new_columns = set(df_columns) - set(db_columns)

        if new_columns:
            print(f"偵測到新欄位: {new_columns}。正在演進表格結構...")
            for col in new_columns:
                # 注意：這裡我們假設新欄位是 DOUBLE 類型，可以根據需要調整
                con.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} DOUBLE;")
            print("表格結構演進完成。")
            # 更新資料庫欄位列表
            db_columns = get_table_columns(con, table_name)

    # 4. 對齊並寫入
    # 確保 DataFrame 的欄位順序與資料庫表的欄位順序一致
    # 並且只包含資料庫中存在的欄位
    final_df = pd.DataFrame(columns=db_columns)
    for col in db_columns:
        if col in data_to_write.columns:
            final_df[col] = data_to_write[col]
        else:
            final_df[col] = np.nan # 或 None

    # 使用 UPSERT 邏輯 (如果 symbol 和 Date 是主鍵)
    # 這裡我們簡化為先刪除後插入
    if 'symbol' in final_df.columns and 'Date' in final_df.columns:
        symbols = final_df['symbol'].unique()
        for symbol in symbols:
            con.execute(f"DELETE FROM {table_name} WHERE symbol = ?", [symbol])

    print(f"準備寫入 {len(final_df)} 筆數據...")
    con.register('df_to_insert', final_df)
    con.execute(f"INSERT INTO {table_name} SELECT * FROM df_to_insert")
    print("數據寫入成功。")


def main():
    # --- 模擬從 CryptoFactorEngine 輸出的 DataFrame ---
    data = {
        'Date': pd.to_datetime(pd.date_range('2023-01-01', periods=5)),
        'symbol': ['BTC-USD'] * 5,
        'Open': [20000, 21000, 20500, 22000, 21500],
        'High': [21000, 22000, 21500, 23000, 22500],
        'Low': [19000, 20000, 19500, 21000, 20500],
        'Close': [20500, 21500, 21000, 22500, 22000],
        'Volume': [100, 200, 150, 300, 250],
        'factor_corr_nq': [0.5, 0.6, 0.7, 0.8, 0.9],
        'factor_fear_greed_proxy': [0.1, 0.2, 0.15, 0.25, 0.22],
        'new_factor_test': [1,2,3,4,5] # 模擬一個全新的因子
    }
    mock_df = pd.DataFrame(data)
    print("--- 創建的模擬 DataFrame ---")
    print(mock_df)
    print("\n")

    # --- 連接到資料庫 ---
    db_path = "data/analytics_warehouse/factors.duckdb"
    # 為了偵錯，我們先刪除舊的資料庫文件
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"已刪除舊的資料庫文件: {db_path}")

    con = duckdb.connect(db_path)
    print(f"已連接到資料庫: {db_path}")

    # --- 執行穩健寫入 ---
    print("\n--- 第一次寫入 (創建表格) ---")
    robust_db_writer(con, mock_df, 'factors')

    # --- 再次寫入以測試更新和結構演進 ---
    data2 = {
        'Date': pd.to_datetime(pd.date_range('2023-01-03', periods=3)),
        'symbol': ['BTC-USD'] * 3,
        'Open': [30000, 31000, 30500],
        'High': [31000, 32000, 31500],
        'Low': [29000, 30000, 29500],
        'Close': [30500, 31500, 31000],
        'Volume': [1000, 2000, 1500],
        'factor_corr_nq': [0.9, 0.8, 0.7],
        'factor_fear_greed_proxy': [0.3, 0.4, 0.35],
        'another_new_factor': [10, 20, 30] # 模擬另一個新因子
    }
    mock_df2 = pd.DataFrame(data2)
    print("\n--- 第二次寫入 (更新和演進) ---")
    robust_db_writer(con, mock_df2, 'factors')

    # --- 驗證結果 ---
    print("\n--- 驗證最終結果 ---")
    result = con.execute("SELECT * FROM factors").fetchdf()
    print(result)

    con.close()

if __name__ == "__main__":
    main()
