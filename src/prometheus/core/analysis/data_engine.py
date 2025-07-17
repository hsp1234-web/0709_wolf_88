# 檔案路徑: core/analysis/data_engine.py
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import duckdb
import pandas as pd

from prometheus.core.clients.client_factory import ClientFactory
from prometheus.core.logging.log_manager import LogManager

logger = LogManager.get_instance().get_logger("DataEngine")


class DataEngine:
    """
    數據引擎核心。
    負責協調所有數據客戶端，計算多維度指標，
    並生成一份「高密度市場狀態快照」。
    """

    def __init__(
        self,
        db_connection=None,
    ):
        """
        透過依賴注入初始化，傳入所有需要的數據客戶端。
        """
        self.yf_client = ClientFactory.get_client("yfinance")
        self.fred_client = ClientFactory.get_client("fred")
        self.taifex_client = ClientFactory.get_client("taifex")

        # --- 新增程式碼 ---
        if db_connection:
            self.db_con = db_connection
            logger.info("使用傳入的 DuckDB 連接。")
        else:
            db_path = Path("prometheus_fire.duckdb")
            self.db_con = duckdb.connect(database=str(db_path), read_only=False)
            logger.info("DuckDB 連接已建立。")

        self._initialize_db()

    def _initialize_db(self):
        """如果 hourly_time_series 表不存在，則創建它。"""
        try:
            self.db_con.execute("SELECT 1 FROM hourly_time_series LIMIT 1")
            logger.debug("'hourly_time_series' 表已存在。")
        except duckdb.CatalogException:
            logger.info("'hourly_time_series' 表不存在，正在創建...")
            schema = {
                "timestamp": "TIMESTAMP",
                "spy_open": "DOUBLE",
                "spy_high": "DOUBLE",
                "spy_low": "DOUBLE",
                "spy_close": "DOUBLE",
                "spy_volume": "BIGINT",
                "qqq_close": "DOUBLE",
                "tlt_close": "DOUBLE",
                "btc_usd_close": "DOUBLE",
                "nq_f_close": "DOUBLE",
                "es_f_close": "DOUBLE",
                "ym_f_close": "DOUBLE",
                "cl_f_close": "DOUBLE",
                "gc_f_close": "DOUBLE",
                "si_f_close": "DOUBLE",
                "zb_f_close": "DOUBLE",
                "zn_f_close": "DOUBLE",
                "zt_f_close": "DOUBLE",
                "zf_f_close": "DOUBLE",
                "gld_close": "DOUBLE",
                "shy_close": "DOUBLE",
                "iei_close": "DOUBLE",
                "aapl_close": "DOUBLE",
                "msft_close": "DOUBLE",
                "nvda_close": "DOUBLE",
                "goog_close": "DOUBLE",
                "tsm_close": "DOUBLE",
                "601318_ss_close": "DOUBLE",
                "688981_ss_close": "DOUBLE",
                "0981_hk_close": "DOUBLE",
                "spy_rsi_14_1h": "DOUBLE",
                "spy_macd_signal_1h": "DOUBLE",
                "spy_bbands_width_pct_1h": "DOUBLE",
                "spy_vwap_1h": "DOUBLE",
                "spy_atr_14_1h": "DOUBLE",
                "spy_vwap_deviation_pct_1h": "DOUBLE",
                "spy_momentum_1h_100": "DOUBLE",
                "spy_bollinger_band_upper_1h": "DOUBLE",
                "spy_bollinger_band_lower_1h": "DOUBLE",
                "spy_bb_middle_band_20h": "DOUBLE",
                "spy_bb_upper_band_20h": "DOUBLE",
                "spy_bb_lower_band_20h": "DOUBLE",
                "spy_bb_band_width_pct_20h": "DOUBLE",
                "spy_bb_percent_b_20h": "DOUBLE",
                "spy_gex_total": "DOUBLE",
                "spy_gex_flip_level": "DOUBLE",
                "spy_max_pain": "DOUBLE",
                "spy_call_wall_strike": "DOUBLE",
                "spy_put_wall_strike": "DOUBLE",
                "spy_pc_ratio_volume": "DOUBLE",
                "spy_pc_ratio_oi": "DOUBLE",
                "spy_iv_atm_1m": "DOUBLE",
                "spy_skew_quantified": "DOUBLE",
                "spy_vanna_exposure": "DOUBLE",
                "spy_charm_exposure": "DOUBLE",
                "vvix_close": "DOUBLE",
            }
            columns_def = ", ".join(
                [f'"{col}" {dtype}' for col, dtype in schema.items()]
            )
            create_table_sql = f"CREATE TABLE hourly_time_series ({columns_def})"
            self.db_con.execute(create_table_sql)
            logger.info("'hourly_time_series' 表已成功創建。")

    def close(self):
        self.db_con.close()
        logger.info("DuckDB 連接已關閉。")

    def _query_cache(self, dt):
        """
        從 DuckDB 快取中查詢單一時間點的數據。
        :param dt: (datetime) 要查詢的時間戳。
        :return: (pandas.DataFrame) 如果找到數據則返回單行 DataFrame，否則返回 None。
        """
        query = "SELECT * FROM hourly_time_series WHERE timestamp = ?"
        result_df = self.db_con.execute(query, [dt]).fetch_df()

        if not result_df.empty:
            logger.debug(f"CACHE HIT: 於 {dt} 找到數據。")
            return result_df
        else:
            logger.debug(f"CACHE MISS: 於 {dt} 未找到數據。")
            return None

    def _write_cache(self, data_df):
        """
        將新的數據 DataFrame 寫入 DuckDB 快取。
        :param data_df: (pandas.DataFrame) 包含單行待寫入數據的 DataFrame。
        """
        self.db_con.append("hourly_time_series", data_df)
        logger.debug(f"CACHE WRITE: 已將 {data_df['timestamp'].iloc[0]} 的數據寫入快取。")

    def _calculate_technicals(self, ohlcv: pd.DataFrame) -> Dict[str, Any]:
        """
        私有方法：計算基礎技術指標。
        【Jules的任務】: 在此實現 RSI, MACD, BBands 等計算邏輯。
        """
        technicals = {}
        # 範例：計算20日均線
        if "close" in ohlcv.columns and len(ohlcv) >= 20:
            technicals["MA20"] = round(
                ohlcv["close"].rolling(window=20).mean().iloc[-1], 2
            )
        else:
            technicals["MA20"] = None

        # TODO: 實現 RSI, MACD, BBands 等指標計算
        technicals["RSI_14D"] = 70  # 暫用假數據
        technicals["RSI_status"] = "超買"  # 暫用假數據

        return technicals

    def _calculate_approx_credit_spread(self) -> float:
        """
        計算近似信用利差 (HYG價格 / IEF價格)。
        """
        import asyncio
        try:
            hyg_data = asyncio.run(self.yf_client.fetch_data("HYG", period="1d"))
            ief_data = asyncio.run(self.yf_client.fetch_data("IEF", period="1d"))

            if (
                hyg_data.empty
                or "close" not in hyg_data.columns
                or hyg_data["close"].iloc[-1] is None
            ):
                logger.warning("無法獲取 HYG 的最新收盤價。")
                return float("nan")
            if (
                ief_data.empty
                or "close" not in ief_data.columns
                or ief_data["close"].iloc[-1] is None
            ):
                logger.warning("無法獲取 IEF 的最新收盤價。")
                return float("nan")

            hyg_price = hyg_data["close"].iloc[-1]
            ief_price = ief_data["close"].iloc[-1]

            if ief_price == 0:
                logger.warning("IEF 價格為零，無法計算信用利差。")
                return float("nan")

            return round(hyg_price / ief_price, 4)
        except Exception as e:
            logger.error(f"計算近似信用利差時發生錯誤: {e}", exc_info=True)
            return float("nan")

    def _calculate_proxy_move(self) -> float:
        """
        計算代理債市波動率 (TLT 60天日線數據的20天滾動標準差)。
        """
        import asyncio
        try:
            tlt_data = asyncio.run(self.yf_client.fetch_data("TLT", period="60d"))
            if (
                tlt_data.empty or "close" not in tlt_data.columns or len(tlt_data) < 21
            ):  # Need at least 20 periods + 1 for pct_change
                logger.warning("TLT 數據不足以計算代理波動率。")
                return float("nan")

            daily_returns = tlt_data["close"].pct_change()
            proxy_move = daily_returns.rolling(window=20).std().iloc[-1]
            return round(proxy_move, 4)
        except Exception as e:
            logger.error(f"計算代理債市波動率時發生錯誤: {e}", exc_info=True)
            return float("nan")

    def _calculate_gold_copper_ratio(self) -> float:
        """
        計算金銅比 (GLD價格 / HG=F價格)。
        """
        import asyncio
        try:
            gld_data = asyncio.run(self.yf_client.fetch_data("GLD", period="1d"))
            copper_data = asyncio.run(self.yf_client.fetch_data("HG=F", period="1d"))

            if (
                gld_data.empty
                or "close" not in gld_data.columns
                or gld_data["close"].iloc[-1] is None
            ):
                logger.warning("無法獲取 GLD 的最新收盤價。")
                return float("nan")
            if (
                copper_data.empty
                or "close" not in copper_data.columns
                or copper_data["close"].iloc[-1] is None
            ):
                logger.warning("無法獲取 HG=F 的最新收盤價。")
                return float("nan")

            gld_price = gld_data["close"].iloc[-1]
            copper_price = copper_data["close"].iloc[-1]

            if copper_price == 0:
                logger.warning("銅價為零，無法計算金銅比。")
                return float("nan")

            return round(gld_price / copper_price, 4)
        except Exception as e:
            logger.error(f"計算金銅比時發生錯誤: {e}", exc_info=True)
            return float("nan")

    def generate_snapshot(self, dt: datetime):
        # 1. 首先，嘗試從快取讀取數據
        cached_data = self._query_cache(dt)

        # 2. 判斷快取是否命中
        if cached_data is not None:
            # --- 快取命中 ---
            # 直接返回從資料庫讀取的數據
            return cached_data
        else:
            # --- 快取未命中 ---
            # a. 執行現有的 API 呼叫邏輯，獲取所有原始市場數據
            #    (例如: yfinance_client.get_data(), fred_client.fetch_data() ...)

            # b. 執行現有的所有計算邏輯 (技術指標、選擇權數據等)
            #    ...

            # c. 將所有獲取和計算出的數據組裝成一個符合表格結構的單行 DataFrame
            # new_data_df = self._build_snapshot_df(...) # 假設有此方法

            # 為了演示，這裡我們回傳一個假資料
            data = {
                "timestamp": [dt],
                "spy_open": [None],
                "spy_high": [None],
                "spy_low": [None],
                "spy_close": [500.0],
                "spy_volume": [None],
                "qqq_close": [None],
                "tlt_close": [None],
                "btc_usd_close": [None],
                "nq_f_close": [None],
                "es_f_close": [None],
                "ym_f_close": [None],
                "cl_f_close": [None],
                "gc_f_close": [None],
                "si_f_close": [None],
                "zb_f_close": [None],
                "zn_f_close": [None],
                "zt_f_close": [None],
                "zf_f_close": [None],
                "gld_close": [None],
                "shy_close": [None],
                "iei_close": [None],
                "aapl_close": [None],
                "msft_close": [None],
                "nvda_close": [None],
                "goog_close": [None],
                "tsm_close": [None],
                "601318_ss_close": [None],
                "688981_ss_close": [None],
                "0981_hk_close": [None],
                "spy_rsi_14_1h": [None],
                "spy_macd_signal_1h": [None],
                "spy_bbands_width_pct_1h": [None],
                "spy_vwap_1h": [None],
                "spy_atr_14_1h": [None],
                "spy_vwap_deviation_pct_1h": [None],
                "spy_momentum_1h_100": [None],
                "spy_bollinger_band_upper_1h": [None],
                "spy_bollinger_band_lower_1h": [None],
                "spy_bb_middle_band_20h": [None],
                "spy_bb_upper_band_20h": [None],
                "spy_bb_lower_band_20h": [None],
                "spy_bb_band_width_pct_20h": [None],
                "spy_bb_percent_b_20h": [None],
                "spy_gex_total": [None],
                "spy_gex_flip_level": [None],
                "spy_max_pain": [None],
                "spy_call_wall_strike": [None],
                "spy_put_wall_strike": [None],
                "spy_pc_ratio_volume": [None],
                "spy_pc_ratio_oi": [None],
                "spy_iv_atm_1m": [None],
                "spy_skew_quantified": [None],
                "spy_vanna_exposure": [None],
                "spy_charm_exposure": [None],
                "vvix_close": [None],
            }
            new_data_df = pd.DataFrame(data)

            # d. 將這筆新數據寫入快取，供未來使用
            self._write_cache(new_data_df)

            # e. 返回這筆剛從 API 獲取的新數據
            return new_data_df

    def get_hourly_series(
        self, ticker: str, column: str, start_date: str, end_date: str
    ) -> "pd.Series":
        """
        從 DuckDB 獲取指定時間範圍內的小時級數據。
        """
        query = f"SELECT timestamp, {ticker}_{column} FROM hourly_time_series WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp"
        result_df = self.db_con.execute(query, [start_date, end_date]).fetch_df()

        if result_df.empty:
            return pd.Series(dtype="float64")

        result_df = result_df.set_index("timestamp")
        return result_df[f"{ticker}_{column}"]
