import duckdb
import os
import pandas as pd
import numpy as np
import pandas_ta

def main():
    db_path = "data/analytics_warehouse/factors.duckdb"
    table_name = "universal_factors"

    if not os.path.exists(db_path):
        print(f"錯誤：找不到數據庫檔案 '{db_path}'")
        return

    try:
        with duckdb.connect(db_path) as con:
            df = con.execute(f"SELECT * FROM {table_name}").fetchdf()

        print("從數據庫讀取數據完畢，開始進行精度驗證...")

        # 重新計算一個因子作為參考
        df['expected_mom_20d'] = df['Close'].pct_change(periods=20)

        # 比較計算結果與儲存的結果
        # 使用 np.isclose 來處理浮點數比較
        comparison = pd.Series(
            np.isclose(df['factor_mom_20d'], df['expected_mom_20d'], atol=1e-6, equal_nan=True)
        )

        # 忽略 NaN 值（滾動窗口導致的）
        comparison = comparison.dropna()

        if comparison.all():
            print("[精度驗證通過]")
        else:
            print("[精度驗證失敗]")
            print("不匹配的數據：")
            print(df[~comparison])

    except Exception as e:
        print(f"驗證精度時發生錯誤: {e}")

if __name__ == "__main__":
    main()
