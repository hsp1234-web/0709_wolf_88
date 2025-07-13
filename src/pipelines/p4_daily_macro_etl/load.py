# -*- coding: utf-8 -*-
"""
數據管線第三階段：數據加載器 (Loader)
"""

import logging

import pandas as pd

from core.db.db_manager import DBManager

logger = logging.getLogger(__name__)


def run_load(transformed_df: pd.DataFrame):
    """
    核心數據加載函式。

    將最終的、統一的 DataFrame 寫入到 DuckDB 數據庫中。

    Args:
        transformed_df (pd.DataFrame): 來自 transform.run_transformation() 的最終 DataFrame。
    """
    if transformed_df.empty:
        logger.warning("傳入的 DataFrame 為空，加載流程終止。")
        return

    table_name = "daily_macro_market_data"
    logger.info(f"數據加載流程開始，目標數據表: '{table_name}'...")

    try:
        # 使用 with 語句確保數據庫連接被妥善管理
        with DBManager() as db_manager:
            # 在寫入前，如果索引是日期且沒有名稱，給它一個標準名稱
            if (
                isinstance(transformed_df.index, pd.DatetimeIndex)
                and transformed_df.index.name is None
            ):
                transformed_df.index.name = "Date"

            # 將 DataFrame 寫入數據庫，使用 'replace' 模式
            db_manager.write_dataframe(
                df=transformed_df.reset_index(),  # DuckDB 寫入時，將索引變為普通列
                table_name=table_name,
                if_exists="replace",
                create_index=True,  # 在 'Date' 列上創建索引
            )

        logger.info(f"成功將數據加載到 '{table_name}' 數據表。")

    except Exception as e:
        logger.error(f"數據加載過程中發生錯誤: {e}", exc_info=True)
        # 重新拋出異常，讓上層 run_etl.py 捕捉並終止管線
        raise


if __name__ == "__main__":
    # 配置日誌以進行本地測試
    logging.basicConfig(level=logging.INFO)

    # 創建一個模擬的 DataFrame
    mock_df = pd.DataFrame(
        {"GSPC_daily_close": [4000, 4010, 4020], "DGS10": [3.5, 3.55, 3.6]},
        index=pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
    )

    print("--- [測試] 執行數據加載模組 ---")
    try:
        run_load(mock_df)
        print("\n數據加載模組測試成功！")

        # 驗證數據是否已寫入
        print("\n--- 驗證數據 ---")
        with DBManager() as db:
            result = db.connection.table("daily_macro_market_data").to_df()
            print("從數據庫讀取到的數據:")
            print(result)
            assert not result.empty
            assert "Date" in result.columns

    except Exception as e:
        print(f"\n測試過程中發生錯誤: {e}")

    print("\n--- [測試] 數據加載模組執行完畢 ---")
