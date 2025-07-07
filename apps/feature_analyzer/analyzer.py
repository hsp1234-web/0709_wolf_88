# apps/feature_analyzer/analyzer.py
import duckdb
import pandas as pd
import numpy as np # 引入 numpy
from pathlib import Path

# 假設 analytics_mart.duckdb 位於專案根目錄
# 這個路徑可能需要根據實際的項目結構或配置進行調整
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "analytics_mart.duckdb"

class ChimeraAnalyzer:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = str(db_path)
        self.ohlcv_table_1d = "ohlcv_1d" # 假設日OHLCV數據表名
        self.institutional_trades_table = "institutional_trades"
        # 新的複合分析結果表，將在後續步驟中定義其完整創建邏輯
        self.composite_signal_table = "chimera_daily_signals"

    def _connect_db(self):
        try:
            con = duckdb.connect(database=self.db_path, read_only=False)
            print(f"成功連接到資料庫: {self.db_path}")
            return con
        except Exception as e:
            print(f"連接資料庫 {self.db_path} 時發生錯誤: {e}")
            raise

    def _get_daily_ohlcv_data(self, con: duckdb.DuckDBPyConnection, start_date: str | None = None, end_date: str | None = None, stock_ids: list[str] | None = None) -> pd.DataFrame:
        """從 ohlcv_1d 表讀取日 OHLCV 數據"""
        query = f"SELECT timestamp AS date, product_id AS stock_id, open, high, low, close, volume FROM {self.ohlcv_table_1d}"

        conditions = []
        params = {}
        if start_date:
            conditions.append("date >= $start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("date <= $end_date")
            params["end_date"] = end_date
        if stock_ids:
            conditions.append("stock_id IN {}".format(tuple(stock_ids) if len(stock_ids) > 1 else f"('{stock_ids[0]}')"))
            # DuckDB 的 $ 參數化不支持直接用於 IN 子句中的列表，所以這裡直接格式化，需確保 stock_ids 來源安全

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY stock_id, date"

        print(f"正在讀取日 OHLCV 數據 ({self.ohlcv_table_1d})...")
        try:
            df = con.execute(query, params).fetchdf()
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date']).dt.date # 確保 date 欄位是 date 類型
            print(f"成功讀取 {len(df)} 筆日 OHLCV 數據。")
            return df
        except Exception as e:
            print(f"讀取 {self.ohlcv_table_1d} 表時發生錯誤: {e}")
            return pd.DataFrame()

    def _get_daily_institutional_net_shares(self, con: duckdb.DuckDBPyConnection, start_date: str | None = None, end_date: str | None = None, stock_ids: list[str] | None = None) -> pd.DataFrame:
        """從 institutional_trades 表讀取並聚合每日總法人淨買賣超數據"""
        query = f"""
        SELECT
            date,
            stock_id,
            SUM(net_shares) AS total_net_shares
        FROM {self.institutional_trades_table}
        """
        conditions = []
        params = {}
        if start_date:
            conditions.append("date >= $start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("date <= $end_date")
            params["end_date"] = end_date
        if stock_ids:
            conditions.append("stock_id IN {}".format(tuple(stock_ids) if len(stock_ids) > 1 else f"('{stock_ids[0]}')"))

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " GROUP BY date, stock_id ORDER BY stock_id, date"

        print(f"正在讀取並聚合每日法人淨買賣超數據 ({self.institutional_trades_table})...")
        try:
            df = con.execute(query, params).fetchdf()
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date']).dt.date # 確保 date 欄位是 date 類型
            print(f"成功讀取並聚合 {len(df)} 筆每日法人淨買賣超數據。")
            return df
        except Exception as e:
            print(f"讀取 {self.institutional_trades_table} 表時發生錯誤: {e}")
            return pd.DataFrame()

    def _merge_data(self, ohlcv_df: pd.DataFrame, institutional_df: pd.DataFrame) -> pd.DataFrame:
        """將 OHLCV 數據與法人數據按 date 和 stock_id 左連接"""
        if ohlcv_df.empty:
            print("OHLCV 數據為空，無法進行合併。")
            return pd.DataFrame()

        if institutional_df.empty:
            print("法人數據為空，OHLCV 數據將不包含法人相關欄位。")
            # 直接返回 ohlcv_df，後續分析流程需要能處理 total_net_shares 為 NaN 的情況
            ohlcv_df['total_net_shares'] = np.nan
            return ohlcv_df

        print("正在合併 OHLCV 數據與法人淨買賣超數據...")
        # 確保 'date' 欄位都是 datetime.date 類型，以利合併
        # _get_daily_ohlcv_data 和 _get_daily_institutional_net_shares 中已處理

        merged_df = pd.merge(ohlcv_df, institutional_df, on=['date', 'stock_id'], how='left')
        # 左連接後，沒有法人數據的日期，其 total_net_shares 會是 NaN
        print(f"數據合併完成。合併後共 {len(merged_df)} 筆記錄。")
        return merged_df

    # calculate_quadrant 和 analyze_features 的邏輯將在後續步驟中遷移和修改
    # analyze_features 將被重構為 run_composite_analysis

    def calculate_quadrant(self, price_change_pct: float, volume_change_pct: float) -> int:
        """
        根據價格變化百分比和成交量變化百分比確定象限。
        (此函數從舊的 run.py 遷移過來，邏輯暫時不變)
        """
        if price_change_pct > 0 and volume_change_pct > 0: return 1 # 價漲量增
        elif price_change_pct < 0 and volume_change_pct > 0: return 2 # 價跌量增
        elif price_change_pct < 0 and volume_change_pct < 0: return 3 # 價跌量縮
        elif price_change_pct > 0 and volume_change_pct < 0: return 4 # 價漲量縮
        elif price_change_pct == 0 or volume_change_pct == 0:
            if price_change_pct > 0: return 1
            if price_change_pct < 0: return 2
            if volume_change_pct > 0: return 1
            if volume_change_pct < 0: return 3
        return 0 # 預設或無法分類

    def run_feature_engineering(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        在合併後的 DataFrame 上執行基礎的價量特徵工程。
        (此部分邏輯從舊的 run.py 中的 analyze_features 遷移和調整)
        """
        if df.empty or 'close' not in df.columns or 'volume' not in df.columns:
            print("數據不完整，無法計算價量變化百分比。")
            return df

        print("計算價格與成交量變化百分比...")
        df['price_change_pct'] = df.groupby('stock_id')['close'].pct_change().fillna(0) * 100

        df['volume_prev'] = df.groupby('stock_id')['volume'].shift(1)
        conditions = [
            df['volume_prev'].isnull(),
            (df['volume_prev'] == 0) & (df['volume'] == 0),
            (df['volume_prev'] == 0) & (df['volume'] > 0)
        ]
        choices = [0, 0, 100.0]
        df['volume_change_pct'] = pd.Series(
            np.select(conditions, choices, default=(df['volume'] - df['volume_prev']) / df['volume_prev'] * 100),
            index=df.index
        ).fillna(0)

        df.drop(columns=['volume_prev'], inplace=True, errors='ignore')

        print("計算價量四象限...")
        df['price_volume_quadrant'] = df.apply(
            lambda row: self.calculate_quadrant(row['price_change_pct'], row['volume_change_pct']),
            axis=1
        )
        return df

    def _get_price_volume_quadrant_label(self, quadrant_code: int) -> str:
        """將價量四象限代碼轉換為可讀標籤"""
        labels = {
            1: "價漲量增",
            2: "價跌量增",
            3: "價跌量縮",
            4: "價漲量縮",
            0: "價量平移" # 或其他無法分類的標籤
        }
        return labels.get(quadrant_code, "象限未知")

    def _calculate_institutional_flow_label(self, total_net_shares: float | None, threshold_buy: float = 0, threshold_sell: float = 0) -> str:
        """
        根據總法人淨買賣超計算籌碼流向標籤。
        threshold_buy: 定義「買超」的最小正值 (不含)。
        threshold_sell: 定義「賣超」的最大負值 (不含)。
        例如: threshold_buy=1000, threshold_sell=-1000
              net_shares > 1000 -> 法人買超
              net_shares < -1000 -> 法人賣超
              -1000 <= net_shares <= 1000 -> 法人中性
        如果使用預設值 0, 則 >0 為買超, <0 為賣超, ==0 為中性。
        """
        if pd.isna(total_net_shares):
            return "籌碼未知"

        if total_net_shares > threshold_buy:
            return "法人買超"
        elif total_net_shares < threshold_sell: # 注意這裡是 < threshold_sell (一個負數)
            return "法人賣超"
        else: # total_net_shares is between threshold_sell and threshold_buy (inclusive if they are non-zero) or exactly 0
            return "法人中性"

    def _apply_composite_signal_logic(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        在已包含價量四象限和總法人淨買賣超的 DataFrame 上應用複合信號邏輯。
        """
        if df.empty:
            return df

        if 'price_volume_quadrant' not in df.columns:
            print("錯誤: 'price_volume_quadrant' 欄位不存在，無法計算複合信號。")
            return df
        # total_net_shares 可能不存在 (如果法人數據完全缺失)，或者存在但部分行為 NaN

        print("計算籌碼流向標籤與複合信號...")

        # 應用籌碼流向標籤
        # 這裡使用預設閾值 0，即 >0 為買超, <0 為賣超, ==0 為中性
        df['institutional_flow_label'] = df['total_net_shares'].apply(
            lambda x: self._calculate_institutional_flow_label(x)
        )

        # 獲取價量象限的可讀標籤
        df['price_volume_label'] = df['price_volume_quadrant'].apply(self._get_price_volume_quadrant_label)

        # 生成複合信號
        df['composite_signal'] = df['price_volume_label'] + "_" + df['institutional_flow_label']

        print("複合信號計算完成。")
        return df

    def _ensure_composite_signal_table_exists(self, con: duckdb.DuckDBPyConnection):
        """確保 chimera_daily_signals 表格在 DuckDB 中存在"""
        try:
            # 欄位根據規劃 1.e 和後續分析中實際產生的欄位來定義
            # price_change_pct, volume_change_pct 也一併存入供參考
            con.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.composite_signal_table} (
                date DATE,
                stock_id VARCHAR,
                price_change_pct DOUBLE,
                volume_change_pct DOUBLE,
                price_volume_quadrant INTEGER,
                price_volume_label VARCHAR,
                total_net_shares BIGINT,       -- 可能為 NULL (如果當日無法人數據)
                institutional_flow_label VARCHAR,
                composite_signal VARCHAR,
                PRIMARY KEY (date, stock_id)
            );
            """)
            print(f"資料表 '{self.composite_signal_table}' 已確認/創建。")
        except Exception as e:
            print(f"檢查或創建 {self.composite_signal_table} 表格時發生錯誤: {e}")
            raise

    def _store_composite_signals(self, con: duckdb.DuckDBPyConnection, data_df: pd.DataFrame):
        """將包含複合信號的分析結果儲存到 DuckDB"""
        if data_df.empty:
            print("沒有複合信號數據可儲存。")
            return

        # 選取要儲存的欄位，確保順序和表格定義一致 (雖然 DuckDB append 不嚴格要求順序)
        # 必須確保 data_df 中包含這些欄位
        columns_to_store = [
            'date', 'stock_id',
            'price_change_pct', 'volume_change_pct',
            'price_volume_quadrant', 'price_volume_label',
            'total_net_shares', 'institutional_flow_label',
            'composite_signal'
        ]
        # 檢查 data_df 是否包含所有必要欄位
        missing_cols = [col for col in columns_to_store if col not in data_df.columns]
        if missing_cols:
            print(f"錯誤: DataFrame 中缺少以下欄位，無法儲存: {missing_cols}")
            return

        df_to_store = data_df[columns_to_store]

        print(f"準備將 {len(df_to_store)} 筆複合信號結果儲存到 {self.composite_signal_table}...")
        try:
            # 實現 Upsert 邏輯: 先刪除已存在的記錄，再插入新的
            # 假設 date 和 stock_id 是複合主鍵
            # 為了簡化，這裡可以對整個 DataFrame 的日期和股票範圍進行刪除
            # 或者更精確地，逐條 Upsert (但效率較低)
            # DuckDB 的 INSERT OR REPLACE (SQLite) 或 ON CONFLICT (PostgreSQL/DuckDB) 語法更適合 Upsert
            # 使用 ON CONFLICT (col1, col2, ...) DO UPDATE SET ...

            # 這裡採用先刪後插的策略，適用於批次更新
            # 獲取 DataFrame 中的最小/最大日期和所有股票ID，以縮小刪除範圍
            if not df_to_store.empty:
                min_date = df_to_store['date'].min()
                max_date = df_to_store['date'].max()
                stock_ids_in_df = tuple(df_to_store['stock_id'].unique())

                if not stock_ids_in_df: # 如果 stock_ids_in_df 為空
                    print("DataFrame 中沒有 stock_id，無法執行刪除操作。")
                    return

                # 處理 stock_ids_in_df 只有一個元素的情況
                stock_id_filter_sql = f"stock_id = '{stock_ids_in_df[0]}'" if len(stock_ids_in_df) == 1 else f"stock_id IN {stock_ids_in_df}"

                delete_query = f"""
                DELETE FROM {self.composite_signal_table}
                WHERE date >= '{min_date}' AND date <= '{max_date}' AND {stock_id_filter_sql}
                """
                con.execute(delete_query)
                print(f"已刪除在 {min_date} 至 {max_date} 期間，針對股票 {stock_ids_in_df} 的舊記錄 (如有)。")

            con.append(self.composite_signal_table, df_to_store)
            con.commit() # 確保事務提交
            print(f"成功將 {len(df_to_store)} 筆結果寫入 '{self.composite_signal_table}'。")

        except Exception as e:
            print(f"儲存複合信號結果到 DuckDB 時發生錯誤: {e}")
            # 考慮回滾或更複雜的錯誤處理
            raise

    def run_composite_analysis(self, start_date: str | None = None, end_date: str | None = None, stock_ids: list[str] | None = None):
        """
        執行完整的複合分析流程：
        1. 連接資料庫並確保目標表格存在。
        2. 讀取並合併 OHLCV 及法人數據。
        3. 執行價量特徵工程 (計算百分比變化、價量四象限)。
        4. 計算籌碼流向標籤及複合信號。
        5. 儲存結果到資料庫。
        """
        print(f"開始執行複合分析 (股票: {stock_ids or '所有'}, 日期: {start_date or '最早'} 至 {end_date or '最新'})...")

        try:
            with self._connect_db() as con:
                # 步驟 1: 確保目標表格存在
                self._ensure_composite_signal_table_exists(con)

                # 步驟 2: 讀取並合併數據
                ohlcv_df = self._get_daily_ohlcv_data(con, start_date, end_date, stock_ids)
                if ohlcv_df.empty:
                    print("沒有讀取到 OHLCV 數據，複合分析中止。")
                    return

                institutional_df = self._get_daily_institutional_net_shares(con, start_date, end_date, stock_ids)
                # institutional_df 為空是可接受的，_merge_data 會處理

                merged_df = self._merge_data(ohlcv_df, institutional_df)
                if merged_df.empty and not ohlcv_df.empty: # 如果合併後變空，但 ohlcv_df 原本有數據，說明合併邏輯有問題
                    print("數據合併後為空，但原始 OHLCV 數據存在。請檢查合併邏輯。複合分析中止。")
                    return
                if merged_df.empty:
                    print("合併後的數據集為空，複合分析中止。")
                    return

                # 步驟 3: 執行價量特徵工程
                featured_df = self.run_feature_engineering(merged_df)

                # 步驟 4: 計算籌碼流向標籤及複合信號
                final_df = self._apply_composite_signal_logic(featured_df)

                # 步驟 5: 儲存結果
                self._store_composite_signals(con, final_df)

                print("複合分析流程執行完畢。")

        except Exception as e:
            print(f"執行複合分析過程中發生嚴重錯誤: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    # 初步測試
    print("執行 ChimeraAnalyzer 初步測試...")
    # 創建一個虛擬的 analytics_mart.duckdb 用於測試
    # 實際測試中，我們會在 _test_chimera_harness.py 中準備測試數據庫
    test_db_path = Path("./temp_test_chimera.duckdb")

    # 刪除已存在的測試資料庫檔案，確保每次測試都是乾淨的環境
    if test_db_path.exists():
        test_db_path.unlink()

    analyzer = ChimeraAnalyzer(db_path=test_db_path)

    try:
        with analyzer._connect_db() as con:
            # 準備虛擬數據用於測試
            # 1. ohlcv_1d
            con.execute(f"""
            CREATE TABLE IF NOT EXISTS {analyzer.ohlcv_table_1d} (
                timestamp TIMESTAMP,
                product_id VARCHAR,
                open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT,
                PRIMARY KEY (timestamp, product_id)
            );""")
            ohlcv_data = [
                (pd.to_datetime('2023-01-01').date(), 'TSMC', 100.0, 105.0, 99.0, 102.0, 10000),
                (pd.to_datetime('2023-01-02').date(), 'TSMC', 102.0, 108.0, 101.0, 107.0, 12000),
                (pd.to_datetime('2023-01-03').date(), 'TSMC', 107.0, 110.0, 105.0, 106.0, 8000),
                (pd.to_datetime('2023-01-01').date(), 'UMC', 50.0, 52.0, 49.0, 51.0, 20000),
                (pd.to_datetime('2023-01-02').date(), 'UMC', 51.0, 51.0, 48.0, 49.0, 25000),
            ]
            # DuckDB 的 timestamp 類型可以直接接受 date 物件
            con.executemany(f"INSERT INTO {analyzer.ohlcv_table_1d} VALUES (?, ?, ?, ?, ?, ?, ?)", ohlcv_data)
            print(f"已插入虛擬 OHLCV 數據到 {analyzer.ohlcv_table_1d}")

            # 2. institutional_trades
            con.execute(f"""
            CREATE TABLE IF NOT EXISTS {analyzer.institutional_trades_table} (
                date DATE, stock_id VARCHAR, investor_type VARCHAR,
                buy_shares BIGINT, sell_shares BIGINT, net_shares BIGINT,
                PRIMARY KEY (date, stock_id, investor_type)
            );""")
            institutional_data = [
                (pd.to_datetime('2023-01-01').date(), 'TSMC', 'Foreign_Dealer', 500, 100, 400),
                (pd.to_datetime('2023-01-01').date(), 'TSMC', 'Investment_Trust', 200, 0, 200),
                (pd.to_datetime('2023-01-02').date(), 'TSMC', 'Foreign_Dealer', 100, 600, -500),
                (pd.to_datetime('2023-01-03').date(), 'TSMC', 'Dealer_Self', 50, 50, 0), # 中性
                (pd.to_datetime('2023-01-01').date(), 'UMC', 'Foreign_Dealer', 300, 200, 100),
                # UMC 2023-01-02 無法人數據
            ]
            con.executemany(f"INSERT INTO {analyzer.institutional_trades_table} VALUES (?, ?, ?, ?, ?, ?)", institutional_data)
            print(f"已插入虛擬法人交易數據到 {analyzer.institutional_trades_table}")

            # 測試數據讀取與合併
            ohlcv_df = analyzer._get_daily_ohlcv_data(con)
            institutional_df = analyzer._get_daily_institutional_net_shares(con)
            merged_df = analyzer._merge_data(ohlcv_df, institutional_df)

            print("\n--- 合併後的數據 (初步) ---")
            print(merged_df)

            # 測試特徵工程 (價量百分比和象限)
            featured_df = analyzer.run_feature_engineering(merged_df.copy()) # 使用 copy 以免修改 merged_df
            print("\n--- 特徵工程後的數據 (含價量象限) ---")
            # print(featured_df[['date', 'stock_id', 'close', 'volume', 'price_change_pct', 'volume_change_pct', 'price_volume_quadrant', 'total_net_shares']])

            # # 測試複合信號邏輯 (這部分現在包含在 run_composite_analysis 中)
            # composite_df = analyzer._apply_composite_signal_logic(featured_df.copy())
            # print("\n--- 複合信號處理後的數據 ---")
            # print(composite_df[['date', 'stock_id', 'price_volume_quadrant', 'price_volume_label', 'total_net_shares', 'institutional_flow_label', 'composite_signal']])

            # 執行完整的複合分析流程 (這會包含創建表格和儲存數據)
            print("\n--- 執行完整的複合分析流程 ---")
            analyzer.run_composite_analysis(stock_ids=['TSMC', 'UMC']) # 針對測試數據中的股票

            # 驗證數據是否已寫入 (可選, 手動檢查或添加更多測試代碼)
            print("\n--- 從資料庫讀取已儲存的複合信號 (驗證) ---")
            verify_df = con.execute(f"SELECT * FROM {analyzer.composite_signal_table} WHERE stock_id IN ('TSMC', 'UMC')").fetchdf()
            if not verify_df.empty:
                print(f"在 {analyzer.composite_signal_table} 中查詢到 {len(verify_df)} 筆記錄:")
                print(verify_df)
            else:
                print(f"未在 {analyzer.composite_signal_table} 中查詢到 TSMC 或 UMC 的記錄。")


    except Exception as e:
        print(f"初步測試時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理測試資料庫檔案
        if test_db_path.exists():
            # 在關閉連接之前，確保所有操作已提交且連接已釋放
            # 如果 'con' 仍然活躍，需要先關閉它
            # DuckDB 連接在 with 語句結束時會自動關閉
            print(f"清理測試資料庫檔案: {test_db_path}")
            # test_db_path.unlink() # 暫時註解掉，方便手動檢查 DB 內容
            print(f"提醒：測試資料庫 {test_db_path} 未被自動刪除，方便手動檢查。")

    print("ChimeraAnalyzer 初步測試完畢。")
