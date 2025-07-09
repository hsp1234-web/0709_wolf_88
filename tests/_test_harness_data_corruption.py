# -*- coding: utf-8 -*-
"""
整合測試腳本：數據內容污染模擬

此腳本用於驗證系統的數據處理模組 (`finmind_ETF_scraper.process_raw_data`)
在處理包含格式錯誤或邏輯異常的數據時的健壯性。
"""
import unittest
import pandas as pd
import numpy as np
import io
import sys
import os
import tempfile

# 嘗試導入被測試的函數

# --- 標準化「路徑自我校正」樣板碼 START ---
# 取得目前腳本檔案的目錄
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 自動偵測專案根目錄 (假設 .git 在根目錄，或存在 README.md)
project_root = current_script_dir
max_levels_up = 5 # 防止無限迴圈，可根據專案深度調整
for _ in range(max_levels_up):
    # 檢查是否存在 .git 目錄或 AGENTS.md (或 README.md) 作為根目錄標記
    if os.path.isdir(os.path.join(project_root, '.git')) or \
       os.path.isfile(os.path.join(project_root, 'AGENTS.md')) or \
       os.path.isfile(os.path.join(project_root, 'README.md')):
        break
    parent_dir = os.path.dirname(project_root)
    if parent_dir == project_root: # 已達檔案系統頂層
        project_root = os.path.abspath(os.path.join(current_script_dir, '..')) # tests/ 腳本，根目錄是上一層
        print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑 (tests 腳本): {project_root}")
        break
    project_root = parent_dir
else: # 如果迴圈正常結束 (未 break)
    project_root = os.path.abspath(os.path.join(current_script_dir, '..')) # 後備方案
    print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑 (tests 腳本): {project_root}")

if project_root not in sys.path:
    sys.path.insert(0, project_root)
# print(f"DEBUG: 專案根目錄 {project_root} 已添加到 sys.path")
# --- 標準化「路徑自我校正」樣板碼 END ---

from finmind_ETF_scraper import process_raw_data

class TestDataCorruption(unittest.TestCase):
    """
    測試數據內容污染情境。
    """

    def setUp(self):
        """
        每個測試方法執行前呼叫。
        設置 stdout 捕獲和臨時檔案目錄。
        """
        self.held_stdout = sys.stdout
        sys.stdout = io.StringIO()
        # 創建一個臨時目錄來存放 Parquet 檔案
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir_path = self.temp_dir_obj.name

    def tearDown(self):
        """
        每個測試方法執行後呼叫。
        恢復 stdout 並清理臨時目錄。
        """
        sys.stdout.close()
        sys.stdout = self.held_stdout
        # 清理臨時目錄及其內容
        self.temp_dir_obj.cleanup()

    def _create_parquet_file(self, df: pd.DataFrame, filename_prefix: str) -> str:
        """
        輔助方法：將 DataFrame 存為臨時 Parquet 檔案。
        返回檔案路徑。
        """
        # 使用 NamedTemporaryFile 來獲取一個帶有檔案名的臨時檔案路徑，然後關閉它，讓 pandas 寫入
        # 這樣可以確保檔案名是唯一的，並且在 self.temp_dir_path 下創建
        with tempfile.NamedTemporaryFile(delete=False, suffix=".parquet", prefix=filename_prefix, dir=self.temp_dir_path) as tmp_file:
            file_path = tmp_file.name
        df.to_parquet(file_path)
        return file_path

    def test_data_format_errors(self):
        """
        情境一：測試數據格式錯誤。
        - open_price 包含 'N/A'
        - close_price 包含 None
        - trade_volume 包含 'error_string'
        - trade_volume 包含 float (e.g., 123.45)
        """
        # 準備包含格式錯誤的數據
        raw_data_list = [
            {'date': '2023-01-01', 'stock_id': '0050', 'open_price': 100.0, 'high_price': 102.0, 'low_price': 99.0, 'close_price': 101.0, 'trade_volume': 1000}, # 正常
            {'date': '2023-01-02', 'stock_id': '0051', 'open_price': 'N/A', 'high_price': 52.0, 'low_price': 50.0, 'close_price': 51.0, 'trade_volume': 2000}, # open_price 格式錯誤
            {'date': '2023-01-03', 'stock_id': '0052', 'open_price': 20.0, 'high_price': 22.0, 'low_price': 19.0, 'close_price': None, 'trade_volume': 1500},    # close_price 格式錯誤 (None)
            {'date': '2023-01-04', 'stock_id': '0053', 'open_price': 30.0, 'high_price': 32.0, 'low_price': 29.0, 'close_price': 31.0, 'trade_volume': 'error_string'}, # trade_volume 格式錯誤
            {'date': '2023-01-05', 'stock_id': '0054', 'open_price': 40.0, 'high_price': 42.0, 'low_price': 39.0, 'close_price': 41.0, 'trade_volume': 250.75}, # trade_volume 格式錯誤 (float)
            {'date': '2023-01-06', 'stock_id': '0055', 'open_price': 110.0, 'high_price': 112.0, 'low_price': 109.0, 'close_price': 111.0, 'trade_volume': 3000}  # 正常
        ]
        original_df = pd.DataFrame(raw_data_list)

        # 模擬 process_raw_data 的輸入是 DataFrame
        # 在實際流程中，可能是從 Parquet 讀取，但 process_raw_data 直接收 DataFrame
        # file_path = self._create_parquet_file(original_df, "format_errors_")
        # input_df = pd.read_parquet(file_path)

        input_df = original_df.copy()
        initial_row_count = len(input_df)

        # 呼叫被測試的函數
        cleaned_df = process_raw_data(input_df)
        output = sys.stdout.getvalue()

        # 驗證1：處理後的 DataFrame 行數應少於原始 DataFrame (因為有4行錯誤)
        self.assertEqual(len(cleaned_df), 2, "清洗後應只剩下2行正常數據")
        self.assertLess(len(cleaned_df), initial_row_count, "處理後的行數應少於原始行數")

        # 驗證2：內容的潔淨度 - 確保留下的數據是正確的
        expected_stock_ids = ['0050', '0055']
        self.assertListEqual(cleaned_df['stock_id'].tolist(), expected_stock_ids, "留下的數據 stock_id 不正確")
        self.assertTrue(pd.api.types.is_integer_dtype(cleaned_df['trade_volume']), "清洗後 trade_volume 應為整數類型")


        # 驗證3：檢查 stdout 是否包含預期的作戰報告
        self.assertIn("指揮官，偵測到索引 1 的數據在 'open_price' 欄位格式不符預期 (值: 'N/A')。該行數據已被標記並將自動跳過。", output)
        self.assertIn("指揮官，偵測到索引 2 的數據在 'close_price' 欄位格式不符預期 (值: 'nan')。該行數據已被標記並將自動跳過。", output) # None 轉為 np.nan，再轉為 'nan'
        self.assertIn("指揮官，偵測到索引 3 的數據在 'trade_volume' 欄位格式不符預期 (值: 'error_string')。該行數據已被標記並將自動跳過。", output)
        self.assertIn("指揮官，偵測到索引 4 的數據在 'trade_volume' 欄位值 '250.75' 非整數。該行數據已被標記並將自動跳過。", output)
        self.assertIn("指揮官，原始數據共 6 行，在清洗過程中，共有 4 行因數據問題被自動跳過。", output)

        # 驗證 process_raw_data 不會因錯誤而崩潰 (如果能執行到這裡，代表沒有未處理的異常)
        self.assertIsNotNone(cleaned_df, "process_raw_data 不應返回 None")

    def test_data_logic_errors(self):
        """
        情境二：測試數據邏輯異常。
        - close_price 為負數 (-100.0)
        - trade_volume 為 0
        """
        raw_data_list = [
            {'date': '2023-02-01', 'stock_id': '0060', 'open_price': 10.0, 'high_price': 12.0, 'low_price': 9.0, 'close_price': 11.0, 'trade_volume': 100}, # 正常
            {'date': '2023-02-02', 'stock_id': '0061', 'open_price': 20.0, 'high_price': 22.0, 'low_price': 18.0, 'close_price': -100.0, 'trade_volume': 200}, # close_price 邏輯異常
            {'date': '2023-02-03', 'stock_id': '0062', 'open_price': 30.0, 'high_price': 32.0, 'low_price': 28.0, 'close_price': 31.0, 'trade_volume': 0},       # trade_volume 邏輯異常
            {'date': '2023-02-04', 'stock_id': '0063', 'open_price': 40.0, 'high_price': 42.0, 'low_price': 38.0, 'close_price': -5.0, 'trade_volume': 0}        # 兩種邏輯異常
        ]
        original_df = pd.DataFrame(raw_data_list)

        input_df = original_df.copy()
        initial_row_count = len(input_df)

        cleaned_df = process_raw_data(input_df)
        output = sys.stdout.getvalue()

        # 驗證1：處理後的 DataFrame 行數應少於原始 DataFrame (因為有3行含邏輯錯誤)
        self.assertEqual(len(cleaned_df), 1, "清洗後應只剩下1行正常數據")
        self.assertLess(len(cleaned_df), initial_row_count, "處理後的行數應少於原始行數")

        # 驗證2：內容的潔淨度
        self.assertEqual(cleaned_df['stock_id'].iloc[0], '0060', "留下的數據 stock_id 不正確")
        self.assertTrue(all(cleaned_df['close_price'] >= 0), "清洗後的 close_price 不應為負")
        self.assertTrue(all(cleaned_df['trade_volume'] > 0), "清洗後的 trade_volume 不應為0")
        self.assertTrue(pd.api.types.is_integer_dtype(cleaned_df['trade_volume']), "清洗後 trade_volume 應為整數類型")

        # 驗證3：檢查 stdout 是否包含預期的作戰報告
        self.assertIn("指揮官，偵測到索引 1 的數據 'close_price' 為負數 (-100.0)。該行數據已被標記並將自動跳過。", output)
        self.assertIn("指揮官，偵測到索引 2 的數據 'trade_volume' 為零。該行數據已被標記並將自動跳過。", output)
        # 檢查索引為 3 的行，它有兩個問題，應該都會被報告（或至少報告一個導致跳過的）
        # 根據目前的 finmind_ETF_scraper.py 實作，它會先報告 close_price 問題，然後 trade_volume 問題
        self.assertIn("指揮官，偵測到索引 3 的數據 'close_price' 為負數 (-5.0)。該行數據已被標記並將自動跳過。", output)
        # 如果 close_price 問題導致跳過，trade_volume 的邏輯問題可能不會在同一行的後續檢查中再次打印（因為行已被標記）
        # 但如果 finmind_ETF_scraper.py 的邏輯是先檢查所有再決定跳過，那兩個都會打印。
        # 目前的實作是，如果一個問題導致 rows_to_drop[index] = True，後續檢查到同一 index 的其他問題時，不會重複打印「該行數據已被標記並將自動跳過」
        # 但它仍會打印「指揮官，原始數據共 X 行... Y 行因數據問題被自動跳過。」
        self.assertIn("指揮官，原始數據共 4 行，在清洗過程中，共有 3 行因數據問題被自動跳過。", output)

        self.assertIsNotNone(cleaned_df, "process_raw_data 不應返回 None")

    def test_mixed_errors_and_missing_column(self):
        """
        測試混合錯誤類型以及缺少一個關鍵欄位的情況。
        """
        raw_data_list = [
            {'date': '2023-03-01', 'stock_id': '0070', 'open_price': 10.0, 'high_price': 12.0, 'low_price': 9.0, 'close_price': 11.0, 'trade_volume': 100}, # 正常
            {'date': '2023-03-02', 'stock_id': '0071', 'open_price': 'BAD', 'high_price': 22.0, 'low_price': 18.0, 'close_price': -20.0, 'trade_volume': 200}, # open_price 格式錯誤, close_price 邏輯錯誤
            {'date': '2023-03-03', 'stock_id': '0072', 'open_price': 30.0, 'high_price': 32.0, 'low_price': 28.0, 'close_price': 31.0, 'trade_volume': 0}       # trade_volume 邏輯異常
        ]
        # 故意缺少 'low_price' 欄位
        original_df = pd.DataFrame(raw_data_list).drop(columns=['low_price'])

        input_df = original_df.copy()
        initial_row_count = len(input_df)

        cleaned_df = process_raw_data(input_df)
        output = sys.stdout.getvalue()

        # 預期結果：
        # 行 0 ('0070')：正常，但缺少 low_price，process_raw_data 應打印缺少欄位警告，但不一定丟棄。
        #                 根據目前 process_raw_data 實作，僅打印警告，不丟棄（除非該欄位檢查失敗）。
        #                 由於 'low_price' 檢查被跳過，此行應保留。
        # 行 1 ('0071')：open_price 格式錯誤，close_price 邏輯錯誤。應被丟棄。
        # 行 2 ('0072')：trade_volume 邏輯錯誤。應被丟棄。

        self.assertEqual(len(cleaned_df), 1, "清洗後應只剩下1行數據('0070')")
        self.assertEqual(cleaned_df['stock_id'].iloc[0], '0070')

        self.assertIn("指揮官，輸入數據缺少必要欄位 'low_price'，相關數據行可能無法正確處理。", output)
        self.assertIn("指揮官，偵測到索引 1 的數據在 'open_price' 欄位格式不符預期 (值: 'BAD')。該行數據已被標記並將自動跳過。", output)
        # 由於索引 1 的 open_price 格式錯誤導致跳過，close_price 的邏輯錯誤可能不會再為該行打印跳過訊息
        self.assertIn("指揮官，偵測到索引 2 的數據 'trade_volume' 為零。該行數據已被標記並將自動跳過。", output)
        self.assertIn("指揮官，原始數據共 3 行，在清洗過程中，共有 2 行因數據問題被自動跳過。", output)


if __name__ == '__main__':
    # 確保可以通過 python tests/_test_harness_data_corruption.py 執行
    unittest.main()
