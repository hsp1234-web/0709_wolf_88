# apps/feature_analyzer/run.py

import duckdb
import pandas as pd
import argparse
from pathlib import Path
import sys  # 導入 sys
import os  # 導入 os

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    # 獲取目前腳本的絕對路徑
    current_script_path = Path(__file__).resolve()
    # 假設此腳本位於 apps/[app_name] 目錄下，專案根目錄是其再上兩層
    project_root = current_script_path.parent.parent.parent
    # 將專案根目錄加入 sys.path
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except (
    NameError
):  # __file__ is not defined, common in interactive shells or certain execution contexts
    project_root = Path(os.getcwd())
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    print(
        f"警告：__file__ 未定義，專案路徑校正可能不準確。已將 {project_root} 加入 sys.path。",
        file=sys.stderr,
    )
except Exception as e:
    print(
        f"專案路徑校正時發生錯誤 (apps/feature_analyzer/run.py): {e}", file=sys.stderr
    )
# --- 標準化「路徑自我校正」樣板碼 END ---


# project_root 現在由標準樣板碼定義
# 假設 analytics_mart.duckdb 位於專案根目錄下的 "data" 資料夾中 (舊的象限分析用)
DEFAULT_DATA_DIR = project_root / "data"
ANALYTICS_DB_PATH = DEFAULT_DATA_DIR / "analytics_mart.duckdb"

# 與 time_aggregator 中定義的時間週期保持一致 (舊的象限分析用)
TIME_PERIODS = {
    "1min": "1T",
    "5min": "5T",
    "15min": "15T",
    "1h": "1H",
    "4h": "4H",
    "1d": "1D",
}


def create_quadrant_analysis_tables(con: duckdb.DuckDBPyConnection):
    """
    在 analytics_mart.duckdb 中為每個時間週期創建價格/量能四象限分析結果資料表。
    """
    for period_name in TIME_PERIODS.keys():
        table_name = f"quadrant_analysis_{period_name}"
        try:
            con.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    timestamp TIMESTAMP,
                    product_id VARCHAR,
                    price_change_pct DOUBLE,
                    volume_change_pct DOUBLE,
                    quadrant INTEGER,
                    PRIMARY KEY (timestamp, product_id)
                );
            """
            )
            print(f"資料表 '{table_name}' 已創建或已存在。")
        except Exception as e:
            print(f"創建資料表 '{table_name}' 時發生錯誤: {e}")


def calculate_quadrant(price_change_pct: float, volume_change_pct: float) -> int:
    """
    根據價格變化百分比和成交量變化百分比確定象限。
    象限一：價漲量增 (動能強勁)
    象限二：價跌量增 (恐慌或拋售)
    象限三：價跌量縮 (動能趨緩)
    象限四：價漲量縮 (上漲力道減弱)
    """
    if price_change_pct > 0 and volume_change_pct > 0:
        return 1
    elif price_change_pct < 0 and volume_change_pct > 0:
        return 2
    elif price_change_pct < 0 and volume_change_pct < 0:
        return 3
    elif price_change_pct > 0 and volume_change_pct < 0:
        return 4
    # 處理變化為0或無法分類的情況，例如價格不變或成交量不變
    # 這裡暫時將其歸類為 0，可以根據需求調整
    elif price_change_pct == 0 or volume_change_pct == 0:
        if price_change_pct > 0:
            return 1  # 價漲量平，視為象限1的特例
        if price_change_pct < 0:
            return 2  # 價跌量平，視為象限2的特例
        if volume_change_pct > 0:
            return 1  # 價平量增，視為象限1的特例
        if volume_change_pct < 0:
            return 3  # 價平量縮，視為象限3的特例
    return 0  # 預設或無法分類


def analyze_features(analytics_db_path: Path):
    """
    讀取 analytics_mart.duckdb 中的 OHLCV 數據，執行特徵分析，並將結果存回資料庫。
    """
    if not analytics_db_path.exists():
        print(
            f"錯誤：分析資料庫 '{analytics_db_path}' 不存在。請先執行 time_aggregator。"
        )
        return

    print(f"正在連接到分析資料庫: {analytics_db_path}")
    try:
        with duckdb.connect(database=str(analytics_db_path), read_only=False) as con:
            print("成功連接到分析資料庫。")
            create_quadrant_analysis_tables(con)

            for period_name in TIME_PERIODS.keys():
                ohlcv_table_name = f"ohlcv_{period_name}"
                quadrant_table_name = f"quadrant_analysis_{period_name}"

                print(f"\n正在處理週期: {period_name} (來源資料表: {ohlcv_table_name})")

                # 讀取特定週期的 OHLCV 數據，按 product_id 和 timestamp 排序
                try:
                    ohlcv_df = con.execute(
                        f"""
                        SELECT timestamp, product_id, close, volume
                        FROM {ohlcv_table_name}
                        ORDER BY product_id, timestamp
                    """
                    ).fetchdf()
                except duckdb.CatalogException:
                    print(
                        f"錯誤：資料表 '{ohlcv_table_name}' 不存在於資料庫中。跳過此週期。"
                    )
                    continue

                if ohlcv_df.empty:
                    print(f"資料表 '{ohlcv_table_name}' 中沒有數據。跳過此週期。")
                    continue

                print(f"成功從 '{ohlcv_table_name}' 讀取 {len(ohlcv_df)} 筆數據。")

                # 計算價格變化百分比和成交量變化百分比
                # 使用 groupby('product_id')確保每個商品的變化是獨立計算的
                ohlcv_df["price_change_pct"] = (
                    ohlcv_df.groupby("product_id")["close"].pct_change().fillna(0) * 100
                )
                # 成交量變化百分比，處理分母為0的情況 (例如第一個K棒的成交量為0，或者前期成交量為0)
                # (V_current - V_previous) / V_previous
                # 如果 V_previous 是 0, (V_current - 0) / 0 -> inf.
                # 如果 V_current 也是 0, 0 / 0 -> NaN.
                # 如果 V_current > 0, V_previous = 0, 變化視為無限大或一個極大值 (例如100% * sign(V_current))
                # 如果 V_current = 0, V_previous > 0, 變化是 -100%

                # 計算成交量差異
                ohlcv_df["volume_prev"] = ohlcv_df.groupby("product_id")[
                    "volume"
                ].shift(1)

                # 計算百分比變化，處理 V_previous 為 0 的情況
                # 1. V_prev is NA (first row for a product_id): volume_change_pct = 0
                # 2. V_prev is 0 and V_curr is 0: volume_change_pct = 0
                # 3. V_prev is 0 and V_curr is >0: volume_change_pct = 100 (表示從無到有，給予100%增長)
                # 4. V_prev > 0: (V_curr - V_prev) / V_prev * 100

                conditions = [
                    ohlcv_df["volume_prev"].isnull(),  # Case 1
                    (ohlcv_df["volume_prev"] == 0)
                    & (ohlcv_df["volume"] == 0),  # Case 2
                    (ohlcv_df["volume_prev"] == 0) & (ohlcv_df["volume"] > 0),  # Case 3
                ]
                choices = [
                    0,  # Case 1 result
                    0,  # Case 2 result
                    100.0,  # Case 3 result
                ]

                ohlcv_df["volume_change_pct"] = pd.Series(
                    np.select(
                        conditions,
                        choices,
                        default=(ohlcv_df["volume"] - ohlcv_df["volume_prev"])
                        / ohlcv_df["volume_prev"]
                        * 100,
                    ),
                    index=ohlcv_df.index,
                ).fillna(
                    0
                )  # fillna for the default case if any division by zero not caught by conditions occurs, or for the very first row after shift.

                # 應用象限分類函數
                ohlcv_df["quadrant"] = ohlcv_df.apply(
                    lambda row: calculate_quadrant(
                        row["price_change_pct"], row["volume_change_pct"]
                    ),
                    axis=1,
                )

                # 準備要寫入的數據
                result_df = ohlcv_df[
                    [
                        "timestamp",
                        "product_id",
                        "price_change_pct",
                        "volume_change_pct",
                        "quadrant",
                    ]
                ]

                # 寫入結果到新的分析資料表
                # 為了確保冪等性，先刪除已存在的數據
                # 注意：這裡假設 `timestamp` 和 `product_id` 的組合是唯一的，並且 `ohlcv_df` 中的 `timestamp` 是該週期的起始時間
                if not result_df.empty:
                    min_ts = result_df["timestamp"].min()
                    max_ts = result_df["timestamp"].max()

                    # 獲取所有在此時間範圍內的 product_id
                    product_ids_in_batch = result_df["product_id"].unique()
                    product_ids_tuple = tuple(product_ids_in_batch)

                    # 如果只有一個 product_id，SQL 的 IN 子句需要特殊處理
                    if len(product_ids_tuple) == 1:
                        product_ids_tuple_sql = f"('{product_ids_tuple[0]}')"
                    else:
                        product_ids_tuple_sql = str(product_ids_tuple)

                    delete_query = f"""
                    DELETE FROM {quadrant_table_name}
                    WHERE product_id IN {product_ids_tuple_sql}
                    AND timestamp >= '{min_ts}' AND timestamp <= '{max_ts}';
                    """
                    # print(f"執行刪除查詢: {delete_query}") # Debugging
                    con.execute(delete_query)

                    con.append(quadrant_table_name, result_df)
                    print(
                        f"成功將 {len(result_df)} 筆數據寫入 '{quadrant_table_name}'。"
                    )
                else:
                    print(f"在週期 '{period_name}' 沒有計算出任何象限分析結果。")

        print("\n特徵分析完成。")

    except Exception as e:
        print(f"處理過程中發生錯誤: {e}")
        import traceback

        traceback.print_exc()


def main(args):  # 修改這裡，讓 main 函數接受 args
    # parser = argparse.ArgumentParser(description="特徵分析儀：計算價格/量能變化四象限。") # 解析器移到 if __name__ == "__main__":
    # parser.add_argument("--analytics_db", type=str, default=str(ANALYTICS_DB_PATH), help="分析結果資料庫路徑")
    # args = parser.parse_args() # 解析器移到 if __name__ == "__main__":

    analytics_db_path = Path(args.analytics_db)  # args 現在是傳入的

    # 確保 data 目錄存在 (如果 time_aggregator 未執行過)
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 根據參數選擇執行哪個分析
    if args.run_correlation:
        from .cross_market_analyzer import (
            run_cross_market_correlation_analysis,
            CORE_ASSETS as CMA_CORE_ASSETS,
        )  # 重新使用 CMA_CORE_ASSETS

        assets_for_corr = (
            args.correlation_assets if args.correlation_assets else CMA_CORE_ASSETS
        )
        window_for_corr = (
            args.correlation_window if args.correlation_window else 30
        )  # 匹配 cma 內部預設

        print("準備執行跨市場相關性分析。")
        run_cross_market_correlation_analysis(
            assets_to_analyze=assets_for_corr,
            window=window_for_corr,
            market_db_path=args.market_data_db,
            analytics_db_path=args.analytics_mart_db,
        )

    if args.run_quadrant:
        print("\n準備執行象限分析。")
        # 舊的象限分析使用 --analytics_db 參數指定的路徑
        analyze_features(analytics_db_path)  # analytics_db_path 來自 args.analytics_db

    if args.run_dealer_analysis:
        from .dealer_position_analyzer import (
            run_dealer_position_analysis,
        )  # 只導入需要的

        print("準備執行一級交易商持有量分析。")
        run_dealer_position_analysis(
            market_db_path=args.market_data_db,  # 從 args 傳遞
            analytics_db_path=args.analytics_mart_db,  # 從 args 傳遞
        )

    # 新增：執行奇美拉複合分析
    if args.run_chimera_analysis:
        from apps.feature_analyzer.analyzer import ChimeraAnalyzer  # 修改為絕對導入

        print("\n準備執行奇美拉複合價量與籌碼分析。")
        # ChimeraAnalyzer 使用 analytics_mart_db
        # ChimeraAnalyzer 內部預設 db path 是 analytics_mart.duckdb (相對於專案根目錄)
        # 如果命令行傳入的 analytics_mart_db 與其預設不同，則使用命令行傳入的
        # ChimeraAnalyzer 的建構函數接受 db_path 參數
        chimera_analyzer = ChimeraAnalyzer(db_path=Path(args.analytics_mart_db))
        chimera_analyzer.run_composite_analysis(
            start_date=args.start_date,  # 需要為 Chimera 新增 start_date, end_date, stock_ids 參數
            end_date=args.end_date,
            stock_ids=args.stock_ids,
        )

    # 新增：執行 TAIFEX P/C Ratio 分析
    if args.run_taifex_pc_ratio:
        from apps.feature_analyzer.analyzer import ChimeraAnalyzer  # 確保已導入

        print("\n準備執行 TAIFEX Put/Call Ratio 分析。")
        # ChimeraAnalyzer 實例化時使用 args.analytics_mart_db
        analyzer_instance = ChimeraAnalyzer(db_path=Path(args.analytics_mart_db))
        analyzer_instance.run_taifex_pc_ratio_analysis(
            start_date=args.start_date,  # 可以共用 start/end date
            end_date=args.end_date,
            target_products=args.pc_ratio_products,
        )

    active_analyses = [
        args.run_correlation,
        args.run_quadrant,
        args.run_dealer_analysis,
        args.run_chimera_analysis,  # 新增
        args.run_taifex_pc_ratio,
    ]
    if not any(active_analyses):
        print(
            "未指定要執行的分析類型。請使用 --run_quadrant, --run_correlation, --run_dealer_analysis, --run_chimera_analysis, 或 --run_taifex_pc_ratio。"
        )


if __name__ == "__main__":
    # 設定 Pandas 以顯示所有欄位，方便調試
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 1000)
    import numpy as np  # numpy for np.select

    # 修改 ArgumentParser
    parser = argparse.ArgumentParser(description="特徵分析儀：計算各種金融市場特徵。")
    parser.add_argument(
        "--market_data_db",
        type=str,
        default="market_data.duckdb",
        help="來源市場數據資料庫路徑 (預設: market_data.duckdb)",
    )
    # 將 analytics_mart_db 的預設路徑與 ChimeraAnalyzer 中的 DEFAULT_DB_PATH 對齊
    # ChimeraAnalyzer 中的 DEFAULT_DB_PATH 是基於 analyzer.py 的位置計算的，指向專案根目錄下的 analytics_mart.duckdb
    # 這裡的 run.py 在同一目錄下，所以其相對路徑計算方式應類似或直接使用絕對/已知相對路徑
    # 為簡單起見，這裡我們假設 analytics_mart.duckdb 就在專案根目錄
    # 如果 DEFAULT_DATA_DIR/ANALYTICS_DB_PATH (舊的) 指向 data/analytics_mart.duckdb
    # 而 ChimeraAnalyzer 指向 analytics_mart.duckdb (根目錄)
    # 則需要統一。假設統一到根目錄的 analytics_mart.duckdb
    # 因此，這裡的 default 可以是 "analytics_mart.duckdb"
    # 或者，讓 ChimeraAnalyzer 的 db_path 也由 args.analytics_mart_db 決定，這樣更靈活
    # 目前 ChimeraAnalyzer(db_path=Path(args.analytics_mart_db)) 已經這樣做了。

    # 統一 analytics_mart_db 的預設路徑，使其與 ChimeraAnalyzer 中的 DEFAULT_DB_PATH 計算方式一致
    # 即專案根目錄下的 analytics_mart.duckdb
    # 若 run.py 和 analyzer.py 在同一 apps/feature_analyzer/ 目錄下，
    # 則 DEFAULT_DB_PATH (in analyzer.py) = Path(__file__).resolve().parent.parent.parent / "analytics_mart.duckdb"
    # 在 run.py 中，如果也想指向同一個檔案：
    run_py_default_analytics_mart_path = (
        Path(__file__).resolve().parent.parent.parent / "analytics_mart.duckdb"
    )

    parser.add_argument(
        "--analytics_mart_db",
        type=str,
        default=str(run_py_default_analytics_mart_path),
        help="目標分析結果資料庫路徑 (預設: 專案根目錄下的 analytics_mart.duckdb)",
    )
    # 舊的 --analytics_db 參數，如果不再嚴格需要，可以考慮移除或使其也指向 analytics_mart_db
    parser.add_argument(
        "--analytics_db",
        type=str,
        default=str(ANALYTICS_DB_PATH),
        help="分析結果資料庫路徑 (主要用於舊的象限分析，預設: data/analytics_mart.duckdb)",
    )

    parser.add_argument(
        "--run_quadrant", action="store_true", help="執行價格/量能四象限分析 (舊版)"
    )
    parser.add_argument(
        "--run_correlation", action="store_true", help="執行跨市場相關性分析"
    )
    parser.add_argument(
        "--correlation_assets",
        nargs="+",
        default=None,
        help="用於相關性分析的資產代碼列表",
    )
    parser.add_argument(
        "--correlation_window", type=int, default=None, help="相關性分析的滾動窗口大小"
    )
    parser.add_argument(
        "--run_dealer_analysis", action="store_true", help="執行一級交易商持有量分析"
    )

    # 為奇美拉分析添加新的參數
    parser.add_argument(
        "--run_chimera_analysis",
        action="store_true",
        help="執行奇美拉複合價量與籌碼分析 (日線級別)",
    )
    parser.add_argument(
        "--start_date", type=str, default=None, help="奇美拉分析開始日期 (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end_date", type=str, default=None, help="奇美拉分析結束日期 (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--stock_ids",
        nargs="+",
        default=None,
        help="要進行奇美拉分析的股票代碼列表 (可選，預設處理所有)",
    )
    parser.add_argument(
        "--run_taifex_pc_ratio",
        action="store_true",
        help="執行 TAIFEX Put/Call Ratio 分析",
    )
    parser.add_argument(
        "--pc_ratio_products",
        nargs="+",
        default=["TXO"],
        help="要計算 P/C Ratio 的期交所選擇權商品代號列表 (預設: ['TXO'])",
    )

    args = parser.parse_args()

    active_analyses = [
        args.run_correlation,
        args.run_quadrant,
        args.run_dealer_analysis,
        args.run_chimera_analysis,
        args.run_taifex_pc_ratio,  # 新增
    ]
    if not any(active_analyses):
        print(
            "提醒：未指定明確的分析任務。請使用 --run_quadrant, --run_correlation, --run_dealer_analysis, --run_chimera_analysis, 或 --run_taifex_pc_ratio 來執行特定分析。"
        )

    main(args)
