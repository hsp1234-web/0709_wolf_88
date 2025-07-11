# apps/feature_analyzer/analyzer.py
from __future__ import annotations
import duckdb
import pandas as pd
import numpy as np
import traceback
from pathlib import Path
from datetime import datetime
import pytz # Ensure pytz is imported if used, e.g. datetime.now(pytz.utc)
from typing import Optional, List, Dict, Any

DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent.parent / "analytics_mart.duckdb"
)


class ChimeraAnalyzer:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = str(db_path)
        self.ohlcv_table_1d = "ohlcv_1d"
        self.institutional_trades_table = "institutional_trades"
        self.composite_signal_table = "chimera_daily_signals"
        self.taifex_pc_ratio_table = "taifex_pc_ratios"

    def _connect_db(self) -> duckdb.DuckDBPyConnection:
        try:
            con = duckdb.connect(database=self.db_path, read_only=False)
            print(f"成功連接到資料庫: {self.db_path}")
            return con
        except Exception as e:
            print(f"連接資料庫 {self.db_path} 時發生錯誤: {e}")
            raise

    def _get_daily_ohlcv_data(
        self,
        con: duckdb.DuckDBPyConnection,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        stock_ids: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        query = f"SELECT timestamp AS date, product_id AS stock_id, open, high, low, close, volume FROM {self.ohlcv_table_1d}"
        conditions: List[str] = []
        params: Dict[str, Any] = {}
        if start_date:
            conditions.append("date >= $start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("date <= $end_date")
            params["end_date"] = end_date
        if stock_ids:
            conditions.append(
                "stock_id IN {}".format(
                    tuple(stock_ids) if len(stock_ids) > 1 else f"('{stock_ids[0]}')"
                )
            )
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY stock_id, date"
        print(f"正在讀取日 OHLCV 數據 ({self.ohlcv_table_1d})...")
        try:
            df = con.execute(query, params).fetchdf()
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.date
            print(f"成功讀取 {len(df)} 筆日 OHLCV 數據。")
            return df
        except Exception as e:
            print(f"讀取 {self.ohlcv_table_1d} 表時發生錯誤: {e}")
            return pd.DataFrame()

    def _get_daily_institutional_net_shares(
        self,
        con: duckdb.DuckDBPyConnection,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        stock_ids: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        query = f"""
        SELECT date, stock_id, SUM(net_shares) AS total_net_shares
        FROM {self.institutional_trades_table}"""
        conditions: List[str] = []
        params: Dict[str, Any] = {}
        if start_date:
            conditions.append("date >= $start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("date <= $end_date")
            params["end_date"] = end_date
        if stock_ids:
            conditions.append(
                "stock_id IN {}".format(
                    tuple(stock_ids) if len(stock_ids) > 1 else f"('{stock_ids[0]}')"
                )
            )
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " GROUP BY date, stock_id ORDER BY stock_id, date"
        print(
            f"正在讀取並聚合每日法人淨買賣超數據 ({self.institutional_trades_table})..."
        )
        try:
            df = con.execute(query, params).fetchdf()
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.date
            print(f"成功讀取並聚合 {len(df)} 筆每日法人淨買賣超數據。")
            return df
        except Exception as e:
            print(f"讀取 {self.institutional_trades_table} 表時發生錯誤: {e}")
            return pd.DataFrame()

    def _merge_data(
        self, ohlcv_df: pd.DataFrame, institutional_df: pd.DataFrame
    ) -> pd.DataFrame:
        if ohlcv_df.empty:
            return pd.DataFrame()
        if institutional_df.empty:
            ohlcv_df["total_net_shares"] = np.nan
            return ohlcv_df
        print("正在合併 OHLCV 數據與法人淨買賣超數據...")
        merged_df = pd.merge(
            ohlcv_df, institutional_df, on=["date", "stock_id"], how="left"
        )
        print(f"數據合併完成。合併後共 {len(merged_df)} 筆記錄。")
        return merged_df

    def calculate_quadrant(
        self, price_change_pct: float, volume_change_pct: float
    ) -> int:
        if price_change_pct > 0 and volume_change_pct > 0:
            return 1
        elif price_change_pct < 0 and volume_change_pct > 0:
            return 2
        elif price_change_pct < 0 and volume_change_pct < 0:
            return 3
        elif price_change_pct > 0 and volume_change_pct < 0:
            return 4
        elif price_change_pct == 0 or volume_change_pct == 0:
            if price_change_pct > 0:
                return 1
            if price_change_pct < 0:
                return 2
            if volume_change_pct > 0:
                return 1
            if volume_change_pct < 0:
                return 3
        return 0

    def run_feature_engineering(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "close" not in df.columns or "volume" not in df.columns:
            return df
        print("計算價格與成交量變化百分比...")
        df["price_change_pct"] = (
            df.groupby("stock_id")["close"].pct_change().fillna(0) * 100
        )
        df["volume_prev"] = df.groupby("stock_id")["volume"].shift(1)

        # Default for division by zero or NaN in volume_prev
        default_volume_change = 0.0
        # Condition for volume_prev being 0 but volume > 0 (infinite change, represented as 100% or a large number)
        # Or handle as per specific domain logic, here using 100.0 as a placeholder for significant increase.
        volume_increase_from_zero = 100.0

        conditions = [
            df["volume_prev"].isnull(), # No previous volume, change is undefined or 0
            (df["volume_prev"] == 0) & (df["volume"] == 0), # Zero to Zero, change is 0
            (df["volume_prev"] == 0) & (df["volume"] > 0),  # Zero to Positive, e.g. 100% or specific large value
        ]
        choices = [default_volume_change, default_volume_change, volume_increase_from_zero]

        # Calculate percentage change where volume_prev is not zero
        # Ensure volume_prev is not None and not zero before division
        vol_change_calc = np.where(
            (df["volume_prev"].notnull()) & (df["volume_prev"] != 0),
            (df["volume"] - df["volume_prev"]) / df["volume_prev"] * 100,
            default_volume_change # Default if volume_prev is None or 0 (covered by conditions but good fallback)
        )

        df["volume_change_pct"] = pd.Series(
            np.select(conditions, choices, default=vol_change_calc),
            index=df.index,
        ).fillna(default_volume_change)

        df.drop(columns=["volume_prev"], inplace=True, errors="ignore")
        print("計算價量四象限...")
        df["price_volume_quadrant"] = df.apply(
            lambda row: self.calculate_quadrant(
                row["price_change_pct"], row["volume_change_pct"]
            ),
            axis=1,
        )
        return df

    def _get_price_volume_quadrant_label(self, quadrant_code: int) -> str:
        labels: Dict[int, str] = {
            1: "價漲量增",
            2: "價跌量增",
            3: "價跌量縮",
            4: "價漲量縮",
            0: "價量平移",
        }
        return labels.get(quadrant_code, "象限未知")

    def _calculate_institutional_flow_label(
        self,
        total_net_shares: Optional[float],
        threshold_buy: float = 0,
        threshold_sell: float = 0,
    ) -> str:
        if pd.isna(total_net_shares):
            return "籌碼未知"

        # total_net_shares is a float here (not None or NaN) due to pd.isna check
        if total_net_shares > threshold_buy:
            return "法人買超"
        elif total_net_shares < threshold_sell:
            return "法人賣超"
        else:
            return "法人中性"

    def _apply_composite_signal_logic(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        if "price_volume_quadrant" not in df.columns:
            print("警告: _apply_composite_signal_logic - DataFrame 中缺少 'price_volume_quadrant' 欄位。")
            return df
        print("計算籌碼流向標籤與複合信號...")
        df["institutional_flow_label"] = df["total_net_shares"].apply(
            lambda x: self._calculate_institutional_flow_label(x)
        )
        df["price_volume_label"] = df["price_volume_quadrant"].apply(
            self._get_price_volume_quadrant_label
        )
        df["composite_signal"] = (
            df["price_volume_label"] + "_" + df["institutional_flow_label"]
        )
        print("複合信號計算完成。")
        return df

    def _ensure_composite_signal_table_exists(self, con: duckdb.DuckDBPyConnection) -> None:
        try:
            con.execute(
                f"""
            CREATE TABLE IF NOT EXISTS {self.composite_signal_table} (
                date DATE, stock_id VARCHAR, price_change_pct DOUBLE, volume_change_pct DOUBLE,
                price_volume_quadrant INTEGER, price_volume_label VARCHAR,
                total_net_shares BIGINT, institutional_flow_label VARCHAR, composite_signal VARCHAR,
                PRIMARY KEY (date, stock_id)
            );"""
            )
            print(f"資料表 '{self.composite_signal_table}' 已確認/創建。")
        except Exception as e:
            print(f"檢查或創建 {self.composite_signal_table} 表格時發生錯誤: {e}")
            raise

    def _store_composite_signals(
        self, con: duckdb.DuckDBPyConnection, data_df: pd.DataFrame
    ) -> None:
        if data_df.empty:
            return
        columns_to_store = [
            "date", "stock_id", "price_change_pct", "volume_change_pct",
            "price_volume_quadrant", "price_volume_label", "total_net_shares",
            "institutional_flow_label", "composite_signal",
        ]
        missing_cols = [col for col in columns_to_store if col not in data_df.columns]
        if missing_cols:
            print(f"錯誤: DataFrame 中缺少以下欄位，無法儲存: {missing_cols}")
            return
        df_to_store = data_df[columns_to_store]
        print(
            f"準備將 {len(df_to_store)} 筆複合信號結果儲存到 {self.composite_signal_table}..."
        )
        try:
            if not df_to_store.empty:
                min_date = df_to_store["date"].min()
                max_date = df_to_store["date"].max()
                stock_ids_in_df = tuple(df_to_store["stock_id"].unique())
                if not stock_ids_in_df:
                    return
                stock_id_filter_sql = (
                    f"stock_id = '{stock_ids_in_df[0]}'"
                    if len(stock_ids_in_df) == 1
                    else f"stock_id IN {stock_ids_in_df}"
                )
                delete_query = f"DELETE FROM {self.composite_signal_table} WHERE date >= '{min_date}' AND date <= '{max_date}' AND {stock_id_filter_sql}"
                con.execute(delete_query)
                print(
                    f"已刪除在 {min_date} 至 {max_date} 期間，針對股票 {stock_ids_in_df} 的舊記錄 (如有)。"
                )
            con.append(self.composite_signal_table, df_to_store)
            print(
                f"成功將 {len(df_to_store)} 筆結果寫入 '{self.composite_signal_table}'。"
            )
        except Exception as e:
            print(f"儲存複合信號結果到 DuckDB 時發生錯誤: {e}")
            raise

    def run_composite_analysis(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        stock_ids: Optional[List[str]] = None,
    ) -> None:
        print(
            f"開始執行複合分析 (股票: {stock_ids or '所有'}, 日期: {start_date or '最早'} 至 {end_date or '最新'})..."
        )
        try:
            with self._connect_db() as con:
                self._ensure_composite_signal_table_exists(con)
                ohlcv_df = self._get_daily_ohlcv_data(
                    con, start_date, end_date, stock_ids
                )
                if ohlcv_df.empty:
                    print("沒有讀取到 OHLCV 數據，複合分析中止。")
                    return
                institutional_df = self._get_daily_institutional_net_shares(
                    con, start_date, end_date, stock_ids
                )
                merged_df = self._merge_data(ohlcv_df, institutional_df)
                if merged_df.empty:
                    print("合併後的數據集為空，複合分析中止。")
                    return
                featured_df = self.run_feature_engineering(merged_df)
                final_df = self._apply_composite_signal_logic(featured_df)
                self._store_composite_signals(con, final_df)
                print("複合分析流程執行完畢。")
        except Exception as e:
            print(f"執行複合分析過程中發生嚴重錯誤: {e}")
            traceback.print_exc()

    def _ensure_taifex_pc_ratio_table_exists(self, con: duckdb.DuckDBPyConnection) -> None:
        try:
            con.execute(
                f"""
            CREATE TABLE IF NOT EXISTS {self.taifex_pc_ratio_table} (
                trading_date DATE, product_id VARCHAR, pc_volume_ratio DOUBLE, pc_oi_ratio DOUBLE,
                total_put_volume BIGINT, total_call_volume BIGINT,
                total_put_oi BIGINT, total_call_oi BIGINT,
                calculated_at TIMESTAMPTZ, PRIMARY KEY (trading_date, product_id)
            );"""
            )
            print(f"資料表 '{self.taifex_pc_ratio_table}' 已確認/創建。")
        except Exception as e:
            print(f"檢查或創建 {self.taifex_pc_ratio_table} 表格時發生錯誤: {e}")
            raise

    def run_taifex_pc_ratio_analysis(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        target_products: Optional[List[str]] = None,
    ) -> None:
        if not target_products:
            print("未指定目標產品 (target_products)，P/C Ratio 分析跳過。")
            return

        print(
            f"開始執行 TAIFEX Put/Call Ratio 分析 (產品: {target_products}, 日期: {start_date or '最早'} 至 {end_date or '最新'})..."
        )

        try:
            with self._connect_db() as con:
                self._ensure_taifex_pc_ratio_table_exists(con)

                product_conditions_list: List[str] = []
                for p in target_products:
                    product_conditions_list.append(f"product_id LIKE '{p}%'")
                product_filter_condition = " OR ".join(product_conditions_list)

                case_when_conditions = " ".join(
                    [f"WHEN product_id LIKE '{p}%' THEN '{p}'" for p in target_products]
                )

                final_params: List[Any] = []
                cte_date_conditions_sql_parts: List[str] = []
                if start_date:
                    cte_date_conditions_sql_parts.append("trading_date >= ?")
                    final_params.append(start_date)
                if end_date:
                    cte_date_conditions_sql_parts.append("trading_date <= ?")
                    final_params.append(end_date)

                cte_date_filter_sql = ""
                if cte_date_conditions_sql_parts:
                    cte_date_filter_sql = " AND " + " AND ".join(cte_date_conditions_sql_parts)

                query = f"""
                WITH RelevantOptions AS (
                    SELECT
                        trading_date, product_id,
                        CASE {case_when_conditions} ELSE SUBSTRING(product_id, 1, 3) END AS underlying_product,
                        option_type, volume, open_interest
                    FROM daily_ohlc
                    WHERE option_type IN ('買權', '賣權') AND ({product_filter_condition}) {cte_date_filter_sql}
                )
                SELECT
                    trading_date, underlying_product AS product_id,
                    SUM(CASE WHEN option_type = '賣權' THEN volume ELSE 0 END) AS total_put_volume,
                    SUM(CASE WHEN option_type = '買權' THEN volume ELSE 0 END) AS total_call_volume,
                    SUM(CASE WHEN option_type = '賣權' THEN open_interest ELSE 0 END) AS total_put_oi,
                    SUM(CASE WHEN option_type = '買權' THEN open_interest ELSE 0 END) AS total_call_oi
                FROM RelevantOptions
                GROUP BY trading_date, underlying_product
                ORDER BY trading_date, underlying_product;
                """
                print(f"正在查詢 daily_ohlc 數據以計算 P/C Ratio... Query: {query} with params {final_params}")
                pc_data_df = con.execute(query, final_params).fetchdf()

                if pc_data_df.empty:
                    print("未找到符合條件的選擇權數據計算 P/C Ratio。")
                    return
                print(f"成功查詢到 {len(pc_data_df)} 筆待計算的 P/C Ratio 聚合數據。")

                pc_data_df["pc_volume_ratio"] = np.where(
                    pc_data_df["total_call_volume"] > 0,
                    pc_data_df["total_put_volume"] / pc_data_df["total_call_volume"],
                    np.nan)
                pc_data_df["pc_oi_ratio"] = np.where(
                    pc_data_df["total_call_oi"] > 0,
                    pc_data_df["total_put_oi"] / pc_data_df["total_call_oi"],
                    np.nan)
                pc_data_df["calculated_at"] = datetime.now(pytz.utc)

                if not pc_data_df.empty:
                    min_date_pc = pc_data_df["trading_date"].min()
                    max_date_pc = pc_data_df["trading_date"].max()
                    products_in_batch_pc = tuple(pc_data_df["product_id"].unique())

                    if products_in_batch_pc:
                        product_id_filter_pc_sql = (
                            f"product_id = '{products_in_batch_pc[0]}'"
                            if len(products_in_batch_pc) == 1
                            else f"product_id IN {products_in_batch_pc}")
                        delete_pc_query = f"""
                        DELETE FROM {self.taifex_pc_ratio_table}
                        WHERE trading_date >= '{min_date_pc}' AND trading_date <= '{max_date_pc}' AND {product_id_filter_pc_sql}
                        """
                        con.execute(delete_pc_query)
                        print(f"已刪除 P/C Ratio 表中在 {min_date_pc} 至 {max_date_pc} 期間，針對產品 {products_in_batch_pc} 的舊記錄 (如有)。")

                con.append(self.taifex_pc_ratio_table, pc_data_df[[
                    "trading_date", "product_id", "pc_volume_ratio", "pc_oi_ratio",
                    "total_put_volume", "total_call_volume", "total_put_oi", "total_call_oi",
                    "calculated_at"]])
                print(f"成功計算並儲存 {len(pc_data_df)} 筆 P/C Ratio 數據到 {self.taifex_pc_ratio_table}。")
        except Exception as e:
            print(f"執行 TAIFEX P/C Ratio 分析過程中發生嚴重錯誤: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    print("執行 ChimeraAnalyzer 初步測試...")
    test_db_path = Path("./temp_test_chimera.duckdb")
    if test_db_path.exists():
        test_db_path.unlink(missing_ok=True)
    analyzer = ChimeraAnalyzer(db_path=test_db_path)
    try:
        with analyzer._connect_db() as con:
            con.execute(f"""CREATE TABLE IF NOT EXISTS {analyzer.ohlcv_table_1d} (timestamp TIMESTAMP, product_id VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT, PRIMARY KEY (timestamp, product_id));""")
            ohlcv_data = [
                (pd.to_datetime("2023-01-01").date(), "TSMC", 100.0, 105.0, 99.0, 102.0, 10000),
                (pd.to_datetime("2023-01-02").date(), "TSMC", 102.0, 108.0, 101.0, 107.0, 12000),
            ]
            con.executemany(f"INSERT INTO {analyzer.ohlcv_table_1d} VALUES (?, ?, ?, ?, ?, ?, ?)", ohlcv_data)

            con.execute(f"""CREATE TABLE IF NOT EXISTS {analyzer.institutional_trades_table} (date DATE, stock_id VARCHAR, investor_type VARCHAR, buy_shares BIGINT, sell_shares BIGINT, net_shares BIGINT, PRIMARY KEY (date, stock_id, investor_type));""")
            institutional_data = [(pd.to_datetime("2023-01-01").date(), "TSMC", "Foreign_Dealer", 500, 100, 400)]
            con.executemany(f"INSERT INTO {analyzer.institutional_trades_table} VALUES (?, ?, ?, ?, ?, ?)", institutional_data)

            con.execute("""CREATE TABLE IF NOT EXISTS daily_ohlc (trading_date DATE, product_id VARCHAR, expiry_month VARCHAR, strike_price DOUBLE, option_type VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, settlement_price DOUBLE, volume UBIGINT, open_interest UBIGINT, trading_session VARCHAR, source_file VARCHAR, member_file VARCHAR, transformed_at TIMESTAMPTZ);""")
            pc_test_data = [
                (pd.to_datetime("2023-01-01").date(), "TXO01C18000", "202301", 18000.0, "買權", 1.0,1.0,1.0,1.0,1.0, 100, 1000, "一般", "f.csv", None, datetime.now(pytz.utc)),
                (pd.to_datetime("2023-01-01").date(), "TXO01P17000", "202301", 17000.0, "賣權", 1.0,1.0,1.0,1.0,1.0, 80, 800, "一般", "f.csv", None, datetime.now(pytz.utc)),
            ]
            con.executemany("INSERT INTO daily_ohlc VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", pc_test_data)

            print("\n--- 執行完整的複合分析流程 ---")
            analyzer.run_composite_analysis(stock_ids=["TSMC"])
            verify_df = con.execute(f"SELECT * FROM {analyzer.composite_signal_table} WHERE stock_id = 'TSMC'").fetchdf()
            print(f"複合信號結果:\n{verify_df}")

            print("\n--- 執行 TAIFEX P/C Ratio 分析 ---")
            analyzer.run_taifex_pc_ratio_analysis(target_products=["TXO"], start_date="2023-01-01", end_date="2023-01-01")
            verify_pc_df = con.execute(f"SELECT * FROM {analyzer.taifex_pc_ratio_table} WHERE product_id = 'TXO'").fetchdf()
            print(f"P/C Ratio 結果:\n{verify_pc_df}")

    except Exception as e:
        print(f"初步測試時發生錯誤: {e}")
        traceback.print_exc()
    finally:
        if test_db_path.exists():
            print(f"提醒：測試資料庫 {test_db_path} 未被自動刪除，方便手動檢查。")
    print("ChimeraAnalyzer 初步測試完畢。")
