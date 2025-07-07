# apps/report_generator/generator.py
import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime

# 嘗試導入 matplotlib，如果失敗則在需要時提示用戶安裝
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from mplfinance.original_flavor import candlestick_ohlc # 使用舊版 mplfinance API 繪製K線
    # 注意: mplfinance.plot() 是新版API，更易用，但這裡先用 candlestick_ohlc 以便更精細控制標記
    # 如果 mplfinance 未安裝，candlestick_ohlc 也會報錯
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("警告：matplotlib 或 mplfinance 未安裝。報告生成功能將受限。請運行 'pip install matplotlib mplfinance'")

class ReportGenerator:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        if not MATPLOTLIB_AVAILABLE:
            # 可以在這裡決定是拋出異常還是僅打印警告並繼續（但無法繪圖）
            # raise ImportError("Matplotlib 和 mplfinance 是生成報告的必要套件。請安裝它們。")
            print("錯誤：Matplotlib 和 mplfinance 未安裝，無法初始化 ReportGenerator。")


    def _connect_db(self):
        try:
            con = duckdb.connect(database=self.db_path, read_only=True) # 報告生成通常是唯讀
            print(f"成功連接到資料庫 (唯讀): {self.db_path}")
            return con
        except Exception as e:
            print(f"連接資料庫 {self.db_path} 時發生錯誤: {e}")
            raise

    def _fetch_data(self, con: duckdb.DuckDBPyConnection, stock_id: str, start_date_str: str, end_date_str: str) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
        """獲取 OHLCV 和 Chimera 信號數據"""
        ohlcv_df = None
        chimera_df = None

        try:
            # 獲取 OHLCV 數據 (假設表名為 ohlcv_1d)
            # 注意：ohlcv_1d 中的 timestamp 欄位需要與 chimera_daily_signals 的 date 欄位對齊
            # ChimeraAnalyzer 產生的 chimera_daily_signals 的 date 欄位是 DATE 類型
            # ohlcv_1d 的 timestamp 若是 TIMESTAMP 類型，讀取後需轉換為 date
            query_ohlcv = """
            SELECT
                CAST(timestamp AS DATE) AS date, -- 將 timestamp 轉換為 date
                open, high, low, close, volume
            FROM ohlcv_1d
            WHERE product_id = $stock_id AND CAST(timestamp AS DATE) BETWEEN $start_date AND $end_date
            ORDER BY date;
            """
            ohlcv_df = con.execute(query_ohlcv, {'stock_id': stock_id, 'start_date': start_date_str, 'end_date': end_date_str}).fetchdf()
            if not ohlcv_df.empty:
                 ohlcv_df['date'] = pd.to_datetime(ohlcv_df['date']) # 轉換為 pandas datetime 物件
                 print(f"成功讀取 {len(ohlcv_df)} 筆 {stock_id} 的 OHLCV 數據。")
            else:
                print(f"未找到 {stock_id} 在 {start_date_str} 至 {end_date_str} 的 OHLCV 數據。")
                return None, None

        except Exception as e:
            print(f"讀取 OHLCV 數據時發生錯誤: {e}")
            return None, None # 如果 OHLCV 數據失敗，則不繼續

        try:
            # 獲取 Chimera 信號數據
            query_chimera = """
            SELECT date, stock_id, price_volume_label, institutional_flow_label, composite_signal
            FROM chimera_daily_signals
            WHERE stock_id = $stock_id AND date BETWEEN $start_date AND $end_date
            ORDER BY date;
            """
            chimera_df = con.execute(query_chimera, {'stock_id': stock_id, 'start_date': start_date_str, 'end_date': end_date_str}).fetchdf()
            if not chimera_df.empty:
                chimera_df['date'] = pd.to_datetime(chimera_df['date']) # 轉換為 pandas datetime 物件
                print(f"成功讀取 {len(chimera_df)} 筆 {stock_id} 的 Chimera 信號數據。")
            else:
                print(f"未找到 {stock_id} 在 {start_date_str} 至 {end_date_str} 的 Chimera 信號數據。")
                # 即使沒有 Chimera 數據，依然可以繪製 K 線圖，所以這裡不直接返回 None

        except Exception as e:
            print(f"讀取 Chimera 信號數據時發生錯誤: {e}")
            # Chimera 數據是可選的，如果失敗，僅 chimera_df 為 None

        return ohlcv_df, chimera_df

    def _plot_report(self, stock_id: str, ohlcv_df: pd.DataFrame, chimera_df: pd.DataFrame | None) -> plt.Figure | None:
        """繪製K線圖、成交量圖，並疊加複合信號標記"""
        if not MATPLOTLIB_AVAILABLE:
            print("Matplotlib/mplfinance 未安裝，無法繪製報告。")
            return None

        if ohlcv_df.empty:
            print("沒有 OHLCV 數據可供繪製。")
            return None

        print("開始繪製報告圖表...")
        fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(15, 10), gridspec_kw={'height_ratios': [3, 1]})
        fig.suptitle(f"股票 {stock_id} 複合信號分析報告 ({ohlcv_df['date'].min().strftime('%Y-%m-%d')} 至 {ohlcv_df['date'].max().strftime('%Y-%m-%d')})", fontsize=16)

        # 1. 繪製K線圖 (使用 mplfinance.original_flavor)
        # 準備 candlestick_ohlc 所需的數據格式 (date, open, high, low, close)
        # date 需要是 matplotlib compatible float format
        ohlc_data_for_plot = ohlcv_df[['date', 'open', 'high', 'low', 'close']].copy()
        ohlc_data_for_plot['date_num'] = ohlc_data_for_plot['date'].map(mdates.date2num)

        candlestick_ohlc(ax1, ohlc_data_for_plot[['date_num', 'open', 'high', 'low', 'close']].values, width=0.6, colorup='green', colordown='red', alpha=0.8)
        ax1.set_ylabel("股價")
        ax1.grid(True, linestyle='--', alpha=0.7)

        # 2. 繪製成交量柱狀圖
        ax2.bar(ohlcv_df['date'], ohlcv_df['volume'], color='grey', alpha=0.7, width=0.8)
        ax2.set_ylabel("成交量")
        ax2.grid(True, linestyle='--', alpha=0.7)

        # 設定X軸日期格式
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45) # 旋轉日期標籤以防重疊

        # 3. 疊加複合信號標記
        if chimera_df is not None and not chimera_df.empty:
            merged_for_plot = pd.merge(ohlcv_df.reset_index(), chimera_df, on='date', how='left')

            for i, row in merged_for_plot.iterrows():
                signal = row.get('composite_signal', '') # 使用 .get 以防欄位不存在
                # 確保日期在繪圖範圍內，並且有信號
                if pd.notna(signal) and row['date'] in ohlc_data_for_plot['date'].values:
                    # 獲取該日期對應的K線位置 (使用索引或日期)
                    # K線高點用於在其上方標記
                    y_pos = row['high'] * 1.02 # 在高點上方一點

                    # 根據信號類型選擇標記
                    # 統一標記大小和透明度，除非特別強調
                    marker_size = 8
                    alpha_value = 0.85

                    if signal == "價漲量增_法人買超":
                        # 鮮明的綠色向上箭頭
                        ax1.plot(row['date'], y_pos, '^', color='green', markersize=marker_size+2, alpha=alpha_value, label='價漲量增_法人買超' if '價漲量增_法人買超' not in ax1.get_legend_handles_labels()[1] else "")
                    elif signal == "價跌量增_法人賣超":
                        # 鮮明的紅色向下箭頭
                        ax1.plot(row['date'], y_pos, 'v', color='red', markersize=marker_size+2, alpha=alpha_value, label='價跌量增_法人賣超' if '價跌量增_法人賣超' not in ax1.get_legend_handles_labels()[1] else "")
                    # 其他信號使用圓點標示，並根據籌碼流向決定顏色基調
                    elif "法人買超" in signal: # 其他類型的法人買超 (例如價跌量縮_法人買超)
                        ax1.plot(row['date'], y_pos, 'o', color='lightgreen', markersize=marker_size, alpha=alpha_value, label='其他買超相關信號' if '其他買超相關信號' not in ax1.get_legend_handles_labels()[1] else "")
                    elif "法人賣超" in signal: # 其他類型的法人賣超
                         ax1.plot(row['date'], y_pos, 'o', color='lightcoral', markersize=marker_size, alpha=alpha_value, label='其他賣超相關信號' if '其他賣超相關信號' not in ax1.get_legend_handles_labels()[1] else "")
                    elif "法人中性" in signal:
                        ax1.plot(row['date'], y_pos, 'o', color='gold', markersize=marker_size, alpha=alpha_value, label='法人中性相關信號' if '法人中性相關信號' not in ax1.get_legend_handles_labels()[1] else "")
                    elif "籌碼未知" in signal:
                        ax1.plot(row['date'], y_pos, 'o', color='silver', markersize=marker_size-2, alpha=alpha_value-0.2, label='籌碼未知相關信號' if '籌碼未知相關信號' not in ax1.get_legend_handles_labels()[1] else "")

            # 產生圖例，避免重複標籤
            handles, labels = ax1.get_legend_handles_labels()
            if handles: # 只有在有標記時才顯示圖例
                 # 按標籤排序圖例，可以使圖例更整齊
                 # sorted_legend_elements = sorted(zip(labels, handles), key=lambda x: x[0])
                 # by_label = dict(sorted_legend_elements)
                 by_label = dict(zip(labels, handles)) # 保持原樣，或者按出現順序
                 ax1.legend(by_label.values(), by_label.keys(), loc='upper left', fontsize='small')

        plt.tight_layout(rect=[0, 0, 1, 0.96]) # 調整佈局以容納主標題
        print("圖表繪製完成。")
        return fig

    def generate_report(self, stock_id: str, start_date_str: str, end_date_str: str, output_dir: Path) -> Path | None:
        """生成並儲存報告圖檔"""
        if not MATPLOTLIB_AVAILABLE:
            print("Matplotlib/mplfinance 未安裝，無法生成報告。")
            return None

        try:
            with self._connect_db() as con:
                ohlcv_df, chimera_df = self._fetch_data(con, stock_id, start_date_str, end_date_str)

            if ohlcv_df is None or ohlcv_df.empty:
                print(f"股票 {stock_id} 在指定日期範圍內無 OHLCV 數據，無法生成報告。")
                return None

            fig = self._plot_report(stock_id, ohlcv_df, chimera_df)

            if fig:
                # 確保輸出目錄存在
                output_dir.mkdir(parents=True, exist_ok=True)

                # 生成檔案名
                filename = f"{stock_id}_{start_date_str.replace('-', '')}_{end_date_str.replace('-', '')}_report.png"
                report_path = output_dir / filename

                fig.savefig(report_path)
                plt.close(fig) # 關閉圖形以釋放記憶體
                print(f"報告已儲存至: {report_path}")
                return report_path
            else:
                print("圖表物件未成功創建，無法儲存報告。")
                return None

        except Exception as e:
            print(f"生成報告 {stock_id} 時發生錯誤: {e}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == '__main__':
    # 初步測試 (需要一個包含 ohlcv_1d 和 chimera_daily_signals 表的 duckdb 文件)
    print("執行 ReportGenerator 初步測試...")

    # 準備一個臨時的測試資料庫
    test_db_for_report_path = Path("./temp_report_test.duckdb")
    if test_db_for_report_path.exists():
        test_db_for_report_path.unlink()

    try:
        with duckdb.connect(str(test_db_for_report_path)) as con:
            # 創建並填充 ohlcv_1d
            con.execute("""
            CREATE TABLE ohlcv_1d (
                timestamp TIMESTAMP, product_id VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT
            );""")
            ohlcv_test_data = [
                (datetime(2023,1,1), 'TESTS', 10,12,9,11,1000), (datetime(2023,1,2), 'TESTS', 11,13,10.5,12.5,1200),
                (datetime(2023,1,3), 'TESTS', 12.5,12.5,11,11.5,800), (datetime(2023,1,4), 'TESTS', 11.5,12,11,11.8,1500),
                (datetime(2023,1,5), 'TESTS', 11.8,13,11.5,12.8,2000)
            ]
            con.executemany("INSERT INTO ohlcv_1d VALUES (?,?,?,?,?,?,?)", ohlcv_test_data)

            # 創建並填充 chimera_daily_signals
            con.execute("""
            CREATE TABLE chimera_daily_signals (
                date DATE, stock_id VARCHAR, price_volume_label VARCHAR,
                institutional_flow_label VARCHAR, composite_signal VARCHAR
            );""")
            chimera_test_data = [
                (datetime(2023,1,2).date(), 'TESTS', '價漲量增', '法人買超', '價漲量增_法人買超'),
                (datetime(2023,1,3).date(), 'TESTS', '價跌量縮', '法人賣超', '價跌量縮_法人賣超'),
                (datetime(2023,1,4).date(), 'TESTS', '價漲量增', '法人中性', '價漲量增_法人中性'),
                (datetime(2023,1,5).date(), 'TESTS', '價漲量增', '籌碼未知', '價漲量增_籌碼未知'),
            ]
            con.executemany("INSERT INTO chimera_daily_signals VALUES (?,?,?,?,?)", chimera_test_data)

        # 執行報告生成
        if MATPLOTLIB_AVAILABLE:
            output_test_dir = Path("./test_reports_output")
            generator = ReportGenerator(db_path=test_db_for_report_path)
            report_file = generator.generate_report(
                stock_id='TESTS',
                start_date_str='2023-01-01',
                end_date_str='2023-01-05',
                output_dir=output_test_dir
            )
            if report_file and report_file.exists():
                print(f"初步測試報告生成成功: {report_file}")
            else:
                print("初步測試報告生成失敗。")
        else:
            print("Matplotlib/mplfinance 未安裝，跳過 ReportGenerator 的 __main__ 測試中的繪圖部分。")

    except Exception as e:
        print(f"ReportGenerator 初步測試時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if test_db_for_report_path.exists():
            # test_db_for_report_path.unlink() # 方便檢查
            print(f"提醒: 測試資料庫 {test_db_for_report_path} 未自動刪除。")

    print("ReportGenerator 初步測試完畢。")
