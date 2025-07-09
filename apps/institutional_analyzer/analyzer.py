# apps/institutional_analyzer/analyzer.py
import os
import duckdb
import pandas as pd
from apps.finmind_client.client import FinMindClient # 導入內部化的 FinMindClient
from datetime import datetime

# --- 路徑自我校正樣板碼 START ---
# 確保可以正確找到 analytics_mart.duckdb
try:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.abspath(os.path.join(current_script_dir, '..', '..'))
    # 修改 DB_PATH 指向 market_data.duckdb
    DB_PATH = os.path.join(project_root_dir, "market_data.duckdb")
except Exception as e:
    print(f"專案路徑校正時發生錯誤 (analyzer.py): {e}", file=sys.stderr)
    # Fallback 也應指向 market_data.duckdb
    DB_PATH = "market_data.duckdb" # Fallback
# --- 路徑自我校正樣板碼 END ---

class InstitutionalAnalyzer:
    def __init__(self, stock_id: str, start_date: str, end_date: str, api_token: str = None):
        self.stock_id = stock_id
        self.start_date = start_date
        self.end_date = end_date
        self.fm_client = FinMindClient(api_token=api_token) # 初始化 FinMindClient
        self.db_path = DB_PATH
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        """確保 institutional_trades 表格在 DuckDB 中存在"""
        try:
            con = duckdb.connect(self.db_path)
            # IF NOT EXISTS 避免重複創建；定義表格欄位
            # 外資 (Foreign Dealer), 投信 (Investment Trust), 自營商 (Dealer)
            # buy: 買超張數, sell: 賣超張數, net: 淨買賣超張數 (buy - sell)
            con.execute("""
            CREATE TABLE IF NOT EXISTS institutional_trades (
                date DATE,
                stock_id VARCHAR,
                investor_type VARCHAR,      -- 'Foreign_Dealer', 'Investment_Trust', 'Dealer_Self', 'Dealer_Hedging'
                buy_shares BIGINT,          -- 買進股數
                sell_shares BIGINT,         -- 賣出股數
                net_shares BIGINT,          -- 買賣超股數 (buy_shares - sell_shares)
                PRIMARY KEY (date, stock_id, investor_type)
            );
            """)
            con.close()
            print(f"資料庫 {self.db_path} 中的 institutional_trades 表格已確認/創建。")
        except Exception as e:
            print(f"檢查或創建 institutional_trades 表格時發生錯誤: {e}")
            raise

    def fetch_data(self) -> pd.DataFrame | None:
        """使用 FinMindClient 獲取三大法人買賣超數據"""
        print(f"正在從 FinMind API 獲取股票 {self.stock_id} 從 {self.start_date} 到 {self.end_date} 的三大法人買賣超數據...")
        try:
            df = self.fm_client.get_taiwan_stock_institutional_investors_buy_sell(
                data_id=self.stock_id,
                start_date=self.start_date,
                end_date=self.end_date
            )
            if df is not None and not df.empty:
                print(f"成功獲取 {len(df)} 筆數據。")
                return df
            else:
                print(f"未獲取到股票 {self.stock_id} 在指定期間的數據。")
                return None
        except Exception as e:
            print(f"調用 FinMind API (get_taiwan_stock_institutional_investors_buy_sell) 時發生錯誤: {e}")
            return None

    def analyze_data(self, data: pd.DataFrame) -> pd.DataFrame | None:
        """
        處理與聚合數據。
        FinMind 的 'TaiwanStockInstitutionalInvestorsBuySell' 資料集 schema 參考:
        date, stock_id, name, buy, sell
        'name' 欄位包含: 外資及陸資(不含外資自營商), 外資自營商, 投信, 自營商(自行買賣), 自營商(避險)
        我們需要將這些 'name' 對應到我們的 'investor_type'
        並計算淨買賣超 (net_shares)
        """
        if data is None or data.empty:
            print("沒有數據可供分析。")
            return None

        print("開始分析數據...")
        processed_data = data.copy()

        # 欄位名稱映射與選擇
        # FinMind 'buy' 和 'sell' 單位是「張」，一張是 1000 股。我們儲存為「股」。
        # 'name' 欄位對應 investor_type
        investor_map = {
            "Foreign_Investor_and_Chinese_Investor": "Foreign_Dealer", # 外資及陸資(不含外資自營商)
            "Foreign_Dealer_Self": "Foreign_Dealer", # 外資自營商 (併入外資)
            "Investment_Trust": "Investment_Trust", # 投信
            "Dealer_Self_Proprietary": "Dealer_Self", # 自營商(自行買賣)
            "Dealer_Hedge": "Dealer_Hedging" # 自營商(避險)
        }
        processed_data['investor_type'] = processed_data['name'].map(investor_map)

        # 轉換 'buy' 和 'sell' 為股數 (乘以 1000)
        processed_data['buy_shares'] = processed_data['buy'] * 1000
        processed_data['sell_shares'] = processed_data['sell'] * 1000
        processed_data['net_shares'] = processed_data['buy_shares'] - processed_data['sell_shares']

        # 選取所需欄位並重命名
        processed_data = processed_data[['date', 'stock_id', 'investor_type', 'buy_shares', 'sell_shares', 'net_shares']]

        # 轉換日期格式
        processed_data['date'] = pd.to_datetime(processed_data['date']).dt.date

        # 按 investor_type 分組，以處理 "Foreign_Investor_and_Chinese_Investor" 和 "Foreign_Dealer_Self" 都映射到 "Foreign_Dealer" 的情況
        # 我們需要將同一天、同一股票、同一 investor_type (合併後的) 的買賣股數加總
        aggregation_functions = {
            'buy_shares': 'sum',
            'sell_shares': 'sum',
            'net_shares': 'sum'
        }
        final_data = processed_data.groupby(['date', 'stock_id', 'investor_type'], as_index=False).agg(aggregation_functions)

        print(f"數據分析完成，處理了 {len(final_data)} 筆聚合後的記錄。")
        return final_data


    def store_results(self, analyzed_data: pd.DataFrame):
        """將分析結果儲存到 DuckDB 的 institutional_trades 表格"""
        if analyzed_data is None or analyzed_data.empty:
            print("沒有分析結果可儲存。")
            return

        print(f"準備將 {len(analyzed_data)} 筆結果儲存到 DuckDB...")
        try:
            con = duckdb.connect(self.db_path)
            # 使用 DuckDB 的 upsert 功能 (INSERT OR REPLACE)
            # 這需要表格有 PRIMARY KEY
            # 這裡我們逐筆插入或替換，也可以考慮先刪除符合條件的舊資料再插入新資料

            for index, row in analyzed_data.iterrows():
                # DuckDB 的日期格式是 YYYY-MM-DD
                date_str = row['date'].strftime('%Y-%m-%d')
                # ON CONFLICT DO UPDATE 語法更適合 upsert
                # 注意：欄位名稱的大小寫和 SQL 中的一致性
                sql = f"""
                INSERT INTO institutional_trades (date, stock_id, investor_type, buy_shares, sell_shares, net_shares)
                VALUES ('{date_str}', '{row['stock_id']}', '{row['investor_type']}', {row['buy_shares']}, {row['sell_shares']}, {row['net_shares']})
                ON CONFLICT (date, stock_id, investor_type) DO UPDATE SET
                    buy_shares = EXCLUDED.buy_shares,
                    sell_shares = EXCLUDED.sell_shares,
                    net_shares = EXCLUDED.net_shares;
                """
                con.execute(sql)
            con.commit() # 確保事務被提交
            con.close()
            print(f"成功將 {len(analyzed_data)} 筆結果儲存/更新至 institutional_trades 表格。")
        except Exception as e:
            print(f"儲存結果到 DuckDB 時發生錯誤: {e}")
            # 考慮是否需要回滾或更複雜的錯誤處理
            raise

    def run_analysis(self):
        """執行完整的數據獲取、分析與儲存流程"""
        print(f"開始為股票 {self.stock_id} 執行法人籌碼分析 ({self.start_date} 至 {self.end_date})...")
        raw_data_df = self.fetch_data()

        if raw_data_df is not None and not raw_data_df.empty:
            analyzed_data_df = self.analyze_data(raw_data_df)
            if analyzed_data_df is not None and not analyzed_data_df.empty:
                self.store_results(analyzed_data_df)
                print(f"股票 {self.stock_id} 的法人籌碼分析完成並已儲存。")
            else:
                print(f"股票 {self.stock_id} 的數據分析步驟未產生結果。")
        else:
            print(f"無法獲取股票 {self.stock_id} 的數據，分析中止。")

if __name__ == '__main__':
    # 此部分為初步測試，之後會由 run.py 調用
    # 需要設定 FINMIND_API_TOKEN 環境變數才能實際獲取數據
    print("執行 InstitutionalAnalyzer 初步測試...")

    # 從環境變數讀取 API Token
    # 在 Jules 的環境中，這可能需要指揮官預先設定
    # 或者在執行 run.py 時透過參數傳入
    api_token = os.getenv("FINMIND_API_TOKEN")
    if not api_token:
        print("警告：FINMIND_API_TOKEN 環境變數未設定。FinMindClient 將無法獲取真實數據，僅能進行初始化。")
        # 為了讓測試能跑通初始化，即使沒有 token 也繼續，但 fetch_data 會失敗或返回空
        # client 初始化時若 token 為 None 會報錯，除非我們傳遞一個虛擬 token
        # FinMindClient 已經處理了這個情況，如果 token 是 None，它會 raise ValueError
        # 因此，這裡我們應該只在有 token 的情況下才執行
        # 或者，我們讓 FinMindClient 接受 dummy token 進行測試
        # 依照鑽石計畫的 client.py，它會在 token 為空時報錯。
        # 所以這裡我們應該提示用戶如何設定 token
        print("請設定 FINMIND_API_TOKEN 環境變數，或確保在調用時傳入 api_token。")
        print("測試將嘗試使用一個虛擬 token 進行，但預期 fetch_data 會失敗。")
        api_token = "DUMMY_TOKEN_FOR_TESTING_ANALYZER" # 使用虛擬 token 以便測試初始化

    # 測試用的股票代碼和日期
    test_stock = "2330" # 台積電
    test_start = "2023-10-01"
    test_end = "2023-10-05" # 短一點的日期範圍以利測試

    print(f"測試目標: 股票 {test_stock}, 日期 {test_start} 至 {test_end}")

    try:
        analyzer = InstitutionalAnalyzer(
            stock_id=test_stock,
            start_date=test_start,
            end_date=test_end,
            api_token=api_token # 傳入 token
        )
        analyzer.run_analysis()
        print("\nInstitutionalAnalyzer 初步測試執行完畢。")

        # 初步驗證數據是否寫入 (如果 API 成功且有數據)
        if api_token != "DUMMY_TOKEN_FOR_TESTING_ANALYZER": # 只在有真實 token 時才預期有數據
            print("\n--- 初步數據庫驗證 ---")
            try:
                con = duckdb.connect(DB_PATH, read_only=True)
                result_df = con.execute(f"SELECT * FROM institutional_trades WHERE stock_id = '{test_stock}' AND date >= '{test_start}' AND date <= '{test_end}' ORDER BY date, investor_type").fetchdf()
                if not result_df.empty:
                    print(f"在 institutional_trades 表中找到 {len(result_df)} 筆關於 {test_stock} 的測試數據:")
                    print(result_df.head())
                else:
                    print(f"未在 institutional_trades 表中找到關於 {test_stock} 的測試數據。這可能是因為 API 未返回數據，或 API Token 無效/額度用盡。")
                con.close()
            except Exception as e:
                print(f"查詢 DuckDB 進行驗證時發生錯誤: {e}")
        else:
            print("\n由於使用虛擬 API Token，不執行數據庫驗證。")

    except ValueError as ve:
        print(f"初始化 InstitutionalAnalyzer 失敗: {ve}")
    except Exception as e:
        print(f"執行 InstitutionalAnalyzer 初步測試時發生未預期錯誤: {e}")
