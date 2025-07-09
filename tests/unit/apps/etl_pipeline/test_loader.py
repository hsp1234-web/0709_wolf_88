# tests/unit/apps/etl_pipeline/test_loader.py
import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
from pathlib import Path
import pandas as pd # For creating dummy parquet
import duckdb # For SchemaMismatchError

# --- 確保 apps.etl_pipeline.loader 可以被導入 ---
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

from apps.etl_pipeline import loader # Assuming loader.py is in apps/etl_pipeline
from apps.etl_pipeline.loader import SchemaMismatchError # Import custom exception

class TestLoader(unittest.TestCase):

    def setUp(self):
        self.test_output_dir = Path("./temp_test_loader_output")
        self.test_output_dir.mkdir(parents=True, exist_ok=True)

        self.dummy_parquet_path = self.test_output_dir / "test_data.parquet"
        self.dummy_db_path = self.test_output_dir / "test_db.duckdb"
        self.table_name = "test_table"

        # Create a dummy parquet file
        pd.DataFrame({'colA': [1, 2], 'colB': ['val1', 'val2']}).to_parquet(self.dummy_parquet_path)

        self.test_argv = [
            "--parquet-file", str(self.dummy_parquet_path),
            "--db-path", str(self.dummy_db_path),
            "--table-name", self.table_name,
            "--primary-key", "colA", # Assuming colA is a primary key for some tests
            "--loglevel", "DEBUG"
        ]

    def tearDown(self):
        if self.dummy_parquet_path.exists():
            self.dummy_parquet_path.unlink()
        if self.dummy_db_path.exists():
            self.dummy_db_path.unlink()
        if self.test_output_dir.exists():
            try:
                self.test_output_dir.rmdir() # Only removes if empty
            except OSError:
                # print(f"Warning: Could not remove {self.test_output_dir}, it might not be empty.")
                pass

    @patch('apps.etl_pipeline.loader.duckdb.connect')
    def test_run_loading_successful_creation(self, mock_duckdb_connect):
        """
        測試 run_loading 首次成功創建表格並載入數據。
        """
        mock_conn = MagicMock()
        mock_duckdb_connect.return_value.__enter__.return_value = mock_conn

        # Simulate table does not exist initially, then schema comparison is fine
        # _get_table_schema_from_db returns None if table doesn't exist
        with patch('apps.etl_pipeline.loader._get_table_schema_from_db', return_value=None) as mock_get_schema:
            result = loader.run_loading(self.test_argv)

        self.assertTrue(result, "run_loading 應在成功創建和載入時返回 True")
        mock_duckdb_connect.assert_called_with(database=str(self.dummy_db_path), read_only=False)
        # Check if CREATE TABLE ... AS SELECT ... was called
        # This is a bit simplified; a more robust check would inspect the SQL string
        create_table_call_found = False
        for call in mock_conn.execute.call_args_list:
            if "CREATE TABLE" in call[0][0] and f"\"{self.table_name}\"" in call[0][0]:
                create_table_call_found = True
                break
        self.assertTrue(create_table_call_found, "CREATE TABLE AS SELECT 應被調用")


    @patch('apps.etl_pipeline.loader.duckdb.connect')
    @patch('apps.etl_pipeline.loader._get_parquet_schema')
    @patch('apps.etl_pipeline.loader._get_table_schema_from_db')
    @patch('apps.etl_pipeline.loader._compare_schemas', return_value=True) # Assume schemas match
    def test_run_loading_successful_append_with_pk(
        self, mock_compare, mock_get_db_schema, mock_get_pq_schema, mock_duckdb_connect
    ):
        """
        測試 run_loading 在表格已存在且 Schema 匹配時，成功執行冪等插入。
        """
        mock_conn = MagicMock()
        mock_duckdb_connect.return_value.__enter__.return_value = mock_conn

        # Simulate table exists
        mock_get_db_schema.return_value = [{'name': 'colA', 'type': 'INTEGER'}, {'name': 'colB', 'type': 'VARCHAR'}]
        mock_get_pq_schema.return_value = [{'name': 'colA', 'type': 'INTEGER'}, {'name': 'colB', 'type': 'VARCHAR'}]

        result = loader.run_loading(self.test_argv)

        self.assertTrue(result, "run_loading 應在成功冪等插入時返回 True")
        # Check for INSERT INTO ... WHERE NOT EXISTS ... or similar logic
        insert_call_found = False
        for call in mock_conn.execute.call_args_list:
            sql_command = call[0][0]
            if "INSERT INTO" in sql_command and f"\"{self.table_name}\"" in sql_command and "NOT EXISTS" in sql_command :
                insert_call_found = True
                break
        self.assertTrue(insert_call_found, "冪等 INSERT 查詢應被調用")


    def test_run_loading_missing_arguments(self):
        """
        測試 run_loading 在缺少必要參數時 argparse 是否正確處理。
        """
        with self.assertRaises(SystemExit) as cm:
            loader.run_loading(["--db-path", str(self.dummy_db_path), "--table-name", self.table_name])
        self.assertEqual(cm.exception.code, 2) # Missing --parquet-file

        with self.assertRaises(SystemExit) as cm:
            loader.run_loading(["--parquet-file", str(self.dummy_parquet_path), "--table-name", self.table_name])
        self.assertEqual(cm.exception.code, 2) # Missing --db-path

    @patch('apps.etl_pipeline.loader._load_parquet_to_db_internal', side_effect=SchemaMismatchError("Mocked schema mismatch"))
    def test_run_loading_schema_mismatch(self, mock_internal_load_fail):
        """
        測試當 _load_parquet_to_db_internal 因 SchemaMismatchError 失敗時，run_loading 返回 False。
        """
        result = loader.run_loading(self.test_argv)
        self.assertFalse(result, "run_loading 應在 SchemaMismatchError 時返回 False")
        mock_internal_load_fail.assert_called_once()

    def test_run_loading_parquet_file_not_found(self):
        """
        測試當 Parquet 檔案不存在時，函數是否返回 False。
        """
        invalid_argv = [
            "--parquet-file", "non_existent.parquet",
            "--db-path", str(self.dummy_db_path),
            "--table-name", self.table_name
        ]
        # We need to patch Path.exists for the parquet file check in _load_parquet_to_db_internal
        with patch('apps.etl_pipeline.loader.Path.exists', side_effect=lambda p: False if "non_existent.parquet" in str(p) else True):
            result = loader.run_loading(invalid_argv)
        self.assertFalse(result, "run_loading 應在 Parquet 檔案不存在時返回 False")

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
