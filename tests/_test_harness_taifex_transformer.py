# -*- coding: utf-8 -*-
"""
TAIFEX 情報轉換器 (`transformer.py`) 的整合測試與壓力測試腳本。

此腳本專注於驗證 `process_zip_file` 函數在各種「情報毀損」情境下的行為，
確保其健壯性、正確的錯誤處理以及資源清理。

測試原則：
1.  **嚴禁網路**：此腳本不應包含任何網路連線活動。
2.  **動態模擬**：所有用於測試的 `.zip` 檔案，都必須在測試案例執行期間動態生成。
3.  **完全潔淨**：使用 `unittest` 的 `setUp/tearDown` 確保所有臨時檔案與目錄被徹底清除。
"""
import unittest
import os
import sys
import tempfile
import zipfile
from pathlib import Path
import pandas as pd
# import pyarrow # pyarrow 會在 pandas.to_parquet 時隱式需要，通常不需要直接導入進行基本操作
import shutil # 用於 tearDown 中的 rmtree
import logging
from io import BytesIO, StringIO
from unittest.mock import patch, MagicMock

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
        project_root_var = os.path.abspath(os.path.join(current_script_dir, '..')) # tests/ 腳本，根目錄是上一層
        print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑 (tests 腳本): {project_root_var}")
        break
    project_root_var = parent_dir
else: # 如果迴圈正常結束 (未 break)
    project_root_var = os.path.abspath(os.path.join(current_script_dir, '..')) # 後備方案
    print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑 (tests 腳本): {project_root_var}")

if project_root_var not in sys.path:
    sys.path.insert(0, project_root_var)
# print(f"DEBUG: 專案根目錄 {project_root_var} 已添加到 sys.path")
# --- 標準化「路徑自我校正」樣板碼 END ---

from pathlib import Path # 確保 Path 在此處導入
project_root = Path(project_root_var) # 保持 project_root 變數（如果後續測試代碼中用到了）

from apps.taifex_data_transformer.transformer import process_zip_file

class TestTaifexTransformer(unittest.TestCase):
    temp_dir_path: Path
    output_subdir_path: Path # 專門用於存放 parquet 輸出的子目錄
    mock_logger: MagicMock

    def setUp(self):
        """為每個測試案例設置一個乾淨的臨時工作環境。"""
        # 創建一個主臨時目錄
        self.temp_dir_path = Path(tempfile.mkdtemp(prefix="test_transformer_"))
        # 在主臨時目錄下創建一個專用的輸出子目錄
        self.output_subdir_path = self.temp_dir_path / "output_parquet"
        self.output_subdir_path.mkdir(parents=True, exist_ok=True)

        # 設置 Mock Logger 以捕獲日誌輸出
        # 我們將 patch 'apps.taifex_data_transformer.transformer.DEFAULT_LOGGER'
        # 以及 'apps.taifex_data_transformer.transformer.logging.getLogger' 以確保所有日誌路徑都被覆蓋

        # 為了簡化，我們將在每個測試方法中 patch 'process_zip_file' 的 logger 參數
        # 或者 patch 全局的 DEFAULT_LOGGER
        self.mock_logger = MagicMock(spec=logging.Logger)

        # 清理 stdout 捕獲（如果使用）
        # self.held_stdout = None # 用於 patch sys.stdout
        # self.stdout_capture = StringIO()

        # print(f"\n[SETUP] 測試 {self.id()} 的臨時目錄已創建: {self.temp_dir_path}")
        # print(f"[SETUP] 輸出子目錄: {self.output_subdir_path}")


    def tearDown(self):
        """在每個測試案例結束後清理臨時檔案和目錄。"""
        if self.temp_dir_path.exists():
            try:
                shutil.rmtree(self.temp_dir_path)
                # print(f"[TEARDOWN] 臨時目錄已成功刪除: {self.temp_dir_path}")
            except Exception as e:
                # 在測試環境中，如果清理失敗，打印錯誤但不要讓 tearDown 拋出異常，以免掩蓋實際的測試失敗
                print(f"[TEARDOWN_ERROR] 清理臨時目錄 {self.temp_dir_path} 失敗: {e}", file=sys.stderr)

        # # 還原 stdout (如果使用)
        # if self.held_stdout:
        #    sys.stdout = self.held_stdout

    def assert_no_parquet_files(self, directory: Path, message: str = "輸出目錄中不應存在 Parquet 檔案"):
        """斷言指定目錄中沒有 .parquet 檔案。"""
        parquet_files = list(directory.glob("*.parquet"))
        self.assertEqual(len(parquet_files), 0, f"{message} (在 {directory} 中找到: {[f.name for f in parquet_files]})")

    def assert_log_contains(self, expected_substring: str, level: str = "error"):
        """斷言 mock_logger 的指定級別的日誌中包含特定子字串。"""
        log_calls = []
        if level == "error":
            log_calls = self.mock_logger.error.call_args_list
        elif level == "warning":
            log_calls = self.mock_logger.warning.call_args_list
        elif level == "info":
            log_calls = self.mock_logger.info.call_args_list
        # 可以根據需要擴展其他級別

        found = any(expected_substring in str(call_args[0]) for call_args in log_calls)
        self.assertTrue(found, f"預期的日誌子字串 '{expected_substring}' 未在 {level.upper()} 日誌中找到。\n捕獲到的 {level.upper()} 日誌: {log_calls}")

    # --- 接下來是各個測試案例 ---

    def test_process_zip_file_handles_corrupted_zip(self):
        """
        情境一：情報包損毀
        測試：當 process_zip_file 嘗試處理一個無效的 ZIP 檔案時，
              應捕獲 zipfile.BadZipFile，不產生輸出，並記錄錯誤。
        """
        corrupted_zip_path = self.temp_dir_path / "corrupted.zip"
        with open(corrupted_zip_path, "wb") as f:
            f.write(b"This is definitely not a zip file content.")

        # 執行被測函數，傳入 mock logger
        process_zip_file(str(corrupted_zip_path), str(self.output_subdir_path), logger=self.mock_logger)

        # 驗收：無 Parquet 輸出
        self.assert_no_parquet_files(self.output_subdir_path)

        # 驗收：日誌包含預期的錯誤訊息
        self.assert_log_contains("[ERROR] 情報包毀損，無法解碼。", level="error")
        self.assert_log_contains(f"檔案路徑: {corrupted_zip_path}", level="error")

    def test_process_zip_file_handles_empty_zip(self):
        """
        情境二 Part A：情報內容不符 (空 ZIP)
        測試：當 process_zip_file 處理一個空的 ZIP 檔案時，
              應不產生輸出，並記錄未找到目標 CSV 的錯誤。
        """
        empty_zip_path = self.temp_dir_path / "empty.zip"
        with zipfile.ZipFile(empty_zip_path, 'w') as zf:
            pass # 創建一個空的 zip 檔案

        process_zip_file(str(empty_zip_path), str(self.output_subdir_path), logger=self.mock_logger)

        self.assert_no_parquet_files(self.output_subdir_path)
        self.assert_log_contains("[ERROR] 情報包內容與預期不符，未找到目標 CSV 檔案。", level="error")
        self.assert_log_contains(f"檔案路徑: {empty_zip_path}", level="error")
        # _find_target_csv_in_zip 內部也會記錄 "在情報包中未找到任何 CSV 檔案。"
        self.assert_log_contains("在情報包中未找到任何 CSV 檔案。", level="error")


    def test_process_zip_file_handles_zip_without_target_csv(self):
        """
        情境二 Part B：情報內容不符 (ZIP 中無目標 CSV)
        測試：當 process_zip_file 處理一個包含非目標檔案但無目標 CSV 的 ZIP 時，
              應不產生輸出，並記錄未找到目標 CSV 的錯誤。
        """
        wrong_content_zip_path = self.temp_dir_path / "wrong_content.zip"
        with zipfile.ZipFile(wrong_content_zip_path, 'w') as zf:
            zf.writestr("readme.txt", "This is a test file.")
            zf.writestr("image.jpg", b"some image data")

        process_zip_file(str(wrong_content_zip_path), str(self.output_subdir_path), logger=self.mock_logger)

        self.assert_no_parquet_files(self.output_subdir_path)
        self.assert_log_contains("[ERROR] 情報包內容與預期不符，未找到目標 CSV 檔案。", level="error")
        self.assert_log_contains(f"檔案路徑: {wrong_content_zip_path}", level="error")
        self.assert_log_contains("在情報包中未找到任何 CSV 檔案。", level="error")

    def test_process_zip_file_handles_encoding_error(self):
        """
        情境三：情報編碼錯誤
        測試：當目標 CSV 檔案使用非 UTF-8 編碼 (例如 BIG5) 時，
              應捕獲 UnicodeDecodeError，不產生輸出，並記錄編碼錯誤。
        """
        # 假設約定的 CSV 檔名，或者讓 _find_target_csv_in_zip 找到它
        # 為了與 transformer.py 中的 _find_target_csv_in_zip 邏輯對齊，
        # 我們可以簡單地命名為 data.csv，或者一個包含 "Daily" 的名稱。
        # 這裡我們使用一個簡單的名稱，因為目前 _find_target_csv_in_zip 會選第一個 .csv。
        target_csv_name_in_zip = "daily_data_big5.csv"
        csv_content_string = "欄位A,欄位B\n值一,值二\n測試,資料" # 包含中文字符

        try:
            big5_encoded_bytes = csv_content_string.encode('big5')
        except UnicodeEncodeError as uee:
            self.skipTest(f"無法將測試字串編碼為 BIG5，可能是環境問題或字串包含 BIG5 不支援的字元: {uee}")
            return

        encoding_error_zip_path = self.temp_dir_path / "encoding_error.zip"
        with zipfile.ZipFile(encoding_error_zip_path, 'w') as zf:
            zf.writestr(target_csv_name_in_zip, big5_encoded_bytes)

        process_zip_file(str(encoding_error_zip_path), str(self.output_subdir_path), logger=self.mock_logger)

        self.assert_no_parquet_files(self.output_subdir_path)
        self.assert_log_contains("[ERROR] 情報編碼錯誤，無法使用標準 UTF-8 解碼。", level="error")
        self.assert_log_contains(f"檔案路徑: {encoding_error_zip_path}", level="error")
        self.assert_log_contains(f"CSV 檔案: {target_csv_name_in_zip}", level="error")

    def test_process_zip_file_handles_mismatched_columns(self):
        """
        情境四：情報格式錯亂 (欄位數不一致)
        測試：當 CSV 內容的資料行與表頭的欄位數不一致時，
              應捕獲 pandas.errors.ParserError (或相關錯誤)，不產生輸出，並記錄錯誤。
        """
        target_csv_name_in_zip = "parser_error_data.csv" # 改名以反映錯誤類型
        # 使用一個包含未閉合引號的行來強制觸發 ParserError
        csv_content_string = 'HeaderA,HeaderB\nValue1,"Unclosed Quoted Value\nValue3,Value4'
        utf8_encoded_bytes = csv_content_string.encode('utf-8')

        parser_error_zip_path = self.temp_dir_path / "parser_error_test.zip" # 改 ZIP 檔名
        with zipfile.ZipFile(parser_error_zip_path, 'w') as zf: # <--- 修正此處的變數名
            zf.writestr(target_csv_name_in_zip, utf8_encoded_bytes)

        process_zip_file(str(parser_error_zip_path), str(self.output_subdir_path), logger=self.mock_logger) # <--- 修正此處的變數名

        self.assert_no_parquet_files(self.output_subdir_path)
        # Pandas 的 ParserError 訊息可能多樣，我們檢查一個通用的錯誤訊息
        self.assert_log_contains("[ERROR] 情報內部格式錯亂，欄位數量不一致或解析錯誤。", level="error")
        self.assert_log_contains(f"檔案路徑: {parser_error_zip_path}", level="error") # <--- 修正此處的變數名
        self.assert_log_contains(f"CSV 檔案: {target_csv_name_in_zip}", level="error")

    def test_process_zip_file_success_normal_case(self):
        """
        正常情境 (Happy Path)
        測試：當提供一個包含有效、UTF-8 編碼 CSV 的 ZIP 檔案時，
              應成功生成 Parquet 檔案，且內容正確，無錯誤日誌。
        """
        target_csv_name_in_zip = "daily_data_correct.csv"
        csv_data = {
            '契約': ['TX', 'MX', 'TE', 'TF'],
            '到期月份(週別)': ['202312', '202312W1', '202401', '202402'],
            '開盤價': [17000, 16900, 17050, 16800],
            '最高價': [17100, 16950, 17150, 16850],
            '最低價': [16980, 16880, 17020, 16780],
            '收盤價': [17080, 16920, 17120, 16820],
            '成交量': [100000, 5000, 80000, 70000]
        }
        # 確保所有欄位都是 pandas DataFrame 能接受的類型 (例如，避免直接傳入 Python 的 int)
        source_df = pd.DataFrame(csv_data)

        # 將 DataFrame 轉換為 CSV 字串
        csv_string = source_df.to_csv(index=False, encoding='utf-8')
        utf8_encoded_bytes = csv_string.encode('utf-8')

        good_zip_path = self.temp_dir_path / "good_data.zip"
        with zipfile.ZipFile(good_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(target_csv_name_in_zip, utf8_encoded_bytes)

        process_zip_file(str(good_zip_path), str(self.output_subdir_path), logger=self.mock_logger)

        # 驗收：應生成一個 Parquet 檔案
        parquet_files = list(self.output_subdir_path.glob("*.parquet"))
        self.assertEqual(len(parquet_files), 1, f"應在 {self.output_subdir_path} 中找到一個 Parquet 檔案，實際找到 {len(parquet_files)}")

        output_parquet_path = parquet_files[0]
        self.assertEqual(output_parquet_path.name, Path(target_csv_name_in_zip).stem + ".parquet",
                         f"輸出的 Parquet 檔名應為 '{Path(target_csv_name_in_zip).stem + '.parquet'}'，實際為 '{output_parquet_path.name}'")

        # 驗收：Parquet 檔案內容與原始 DataFrame 一致
        try:
            result_df = pd.read_parquet(output_parquet_path)
            # 在比較 DataFrame 時，要注意潛在的類型差異（例如 int64 vs object if numbers were strings）
            # to_csv 後再 read_csv 可能會改變類型。直接比較 source_df 和 result_df。
            # 如果原始 CSV 包含純數字欄位，pandas 在 read_csv 時可能會推斷為數字類型。
            # source_df 是我們期望的最終類型結構。
            pd.testing.assert_frame_equal(source_df, result_df, check_dtype=True)
        except Exception as e:
            self.fail(f"讀取或比較 Parquet 檔案時發生錯誤: {e}\n"
                      f"原始 DataFrame:\n{source_df}\n"
                      f"結果 DataFrame:\n{result_df if 'result_df' in locals() else '未能讀取'}")


        # 驗收：沒有錯誤日誌
        self.assertEqual(len(self.mock_logger.error.call_args_list), 0,
                         f"不應有錯誤日誌。捕獲到的錯誤日誌: {self.mock_logger.error.call_args_list}")
        self.assertEqual(len(self.mock_logger.warning.call_args_list), 0, # 也檢查警告，除非特定情況下預期有警告
                         f"不應有警告日誌。捕獲到的警告日誌: {self.mock_logger.warning.call_args_list}")

        # 驗收：有成功的 INFO 日誌
        self.assert_log_contains(f"成功將 '{target_csv_name_in_zip}' 從 '{good_zip_path.name}' 轉換並儲存為", level="info")


if __name__ == '__main__':
    # 為了方便單獨運行此測試腳本
    # 注意：直接運行此腳本時，路徑校正樣板碼可能依賴於當前工作目錄的正確性。
    # 推薦使用 `python -m unittest tests._test_harness_taifex_transformer` 從專案根目錄運行。
    unittest.main()
