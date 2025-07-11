# apps/feature_analyzer/dealer_position_analyzer.py
# 這個模組負責分析一級交易商的持有量數據。

import duckdb
import pandas as pd
import traceback

# 資料庫設定
DEFAULT_MARKET_DATA_DB = "market_data.duckdb"  # 來源資料庫
DEFAULT_ANALYTICS_MART_DB = "analytics_mart.duckdb"  # 目標資料庫
DEALER_POSITIONS_TABLE_NAME = "primary_dealer_positions"
DEALER_ANALYSIS_TABLE_NAME = "primary_dealer_analysis"


def fetch_dealer_positions(market_db_path: str) -> pd.DataFrame:
    """
    從指定的 market_data 資料庫的 primary_dealer_positions 表中提取數據。
    """
    query = f"SELECT Date, Total_Positions FROM {DEALER_POSITIONS_TABLE_NAME} ORDER BY Date;"
    try:
        with duckdb.connect(
            market_db_path, read_only=True
        ) as con:  # 使用傳入的 market_db_path
            df = con.execute(query).fetchdf()

        if df.empty:
            print(
                f"警告：在資料庫 {market_db_path} 的 {DEALER_POSITIONS_TABLE_NAME} 表中未找到數據。"
            )
            return pd.DataFrame()

        df["Date"] = pd.to_datetime(df["Date"])
        df.set_index("Date", inplace=True)
        print(
            f"成功從 {DEALER_POSITIONS_TABLE_NAME} (來源: {market_db_path}) 提取了 {len(df)} 筆一級交易商持有量數據。"
        )
        return df
    except Exception as e:
        print(f"從 DuckDB ({market_db_path}) 提取一級交易商持有量數據時發生錯誤: {e}")
        traceback.print_exc()
        return pd.DataFrame()


def calculate_position_changes(positions_df: pd.DataFrame) -> pd.DataFrame:
    """
    計算持有量的週變化和月變化等基礎指標。
    NY Fed 的數據通常是每週一次 (週三數據)，所以 "週變化" 就是直接的 diff。
    "月變化" 可以近似為向前找4週的數據進行比較。

    Args:
        positions_df (pd.DataFrame): 索引為日期，包含 'Total_Positions' 欄的 DataFrame。
    Returns:
        pd.DataFrame: 包含日期、總持有量、週變化、月變化的 DataFrame。
    """
    if positions_df.empty:
        print("錯誤：持有量數據為空，無法計算變化。")
        return pd.DataFrame()

    # 確保數據按日期排序
    positions_df.sort_index(inplace=True)

    # 計算週變化 (直接與上一筆數據比較，因為數據本身是週頻的)
    # Total_Positions 單位已经是實際值
    positions_df["weekly_change"] = positions_df["Total_Positions"].diff()

    # 計算月變化 (近似為與4週前的數據比較)
    # 使用 shift(4) 來獲取4週前的值
    positions_df["monthly_change"] = positions_df["Total_Positions"].diff(periods=4)

    # 計算週變化百分比 (相對於變化前的值)
    # (Current - Previous) / Previous
    # Avoid division by zero if Previous was 0.
    prev_week_positions = positions_df["Total_Positions"].shift(1)
    positions_df["weekly_change_pct"] = (
        positions_df["weekly_change"] / prev_week_positions * 100
    )
    # 修正 FutureWarning: 不使用 inplace=True
    positions_df["weekly_change_pct"] = positions_df["weekly_change_pct"].replace(
        [float("inf"), -float("inf")], 100.0
    )  # 從0到有，視為100%變化

    # 計算月變化百分比
    prev_month_positions = positions_df["Total_Positions"].shift(4)
    positions_df["monthly_change_pct"] = (
        positions_df["monthly_change"] / prev_month_positions * 100
    )
    # 修正 FutureWarning: 不使用 inplace=True
    positions_df["monthly_change_pct"] = positions_df["monthly_change_pct"].replace(
        [float("inf"), -float("inf")], 100.0
    )

    # 重設索引，使 Date 變回欄位
    result_df = positions_df.reset_index()

    # 選擇並重命名欄位以符合目標表結構
    # 根據作戰命令，目標表是 primary_dealer_analysis，欄位可以包括 date, total_positions, weekly_change, monthly_change 等。
    # 我們可以儲存更多計算出的指標。
    result_df = result_df[
        [
            "Date",
            "Total_Positions",
            "weekly_change",
            "monthly_change",
            "weekly_change_pct",
            "monthly_change_pct",
        ]
    ]
    result_df.columns = [
        "date",
        "total_positions",
        "weekly_change",
        "monthly_change",
        "weekly_change_pct",
        "monthly_change_pct",
    ]

    print(f"成功計算了 {len(result_df)} 筆數據的週/月變化。")
    return result_df.dropna(
        subset=["weekly_change", "monthly_change"], how="all"
    )  # 移除最初幾行因 diff 產生的 NaN


def store_dealer_analysis_data(
    df: pd.DataFrame,
    analytics_db_path: str,
    table_name: str = DEALER_ANALYSIS_TABLE_NAME,
):
    """
    將計算出的一級交易商分析數據儲存到指定的 analytics_mart 資料庫。
    """
    if df.empty:
        print(f"沒有一級交易商分析數據可儲存至資料表 {table_name}。")
        return

    try:
        with duckdb.connect(analytics_db_path) as con:  # 使用傳入的 analytics_db_path
            con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")
            print(
                f"一級交易商分析數據已成功儲存至 DuckDB 資料庫 '{analytics_db_path}' 的資料表 '{table_name}'。"
            )
            count_result = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            if count_result:
                print(f"資料表 '{table_name}' 目前包含 {count_result[0]} 筆數據。")
    except Exception as e:
        print(f"儲存一級交易商分析數據至 DuckDB ({analytics_db_path}) 時發生錯誤：{e}")
        traceback.print_exc()


def run_dealer_position_analysis(
    market_db_path: str = DEFAULT_MARKET_DATA_DB,
    analytics_db_path: str = DEFAULT_ANALYTICS_MART_DB,
):
    """
    執行一級交易商持有量分析的主函數。
    """
    print("\n--- 開始一級交易商持有量分析 ---")
    print(f"來源市場數據庫: {market_db_path}")
    print(f"目標分析數據庫: {analytics_db_path}")

    positions_data = fetch_dealer_positions(market_db_path)

    if positions_data.empty:
        print("無法繼續一級交易商持有量分析，因獲取的原始數據不足。")
        return

    analysis_results = calculate_position_changes(positions_data)

    if not analysis_results.empty:
        store_dealer_analysis_data(analysis_results, analytics_db_path)
        print("一級交易商持有量分析執行完畢。")
    else:
        print("一級交易商持有量分析執行完畢，但未產生任何可儲存的分析結果。")


if __name__ == "__main__":
    # (此處的獨立測試將使用預設資料庫名稱)

    print("執行 dealer_position_analyzer.py 獨立測試 (使用預設DB路徑)...")
    run_dealer_position_analysis(
        market_db_path=DEFAULT_MARKET_DATA_DB,
        analytics_db_path=DEFAULT_ANALYTICS_MART_DB,
    )

    print(
        f"\n--- DuckDB 數據驗證 (primary_dealer_analysis, DB: {DEFAULT_ANALYTICS_MART_DB}) ---"
    )
    try:
        with duckdb.connect(DEFAULT_ANALYTICS_MART_DB) as con:  # 連接到預設分析資料庫
            print(
                f"從 DuckDB 讀取 '{DEFAULT_ANALYTICS_MART_DB}' 的 '{DEALER_ANALYSIS_TABLE_NAME}' 資料表進行驗證..."
            )
            tables_df = con.execute("SHOW TABLES").df()
            if DEALER_ANALYSIS_TABLE_NAME not in tables_df["name"].values:
                print(f"錯誤: '{DEALER_ANALYSIS_TABLE_NAME}' 資料表未在資料庫中找到。")
            else:
                retrieved_data = con.table(DEALER_ANALYSIS_TABLE_NAME).df()
                print(
                    f"成功從 '{DEALER_ANALYSIS_TABLE_NAME}' 讀取 {len(retrieved_data)} 筆數據。"
                )
                if not retrieved_data.empty:
                    print(retrieved_data.head())
                    retrieved_data.info()
    except Exception as e:
        print(f"從 DuckDB 驗證讀取一級交易商分析數據時發生錯誤: {e}")
        traceback.print_exc()

    print("--- dealer_position_analyzer.py 測試結束 ---")
