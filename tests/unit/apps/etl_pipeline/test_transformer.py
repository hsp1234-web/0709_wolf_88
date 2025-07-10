# tests/unit/apps/etl_pipeline/test_transformer.py
import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
from pathlib import Path
import zipfile # Needed for creating dummy zip
import pandas as pd

# --- 確保 apps.etl_pipeline.transformer 可以被導入 ---
try:
    current_script_path = Path(__file__).resolve()
    project_root_for_test = current_script_path.parent.parent.parent.parent
    if str(project_root_for_test) not in sys.path:
        sys.path.insert(0, str(project_root_for_test))
except NameError:
    project_root_for_test = Path(os.getcwd())
    if str(project_root_for_test) not in sys.path:
        sys.path.insert(0, str(project_root_for_test))
# --- 完成導入路徑設置 ---

from apps.etl_pipeline import transformer

class TestTransformer(unittest.TestCase):

    def setUp(self):
        self.test_zip_filename = "test_daily_data.zip"
        self.test_csv_filename = "Daily_20230101.csv"
        self.test_output_dir = Path("./temp_test_transformer_output")
        self.test_zip_path = self.test_output_dir / self.test_zip_filename

        # 創建臨時輸出目錄
        self.test_output_dir.mkdir(parents=True, exist_ok=True)

        # 創建一個假的 ZIP 檔案用於測試
        with zipfile.ZipFile(self.test_zip_path, 'w') as zf:
            zf.writestr(self.test_csv_filename, "header1,header2\ndata1,data2\n")

        self.test_argv = [
            "--zipfile", str(self.test_zip_path),
            "--output", str(self.test_output_dir),
            "--loglevel", "DEBUG" # Use DEBUG for more verbose test output if needed
        ]

    def tearDown(self):
        # 清理創建的臨時檔案和目錄
        if self.test_zip_path.exists():
            self.test_zip_path.unlink()

        # 清理 Parquet 檔案 (如果生成了)
        expected_parquet_name = Path(self.test_csv_filename).stem + ".parquet"
        parquet_file = self.test_output_dir / expected_parquet_name
        if parquet_file.exists():
            parquet_file.unlink()

        if self.test_output_dir.exists():
            # Attempt to remove the directory if it's empty
            try:
                self.test_output_dir.rmdir()
            except OSError:
                # If not empty, it might be due to other files or it's fine
                # print(f"Warning: Could not remove {self.test_output_dir} as it might not be empty.")
                pass


    @patch('apps.etl_pipeline.transformer.pd.DataFrame.to_parquet')
    @patch('apps.etl_pipeline.transformer.pd.read_csv')
    @patch('apps.etl_pipeline.transformer.zipfile.ZipFile')
    def test_run_transformation_successful_execution(
        self, mock_zipfile, mock_read_csv, mock_to_parquet
    ):
        """
        測試 run_transformation 在模擬的成功情境下是否能正確執行。
        """
        # 模擬 ZipFile 的行為
        mock_zip_instance = MagicMock()
        mock_zip_instance.namelist.return_value = [self.test_csv_filename]
        mock_zip_instance.read.return_value = b"header1,header2\ndata1,data2" # CSV content as bytes
        mock_zipfile.return_value.__enter__.return_value = mock_zip_instance

        # 模擬 read_csv 返回一個簡單的 DataFrame
        mock_df = pd.DataFrame({'header1': ['data1'], 'header2': ['data2']})
        mock_read_csv.return_value = mock_df

        # 執行函數
        result = transformer.run_transformation(self.test_argv)

        # 驗證結果
        self.assertTrue(result, "run_transformation 應在成功時返回 True")
        mock_zipfile.assert_called_with(self.test_zip_path, 'r')
        mock_read_csv.assert_called_once() # 確保 read_csv 被調用
        mock_to_parquet.assert_called_once() # 確保 to_parquet 被調用

        # 驗證輸出的 parquet 檔案名是否符合預期
        expected_parquet_name = Path(self.test_csv_filename).stem + ".parquet"
        # mock_to_parquet.call_args[0][0] 應該是輸出路徑
        # self.assertEqual(Path(mock_to_parquet.call_args[0][0]).name, expected_parquet_name)
        # More robust check of the first argument to to_parquet
        called_output_path = Path(mock_to_parquet.call_args[0][0])
        self.assertEqual(called_output_path.name, expected_parquet_name)
        self.assertEqual(called_output_path.parent, self.test_output_dir)


    def test_run_transformation_missing_arguments(self):
        """
        測試 run_transformation 在缺少必要參數時 argparse 是否正確處理。
        """
        with self.assertRaises(SystemExit) as cm:
            transformer.run_transformation(["--zipfile", str(self.test_zip_path)]) # Missing --output
        self.assertEqual(cm.exception.code, 2)

        with self.assertRaises(SystemExit) as cm:
            transformer.run_transformation(["--output", str(self.test_output_dir)]) # Missing --zipfile
        self.assertEqual(cm.exception.code, 2)

    def test_run_transformation_zip_not_found(self):
        """
        測試當 ZIP 檔案不存在時，函數是否返回 False。
        """
        invalid_argv = [
            "--zipfile", "non_existent_file.zip",
            "--output", str(self.test_output_dir)
        ]
        result = transformer.run_transformation(invalid_argv)
        self.assertFalse(result, "run_transformation 應在 ZIP 檔案不存在時返回 False")

    @patch('apps.etl_pipeline.transformer._find_target_csv_in_zip', return_value=None)
    def test_run_transformation_no_csv_in_zip(self, mock_find_csv):
        """
        測試當 ZIP 檔案中沒有 CSV 時，函數是否返回 False。
        """
        result = transformer.run_transformation(self.test_argv)
        self.assertFalse(result, "run_transformation 應在 ZIP 中無 CSV 時返回 False")
        mock_find_csv.assert_called_once()

    @patch('apps.etl_pipeline.transformer.zipfile.ZipFile')
    def test_run_transformation_bad_zip_file(self, mock_zipfile):
        """
        測試當 ZIP 檔案損壞時，函數是否返回 False。
        """
        mock_zipfile.side_effect = zipfile.BadZipFile("Mocked bad zip file")

        result = transformer.run_transformation(self.test_argv)
        self.assertFalse(result, "run_transformation 應在 ZIP 檔案損壞時返回 False")

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
