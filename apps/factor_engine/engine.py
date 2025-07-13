from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parents[
        2
    ]  # apps/factor_engine/engine.py -> project_root
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    project_root = Path.cwd()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
# --- 標準化「路徑自我校正」樣板碼 END ---

from core.db.db_manager import DBManager
from core.logger import LogManager


class FactorEngine:
    """
    因子引擎核心類別。
    負責從資料庫讀取市場數據，計算分析因子，並回傳結果。
    """

    def __init__(self, db_manager: DBManager, log_manager: LogManager):
        """
        初始化因子引擎。

        Args:
            db_manager: DBManager 的實例，用於數據庫操作。
            log_manager: LogManager 的實例，用於日誌記錄。
        """
        self.db_manager = db_manager
        self.log_manager = log_manager
        self.log_manager.log("DEBUG", "FactorEngine 已初始化。")

    def get_prices_for_ticker(self, ticker: str) -> pd.DataFrame:
        """
        從 MarketPrices_Daily 表格中讀取指定股票的完整 OHLCV 歷史數據。
        """
        try:
            query = """
            SELECT datetime, open, high, low, close, volume
            FROM MarketPrices_Daily
            WHERE ticker = ?
            ORDER BY datetime ASC
            """
            result_df = self.db_manager.execute_query(query, params=[ticker])

            if not result_df.empty and "datetime" in result_df.columns:
                result_df["datetime"] = pd.to_datetime(result_df["datetime"])
                if result_df["datetime"].dt.tz is None:
                    result_df["datetime"] = result_df["datetime"].dt.tz_localize("UTC")
                else:
                    result_df["datetime"] = result_df["datetime"].dt.tz_convert("UTC")
                result_df = result_df.set_index("datetime")

            result_df.columns = [col.lower() for col in result_df.columns]
            self.log_manager.log(
                "DEBUG", f"成功為 ticker {ticker} 獲取了 {len(result_df)} 筆價格數據。"
            )
            return result_df
        except Exception as e:
            self.log_manager.log("ERROR", f"讀取股票 {ticker} 的價格數據失敗: {e}")
            return pd.DataFrame()

    def calculate_price_volatility(
        self, dataframe: pd.DataFrame, n_days: int = 20
    ) -> pd.Series | None:
        if dataframe.empty or "close" not in dataframe.columns:
            self.log_manager.log(
                "WARNING", "DataFrame 為空或缺少 'close' 欄位，無法計算價格波動率。"
            )
            return None
        dataframe["log_return"] = np.log(
            dataframe["close"].astype(float) / dataframe["close"].astype(float).shift(1)
        )
        price_volatility = dataframe["log_return"].rolling(window=n_days).std()
        self.log_manager.log("DEBUG", f"計算了 {n_days}日價格波動率。")
        return price_volatility

    def calculate_volume_volatility(
        self, dataframe: pd.DataFrame, n_days: int = 20
    ) -> pd.Series | None:
        if dataframe.empty or "volume" not in dataframe.columns:
            self.log_manager.log(
                "WARNING", "DataFrame 為空或缺少 'volume' 欄位，無法計算成交量波動率。"
            )
            return None
        dataframe["volume_change_rate"] = (
            dataframe["volume"].astype(float).pct_change(fill_method=None)
        )
        dataframe.replace([np.inf, -np.inf], np.nan, inplace=True)
        volume_volatility = dataframe["volume_change_rate"].rolling(window=n_days).std()
        self.log_manager.log("DEBUG", f"計算了 {n_days}日成交量波動率。")
        return volume_volatility

    def calculate_rsi(
        self, dataframe: pd.DataFrame, n_days: int = 14
    ) -> pd.Series | None:
        if dataframe.empty or "close" not in dataframe.columns:
            self.log_manager.log(
                "WARNING", "DataFrame 為空或缺少 'close' 欄位，無法計算 RSI。"
            )
            return None
        if not isinstance(dataframe.index, pd.DatetimeIndex):
            self.log_manager.log(
                "WARNING",
                "DataFrame 的索引不是 DatetimeIndex，pandas-ta 可能無法正確計算 RSI。",
            )
            return None
        try:
            if not hasattr(dataframe, "ta"):
                self.log_manager.log(
                    "ERROR",
                    "DataFrame 缺少 'ta' 擴展。Pandas TA 可能未正確加載或與 Pandas 版本不兼容。",
                )
                return None
            rsi_series = dataframe.ta.rsi(length=n_days)
            self.log_manager.log("DEBUG", f"計算了 {n_days}日 RSI。")
            return rsi_series
        except Exception as e:
            self.log_manager.log("ERROR", f"計算 RSI 失敗: {e}")
            return None

    def get_treasury_yields(self) -> pd.DataFrame:
        try:
            query = """
            SELECT date, term, yield
            FROM TreasuryYields_Daily
            ORDER BY date ASC, term ASC;
            """
            raw_yields_df = self.db_manager.execute_query(query)
            if raw_yields_df.empty:
                self.log_manager.log("WARNING", "TreasuryYields_Daily 表格中沒有數據。")
                return pd.DataFrame()
            raw_yields_df["date"] = pd.to_datetime(raw_yields_df["date"])
            if raw_yields_df["date"].dt.tz is None:
                raw_yields_df["date"] = raw_yields_df["date"].dt.tz_localize("UTC")
            else:
                raw_yields_df["date"] = raw_yields_df["date"].dt.tz_convert("UTC")

            def format_term(term_str):
                if "Yr" in term_str:
                    return term_str.replace(" Yr", "Y")
                elif "Mo" in term_str:
                    return term_str.replace(" Mo", "M")
                return term_str

            raw_yields_df["term_formatted"] = raw_yields_df["term"].apply(format_term)
            yields_pivot_df = raw_yields_df.pivot_table(
                index="date", columns="term_formatted", values="yield"
            )
            self.log_manager.log(
                "INFO",
                f"成功從 TreasuryYields_Daily 讀取並轉換了 {len(yields_pivot_df)} 筆殖利率數據。",
            )
            return yields_pivot_df
        except Exception as e:
            self.log_manager.log("ERROR", f"讀取公債殖利率數據失敗: {e}")
            return pd.DataFrame()

    def calculate_yield_spreads(self, yields_dataframe: pd.DataFrame) -> pd.DataFrame:
        if yields_dataframe.empty:
            self.log_manager.log("WARNING", "殖利率數據為空，無法計算利差。")
            return pd.DataFrame()
        spreads_df = pd.DataFrame(index=yields_dataframe.index)
        if "10Y" in yields_dataframe.columns and "2Y" in yields_dataframe.columns:
            yield_10y = pd.to_numeric(yields_dataframe["10Y"], errors="coerce")
            yield_2y = pd.to_numeric(yields_dataframe["2Y"], errors="coerce")
            spreads_df["spread_10y_2y"] = yield_10y - yield_2y
            self.log_manager.log("INFO", "已計算 spread_10y_2y。")
        if "10Y" in yields_dataframe.columns and "3M" in yields_dataframe.columns:
            yield_10y = pd.to_numeric(yields_dataframe["10Y"], errors="coerce")
            yield_3m = pd.to_numeric(yields_dataframe["3M"], errors="coerce")
            spreads_df["spread_10y_3m"] = yield_10y - yield_3m
            self.log_manager.log("INFO", "已計算 spread_10y_3m。")
        return spreads_df

    def calculate_credit_spread_proxy(self) -> pd.DataFrame:
        self.log_manager.log("INFO", "開始計算信用利差代理指標 (HYG/LQD 價格比率)...")
        hyg_prices_df = self.get_prices_for_ticker("HYG")
        if hyg_prices_df.empty:
            return pd.DataFrame()
        lqd_prices_df = self.get_prices_for_ticker("LQD")
        if lqd_prices_df.empty:
            return pd.DataFrame()

        merged_prices = pd.merge(
            hyg_prices_df[["close"]],
            lqd_prices_df[["close"]],
            left_index=True,
            right_index=True,
            how="inner",
            suffixes=("_hyg", "_lqd"),
        )
        if merged_prices.empty:
            self.log_manager.log("WARNING", "HYG 和 LQD 沒有共同交易日期。")
            return pd.DataFrame()

        merged_prices["hyg_close"] = pd.to_numeric(
            merged_prices["close_hyg"], errors="coerce"
        )
        merged_prices["lqd_close"] = pd.to_numeric(
            merged_prices["close_lqd"], errors="coerce"
        )

        proxy_df = pd.DataFrame(index=merged_prices.index)
        proxy_df["HYG_LQD_price_ratio"] = merged_prices["hyg_close"] / merged_prices[
            "lqd_close"
        ].replace(0, np.nan)
        proxy_df.dropna(inplace=True)

        self.log_manager.log(
            "INFO", f"成功計算了 {len(proxy_df)} 筆 HYG/LQD 價格比率數據。"
        )
        return proxy_df


if __name__ == "__main__":
    # This block is for direct execution testing, we create a dummy logger.
    output_dir = project_root / "output"
    log_db_path = output_dir / "logs" / "standalone_test.sqlite"
    archive_dir = output_dir / "logs" / "archive"
    dummy_logger = LogManager(db_path=log_db_path, archive_dir=archive_dir)
    dummy_logger.log(
        "INFO",
        "因子引擎 (FactorEngine) 已定義。此檔案主要作為模組導入，不建議直接執行。",
    )
    dummy_logger.archive_to_file()
