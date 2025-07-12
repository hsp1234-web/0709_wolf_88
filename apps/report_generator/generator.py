# apps/report_generator/generator.py
import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime
import pytz  # 確保導入 pytz 以便在 __main__ 中使用
import sys # For sys.exit
from typing import Any # For type hints

from core.logger import get_logger # 移到頂部
logger = get_logger(__name__)

# 導入 Plotly - 直接導入，如果失敗則讓 ImportError 自然拋出
import plotly.graph_objects as go  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402


class ReportGenerator:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        logger.info(f"ReportGenerator 初始化，使用資料庫路徑: {self.db_path}")

    def _connect_db(self):
        try:
            con = duckdb.connect(database=self.db_path, read_only=True)
            logger.info(f"成功連接到資料庫 (唯讀): {self.db_path}")
            return con
        except Exception as e:
            logger.error(f"連接資料庫 {self.db_path} 時發生錯誤: {e}", exc_info=True)
            raise

    def _validate_timeframe(self, timeframe: str) -> str:
        cleaned_timeframe = timeframe.lower().strip()
        if not cleaned_timeframe:
            logger.error("Timeframe 驗證失敗: 不能為空。")
            raise ValueError("Timeframe 不能為空。")
        if not all(c.isalnum() or c == "_" for c in cleaned_timeframe):
            logger.error(f"Timeframe 驗證失敗: '{timeframe}' 包含無效字符。")
            raise ValueError(f"Timeframe '{timeframe}' 包含無效字符。")
        logger.debug(f"Timeframe '{timeframe}' 驗證通過，清理後為 '{cleaned_timeframe}'.")
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

        internal_stock_id_for_ohlcv = (
            stock_id.replace(".TW", "")
            if isinstance(stock_id, str) and ".TW" in stock_id
            else stock_id
        )
        logger.info(
            f"原始 stock_id (用於報告和 Chimera): '{stock_id}', 內部查詢 ohlcv 使用的 product_id: '{internal_stock_id_for_ohlcv}'"
        )

        try:
            valid_timeframe = self._validate_timeframe(timeframe)
            ohlcv_table_name = f"ohlcv_{valid_timeframe}"
            logger.info(
                f"正在從資料表 '{ohlcv_table_name}' 讀取 {timeframe} OHLCV 數據 (product_id: {internal_stock_id_for_ohlcv})..."
            )

            query_ohlcv = f"""
            SELECT timestamp, open, high, low, close, volume
            FROM {ohlcv_table_name}
            WHERE product_id = $internal_stock_id_for_ohlcv
              AND timestamp >= CAST($start_date AS TIMESTAMP)
              AND timestamp <= CAST($end_date AS TIMESTAMP) + INTERVAL '1 day' - INTERVAL '1 second'
            ORDER BY timestamp;
            """
            params_ohlcv = {
                "internal_stock_id_for_ohlcv": internal_stock_id_for_ohlcv,
                "start_date": start_date_str,
                "end_date": end_date_str,
            }
            ohlcv_df = con.execute(query_ohlcv, params_ohlcv).fetchdf()

            if ohlcv_df.empty:
                logger.warning(
                    f"未找到 {internal_stock_id_for_ohlcv} (原始 {stock_id}) 在 {start_date_str} 至 {end_date_str} ({timeframe} 週期) 的 OHLCV 數據。"
                )
                return None, None, None
            logger.info(
                f"成功讀取 {len(ohlcv_df)} 筆 {internal_stock_id_for_ohlcv} (原始 {stock_id}) 的 {timeframe} OHLCV 數據。"
            )
            if "timestamp" in ohlcv_df.columns:  # 確保 timestamp 是 datetime 對象
                ohlcv_df["timestamp"] = pd.to_datetime(ohlcv_df["timestamp"])
        except duckdb.CatalogException as ce:
            logger.error(
                f"OHLCV 資料表 '{ohlcv_table_name}' (用於 timeframe '{timeframe}') 不存在於資料庫 {self.db_path} 中: {ce}", exc_info=True
            )
            return None, None, None
        except ValueError as ve:
            logger.error(f"Timeframe 相關錯誤: {ve}", exc_info=True)
            return None, None, None
        except Exception as e:
            logger.error(f"讀取 {timeframe} OHLCV 數據時發生錯誤: {e}", exc_info=True)
            return None, None, None

        try:
            query_chimera = """
            SELECT date, stock_id, price_volume_label, institutional_flow_label, composite_signal
            FROM chimera_daily_signals
            WHERE stock_id = $stock_id AND date BETWEEN CAST($start_date AS DATE) AND CAST($end_date AS DATE)
            ORDER BY date;
            """
            params_chimera = {
                "stock_id": stock_id,
                "start_date": start_date_str,
                "end_date": end_date_str,
            }
            chimera_df = con.execute(query_chimera, params_chimera).fetchdf()
            if not chimera_df.empty:
                chimera_df["date"] = pd.to_datetime(
                    chimera_df["date"]
                ).dt.date  # 確保是 date 類型
                logger.info(
                    f"成功讀取 {len(chimera_df)} 筆 {stock_id} 的 Chimera 日信號數據。"
                )
            else:
                logger.info(
                    f"未找到 {stock_id} 在 {start_date_str} 至 {end_date_str} 的 Chimera 日信號數據 (將不顯示信號)。"
                )
        except Exception as e:
            logger.warning(f"讀取 Chimera 日信號數據時發生錯誤: {e} (將不顯示信號)。", exc_info=True)
            chimera_df = None

        pc_ratio_product_to_fetch = None
        if stock_id == "0050.TW" or stock_id == "TXO":  # 如果是0050 ETF 或直接請求 TXO
            pc_ratio_product_to_fetch = "TXO"

        if pc_ratio_product_to_fetch:
            try:
                query_pc_ratio = """
                SELECT trading_date, product_id, pc_volume_ratio, pc_oi_ratio
                FROM taifex_pc_ratios
                WHERE product_id = $product_id
                  AND trading_date >= CAST($start_date AS DATE)
                  AND trading_date <= CAST($end_date AS DATE)
                ORDER BY trading_date;
                """
                params_pc_ratio = {
                    "product_id": pc_ratio_product_to_fetch,
                    "start_date": start_date_str,
                    "end_date": end_date_str,
                }
                pc_ratio_df = con.execute(query_pc_ratio, params_pc_ratio).fetchdf()
                if not pc_ratio_df.empty:
                    pc_ratio_df["trading_date"] = pd.to_datetime(
                        pc_ratio_df["trading_date"]
                    ).dt.date
                    logger.info(
                        f"成功讀取 {len(pc_ratio_df)} 筆 {pc_ratio_product_to_fetch} 的 P/C Ratio 數據。"
                    )
                else:
                    logger.info(
                        f"未找到 {pc_ratio_product_to_fetch} 在 {start_date_str} 至 {end_date_str} 的 P/C Ratio 數據。"
                    )
                    pc_ratio_df = None # 確保即使查詢成功但無數據時也設為 None
            except Exception as e:
                logger.warning(
                    f"讀取 P/C Ratio ({pc_ratio_product_to_fetch}) 數據時發生錯誤: {e}", exc_info=True
                )
                pc_ratio_df = None

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
            logger.warning(f"({timeframe}) 沒有 OHLCV 數據可供繪製。")
            return None

        logger.info(f"開始使用 Plotly 繪製 {timeframe} 報告圖表...")
        x_axis_data = ohlcv_df["timestamp"]

        has_pc_ratio_data = pc_ratio_df is not None and not pc_ratio_df.empty
        num_rows = 3 if has_pc_ratio_data else 2
        row_heights = [0.6, 0.2, 0.2] if has_pc_ratio_data else [0.7, 0.3]

        subplot_titles = ["K線與信號", "成交量"]
        pc_product_id_for_title = "Market" # Default value
        if has_pc_ratio_data and pc_ratio_df is not None:
            if "product_id" in pc_ratio_df.columns and not pc_ratio_df.empty:
                 pc_product_id_for_title = pc_ratio_df["product_id"].iloc[0]
            subplot_titles.append(f"Put/Call Ratio ({pc_product_id_for_title})")

        fig = make_subplots(
            rows=num_rows,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=row_heights,
            subplot_titles=subplot_titles[:num_rows],
        )

        fig.add_trace(
            go.Candlestick(
                x=x_axis_data,
                open=ohlcv_df["open"],
                high=ohlcv_df["high"],
                low=ohlcv_df["low"],
                close=ohlcv_df["close"],
                name=f"K線 ({timeframe})",
                increasing_line_color="red",
                decreasing_line_color="green",
            ),
            row=1,
            col=1,
        )

        volume_colors = [
            "red" if ohlcv_df["close"].iloc[i] >= ohlcv_df["open"].iloc[i] else "green"
            for i in range(len(ohlcv_df))
        ]
        fig.add_trace(
            go.Bar(
                x=x_axis_data,
                y=ohlcv_df["volume"],
                name="成交量",
                marker_color=volume_colors,
            ),
            row=2,
            col=1,
        )

        if chimera_df is not None and not chimera_df.empty:
            ohlcv_for_merge = ohlcv_df.copy()
            ohlcv_for_merge["date_for_signal_merge"] = (
                ohlcv_for_merge["timestamp"].dt.normalize().dt.date
            )
            current_stock_chimera_df = chimera_df[chimera_df["stock_id"] == stock_id]
            merged_for_plot = pd.merge(
                ohlcv_for_merge,
                current_stock_chimera_df,
                left_on="date_for_signal_merge",
                right_on="date",
                how="left",
                suffixes=("", "_chimera"),
            )

            marker_styles = {
                "價漲量增_法人買超": {
                    "symbol": "arrow-up",
                    "color": "green",
                    "size": 10,
                    "legend_group": "buy_signal",
                    "name": "價漲量增_法人買超",
                },
                "價跌量增_法人賣超": {
                    "symbol": "arrow-down",
                    "color": "red",
                    "size": 10,
                    "legend_group": "sell_signal",
                    "name": "價跌量增_法人賣超",
                },
                "其他買超相關信號": {
                    "symbol": "circle",
                    "color": "lightgreen",
                    "size": 7,
                    "legend_group": "buy_signal_other",
                    "name": "其他買超相關",
                },
                "其他賣超相關信號": {
                    "symbol": "circle",
                    "color": "lightcoral",
                    "size": 7,
                    "legend_group": "sell_signal_other",
                    "name": "其他賣超相關",
                },
                "法人中性相關信號": {
                    "symbol": "diamond",
                    "color": "gold",
                    "size": 7,
                    "legend_group": "neutral_signal",
                    "name": "法人中性相關",
                },
                "籌碼未知相關信號": {
                    "symbol": "square",
                    "color": "silver",
                    "size": 6,
                    "legend_group": "unknown_signal",
                    "name": "籌碼未知相關",
                },
            }
            plot_data_points: dict[str, dict[str, list[Any]]] = {
                key: {"x": [], "y": [], "text": []} for key in marker_styles
            }

            for _, row in merged_for_plot.iterrows():
                signal = row.get("composite_signal", "")
                if pd.notna(signal) and pd.notna(row["high"]):
                    y_pos = row["high"] * 1.02
                    style_key = None
                    if signal == "價漲量增_法人買超":
                        style_key = "價漲量增_法人買超"
                    elif signal == "價跌量增_法人賣超":
                        style_key = "價跌量增_法人賣超"
                    elif "法人買超" in signal:
                        style_key = "其他買超相關信號"
                    elif "法人賣超" in signal:
                        style_key = "其他賣超相關信號"
                    elif "法人中性" in signal:
                        style_key = "法人中性相關信號"
                    elif "籌碼未知" in signal:
                        style_key = "籌碼未知相關信號"
                    if style_key:
                        plot_data_points[style_key]["x"].append(row["timestamp"])
                        plot_data_points[style_key]["y"].append(y_pos)
                        plot_data_points[style_key]["text"].append(
                            f"{row['composite_signal']} (日信號)"
                        )

            for style_key, data in plot_data_points.items():
                if data["x"]:
                    style = marker_styles[style_key]
                    fig.add_trace(
                        go.Scatter(
                            x=data["x"],
                            y=data["y"],
                            mode="markers",
                            marker_symbol=style["symbol"],
                            marker_color=style["color"],
                            marker_size=style["size"],
                            name=style["name"],
                            legendgroup=style["legend_group"],
                            hoverinfo="text",
                            text=data["text"],
                        ),
                        row=1,
                        col=1,
                    )

        if has_pc_ratio_data and pc_ratio_df is not None:
            pc_x_axis = pc_ratio_df["trading_date"]
            if "pc_volume_ratio" in pc_ratio_df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=pc_x_axis,
                        y=pc_ratio_df["pc_volume_ratio"],
                        mode="lines",
                        name="P/C Ratio (Volume)",
                        legendgroup="pc_ratio_group",
                    ),
                    row=3,
                    col=1,
                )
            if "pc_oi_ratio" in pc_ratio_df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=pc_x_axis,
                        y=pc_ratio_df["pc_oi_ratio"],
                        mode="lines",
                        name="P/C Ratio (OI)",
                        legendgroup="pc_ratio_group",
                    ),
                    row=3,
                    col=1,
                )

        min_date_str = (
            ohlcv_df["timestamp"].min().strftime("%Y-%m-%d %H:%M")
            if timeframe not in ["1d", "1w", "1m"]
            else ohlcv_df["timestamp"].min().strftime("%Y-%m-%d")
        )
        max_date_str = (
            ohlcv_df["timestamp"].max().strftime("%Y-%m-%d %H:%M")
            if timeframe not in ["1d", "1w", "1m"]
            else ohlcv_df["timestamp"].max().strftime("%Y-%m-%d")
        )

        fig.update_layout(
            title_text=f"股票 {stock_id} ({timeframe}) 複合信號分析報告 ({min_date_str} 至 {max_date_str})",
            xaxis_rangeslider_visible=False,
            showlegend=True,
            legend_title_text="圖例",
            legend=dict(tracegroupgap=10),
            hovermode="x unified",
        )
        fig.update_yaxes(title_text="股價", row=1, col=1)
        fig.update_yaxes(title_text="成交量", row=2, col=1)
        if has_pc_ratio_data and pc_ratio_df is not None:
            pc_product_id_for_y_title = "Market" # Default
            if "product_id" in pc_ratio_df.columns and not pc_ratio_df.empty:
                pc_product_id_for_y_title = pc_ratio_df["product_id"].iloc[0]
            fig.update_yaxes(
                title_text=f"P/C Ratio ({pc_product_id_for_y_title})", row=3, col=1
            )

        logger.info(f"Plotly {timeframe} 圖表繪製完成。")
        return fig

    def generate_report(
        self,
        stock_id: str,
        start_date_str: str,
        end_date_str: str,
        timeframe: str,
        output_dir: Path,
    ) -> Path | None:
        report_file_path = None
        con = None # Initialize con to None for finally block
        try:
            con = self._connect_db() # _connect_db now raises on failure
            ohlcv_df, chimera_df, pc_ratio_df = self._fetch_data(
                con, stock_id, start_date_str, end_date_str, timeframe
            )

            if ohlcv_df is None or ohlcv_df.empty:
                logger.warning(
                    f"股票 {stock_id} ({timeframe}) 在指定日期範圍內無 OHLCV 數據，無法生成報告。"
                )
                return None

            fig = self._plot_report_plotly(
                stock_id, ohlcv_df, chimera_df, pc_ratio_df, timeframe
            )

            if fig:
                output_dir.mkdir(parents=True, exist_ok=True)
                filename = f"{stock_id}_{timeframe}_{start_date_str.replace('-', '')}_{end_date_str.replace('-', '')}_report.html"
                report_file_path = output_dir / filename
                fig.write_html(str(report_file_path))
                logger.info(f"報告已儲存至: {report_file_path} (HTML 格式)")
            else:
                logger.warning(f"Plotly 圖表物件 ({timeframe}) 未成功創建，無法儲存報告。")

            return report_file_path
        except Exception as e:
            logger.error(f"生成報告 {stock_id} ({timeframe}) 時發生錯誤: {e}", exc_info=True)
            return None
        finally:
            if con:
                try:
                    con.close()
                    logger.debug(f"資料庫連接已在 generate_report (stock: {stock_id}) 中關閉。")
                except Exception as e_close:
                    logger.error(f"關閉資料庫連接時發生錯誤: {e_close}", exc_info=True)


if __name__ == "__main__":
    logger.info("執行 ReportGenerator (Plotly 版本) 初步測試...")
    test_db_name = "temp_plotly_report_test.duckdb"
    test_output_dir_name = "test_generator_reports_output"

    test_db_file = Path(test_db_name)
    if test_db_file.exists():
        logger.info(f"正在刪除舊的測試資料庫: {test_db_file}")
        try:
            test_db_file.unlink()
        except OSError as e:
            logger.warning(f"刪除舊測試資料庫失敗: {e}")


    test_output_dir = Path(test_output_dir_name)
    if test_output_dir.exists():
        import shutil
        logger.info(f"正在刪除舊的測試輸出目錄: {test_output_dir}")
        try:
            shutil.rmtree(test_output_dir)
        except OSError as e:
            logger.warning(f"刪除舊測試輸出目錄失敗: {e}")
    try:
        test_output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"創建測試輸出目錄失敗: {e}", exc_info=True)
        # Test cannot proceed if output dir cannot be created
        sys.exit(1)


    db_connection_main_test = None
    try:
        db_connection_main_test = duckdb.connect(str(test_db_file))
        with db_connection_main_test as con: # Use context manager for connection
            con.execute(
                """
            CREATE TABLE IF NOT EXISTS ohlcv_1d (
                timestamp TIMESTAMP, product_id VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT,
                PRIMARY KEY (timestamp, product_id)
            );"""
            )
            ohlcv_1d_data = [
                (datetime(2023, 1, 1), "TEST_STOCK_D", 10, 12, 9, 11, 1000),
                (datetime(2023, 1, 2), "TEST_STOCK_D", 11, 13, 10.5, 12.5, 1200),
                (datetime(2023, 1, 3), "TEST_STOCK_D", 12.5, 12.5, 11, 11.5, 800),
                (
                    datetime(2023, 1, 1),
                    "0050", # Storing as "0050" for ohlcv, ReportGenerator handles .TW mapping
                    120.0,
                    122.0,
                    119.0,
                    121.0,
                    5000,
                ),
                (datetime(2023, 1, 2), "0050", 121.0, 123.0, 120.0, 122.0, 6000),
            ]
            con.executemany(
                "INSERT INTO ohlcv_1d VALUES (?,?,?,?,?,?,?)", ohlcv_1d_data
            )
            logger.info(f"已創建並填充 ohlcv_1d 測試數據到 {test_db_file}")

            con.execute(
                """
            CREATE TABLE IF NOT EXISTS chimera_daily_signals (
                date DATE, stock_id VARCHAR, price_volume_label VARCHAR,
                institutional_flow_label VARCHAR, composite_signal VARCHAR,
                PRIMARY KEY (date, stock_id)
            );"""
            )
            chimera_test_data = [
                (
                    datetime(2023, 1, 1).date(),
                    "TEST_STOCK_D",
                    "價漲量增",
                    "法人買超",
                    "價漲量增_法人買超",
                ),
                (
                    datetime(2023, 1, 2).date(),
                    "TEST_STOCK_D",
                    "價跌量增",
                    "法人賣超",
                    "價跌量增_法人賣超",
                ),
                (
                    datetime(2023, 1, 1).date(),
                    "0050.TW", # stock_id in chimera should match the requested one
                    "價漲量增",
                    "法人買超",
                    "價漲量增_法人買超",
                ),
            ]
            con.executemany(
                "INSERT INTO chimera_daily_signals VALUES (?,?,?,?,?)",
                chimera_test_data,
            )
            logger.info(f"已創建並填充 chimera_daily_signals 測試數據到 {test_db_file}")

            con.execute(
                """
            CREATE TABLE IF NOT EXISTS taifex_pc_ratios (
                trading_date DATE, product_id VARCHAR, pc_volume_ratio DOUBLE, pc_oi_ratio DOUBLE,
                total_put_volume BIGINT, total_call_volume BIGINT, total_put_oi BIGINT, total_call_oi BIGINT, calculated_at TIMESTAMPTZ,
                PRIMARY KEY (trading_date, product_id)
            );"""
            )
            pc_ratio_data = [
                (
                    datetime(2023, 1, 1).date(),
                    "TXO",
                    0.8,
                    0.9,
                    8000,
                    10000,
                    9000,
                    10000,
                    datetime.now(pytz.utc),
                ),
                (
                    datetime(2023, 1, 2).date(),
                    "TXO",
                    0.85,
                    0.92,
                    8500,
                    10000,
                    9200,
                    10000,
                    datetime.now(pytz.utc),
                ),
                (
                    datetime(2023, 1, 3).date(),
                    "TXO",
                    0.90,
                    0.95,
                    9000,
                    10000,
                    9500,
                    10000,
                    datetime.now(pytz.utc),
                ),
            ]
            con.executemany(
                "INSERT INTO taifex_pc_ratios VALUES (?,?,?,?,?,?,?,?,?)", pc_ratio_data
            )
            logger.info(f"已創建並填充 taifex_pc_ratios 測試數據到 {test_db_file}")

        generator = ReportGenerator(db_path=str(test_db_file))

        logger.info("--- 測試生成 TEST_STOCK_D 日線 (1d) 報告 (無P/C Ratio) ---")
        report_1d = generator.generate_report(
            stock_id="TEST_STOCK_D",
            start_date_str="2023-01-01",
            end_date_str="2023-01-03",
            timeframe="1d",
            output_dir=test_output_dir,
        )
        if report_1d and report_1d.exists():
            logger.info(f"TEST_STOCK_D 日線 (1d) 報告生成成功: {report_1d}")
        else:
            logger.error("TEST_STOCK_D 日線 (1d) 報告生成失敗。")

        logger.info("--- 測試生成 0050.TW 日線 (1d) 報告 (應包含 TXO P/C Ratio) ---")
        report_0050 = generator.generate_report(
            stock_id="0050.TW",
            start_date_str="2023-01-01",
            end_date_str="2023-01-03",
            timeframe="1d",
            output_dir=test_output_dir,
        )
        if report_0050 and report_0050.exists():
            logger.info(f"0050.TW 日線 (1d) 報告生成成功: {report_0050}")
        else:
            logger.error("0050.TW 日線 (1d) 報告生成失敗。")

    except Exception as e:
        logger.error(f"ReportGenerator (Plotly 版本) __main__ 測試時發生錯誤: {e}", exc_info=True)
    finally:
        if db_connection_main_test:
            try:
                db_connection_main_test.close()
                logger.debug("主測試資料庫連接已關閉。")
            except Exception as e_close_main:
                logger.error(f"關閉主測試資料庫連接時發生錯誤: {e_close_main}", exc_info=True)

        logger.info(
            f"測試完畢。如果需要，請手動檢查或刪除測試資料庫 '{test_db_file}' 和輸出目錄 '{test_output_dir_name}'。"
        )

    logger.info("ReportGenerator (Plotly 版本) 初步測試完畢。")
