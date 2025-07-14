# apps/report_generator/generator.py
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pytz

from core.logger import LogManager

import plotly.graph_objects as go
from plotly.subplots import make_subplots


class ReportGenerator:
    def __init__(self, db_path: str | Path, log_manager: LogManager):
        self.db_path = str(db_path)
        self.log_manager = log_manager
        self.log_manager.log("INFO", f"ReportGenerator 初始化，使用資料庫路徑: {self.db_path}")

    def _connect_db(self):
        try:
            con = duckdb.connect(database=self.db_path, read_only=True)
            self.log_manager.log("INFO", f"成功連接到資料庫 (唯讀): {self.db_path}")
            return con
        except Exception as e:
            self.log_manager.log("ERROR", f"連接資料庫 {self.db_path} 時發生錯誤: {e}")
            raise

    def _validate_timeframe(self, timeframe: str) -> str:
        cleaned_timeframe = timeframe.lower().strip()
        if not cleaned_timeframe:
            self.log_manager.log("ERROR", "Timeframe 驗證失敗: 不能為空。")
            raise ValueError("Timeframe 不能為空。")
        if not all(c.isalnum() or c == "_" for c in cleaned_timeframe):
            self.log_manager.log("ERROR", f"Timeframe 驗證失敗: '{timeframe}' 包含無效字符。")
            raise ValueError(f"Timeframe '{timeframe}' 包含無效字符。")
        self.log_manager.log("DEBUG", f"Timeframe '{timeframe}' 驗證通過，清理後為 '{cleaned_timeframe}'.")
        return cleaned_timeframe

    def _fetch_data(
        self,
        con: duckdb.DuckDBPyConnection,
        stock_id: str,
        start_date_str: str,
        end_date_str: str,
        timeframe: str,
    ) -> tuple[pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None]:
        ohlcv_df = None
        chimera_df = None
        pc_ratio_df = None

        internal_stock_id_for_ohlcv = stock_id.replace(".TW", "") if isinstance(stock_id, str) and ".TW" in stock_id else stock_id
        self.log_manager.log("INFO", f"原始 stock_id (用於報告和 Chimera): '{stock_id}', 內部查詢 ohlcv 使用的 product_id: '{internal_stock_id_for_ohlcv}'")

        try:
            valid_timeframe = self._validate_timeframe(timeframe)
            ohlcv_table_name = f"ohlcv_{valid_timeframe}"
            self.log_manager.log("INFO", f"正在從資料表 '{ohlcv_table_name}' 讀取 {timeframe} OHLCV 數據 (product_id: {internal_stock_id_for_ohlcv})...")

            query_ohlcv = f"""
            SELECT timestamp, open, high, low, close, volume
            FROM {ohlcv_table_name}
            WHERE product_id = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp;
            """
            ohlcv_df = con.execute(query_ohlcv, [internal_stock_id_for_ohlcv, start_date_str, end_date_str]).fetchdf()

            if ohlcv_df.empty:
                self.log_manager.log("WARNING", f"未找到 {internal_stock_id_for_ohlcv} (原始 {stock_id}) 在 {start_date_str} 至 {end_date_str} ({timeframe} 週期) 的 OHLCV 數據。")
                return None, None, None
            self.log_manager.log("INFO", f"成功讀取 {len(ohlcv_df)} 筆 {internal_stock_id_for_ohlcv} (原始 {stock_id}) 的 {timeframe} OHLCV 數據。")
            ohlcv_df["timestamp"] = pd.to_datetime(ohlcv_df["timestamp"])
        except (duckdb.CatalogException, ValueError) as e:
            self.log_manager.log("ERROR", f"讀取 OHLCV 數據時發生錯誤: {e}")
            return None, None, None

        try:
            query_chimera = "SELECT date, stock_id, price_volume_label, institutional_flow_label, composite_signal FROM chimera_daily_signals WHERE stock_id = ? AND date BETWEEN ? AND ?"
            chimera_df = con.execute(query_chimera, [stock_id, start_date_str, end_date_str]).fetchdf()
            if not chimera_df.empty:
                chimera_df["date"] = pd.to_datetime(chimera_df["date"]).dt.date
                self.log_manager.log("INFO", f"成功讀取 {len(chimera_df)} 筆 {stock_id} 的 Chimera 日信號數據。")
        except Exception as e:
            self.log_manager.log("WARNING", f"讀取 Chimera 日信號數據時發生錯誤: {e}")

        if stock_id in ["0050.TW", "TXO"]:
            try:
                query_pc_ratio = "SELECT trading_date, product_id, pc_volume_ratio, pc_oi_ratio FROM taifex_pc_ratios WHERE product_id = 'TXO' AND trading_date BETWEEN ? AND ?"
                pc_ratio_df = con.execute(query_pc_ratio, [start_date_str, end_date_str]).fetchdf()
                if not pc_ratio_df.empty:
                    pc_ratio_df["trading_date"] = pd.to_datetime(pc_ratio_df["trading_date"]).dt.date
                    self.log_manager.log("INFO", f"成功讀取 {len(pc_ratio_df)} 筆 TXO 的 P/C Ratio 數據。")
            except Exception as e:
                self.log_manager.log("WARNING", f"讀取 P/C Ratio (TXO) 數據時發生錯誤: {e}")

        return ohlcv_df, chimera_df, pc_ratio_df

    def _plot_report_plotly(
        self,
        stock_id: str,
        ohlcv_df: pd.DataFrame,
        chimera_df: pd.DataFrame | None,
        pc_ratio_df: pd.DataFrame | None,
        timeframe: str,
    ) -> go.Figure | None:
        if ohlcv_df.empty:
            self.log_manager.log("WARNING", f"({timeframe}) 沒有 OHLCV 數據可供繪製。")
            return None

        self.log_manager.log("INFO", f"開始使用 Plotly 繪製 {timeframe} 報告圖表...")
        has_pc_ratio_data = pc_ratio_df is not None and not pc_ratio_df.empty
        fig = make_subplots(rows=3 if has_pc_ratio_data else 2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2] if has_pc_ratio_data else [0.7, 0.3])

        fig.add_trace(go.Candlestick(x=ohlcv_df["timestamp"], open=ohlcv_df["open"], high=ohlcv_df["high"], low=ohlcv_df["low"], close=ohlcv_df["close"], name=f"K線 ({timeframe})"), row=1, col=1)
        fig.add_trace(go.Bar(x=ohlcv_df["timestamp"], y=ohlcv_df["volume"], name="成交量"), row=2, col=1)

        if chimera_df is not None and not chimera_df.empty:
            # Simplified signal plotting logic
            buy_signals = chimera_df[chimera_df['composite_signal'].str.contains("買超", na=False)]
            sell_signals = chimera_df[chimera_df['composite_signal'].str.contains("賣超", na=False)]
            fig.add_trace(go.Scatter(x=buy_signals['date'], y=buy_signals['composite_signal'].apply(lambda s: ohlcv_df['high'].max() * 1.05), mode='markers', marker=dict(color='green', symbol='triangle-up', size=8), name='買超信號'), row=1, col=1)
            fig.add_trace(go.Scatter(x=sell_signals['date'], y=sell_signals['composite_signal'].apply(lambda s: ohlcv_df['high'].max() * 1.05), mode='markers', marker=dict(color='red', symbol='triangle-down', size=8), name='賣超信號'), row=1, col=1)

        if has_pc_ratio_data:
            fig.add_trace(go.Scatter(x=pc_ratio_df["trading_date"], y=pc_ratio_df["pc_volume_ratio"], mode='lines', name='P/C Ratio (Volume)'), row=3, col=1)
            fig.add_trace(go.Scatter(x=pc_ratio_df["trading_date"], y=pc_ratio_df["pc_oi_ratio"], mode='lines', name='P/C Ratio (OI)'), row=3, col=1)

        fig.update_layout(title_text=f"股票 {stock_id} ({timeframe}) 複合信號分析報告", xaxis_rangeslider_visible=False)
        self.log_manager.log("INFO", f"Plotly {timeframe} 圖表繪製完成。")
        return fig

    def generate_report(
        self,
        stock_id: str,
        start_date_str: str,
        end_date_str: str,
        timeframe: str,
        output_dir: Path,
    ) -> Path | None:
        try:
            with self._connect_db() as con:
                ohlcv_df, chimera_df, pc_ratio_df = self._fetch_data(con, stock_id, start_date_str, end_date_str, timeframe)
                if ohlcv_df is None or ohlcv_df.empty:
                    self.log_manager.log("WARNING", f"股票 {stock_id} ({timeframe}) 在指定日期範圍內無 OHLCV 數據，無法生成報告。")
                    return None

                fig = self._plot_report_plotly(stock_id, ohlcv_df, chimera_df, pc_ratio_df, timeframe)
                if fig:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    filename = f"{stock_id}_{timeframe}_{start_date_str.replace('-', '')}_{end_date_str.replace('-', '')}_report.html"
                    report_file_path = output_dir / filename
                    fig.write_html(str(report_file_path))
                    self.log_manager.log("INFO", f"報告已儲存至: {report_file_path} (HTML 格式)")
                    return report_file_path
        except Exception as e:
            self.log_manager.log("ERROR", f"生成報告 {stock_id} ({timeframe}) 時發生錯誤: {e}")
        return None


if __name__ == "__main__":
    # Setup for standalone testing
    project_root = Path(__file__).parents[2]
    output_dir = project_root / "output"
    log_db_path = output_dir / "logs" / "standalone_test.sqlite"
    archive_dir = output_dir / "logs" / "archive"
    dummy_logger = LogManager(db_path=log_db_path, archive_dir=archive_dir)

    dummy_logger.log("INFO", "執行 ReportGenerator (Plotly 版本) 初步測試...")
    test_db_name = "temp_plotly_report_test.duckdb"
    test_output_dir = project_root / "test_generator_reports_output"
    test_db_file = project_root / test_db_name

    if test_db_file.exists(): test_db_file.unlink()
    if test_output_dir.exists(): import shutil; shutil.rmtree(test_output_dir)
    test_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with duckdb.connect(str(test_db_file)) as con:
            con.execute("CREATE TABLE ohlcv_1d(timestamp TIMESTAMP, product_id VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT);")
            con.executemany("INSERT INTO ohlcv_1d VALUES (?,?,?,?,?,?,?)", [
                (datetime(2023, 1, 1), "TEST_STOCK_D", 10, 12, 9, 11, 1000),
                (datetime(2023, 1, 2), "TEST_STOCK_D", 11, 13, 10.5, 12.5, 1200),
                (datetime(2023, 1, 1), "0050", 120.0, 122.0, 119.0, 121.0, 5000),
            ])
            con.execute("CREATE TABLE chimera_daily_signals(date DATE, stock_id VARCHAR, price_volume_label VARCHAR, institutional_flow_label VARCHAR, composite_signal VARCHAR);")
            con.executemany("INSERT INTO chimera_daily_signals VALUES (?,?,?,?,?)", [
                (datetime(2023, 1, 1).date(), "TEST_STOCK_D", "價漲量增", "法人買超", "價漲量增_法人買超"),
                (datetime(2023, 1, 1).date(), "0050.TW", "價漲量增", "法人買超", "價漲量增_法人買超"),
            ])
            con.execute("CREATE TABLE taifex_pc_ratios(trading_date DATE, product_id VARCHAR, pc_volume_ratio DOUBLE, pc_oi_ratio DOUBLE, total_put_volume BIGINT, total_call_volume BIGINT, total_put_oi BIGINT, total_call_oi BIGINT, calculated_at TIMESTAMPTZ);")
            con.executemany("INSERT INTO taifex_pc_ratios VALUES (?,?,?,?,?,?,?,?,?)", [
                (datetime(2023, 1, 1).date(), "TXO", 0.8, 0.9, 8000, 10000, 9000, 10000, datetime.now(pytz.utc)),
            ])

        generator = ReportGenerator(db_path=str(test_db_file), log_manager=dummy_logger)
        generator.generate_report("TEST_STOCK_D", "2023-01-01", "2023-01-03", "1d", test_output_dir)
        generator.generate_report("0050.TW", "2023-01-01", "2023-01-03", "1d", test_output_dir)

    except Exception as e:
        dummy_logger.log("ERROR", f"ReportGenerator __main__ 測試時發生錯誤: {e}")
    finally:
        dummy_logger.log("INFO", "測試完畢。")
        dummy_logger.archive_to_file()
