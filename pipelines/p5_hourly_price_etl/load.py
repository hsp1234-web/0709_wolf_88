# -*- coding: utf-8 -*-
"""
數據管線第三階段：小時級價格數據加載器 (Loader)
"""
import logging

import pandas as pd

from core.db.db_manager import DBManager

logger = logging.getLogger(__name__)


def run_load(transformed_df: pd.DataFrame, mode: str):
    """
    將轉換後的 DataFrame 寫入到 DuckDB 數據庫中。

    Args:
        transformed_df (pd.DataFrame): 來自 transform.run_transformation() 的最終 DataFrame。
        mode (str): 操作模式，'backfill' 或 'update'。
    """
    if transformed_df.empty:
        logger.warning("傳入的 DataFrame 為空，加載流程終止。")
        return

    table_name = "hourly_market_data"
    logger.info(f"--- [Loader] 啟動，目標數據表: '{table_name}', 模式: {mode} ---")

    try:
        with DBManager() as db_manager:
            # 準備 DataFrame 進行寫入
            # 1. 確保索引名為 'timestamp'
            if transformed_df.index.name is None:
                transformed_df.index.name = "timestamp"

            df_to_load = transformed_df.reset_index()

            if mode == "update":
                try:
                    # 檢查表格是否存在
                    db_manager.connection.execute(f"DESCRIBE {table_name}")

                    # 更新模式的關鍵：刪除可能重疊的數據
                    min_ts_utc = pd.to_datetime(df_to_load["timestamp"]).min()
                    min_ts_naive = min_ts_utc.tz_localize(None)
                    logger.info(f"更新模式：將刪除 '{table_name}' 中 timestamp >= '{min_ts_naive}' 的現有數據。")
                    delete_query = f"DELETE FROM {table_name} WHERE timestamp >= '{min_ts_naive}'"
                    db_manager.connection.execute(delete_query)
                    logger.info("成功刪除重疊數據。")

                    # 獲取現有表格的欄位
                    existing_columns = [desc[0] for desc in db_manager.connection.execute(f"DESCRIBE {table_name}").fetchall()]

                    # 確保新數據的欄位與現有表格一致
                    df_to_load = df_to_load.reindex(columns=existing_columns).fillna(value=pd.NA)
                    df_to_load['timestamp'] = pd.to_datetime(df_to_load['timestamp'], unit='ns', utc=True)


                except Exception as e:
                    if "not found" in str(e).lower():
                        logger.info(f"數據表 '{table_name}' 尚不存在，將執行首次寫入。")
                    else:
                        raise e


            # 執行寫入操作
            # 對於 backfill，我們替換整個表
            # 對於 update，我們附加新數據
            write_mode = "replace" if mode == "backfill" else "append"
            db_manager.write_dataframe(
                df=df_to_load,
                table_name=table_name,
                if_exists=write_mode,
                create_index=False,  # We handle index creation manually
            )

            # 在 'timestamp' 列上創建索引以優化查詢
            # 僅在首次創建表時或需要時執行
            # DuckDB 會自動處理重複創建索引的情況
            logger.info(f"正在 '{table_name}' 的 'timestamp' 列上創建或確認索引...")
            db_manager.connection.execute(f"CREATE INDEX IF NOT EXISTS idx_timestamp ON {table_name} (timestamp);")


        logger.info(f"--- [Loader] 完成，成功將 {len(df_to_load)} 筆數據加載到 '{table_name}' ---")

    except Exception as e:
        logger.error(f"數據加載過程中發生嚴重錯誤: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # 創建一個模擬的 DataFrame
    mock_df_1 = pd.DataFrame({
        "spy_close": [400, 401, 402],
        "qqq_close": [300, 301, 302]
    }, index=pd.to_datetime(["2023-01-01 10:00:00", "2023-01-01 11:00:00", "2023-01-01 12:00:00"], utc=True))
    mock_df_1.index.name = "timestamp"


    # --- 測試 1: Backfill 模式 ---
    print("\n--- [測試 1] 執行 Backfill 模式 ---")
    try:
        # 先清空舊表
        with DBManager() as db:
            db.connection.execute("DROP TABLE IF EXISTS hourly_market_data;")
            print("已清空舊的 hourly_market_data 表。")

        run_load(mock_df_1, mode="backfill")

        # 驗證數據
        with DBManager() as db:
            result = db.connection.table("hourly_market_data").to_df()
            print("Backfill 後的數據:")
            print(result)
            assert len(result) == 3
            print("✅ Backfill 模式驗證成功！")

    except Exception as e:
        print(f"Backfill 測試失敗: {e}")


    # --- 測試 2: Update 模式 (有重疊數據) ---
    print("\n--- [測試 2] 執行 Update 模式 (有重疊數據) ---")
    mock_df_2 = pd.DataFrame({
        "spy_close": [402.5, 403], # 12:00 的數據更新了
        "qqq_close": [302.5, 303]
    }, index=pd.to_datetime(["2023-01-01 12:00:00", "2023-01-01 13:00:00"], utc=True))
    mock_df_2.index.name = "timestamp"

    try:
        run_load(mock_df_2, mode="update")
        # 驗證數據
        with DBManager() as db:
            result = db.connection.table("hourly_market_data").to_df()
            print("\nUpdate 後的數據:")
            print(result)
            # 總數據應為 4 筆 (10:00, 11:00, 12:00_new, 13:00_new)
            # 舊的 12:00 數據應被刪除
            assert len(result) == 4
            # 驗證 12:00 的數據是新的
            assert result[result['timestamp'] == pd.to_datetime("2023-01-01 12:00:00")]['spy_close'].iloc[0] == 402.5
            print("✅ Update 模式驗證成功！")

    except Exception as e:
        print(f"Update 測試失敗: {e}")


    print("\n--- [測試] 數據加載模組執行完畢 ---")
