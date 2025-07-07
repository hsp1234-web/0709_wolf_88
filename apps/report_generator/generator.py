# apps/report_generator/generator.py
import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime

# 導入 Plotly - 直接導入，如果失敗則讓 ImportError 自然拋出
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class ReportGenerator:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        # 此處不再檢查 PLOTLY_AVAILABLE

    def _connect_db(self):
        try:
            con = duckdb.connect(database=self.db_path, read_only=True)
            print(f"成功連接到資料庫 (唯讀): {self.db_path}")
            return con
        except Exception as e:
            print(f"連接資料庫 {self.db_path} 時發生錯誤: {e}")
            raise

    def _validate_timeframe(self, timeframe: str) -> str:
        cleaned_timeframe = timeframe.lower().strip()
        if not cleaned_timeframe:
            raise ValueError("Timeframe 不能為空。")
        if not all(c.isalnum() or c == '_' for c in cleaned_timeframe):
            raise ValueError(f"Timeframe '{timeframe}' 包含無效字符。")
        return cleaned_timeframe

    def _fetch_data(self, con: duckdb.DuckDBPyConnection, stock_id: str, start_date_str: str, end_date_str: str, timeframe: str) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
        ohlcv_df = None
        chimera_df = None

        # 處理 stock_id 以符合內部 ohlcv_* 表格的 product_id 規範 (移除 .TW)
        internal_stock_id_for_ohlcv = stock_id.replace(".TW", "") if isinstance(stock_id, str) and ".TW" in stock_id else stock_id
        print(f"原始 stock_id (用於報告和 Chimera): '{stock_id}', 內部查詢 ohlcv 使用的 product_id: '{internal_stock_id_for_ohlcv}'")

        try:
            valid_timeframe = self._validate_timeframe(timeframe)
            ohlcv_table_name = f"ohlcv_{valid_timeframe}"
            print(f"正在從資料表 '{ohlcv_table_name}' 讀取 {timeframe} OHLCV 數據 (product_id: {internal_stock_id_for_ohlcv})...")

            query_ohlcv = f"""
            SELECT timestamp, open, high, low, close, volume
            FROM {ohlcv_table_name}
            WHERE product_id = $internal_stock_id_for_ohlcv
              AND timestamp >= CAST($start_date AS TIMESTAMP)
              AND timestamp <= CAST($end_date AS TIMESTAMP) + INTERVAL '1 day' - INTERVAL '1 second'
            ORDER BY timestamp;
            """
            params_ohlcv = {'internal_stock_id_for_ohlcv': internal_stock_id_for_ohlcv, 'start_date': start_date_str, 'end_date': end_date_str}
            ohlcv_df = con.execute(query_ohlcv, params_ohlcv).fetchdf()

            if ohlcv_df.empty:
                print(f"未找到 {internal_stock_id_for_ohlcv} (原始 {stock_id}) 在 {start_date_str} 至 {end_date_str} ({timeframe} 週期) 的 OHLCV 數據。")
                return None, None
            print(f"成功讀取 {len(ohlcv_df)} 筆 {internal_stock_id_for_ohlcv} (原始 {stock_id}) 的 {timeframe} OHLCV 數據。")
        except duckdb.CatalogException:
            print(f"錯誤：OHLCV 資料表 '{ohlcv_table_name}' (用於 timeframe '{timeframe}') 不存在於資料庫 {self.db_path} 中。")
            return None, None
        except ValueError as ve:
            print(f"錯誤: {ve}")
            return None, None
        except Exception as e:
            print(f"讀取 {timeframe} OHLCV 數據時發生錯誤: {e}")
            return None, None

        try:
            query_chimera = """
            SELECT date, stock_id, price_volume_label, institutional_flow_label, composite_signal
            FROM chimera_daily_signals
            WHERE stock_id = $stock_id AND date BETWEEN CAST($start_date AS DATE) AND CAST($end_date AS DATE)
            ORDER BY date;
            """
            params_chimera = {'stock_id': stock_id, 'start_date': start_date_str, 'end_date': end_date_str}
            chimera_df = con.execute(query_chimera, params_chimera).fetchdf()
            if not chimera_df.empty:
                chimera_df['date'] = pd.to_datetime(chimera_df['date'])
                print(f"成功讀取 {len(chimera_df)} 筆 {stock_id} 的 Chimera 日信號數據。")
            else:
                print(f"未找到 {stock_id} 在 {start_date_str} 至 {end_date_str} 的 Chimera 日信號數據 (將不顯示信號)。")
        except Exception as e:
            print(f"讀取 Chimera 日信號數據時發生錯誤: {e} (將不顯示信號)。")
            chimera_df = None

        return ohlcv_df, chimera_df

    def _plot_report_plotly(self, stock_id: str, ohlcv_df: pd.DataFrame, chimera_df: pd.DataFrame | None, timeframe: str) -> go.Figure | None:
        if ohlcv_df.empty:
            print(f"({timeframe}) 沒有 OHLCV 數據可供繪製。")
            return None

        print(f"開始使用 Plotly 繪製 {timeframe} 報告圖表...")
        x_axis_data = ohlcv_df['timestamp']
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

        fig.add_trace(go.Candlestick(x=x_axis_data,
                                     open=ohlcv_df['open'], high=ohlcv_df['high'],
                                     low=ohlcv_df['low'], close=ohlcv_df['close'],
                                     name=f"K線 ({timeframe})",
                                     increasing_line_color='red', decreasing_line_color='green'),
                      row=1, col=1)

        volume_colors = ['red' if ohlcv_df['close'].iloc[i] >= ohlcv_df['open'].iloc[i] else 'green' for i in range(len(ohlcv_df))]
        fig.add_trace(go.Bar(x=x_axis_data, y=ohlcv_df['volume'], name="成交量", marker_color=volume_colors),
                      row=2, col=1)

        if chimera_df is not None and not chimera_df.empty:
            ohlcv_for_merge = ohlcv_df.copy()
            ohlcv_for_merge['date_for_signal_merge'] = ohlcv_for_merge['timestamp'].dt.normalize()
            current_stock_chimera_df = chimera_df[chimera_df['stock_id'] == stock_id]
            merged_for_plot = pd.merge(ohlcv_for_merge, current_stock_chimera_df,
                                       left_on='date_for_signal_merge', right_on='date',
                                       how='left', suffixes=('', '_chimera'))

            marker_styles = {
                "價漲量增_法人買超": {"symbol": "arrow-up", "color": "green", "size": 10, "legend_group": "buy_signal", "name": "價漲量增_法人買超"},
                "價跌量增_法人賣超": {"symbol": "arrow-down", "color": "red", "size": 10, "legend_group": "sell_signal", "name": "價跌量增_法人賣超"},
                "其他買超相關信號": {"symbol": "circle", "color": "lightgreen", "size": 7, "legend_group": "buy_signal_other", "name": "其他買超相關"},
                "其他賣超相關信號": {"symbol": "circle", "color": "lightcoral", "size": 7, "legend_group": "sell_signal_other", "name": "其他賣超相關"},
                "法人中性相關信號": {"symbol": "diamond", "color": "gold", "size": 7, "legend_group": "neutral_signal", "name": "法人中性相關"},
                "籌碼未知相關信號": {"symbol": "square", "color": "silver", "size": 6, "legend_group": "unknown_signal", "name": "籌碼未知相關"}
            }
            plot_data_points = {key: {'x': [], 'y': [], 'text': []} for key in marker_styles}

            for _, row in merged_for_plot.iterrows():
                signal = row.get('composite_signal', '')
                if pd.notna(signal) and pd.notna(row['high']):
                    y_pos = row['high'] * 1.02
                    style_key = None
                    if signal == "價漲量增_法人買超": style_key = "價漲量增_法人買超"
                    elif signal == "價跌量增_法人賣超": style_key = "價跌量增_法人賣超"
                    elif "法人買超" in signal: style_key = "其他買超相關信號"
                    elif "法人賣超" in signal: style_key = "其他賣超相關信號"
                    elif "法人中性" in signal: style_key = "法人中性相關信號"
                    elif "籌碼未知" in signal: style_key = "籌碼未知相關信號"
                    if style_key:
                        plot_data_points[style_key]['x'].append(row['timestamp'])
                        plot_data_points[style_key]['y'].append(y_pos)
                        plot_data_points[style_key]['text'].append(f"{row['composite_signal']} (日信號)")

            for style_key, data in plot_data_points.items():
                if data['x']:
                    style = marker_styles[style_key]
                    fig.add_trace(go.Scatter(
                        x=data['x'], y=data['y'], mode='markers',
                        marker_symbol=style["symbol"], marker_color=style["color"],
                        marker_size=style["size"], name=style["name"],
                        legendgroup=style["legend_group"], hoverinfo='text', text=data['text']
                    ), row=1, col=1)

        min_date_str = ohlcv_df['timestamp'].min().strftime('%Y-%m-%d %H:%M') if timeframe not in ['1d','1w','1m'] else ohlcv_df['timestamp'].min().strftime('%Y-%m-%d')
        max_date_str = ohlcv_df['timestamp'].max().strftime('%Y-%m-%d %H:%M') if timeframe not in ['1d','1w','1m'] else ohlcv_df['timestamp'].max().strftime('%Y-%m-%d')

        fig.update_layout(
            title_text=f"股票 {stock_id} ({timeframe}) 複合信號分析報告 ({min_date_str} 至 {max_date_str})",
            xaxis_rangeslider_visible=False,
            showlegend=True, legend_title_text='信號標記 (日級別)',
            hovermode='x unified'
        )
        fig.update_yaxes(title_text="股價", row=1, col=1)
        fig.update_yaxes(title_text="成交量", row=2, col=1)

        print(f"Plotly {timeframe} 圖表繪製完成。")
        return fig

    def generate_report(self, stock_id: str, start_date_str: str, end_date_str: str, timeframe: str, output_dir: Path) -> Path | None:
        report_file_path = None
        try:
            with self._connect_db() as con:
                ohlcv_df, chimera_df = self._fetch_data(con, stock_id, start_date_str, end_date_str, timeframe)

            if ohlcv_df is None or ohlcv_df.empty:
                print(f"股票 {stock_id} ({timeframe}) 在指定日期範圍內無 OHLCV 數據，無法生成報告。")
                return None

            fig = self._plot_report_plotly(stock_id, ohlcv_df, chimera_df, timeframe)

            if fig:
                output_dir.mkdir(parents=True, exist_ok=True)
                filename = f"{stock_id}_{timeframe}_{start_date_str.replace('-', '')}_{end_date_str.replace('-', '')}_report.html"
                report_file_path = output_dir / filename
                fig.write_html(str(report_file_path))
                print(f"報告已儲存至: {report_file_path} (HTML 格式)")
            else:
                print(f"Plotly 圖表物件 ({timeframe}) 未成功創建，無法儲存報告。")

            return report_file_path
        except Exception as e:
            print(f"生成報告 {stock_id} ({timeframe}) 時發生錯誤: {e}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == '__main__':
    print("執行 ReportGenerator (Plotly 版本) 初步測試...")
    # 測試用的資料庫路徑和輸出目錄
    test_db_name = "temp_plotly_report_test.duckdb"
    test_output_dir_name = "test_generator_reports_output"

    # 清理舊的測試資料庫和輸出目錄 (如果存在)
    test_db_file = Path(test_db_name)
    if test_db_file.exists():
        print(f"正在刪除舊的測試資料庫: {test_db_file}")
        test_db_file.unlink()

    test_output_dir = Path(test_output_dir_name)
    if test_output_dir.exists():
        import shutil
        print(f"正在刪除舊的測試輸出目錄: {test_output_dir}")
        shutil.rmtree(test_output_dir)
    test_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 創建測試資料庫和表
        with duckdb.connect(str(test_db_file)) as con:
            # 創建 ohlcv_1d 表 (用於日線測試)
            con.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_1d (
                timestamp TIMESTAMP, product_id VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT,
                PRIMARY KEY (timestamp, product_id)
            );""")
            ohlcv_1d_data = [
                (datetime(2023,1,1), 'TEST_STOCK_D', 10,12,9,11,1000),
                (datetime(2023,1,2), 'TEST_STOCK_D', 11,13,10.5,12.5,1200),
                (datetime(2023,1,3), 'TEST_STOCK_D', 12.5,12.5,11,11.5,800),
            ]
            con.executemany("INSERT INTO ohlcv_1d VALUES (?,?,?,?,?,?,?)", ohlcv_1d_data)
            print(f"已創建並填充 ohlcv_1d 測試數據到 {test_db_file}")

            # 創建 ohlcv_1h 表 (用於小時線測試)
            con.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_1h (
                timestamp TIMESTAMP, product_id VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT,
                PRIMARY KEY (timestamp, product_id)
            );""")
            ohlcv_1h_data = [
                (datetime(2023,1,1,9,0,0), 'TEST_STOCK_H', 10,10.5,9.8,10.2,200),
                (datetime(2023,1,1,10,0,0), 'TEST_STOCK_H', 10.2,11,10.1,10.8,300),
            ]
            con.executemany("INSERT INTO ohlcv_1h VALUES (?,?,?,?,?,?,?)", ohlcv_1h_data)
            print(f"已創建並填充 ohlcv_1h 測試數據到 {test_db_file}")

            # 創建 ohlcv_5min 表 (用於5分鐘線測試)
            con.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_5min (
                timestamp TIMESTAMP, product_id VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT,
                PRIMARY KEY (timestamp, product_id)
            );""")
            ohlcv_5min_data = [
                (datetime(2023,1,1,9,0,0), 'TEST_STOCK_5M', 100,100.5,99.8,100.2,20),
                (datetime(2023,1,1,9,5,0), 'TEST_STOCK_5M', 100.2,101,100.1,100.8,30),
            ]
            con.executemany("INSERT INTO ohlcv_5min VALUES (?,?,?,?,?,?,?)", ohlcv_5min_data)
            print(f"已創建並填充 ohlcv_5min 測試數據到 {test_db_file}")

            # 創建 chimera_daily_signals 表
            con.execute("""
            CREATE TABLE IF NOT EXISTS chimera_daily_signals (
                date DATE, stock_id VARCHAR, price_volume_label VARCHAR,
                institutional_flow_label VARCHAR, composite_signal VARCHAR,
                PRIMARY KEY (date, stock_id)
            );""")
            chimera_test_data = [
                (datetime(2023,1,1).date(), 'TEST_STOCK_D', '價漲量增', '法人買超', '價漲量增_法人買超'),
                (datetime(2023,1,2).date(), 'TEST_STOCK_D', '價跌量增', '法人賣超', '價跌量增_法人賣超'),
                (datetime(2023,1,1).date(), 'TEST_STOCK_H', '價漲量增', '法人買超', '價漲量增_法人買超'), # Chimera for hourly test stock
                (datetime(2023,1,1).date(), 'TEST_STOCK_5M', '價漲量增', '法人買超', '價漲量增_法人買超'), # Chimera for 5min test stock
            ]
            con.executemany("INSERT INTO chimera_daily_signals VALUES (?,?,?,?,?)", chimera_test_data)
            print(f"已創建並填充 chimera_daily_signals 測試數據到 {test_db_file}")

        generator = ReportGenerator(db_path=str(test_db_file))

        print("\n--- 測試生成日線 (1d) 報告 ---")
        report_1d = generator.generate_report(
            stock_id='TEST_STOCK_D', start_date_str='2023-01-01', end_date_str='2023-01-03',
            timeframe='1d', output_dir=test_output_dir
        )
        if report_1d and report_1d.exists(): print(f"日線 (1d) 報告生成成功: {report_1d}")
        else: print("日線 (1d) 報告生成失敗。")

        print("\n--- 測試生成小時線 (1h) 報告 ---")
        report_1h = generator.generate_report(
            stock_id='TEST_STOCK_H', start_date_str='2023-01-01', end_date_str='2023-01-01',
            timeframe='1h', output_dir=test_output_dir
        )
        if report_1h and report_1h.exists(): print(f"小時線 (1h) 報告生成成功: {report_1h}")
        else: print("小時線 (1h) 報告生成失敗。")

        print("\n--- 測試生成5分鐘線 (5min) 報告 ---")
        report_5min = generator.generate_report(
            stock_id='TEST_STOCK_5M', start_date_str='2023-01-01', end_date_str='2023-01-01',
            timeframe='5min', output_dir=test_output_dir
        )
        if report_5min and report_5min.exists(): print(f"5分鐘線 (5min) 報告生成成功: {report_5min}")
        else: print("5分鐘線 (5min) 報告生成失敗。")

        print("\n--- 測試無效 timeframe (invalid_tf) ---")
        try:
            generator.generate_report(
                stock_id='TEST_STOCK_D', start_date_str='2023-01-01', end_date_str='2023-01-03',
                timeframe='invalid@tf', output_dir=test_output_dir
            )
        except ValueError as ve:
            print(f"成功捕獲無效 timeframe 的 ValueError: {ve}")

        print("\n--- 測試缺少資料表的 timeframe (e.g., 4h if ohlcv_4h not created) ---")
        report_missing_table = generator.generate_report(
            stock_id='TEST_STOCK_D', start_date_str='2023-01-01', end_date_str='2023-01-03',
            timeframe='4h', output_dir=test_output_dir
        )
        if not report_missing_table:
            print(f"缺少資料表 timeframe (4h) 報告按預期未生成。")
        else:
            print(f"錯誤：缺少資料表 timeframe (4h) 報告不應生成，但得到了: {report_missing_table}")

    except Exception as e:
        print(f"ReportGenerator (Plotly 版本) __main__ 測試時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"\n測試完畢。如果需要，請手動檢查或刪除測試資料庫 '{test_db_file}' 和輸出目錄 '{test_output_dir_name}'。")

    print("\nReportGenerator (Plotly 版本) 初步測試完畢。")
