# apps/report_generator/generator.py
import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime

# 導入 Plotly
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    print("警告：Plotly 未安裝。報告生成功能將受限。請運行 'pip install plotly'")

class ReportGenerator:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        if not PLOTLY_AVAILABLE:
            raise ImportError("Plotly 是生成報告的必要套件。請安裝它。")

    def _connect_db(self):
        try:
            con = duckdb.connect(database=self.db_path, read_only=True)
            print(f"成功連接到資料庫 (唯讀): {self.db_path}")
            return con
        except Exception as e:
            print(f"連接資料庫 {self.db_path} 時發生錯誤: {e}")
            raise

    def _fetch_data(self, con: duckdb.DuckDBPyConnection, stock_id: str, start_date_str: str, end_date_str: str) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
        ohlcv_df = None
        chimera_df = None
        try:
            query_ohlcv = """
            SELECT CAST(timestamp AS DATE) AS date, open, high, low, close, volume
            FROM ohlcv_1d
            WHERE product_id = $stock_id AND CAST(timestamp AS DATE) BETWEEN $start_date AND $end_date
            ORDER BY date;
            """
            ohlcv_df = con.execute(query_ohlcv, {'stock_id': stock_id, 'start_date': start_date_str, 'end_date': end_date_str}).fetchdf()
            if not ohlcv_df.empty:
                 ohlcv_df['date'] = pd.to_datetime(ohlcv_df['date'])
                 print(f"成功讀取 {len(ohlcv_df)} 筆 {stock_id} 的 OHLCV 數據。")
            else:
                print(f"未找到 {stock_id} 在 {start_date_str} 至 {end_date_str} 的 OHLCV 數據。")
                return None, None
        except Exception as e:
            print(f"讀取 OHLCV 數據時發生錯誤: {e}")
            return None, None

        try:
            query_chimera = """
            SELECT date, stock_id, price_volume_label, institutional_flow_label, composite_signal
            FROM chimera_daily_signals
            WHERE stock_id = $stock_id AND date BETWEEN $start_date AND $end_date
            ORDER BY date;
            """
            chimera_df = con.execute(query_chimera, {'stock_id': stock_id, 'start_date': start_date_str, 'end_date': end_date_str}).fetchdf()
            if not chimera_df.empty:
                chimera_df['date'] = pd.to_datetime(chimera_df['date'])
                print(f"成功讀取 {len(chimera_df)} 筆 {stock_id} 的 Chimera 信號數據。")
            else:
                print(f"未找到 {stock_id} 在 {start_date_str} 至 {end_date_str} 的 Chimera 信號數據。")
        except Exception as e:
            print(f"讀取 Chimera 信號數據時發生錯誤: {e}")
        return ohlcv_df, chimera_df

    def _plot_report_plotly(self, stock_id: str, ohlcv_df: pd.DataFrame, chimera_df: pd.DataFrame | None) -> go.Figure | None:
        if ohlcv_df.empty:
            print("沒有 OHLCV 數據可供繪製。")
            return None

        print("開始使用 Plotly 繪製報告圖表...")

        # 創建帶有兩個子圖的圖形：一個用於K線，一個用於成交量
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                           vertical_spacing=0.05, row_heights=[0.7, 0.3])

        # 1. 繪製K線圖
        fig.add_trace(go.Candlestick(x=ohlcv_df['date'],
                                     open=ohlcv_df['open'],
                                     high=ohlcv_df['high'],
                                     low=ohlcv_df['low'],
                                     close=ohlcv_df['close'],
                                     name="K線",
                                     increasing_line_color='red', # 台股習慣紅漲綠跌
                                     decreasing_line_color='green'),
                      row=1, col=1)

        # 2. 繪製成交量柱狀圖
        # 根據漲跌決定成交量顏色
        volume_colors = ['red' if ohlcv_df['close'][i] >= ohlcv_df['open'][i] else 'green' for i in range(len(ohlcv_df))]
        fig.add_trace(go.Bar(x=ohlcv_df['date'], y=ohlcv_df['volume'], name="成交量", marker_color=volume_colors),
                      row=2, col=1)

        # 3. 疊加複合信號標記
        # 我們將為每種標記類型創建一個單獨的 scatter trace，以便更好地控制圖例
        if chimera_df is not None and not chimera_df.empty:
            merged_for_plot = pd.merge(ohlcv_df, chimera_df, on='date', how='left')

            # 定義標記樣式
            marker_styles = {
                "價漲量增_法人買超": {"symbol": "arrow-up", "color": "green", "size": 10, "legend_group": "buy_signal", "name": "價漲量增_法人買超"},
                "價跌量增_法人賣超": {"symbol": "arrow-down", "color": "red", "size": 10, "legend_group": "sell_signal", "name": "價跌量增_法人賣超"},
                "其他買超相關信號": {"symbol": "circle", "color": "lightgreen", "size": 7, "legend_group": "buy_signal_other", "name": "其他買超相關"},
                "其他賣超相關信號": {"symbol": "circle", "color": "lightcoral", "size": 7, "legend_group": "sell_signal_other", "name": "其他賣超相關"},
                "法人中性相關信號": {"symbol": "diamond", "color": "gold", "size": 7, "legend_group": "neutral_signal", "name": "法人中性相關"},
                "籌碼未知相關信號": {"symbol": "square", "color": "silver", "size": 6, "legend_group": "unknown_signal", "name": "籌碼未知相關"}
            }

            # 預先準備好每種標記類型的數據列表
            plot_data_points = {key: {'x': [], 'y': [], 'text': []} for key in marker_styles}

            for i, row in merged_for_plot.iterrows():
                signal = row.get('composite_signal', '')
                if pd.notna(signal):
                    y_pos = row['high'] * 1.02 # 標記在K線高點上方

                    style_key = None
                    if signal == "價漲量增_法人買超": style_key = "價漲量增_法人買超"
                    elif signal == "價跌量增_法人賣超": style_key = "價跌量增_法人賣超"
                    elif "法人買超" in signal: style_key = "其他買超相關信號"
                    elif "法人賣超" in signal: style_key = "其他賣超相關信號"
                    elif "法人中性" in signal: style_key = "法人中性相關信號"
                    elif "籌碼未知" in signal: style_key = "籌碼未知相關信號"

                    if style_key:
                        plot_data_points[style_key]['x'].append(row['date'])
                        plot_data_points[style_key]['y'].append(y_pos)
                        plot_data_points[style_key]['text'].append(f"{row['composite_signal']}") # 懸停文本

            # 為每種標記類型添加一個 trace
            for style_key, data in plot_data_points.items():
                if data['x']: # 只有當有數據點時才添加 trace
                    style = marker_styles[style_key]
                    fig.add_trace(go.Scatter(
                        x=data['x'],
                        y=data['y'],
                        mode='markers',
                        marker_symbol=style["symbol"],
                        marker_color=style["color"],
                        marker_size=style["size"],
                        name=style["name"], # 用於圖例
                        legendgroup=style["legend_group"], # 用於分組圖例項
                        hoverinfo='text', # 顯示自定義懸停文本
                        text=data['text']
                    ), row=1, col=1)

        # 更新圖表佈局
        fig.update_layout(
            title_text=f"股票 {stock_id} 複合信號分析報告 ({ohlcv_df['date'].min().strftime('%Y-%m-%d')} 至 {ohlcv_df['date'].max().strftime('%Y-%m-%d')})",
            xaxis_rangeslider_visible=False, # 禁用K線圖下方的範圍滑塊
            showlegend=True,
            legend_title_text='信號標記',
            hovermode='x unified' # 統一X軸的懸停效果
        )
        fig.update_yaxes(title_text="股價", row=1, col=1)
        fig.update_yaxes(title_text="成交量", row=2, col=1)

        print("Plotly 圖表繪製完成。")
        return fig

    def generate_report(self, stock_id: str, start_date_str: str, end_date_str: str, output_dir: Path) -> Path | None:
        if not PLOTLY_AVAILABLE:
            print("Plotly 未安裝，無法生成報告。")
            return None
        try:
            with self._connect_db() as con:
                ohlcv_df, chimera_df = self._fetch_data(con, stock_id, start_date_str, end_date_str)

            if ohlcv_df is None or ohlcv_df.empty:
                print(f"股票 {stock_id} 在指定日期範圍內無 OHLCV 數據，無法生成報告。")
                return None

            fig = self._plot_report_plotly(stock_id, ohlcv_df, chimera_df)

            if fig:
                output_dir.mkdir(parents=True, exist_ok=True)
                # 更改檔案擴展名為 .html
                filename = f"{stock_id}_{start_date_str.replace('-', '')}_{end_date_str.replace('-', '')}_report.html"
                report_path = output_dir / filename

                fig.write_html(str(report_path)) # 保存為 HTML
                print(f"報告已儲存至: {report_path} (HTML 格式)")
                return report_path
            else:
                print("Plotly 圖表物件未成功創建，無法儲存報告。")
                return None
        except Exception as e:
            print(f"生成報告 {stock_id} 時發生錯誤: {e}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == '__main__':
    print("執行 ReportGenerator (Plotly 版本) 初步測試...")
    test_db_for_report_path = Path("./temp_plotly_report_test.duckdb")
    if test_db_for_report_path.exists():
        test_db_for_report_path.unlink()

    try:
        with duckdb.connect(str(test_db_for_report_path)) as con:
            con.execute("""
            CREATE TABLE ohlcv_1d (
                timestamp TIMESTAMP, product_id VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT
            );""")
            ohlcv_test_data = [
                (datetime(2023,1,1), 'PLOTLY_S', 10,12,9,11,1000), (datetime(2023,1,2), 'PLOTLY_S', 11,13,10.5,12.5,1200),
                (datetime(2023,1,3), 'PLOTLY_S', 12.5,12.5,11,11.5,800), (datetime(2023,1,4), 'PLOTLY_S', 11.5,12,11,11.8,1500),
                (datetime(2023,1,5), 'PLOTLY_S', 11.8,13,11.5,12.8,2000)
            ]
            con.executemany("INSERT INTO ohlcv_1d VALUES (?,?,?,?,?,?,?)", ohlcv_test_data)

            con.execute("""
            CREATE TABLE chimera_daily_signals (
                date DATE, stock_id VARCHAR, price_volume_label VARCHAR,
                institutional_flow_label VARCHAR, composite_signal VARCHAR
            );""")
            chimera_test_data = [
                (datetime(2023,1,2).date(), 'PLOTLY_S', '價漲量增', '法人買超', '價漲量增_法人買超'),
                (datetime(2023,1,3).date(), 'PLOTLY_S', '價跌量增', '法人賣超', '價跌量增_法人賣超'), # 修改為價跌量增以測試紅色箭頭
                (datetime(2023,1,4).date(), 'PLOTLY_S', '價漲量增', '法人中性', '價漲量增_法人中性'),
                (datetime(2023,1,5).date(), 'PLOTLY_S', '價漲量縮', '籌碼未知', '價漲量縮_籌碼未知'), # 修改為價漲量縮
            ]
            con.executemany("INSERT INTO chimera_daily_signals VALUES (?,?,?,?,?)", chimera_test_data)

        if PLOTLY_AVAILABLE:
            output_test_dir = Path("./test_plotly_reports_output")
            generator = ReportGenerator(db_path=test_db_for_report_path)
            report_file = generator.generate_report(
                stock_id='PLOTLY_S',
                start_date_str='2023-01-01',
                end_date_str='2023-01-05',
                output_dir=output_test_dir
            )
            if report_file and report_file.exists():
                print(f"初步 Plotly 測試報告生成成功: {report_file}")
            else:
                print("初步 Plotly 測試報告生成失敗。")
        else:
            print("Plotly 未安裝，跳過 ReportGenerator (Plotly 版本) 的 __main__ 測試中的繪圖部分。")

    except Exception as e:
        print(f"ReportGenerator (Plotly 版本) 初步測試時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if test_db_for_report_path.exists():
            print(f"提醒: 測試資料庫 {test_db_for_report_path} 未自動刪除。")

    print("ReportGenerator (Plotly 版本) 初步測試完畢。")
