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
    @patch('apps.etl_pipeline.loader._get_parquet_schema') # 新增對 _get_parquet_schema 的 mock
    def test_run_loading_successful_creation(self, mock_get_pq_schema, mock_duckdb_connect):
        """
        測試 run_loading 首次成功創建表格並載入數據。
        """
        mock_conn = MagicMock()
        # loader.py uses "db_conn = duckdb.connect(...)", not "with duckdb.connect(...) as db_conn:"
        # So, the return_value of the mocked connect should be mock_conn directly.
        mock_duckdb_connect.return_value = mock_conn

        # 模擬 _get_parquet_schema 返回有效的 schema
        mock_get_pq_schema.return_value = [{'name': 'colA', 'type': 'INTEGER'}, {'name': 'colB', 'type': 'VARCHAR'}]

        # Simulate table does not exist initially
        with patch('apps.etl_pipeline.loader._get_table_schema_from_db', return_value=None) as mock_get_db_schema:
            result = loader.run_loading(self.test_argv)

        self.assertTrue(result, "run_loading 應在成功創建和載入時返回 True")
        mock_duckdb_connect.assert_called_with(database=str(self.dummy_db_path), read_only=False)
        # Check if CREATE TABLE ... AS SELECT ... was called
        create_table_as_select_found = False
        for call_args in mock_conn.execute.call_args_list:
            sql_command = str(call_args[0][0]).upper() # Convert to uppercase for case-insensitive check
            normalized_sql = ' '.join(sql_command.split()) # Normalize whitespace

            # More specific check for "CREATE TABLE target_table AS SELECT ... FROM READ_PARQUET(...)"
            expected_create = f'CREATE TABLE "{self.table_name.upper()}"' # DuckDB often upcases unquoted identifiers if not quoted
            expected_as_select_from_parquet = "AS SELECT * FROM READ_PARQUET("

            # In loader.py, table_name is quoted, so it should be case-sensitive if quotes are preserved.
            # Let's adjust the expectation to match the loader's quoting.
            expected_create_quoted = f'CREATE TABLE "{self.table_name}"' # Keep original case as it's quoted

            # Check based on normalized SQL from loader.py
            # loader.py uses: db_conn.execute(f"CREATE TABLE \"{table_name}\" AS SELECT * FROM read_parquet('{str(parquet_path)}')")

            # Normalize the executed SQL command for robust checking
            executed_sql_normalized = ' '.join(str(call_args[0][0]).upper().split())

            # Define expected parts, also normalized and in uppercase
            expected_part1 = f'CREATE TABLE "{self.table_name.upper()}"' # Table name is quoted, so case might matter or DuckDB normalizes it.
                                                                    # loader.py quotes it as is: "{table_name}"
                                                                    # Let's assume loader.py is correct and test against that.
            expected_part1_loader_case = f'CREATE TABLE "{self.table_name}"'
            normalized_part1_loader_case = ' '.join(expected_part1_loader_case.upper().split())


            expected_part2 = "AS SELECT"
            expected_part3 = "FROM READ_PARQUET"

            # Use upper case for comparison of content, but original case for quoted table name
            current_sql_call_for_test = ' '.join(str(call_args[0][0]).split()) # keep original case for quoted table name part

            # DEBUG: Print details
            # print(f"\nDEBUG CREATE SQL CHECK:")
            # print(f"  Executed SQL (normalized for check): '{executed_sql_normalized}'")
            # print(f"  Expected Part 1 (loader case): '{expected_part1_loader_case}'")
            # print(f"  Expected Part 2 (AS SELECT): '{expected_part2}'")
            # print(f"  Expected Part 3 (FROM READ_PARQUET): '{expected_part3}'")
            # print(f"  Checking Part 1 ('{expected_part1_loader_case}') in Original Call ('{current_sql_call_for_test}') : {expected_part1_loader_case in current_sql_call_for_test}")
            # print(f"  Checking Part 2 ('{expected_part2}') in Executed Normalized ('{executed_sql_normalized}') : {expected_part2 in executed_sql_normalized}")
            # print(f"  Checking Part 3 ('{expected_part3}') in Executed Normalized ('{executed_sql_normalized}') : {expected_part3 in executed_sql_normalized}")


            if (expected_part1_loader_case in current_sql_call_for_test and # Check with original case for quoted table name
                expected_part2 in executed_sql_normalized and # Check AS SELECT in uppercase normalized
                expected_part3 in executed_sql_normalized): # Check FROM READ_PARQUET in uppercase normalized
                create_table_as_select_found = True
                break
        self.assertTrue(create_table_as_select_found, f"CREATE TABLE \"{self.table_name}\" AS SELECT ... FROM READ_PARQUET(...) 應被調用. \nCaptured calls:\n{[str(c[0][0]) for c in mock_conn.execute.call_args_list]}")


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
        # loader.py uses "db_conn = duckdb.connect(...)", not "with duckdb.connect(...) as db_conn:"
        # So, the return_value of the mocked connect should be mock_conn directly.
        mock_duckdb_connect.return_value = mock_conn

        # Simulate table exists
        mock_get_db_schema.return_value = [{'name': 'colA', 'type': 'INTEGER'}, {'name': 'colB', 'type': 'VARCHAR'}]
        mock_get_pq_schema.return_value = [{'name': 'colA', 'type': 'INTEGER'}, {'name': 'colB', 'type': 'VARCHAR'}]

        result = loader.run_loading(self.test_argv)

        self.assertTrue(result, "run_loading 應在成功冪等插入時返回 True")
        # Check for INSERT INTO ... WHERE NOT EXISTS ... or similar logic
        insert_call_found = False
        for call in mock_conn.execute.call_args_list:
            sql_command = str(call[0][0]).upper() # 轉換為大寫以便不區分大小寫比較
            # 移除多餘空格和換行符
            normalized_sql = ' '.join(sql_command.split())

            # 檢查核心的冪等插入邏輯片段
            # loader.py 使用 f"INSERT INTO \"{table_name}\""，所以 table_name 的大小寫應與 self.table_name 原始值一致
            target_table_check = f'INSERT INTO "{self.table_name}"' # 使用原始大小寫
            normalized_target_table_check = ' '.join(target_table_check.upper().split()) # 用於與 normalized_sql 比較

            not_exists_check = "WHERE NOT EXISTS" # 這個子句通常是大寫

            # 由於 primary_key 在 loader.py 中也被引號包圍 f'"{primary_key_column}"'
            # 但要確保 self.test_argv 中的 primary_key 與 schema 中的一致
            # pk_col_name_in_sql = f'"{self.test_argv[self.test_argv.index("--primary-key") + 1]}"' # 獲取 --primary-key 的值並加引號
            # pk_check = f'{pk_col_name_in_sql.upper()} = SRC.{pk_col_name_in_sql.upper()}'

            # 簡化檢查，只檢查 "INSERT INTO" "TABLE_NAME" 和 "NOT EXISTS"
            # normalized_sql 是 call[0][0] 的大寫+正規化版本
            # normalized_target_table_check 是 'INSERT INTO "{TABLE_NAME}"' 的大寫+正規化版本

            # DEBUG: Print details
            # print(f"\nDEBUG INSERT SQL CHECK:")
            # print(f"  Normalized Executed SQL: '{normalized_sql}'")
            # print(f"  Normalized Target Table Check: '{normalized_target_table_check}'")
            # print(f"  Not Exists Check: '{not_exists_check}'")
            # print(f"  Checking Target Table: {normalized_target_table_check in normalized_sql}")
            # print(f"  Checking Not Exists: {not_exists_check in normalized_sql}")

            if normalized_target_table_check in normalized_sql and not_exists_check in normalized_sql:
                insert_call_found = True
                break

        # Define expected message parts outside the loop for the assert message
        expected_msg_part_table = f'INSERT INTO "{self.table_name.upper()}"' # As it's normalized for check
        expected_msg_part_condition = "WHERE NOT EXISTS"
        self.assertTrue(insert_call_found, f"冪等 INSERT 查詢 (包含 '{expected_msg_part_table}' 和 '{expected_msg_part_condition}') 應被調用. \nCaptured calls:\n{[str(c[0][0]) for c in mock_conn.execute.call_args_list]}")


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
