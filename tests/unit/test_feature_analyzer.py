import unittest
import duckdb
import pandas as pd
from pathlib import Path
from datetime import date, datetime
import pytz # For timezone aware datetime
import numpy as np
import sys
import os

# --- 標準化「路徑自我校正」樣板碼 START ---
# 取得目前腳本檔案的目錄
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 自動偵測專案根目錄 (假設 .git 在根目錄，或存在 README.md)
project_root_var = current_script_dir # 使用不同的變數名以避免與後續的 project_root 衝突
max_levels_up = 5 # 防止無限迴圈，可根據專案深度調整
for _ in range(max_levels_up):
    # 檢查是否存在 .git 目錄或 AGENTS.md (或 README.md) 作為根目錄標記
    if os.path.isdir(os.path.join(project_root_var, '.git')) or \
       os.path.isfile(os.path.join(project_root_var, 'AGENTS.md')) or \
       os.path.isfile(os.path.join(project_root_var, 'README.md')):
        break
    parent_dir = os.path.dirname(project_root_var)
    if parent_dir == project_root_var: # 已達檔案系統頂層
        # 對於在 tests/unit/ 下的腳本，根目錄通常是向上兩層
        project_root_var = os.path.abspath(os.path.join(current_script_dir, '..', '..'))
        print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑 (tests/unit 腳本): {project_root_var}")
        break
    project_root_var = parent_dir
else: # 如果迴圈正常結束 (未 break)
    project_root_var = os.path.abspath(os.path.join(current_script_dir, '..', '..')) # 後備方案
    print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑 (tests/unit 腳本): {project_root_var}")

if project_root_var not in sys.path:
    sys.path.insert(0, project_root_var)
# print(f"DEBUG: 專案根目錄 {project_root_var} 已添加到 sys.path")
# --- 標準化「路徑自我校正」樣板碼 END ---

from pathlib import Path # 確保 Path 在此處導入
project_root = Path(project_root_var) # 保持 project_root 變數（如果後續測試代碼中用到了）

from apps.feature_analyzer.analyzer import ChimeraAnalyzer

class TestChimeraAnalyzerTaifexPCRatio(unittest.TestCase):

    def setUp(self):
        """為每個測試案例設置一個乾淨的檔案型資料庫。"""
        self.test_db_file = Path("test_temp_analyzer_pc_ratio.duckdb")
        # 確保每次測試開始時刪除舊的測試數據庫檔案
        if self.test_db_file.exists():
            try:
                self.test_db_file.unlink()
            except OSError as e:
                print(f"警告：無法刪除舊的測試資料庫檔案 {self.test_db_file}: {e}", file=sys.stderr)

        self.db_path_str = str(self.test_db_file)

        # 使用一個連接來創建和填充初始表
        with duckdb.connect(self.db_path_str) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_ohlc (
                trading_date DATE, product_id VARCHAR, expiry_month VARCHAR, strike_price DOUBLE,
                option_type VARCHAR, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
                settlement_price DOUBLE, volume UBIGINT, open_interest UBIGINT,
                trading_session VARCHAR, source_file VARCHAR, member_file VARCHAR, transformed_at TIMESTAMPTZ
            );
            """)
            # taifex_pc_ratios 表將由 ChimeraAnalyzer 內部創建，這裡不需要預先創建
            # 但為了冪等性測試，我們可能需要在測試之間確保它是乾淨的
            conn.execute(f"DROP TABLE IF EXISTS taifex_pc_ratios;")

        # Analyzer 將使用相同的檔案路徑
        self.analyzer = ChimeraAnalyzer(db_path=self.db_path_str)

    def tearDown(self):
        """測試結束後刪除臨時資料庫檔案。"""
        if self.test_db_file.exists():
            try:
                self.test_db_file.unlink()
            except OSError as e:
                print(f"警告：無法刪除測試結束後的資料庫檔案 {self.test_db_file}: {e}", file=sys.stderr)

    def _insert_daily_ohlc_data(self, data: list[tuple]):
        with duckdb.connect(self.db_path_str) as conn:
            placeholders = ','.join(['?'] * 16)
            conn.executemany(f"INSERT INTO daily_ohlc VALUES ({placeholders})", data)
            conn.commit()

    def test_pc_ratio_calculation_basic(self):
        """測試基本的 P/C Ratio 計算。"""
        now = datetime.now(pytz.utc)
        test_data = [
            (date(2023, 1, 1), 'TXO01C18000', '202301', 18000, '買權', 1.0,1.0,1.0,1.0,1.0, 100, 1000, '一般', 'f1.csv', None, now),
            (date(2023, 1, 1), 'TXO01P17000', '202301', 17000, '賣權', 1.0,1.0,1.0,1.0,1.0, 80,  800,  '一般', 'f1.csv', None, now),
            (date(2023, 1, 1), 'TEO01C1500',  '202301', 1500,  '買權', 1.0,1.0,1.0,1.0,1.0, 50,  500,  '一般', 'f2.csv', None, now),
            (date(2023, 1, 1), 'TEO01P1400',  '202301', 1400,  '賣權', 1.0,1.0,1.0,1.0,1.0, 60,  600,  '一般', 'f2.csv', None, now),
            (date(2023, 1, 2), 'TXO01C18000', '202301', 18000, '買權', 1.0,1.0,1.0,1.0,1.0, 120, 1200, '一般', 'f3.csv', None, now),
            (date(2023, 1, 2), 'TXO01P17000', '202301', 17000, '賣權', 1.0,1.0,1.0,1.0,1.0, 70,  700,  '一般', 'f3.csv', None, now),
        ]
        self._insert_daily_ohlc_data(test_data)

        self.analyzer.run_taifex_pc_ratio_analysis(target_products=['TXO', 'TEO'], start_date='2023-01-01', end_date='2023-01-02')

        with duckdb.connect(self.db_path_str) as conn:
            result_df = conn.execute(f"SELECT trading_date, product_id, pc_volume_ratio, pc_oi_ratio, total_put_volume, total_call_volume, total_put_oi, total_call_oi FROM {self.analyzer.taifex_pc_ratio_table} ORDER BY trading_date, product_id").fetchdf()

        print("Debug: result_df in test_pc_ratio_calculation_basic:")
        print(result_df.to_string()) # 打印完整的 DataFrame

        # 確保 result_df['trading_date'] 是 date 對象以進行比較
        if not result_df.empty and pd.api.types.is_datetime64_any_dtype(result_df['trading_date']):
            result_df['trading_date'] = result_df['trading_date'].dt.date
        elif not result_df.empty and isinstance(result_df['trading_date'].iloc[0], str): # 如果是字串，嘗試轉換
            try:
                result_df['trading_date'] = pd.to_datetime(result_df['trading_date']).dt.date
            except Exception as e:
                print(f"Warning: Could not convert trading_date column to date objects: {e}")


        self.assertEqual(len(result_df), 3)

        # 增加檢查確保篩選後的 DataFrame 不是空的
        txo_data_20230101_df = result_df[(result_df['trading_date'] == date(2023, 1, 1)) & (result_df['product_id'] == 'TXO')]
        self.assertFalse(txo_data_20230101_df.empty, "No data found for TXO on 2023-01-01")
        txo_20230101 = txo_data_20230101_df.iloc[0]
        self.assertAlmostEqual(txo_20230101['pc_volume_ratio'], 0.8)
        self.assertAlmostEqual(txo_20230101['pc_oi_ratio'], 0.8)
        self.assertEqual(txo_20230101['total_put_volume'], 80)
        self.assertEqual(txo_20230101['total_call_volume'], 100)
        self.assertEqual(txo_20230101['total_put_oi'], 800)
        self.assertEqual(txo_20230101['total_call_oi'], 1000)

        teo_20230101 = result_df[(result_df['trading_date'] == date(2023, 1, 1)) & (result_df['product_id'] == 'TEO')].iloc[0]
        self.assertAlmostEqual(teo_20230101['pc_volume_ratio'], 1.2)
        self.assertAlmostEqual(teo_20230101['pc_oi_ratio'], 1.2)

        txo_20230102 = result_df[(result_df['trading_date'] == date(2023, 1, 2)) & (result_df['product_id'] == 'TXO')].iloc[0]
        self.assertAlmostEqual(txo_20230102['pc_volume_ratio'], 70/120)
        self.assertAlmostEqual(txo_20230102['pc_oi_ratio'], 700/1200)

    def test_pc_ratio_zero_call_volume(self):
        now = datetime.now(pytz.utc)
        test_data = [
            (date(2023, 1, 1), 'TXO01P17000', '202301',17000,'賣權',1.0,1.0,1.0,1.0,1.0, 80, 800, '一般', 'f1.csv', None, now),
            (date(2023, 1, 1), 'TXO01C18000', '202301',18000,'買權',1.0,1.0,1.0,1.0,1.0, 0,  500, '一般', 'f1.csv', None, now),
        ]
        self._insert_daily_ohlc_data(test_data)
        self.analyzer.run_taifex_pc_ratio_analysis(target_products=['TXO'], start_date='2023-01-01', end_date='2023-01-01')
        with duckdb.connect(self.db_path_str) as conn:
            result_df = conn.execute(f"SELECT pc_volume_ratio, pc_oi_ratio FROM {self.analyzer.taifex_pc_ratio_table} WHERE product_id = 'TXO'").fetchdf()
        self.assertTrue(pd.isna(result_df['pc_volume_ratio'].iloc[0]))
        self.assertAlmostEqual(result_df['pc_oi_ratio'].iloc[0], 800/500)

    def test_pc_ratio_no_matching_product_id_in_ohlc(self):
        now = datetime.now(pytz.utc)
        test_data = [
             (date(2023, 1, 1), 'XXX01C18000', '202301',18000,'買權',1.0,1.0,1.0,1.0,1.0, 100, 1000, '一般', 'f1.csv', None, now),
        ]
        self._insert_daily_ohlc_data(test_data)
        self.analyzer.run_taifex_pc_ratio_analysis(target_products=['TXO'])
        with duckdb.connect(self.db_path_str) as conn:
            result_df = conn.execute(f"SELECT * FROM {self.analyzer.taifex_pc_ratio_table}").fetchdf()
        self.assertTrue(result_df.empty)

    def test_pc_ratio_idempotency(self):
        now = datetime.now(pytz.utc)
        test_data = [
            (date(2023, 1, 1), 'TXO01C18000','202301',18000,'買權',1.0,1.0,1.0,1.0,1.0, 100, 1000, '一般', 'f1.csv', None, now),
            (date(2023, 1, 1), 'TXO01P17000','202301',17000,'賣權',1.0,1.0,1.0,1.0,1.0, 80,  800,  '一般', 'f1.csv', None, now),
        ]
        self._insert_daily_ohlc_data(test_data)

        self.analyzer.run_taifex_pc_ratio_analysis(target_products=['TXO'], start_date='2023-01-01', end_date='2023-01-01')
        with duckdb.connect(self.db_path_str) as conn:
            count_after_first_run = conn.execute(f"SELECT COUNT(*) FROM {self.analyzer.taifex_pc_ratio_table}").fetchone()[0]
            first_run_data = conn.execute(f"SELECT * FROM {self.analyzer.taifex_pc_ratio_table} ORDER BY trading_date, product_id").fetchdf()

        self.analyzer.run_taifex_pc_ratio_analysis(target_products=['TXO'], start_date='2023-01-01', end_date='2023-01-01')
        with duckdb.connect(self.db_path_str) as conn:
            count_after_second_run = conn.execute(f"SELECT COUNT(*) FROM {self.analyzer.taifex_pc_ratio_table}").fetchone()[0]
            second_run_data = conn.execute(f"SELECT * FROM {self.analyzer.taifex_pc_ratio_table} ORDER BY trading_date, product_id").fetchdf()

        self.assertEqual(count_after_first_run, 1)
        self.assertEqual(count_after_second_run, 1)
        pd.testing.assert_frame_equal(first_run_data.drop(columns=['calculated_at']), second_run_data.drop(columns=['calculated_at']))

if __name__ == '__main__':
    unittest.main()
