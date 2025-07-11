# 替換檔案: apps/stress_index_calculator/run.py
import os
import sys
import argparse
import duckdb
import pandas as pd
from datetime import datetime, timedelta

# --- 新版 pathlib 標準化路徑定義 ---
from pathlib import Path  # 導入 Path

# 路徑自我校正樣板碼
try:
    # 使用 Path 物件來獲取專案根目錄
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except Exception as e:  # Catches NameError as well
    print(f"專案路徑校正時發生錯誤: {e}", file=sys.stderr)
    # Fallback for interactive/different execution contexts
    if "project_root" not in locals() and isinstance(e, NameError):
        print("嘗試備用路徑校正方法...")
        project_root = Path(os.getcwd())
        # Adjust project_root if cwd is deeper
        if (
            project_root.name == "stress_index_calculator"
            and project_root.parent.name == "apps"
        ):
            project_root = project_root.parent.parent
        elif project_root.name == "apps":
            project_root = project_root.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        print(f"備用路徑校正完成，project_root 設定為: {project_root}")
    else:
        sys.exit(1)
# --- 標準化路徑定義結束 ---

from core.utils import setup_logger
from apps.stress_index_calculator.calculator import (
    calculate_derived_indicators,
    calculate_stress_index,
    calculate_macd_momentum,
)

import logging  # 導入 logging 模組
# --- 常數定義 ---
SOURCE_DB_PATH = project_root / "market_data.duckdb"  # 使用 pathlib
TARGET_DB_PATH = project_root / "analytics_mart.duckdb"  # 使用 pathlib
STRESS_INDEX_TABLE = "dealer_stress_index"


logger = setup_logger(
    "stress_index_calculator", level=logging.DEBUG
)  # 設定日誌級別為 DEBUG


def fetch_source_data(
    db_path: Path, start_date_str: str, end_date_str: str
) -> pd.DataFrame:  # db_path 類型改為 Path
    """從來源資料庫提取所有需要的真實數據並合併"""
    db_path_str = str(db_path)  # 轉換為字串供日誌和 os.path.exists 使用
    logger.info(
        f"正在從 {db_path_str} 提取真實數據，日期範圍: {start_date_str} 至 {end_date_str}..."
    )

    # 檢查資料庫檔案是否存在
    if not db_path.exists():  # 使用 Path 物件的 exists 方法
        logger.error(f"關鍵錯誤：來源資料庫 {db_path_str} 不存在。無法提取真實數據。")
        return pd.DataFrame()

    try:
        with duckdb.connect(
            database=db_path_str, read_only=True
        ) as con:  # 確保傳遞字串
            # 建立一個包含所有交易日的基礎日期表
            # 使用 Yahoo Finance 的 ^GSPC (S&P 500) 作為交易日曆的基準
            # 首先檢查 daily_ohlcv 表是否存在且有 ^GSPC 數據
            check_gspc_query = f"""
            SELECT COUNT(*)
            FROM daily_ohlcv
            WHERE symbol = '^GSPC'
              AND date >= '{start_date_str}'
              AND date <= '{end_date_str}';
            """
            logger.debug(f"Executing SQL: {check_gspc_query}")
            print(f"DEBUG SQL QUERY STRING: ---{check_gspc_query}---")  # Direct print
            gspc_count_result = con.execute(check_gspc_query).fetchone()
            if gspc_count_result is None or gspc_count_result[0] == 0:
                logger.error(
                    f"交易日曆基準 (^GSPC) 在指定日期範圍 {start_date_str} 至 {end_date_str} 內無數據。"
                )
                logger.error("無法建立可靠的交易日序列，數據提取中止。")
                return pd.DataFrame()

            trading_days_view_query = f"""
                CREATE OR REPLACE TEMP VIEW trading_days AS
                SELECT DISTINCT date::DATE AS date_col  -- 顯式轉換為 DATE 型別並重命名以避免衝突
                FROM daily_ohlcv
                WHERE symbol = '^GSPC'
                  AND date >= '{start_date_str}'::DATE
                  AND date <= '{end_date_str}'::DATE;
            """
            logger.debug(f"Executing SQL: {trading_days_view_query}")
            print(
                f"DEBUG SQL QUERY STRING: ---{trading_days_view_query}---"
            )  # Direct print
            con.execute(trading_days_view_query)
            logger.info("交易日曆 TEMP VIEW 'trading_days' 創建成功。")

            # 提取並準備各項數據
            # 1. FRED 數據 (SOFR, DGS10, DGS2, VIX, WRESBAL)
            fred_series_ids = "('SOFR', 'DGS10', 'DGS2', 'VIXCLS', 'WRESBAL')"
            fred_query = f"""
                SELECT date::DATE AS date_col, series_id, value
                FROM fred_data
                WHERE series_id IN {fred_series_ids}
                  AND date >= '{start_date_str}'::DATE
                  AND date <= '{end_date_str}'::DATE;
            """
            logger.debug(f"Executing SQL: {fred_query}")
            print(f"DEBUG SQL QUERY STRING: ---{fred_query}---")  # Direct print
            fred_df_raw = con.execute(fred_query).fetchdf()
            if fred_df_raw.empty:
                logger.warning("FRED 數據在指定日期範圍內為空。")
                # 創建一個空的 pivot 表以避免後續 join 出錯
                fred_df_pivot = pd.DataFrame(
                    columns=["SOFR", "DGS10", "DGS2", "VIX", "Reserves"]
                )
            else:
                fred_df_pivot = fred_df_raw.pivot(
                    index="date_col", columns="series_id", values="value"
                )
                fred_df_pivot.rename(
                    columns={"VIXCLS": "VIX", "WRESBAL": "Reserves"}, inplace=True
                )
            logger.info(
                f"FRED 數據提取完成，原始數據 {len(fred_df_raw)} 筆, Pivot 後 {len(fred_df_pivot)} 筆。"
            )

            # 2. Yahoo Finance 數據 (^MOVE)
            move_query = f"""
                SELECT date::DATE AS date_col, close as Volatility_Index
                FROM daily_ohlcv
                WHERE symbol = '^MOVE'
                  AND date >= '{start_date_str}'::DATE
                  AND date <= '{end_date_str}'::DATE;
            """
            logger.debug(f"Executing SQL: {move_query}")
            print(f"DEBUG SQL QUERY STRING: ---{move_query}---")  # Direct print
            move_df = con.execute(move_query).fetchdf()
            if not move_df.empty:
                move_df = move_df.set_index("date_col")
            logger.info(f"^MOVE 數據提取完成，共 {len(move_df)} 筆。")

            # 3. NY Fed 一級交易商數據
            nyfed_query = f"""
                SELECT date::DATE AS date_col, Total_Positions as Total_Gross_Positions_Millions
                FROM primary_dealer_positions
                WHERE date >= '{start_date_str}'::DATE
                  AND date <= '{end_date_str}'::DATE;
            """
            logger.debug(f"Executing SQL: {nyfed_query}")
            print(f"DEBUG SQL QUERY STRING: ---{nyfed_query}---")  # Direct print
            nyfed_df = con.execute(nyfed_query).fetchdf()
            if not nyfed_df.empty:
                nyfed_df = nyfed_df.set_index("date_col")
            logger.info(f"NY Fed 數據提取完成，共 {len(nyfed_df)} 筆。")

            # 合併數據的基礎 DataFrame
            base_df_query = "SELECT date_col FROM trading_days ORDER BY date_col;"
            logger.debug(f"Executing SQL: {base_df_query}")
            print(f"DEBUG SQL QUERY STRING: ---{base_df_query}---")  # Direct print
            base_df = con.execute(base_df_query).fetchdf()
            if base_df.empty:
                logger.error("交易日曆 'trading_days' 為空，無法進行數據合併。")
                return pd.DataFrame()
            base_df = base_df.set_index("date_col")
            logger.info(f"基礎交易日曆提取完成，共 {len(base_df)} 個交易日。")

            # 合併數據並使用前向填充 (ffill)
            # 確保索引名稱一致以便合併
            final_df = base_df.copy()
            if not fred_df_pivot.empty:
                final_df = final_df.join(fred_df_pivot, how="left")
            else:  # 如果 FRED 數據為空，確保欄位存在
                for col in ["SOFR", "DGS10", "DGS2", "VIX", "Reserves"]:
                    final_df[col] = pd.NA

            if not move_df.empty:
                final_df = final_df.join(move_df, how="left")
            else:  # 如果 MOVE 數據為空
                final_df["Volatility_Index"] = pd.NA

            if not nyfed_df.empty:
                final_df = final_df.join(nyfed_df, how="left")
            else:  # 如果 NYFED 數據為空
                final_df["Total_Gross_Positions_Millions"] = pd.NA

            # 前向填充處理缺失值
            # 某些數據源（如 NYFED）更新頻率較低，ffill 時限制lookback天數是個好習慣，但這裡先簡單 ffill
            final_df.ffill(inplace=True)

            # 確保欄位為數值
            cols_to_convert = [
                "SOFR",
                "DGS10",
                "DGS2",
                "VIX",
                "Reserves",
                "Volatility_Index",
                "Total_Gross_Positions_Millions",
            ]
            for col in cols_to_convert:
                if col in final_df.columns:
                    final_df[col] = pd.to_numeric(final_df[col], errors="coerce")
                else:  # 如果 join 後某個預期欄位不存在 (例如原始數據完全缺失)
                    logger.warning(f"預期欄位 {col} 在合併後不存在，將以 NA 填充。")
                    final_df[col] = pd.NA  # 或 np.nan

            # 篩選掉完全沒有數據的行 (如果 ffill 後仍然是 NaN)
            # 這裡假設日期索引是 'date_col'
            # final_df.dropna(how='all', subset=cols_to_convert, inplace=True)

            logger.info(
                f"成功提取並合併 {len(final_df)} 筆數據。最終欄位: {final_df.columns.tolist()}"
            )
            # 將索引名稱改回 'date' 以符合 calculator.py 的預期
            final_df.index.name = "date"
            return final_df

    except duckdb.Error as e:  # 捕捉 DuckDB 特有的錯誤
        logger.error(f"DuckDB 操作時發生錯誤: {e}")
        logger.error(
            f"涉及的查詢可能包含錯誤的表名、欄位名，或日期範圍 '{start_date_str}' 至 '{end_date_str}' 內無有效數據。"
        )
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"提取真實數據時發生未預期錯誤: {e}", exc_info=True)
        return pd.DataFrame()


def save_results(
    df: pd.DataFrame, db_path: Path, table_name: str
):  # db_path 類型改為 Path
    """將計算結果儲存到目標資料庫"""
    db_path_str = str(db_path)  # 轉換為字串
    if df.empty or "Dealer_Stress_Index" not in df.columns:
        logger.warning("數據為空或缺少關鍵欄位 'Dealer_Stress_Index'，未執行儲存。")
        return

    logger.info(
        f"正在將 {len(df)} 筆計算結果儲存至 {db_path_str} 的 {table_name} 表..."
    )
    try:
        with duckdb.connect(
            database=db_path_str, read_only=False
        ) as con:  # 確保傳遞字串
            # 確保索引 (日期) 被儲存為一個常規列
            df_to_save = df.reset_index()
            con.register("result_df", df_to_save)
            # 確保日期欄位名稱正確，假設索引名是 'date'
            if (
                "date" not in df_to_save.columns
                and "index" in df_to_save.columns
                and pd.api.types.is_datetime64_any_dtype(df_to_save["index"])
            ):
                df_to_save.rename(columns={"index": "date"}, inplace=True)

            con.execute(
                f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM result_df"
            )
        logger.info("儲存成功。")
    except Exception as e:
        logger.error(f"儲存結果時發生錯誤: {e}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="計算交易商壓力指數。")
    today = datetime.now()
    # 預設回測5年，但確保開始日期不早於 DuckDB 中數據的最早日期 (假設為 2000-01-01)
    # 實際應根據數據庫的真實最早日期調整
    five_years_ago = today - timedelta(days=5 * 365)
    earliest_data_date = datetime(2000, 1, 1)  # 假設值
    default_start_dt = max(five_years_ago, earliest_data_date)
    default_start = default_start_dt.strftime("%Y-%m-%d")
    default_end = today.strftime("%Y-%m-%d")

    parser.add_argument(
        "--start_date",
        type=str,
        default=default_start,
        help="計算開始日期 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end_date", type=str, default=default_end, help="計算結束日期 (YYYY-MM-DD)"
    )

    args = parser.parse_args()
    logger.info(f"壓力指數計算任務啟動，日期範圍: {args.start_date} 至 {args.end_date}")

    # 1. 提取數據
    merged_df = fetch_source_data(SOURCE_DB_PATH, args.start_date, args.end_date)
    if merged_df.empty:
        logger.critical("無法獲取來源數據或數據處理後為空，任務中止。")
        sys.exit(1)

    logger.info(f"數據提取完成，共獲得 {len(merged_df)} 行數據。")
    logger.debug(f"提取數據的欄位: {merged_df.columns.tolist()}")
    logger.debug(f"提取數據的索引名稱: {merged_df.index.name}")

    # 2. 執行計算
    # 確保 calculator.py 中的 config 參數與這裡一致
    config = {
        "rolling_window_days": 252,
        "weights": {
            "sofr_dev": 0.20,
            "spread_inv": 0.20,
            "gross_pos": 0.15,
            "move": 0.20,
            "vix": 0.15,
            "pos_res_ratio": 0.10,  # 確保 calculator.py 的 component_mapping 中有對應的 'Pos_Res_Ratio'
        },
        "smoothing_window_stress_index": 5,
        "threshold_ratio_color": 90,  # 根據 calculator.py, 此參數用於 calculate_stress_index
        "enable_macd_momentum_plot": True,  # 此參數用於 calculate_macd_momentum
        "macd_params": {
            "fast": 12,
            "slow": 26,
            "signal": 9,
        },  # 用於 calculate_macd_momentum
        "macd_colors": {
            "blue": "#6495ED",
            "green": "#3CB371",
            "red": "#B22222",
        },  # 用於 calculate_macd_momentum
    }

    # 檢查 calculator.py 是否有 calculate_all_indicators 函式
    # 如果有，則應該調用它，並將 AppConfig (包含 calculation_params) 傳遞過去
    # 目前的 calculator.py 結構是分開調用，我們暫時遵循

    logger.info("開始計算衍生指標...")
    df_derived = calculate_derived_indicators(merged_df)
    logger.info(f"衍生指標計算完成。DataFrame 維度: {df_derived.shape}")
    logger.debug(f"衍生指標 DataFrame 欄位: {df_derived.columns.tolist()}")

    logger.info("開始計算壓力指數...")
    df_stress = calculate_stress_index(
        df_derived, config
    )  # config 應只包含 calculate_stress_index 所需的參數
    logger.info(f"壓力指數計算完成。DataFrame 維度: {df_stress.shape}")
    logger.debug(f"壓力指數 DataFrame 欄位: {df_stress.columns.tolist()}")

    logger.info("開始計算 MACD 動能指標...")
    final_df = calculate_macd_momentum(
        df_stress, config
    )  # config 應只包含 calculate_macd_momentum 所需的參數
    logger.info(f"MACD 動能指標計算完成。最終 DataFrame 維度: {final_df.shape}")
    logger.debug(f"最終 DataFrame 欄位: {final_df.columns.tolist()}")

    # 3. 儲存結果
    save_results(final_df, TARGET_DB_PATH, STRESS_INDEX_TABLE)

    logger.info("壓力指數計算流程執行完畢。")


if __name__ == "__main__":
    main()
