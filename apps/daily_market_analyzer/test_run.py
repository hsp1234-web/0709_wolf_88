import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import argparse
import os
import pandas as pd # For pd.date_range in one of the tests
from datetime import datetime

# Path adjustments
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the functions/classes to be tested from run.py
# This is tricky as run.py is a script. We might need to refactor run.py
# or use import_module if we want to test its functions directly.
# For now, let's assume we can import specific functions if they were refactored.
# Or, we test main() by mocking many things.

# For archive_hardware_stats_to_csv, we can try to import it if run.py is importable
from apps.daily_market_analyzer.run import main as run_main # To test aspects of main
from apps.daily_market_analyzer.run import archive_hardware_stats_to_csv # If it's top-level

# Mock necessary modules that run.py imports
sys.modules['apps.daily_market_analyzer.yfinance_client'] = MagicMock()
sys.modules['apps.daily_market_analyzer.db_manager'] = MagicMock()
sys.modules['apps.daily_market_analyzer.analysis_engine'] = MagicMock()
sys.modules['apps.daily_market_analyzer.report_generator'] = MagicMock()
sys.modules['psutil'] = MagicMock()


class TestRunScriptHardwareArchive(unittest.TestCase):

    def setUp(self):
        self.mock_args = argparse.Namespace(
            project_path_local="/test/local/project",
            gdrive_root="/test/gdrive/",
            db_path="data_workspace/test.db", # This will be used for base_gdrive_path_ref
            # Add other args archive_hardware_stats_to_csv might implicitly use via cli_args
        )

    @patch('apps.daily_market_analyzer.run.os.makedirs')
    @patch('apps.daily_market_analyzer.run.open', new_callable=mock_open)
    @patch('apps.daily_market_analyzer.run.csv.DictWriter')
    def test_archive_hardware_stats_to_csv_writes_local_and_gdrive(self, mock_csv_writer, mock_file_open, mock_makedirs):
        stats = [{"timestamp": "t1", "stage": "s1", "cpu_percent": 10, "ram_percent": 20}]
        ts_str = "20230101_120000"

        # Construct expected paths based on logic in archive_hardware_stats_to_csv
        # base_gdrive_path_ref is args.db_path = "data_workspace/test.db"
        # -> os.path.dirname("data_workspace/test.db") = "data_workspace"
        # -> os.path.join("data_workspace", "logs", "archive")
        expected_local_path = "/test/local/project/data_workspace/logs/archive/hardware_monitor_report_20230101_120000.csv"
        expected_gdrive_path = "/test/gdrive/data_workspace/logs/archive/hardware_monitor_report_20230101_120000.csv"

        # Adjust mock_args for this specific test if gdrive_db_path derivation is complex
        # The function uses cli_args.gdrive_root if base_gdrive_path_ref is not structured as expected.
        # Let's assume base_gdrive_path_ref is cli_args.gdrive_root + cli_args.db_path for simplicity in test
        # if base_gdrive_path_ref is complex to mock, test path generation separately.

        # For this test, let's make base_gdrive_path_ref point to a GDrive DB path
        # so that gdrive_log_archive_base is derived, not using fallback.
        gdrive_db_file_path_on_gdrive = os.path.join(self.mock_args.gdrive_root, self.mock_args.db_path)
        # This would make gdrive_project_data_workspace = /test/gdrive/data_workspace
        # and gdrive_log_archive_base = /test/gdrive/data_workspace/logs/archive

        archive_hardware_stats_to_csv(stats, self.mock_args, ts_str, gdrive_db_file_path_on_gdrive)

        mock_makedirs.assert_any_call(os.path.dirname(expected_local_path), exist_ok=True)
        mock_makedirs.assert_any_call(os.path.dirname(expected_gdrive_path), exist_ok=True)

        # Check open calls
        # Order of calls might vary if local path equals gdrive path (not in this test setup)
        mock_file_open.assert_any_call(expected_local_path, 'w', newline='', encoding='utf-8')
        mock_file_open.assert_any_call(expected_gdrive_path, 'w', newline='', encoding='utf-8')

        # Check CSV writer calls
        mock_csv_writer_instance = mock_csv_writer.return_value
        self.assertEqual(mock_csv_writer_instance.writeheader.call_count, 2)
        self.assertEqual(mock_csv_writer_instance.writerows.call_count, 2)
        mock_csv_writer_instance.writerows.assert_any_call(stats)


    @patch('apps.daily_market_analyzer.run.os.makedirs')
    @patch('apps.daily_market_analyzer.run.open', new_callable=mock_open)
    @patch('apps.daily_market_analyzer.run.csv.DictWriter')
    def test_archive_hardware_stats_no_stats(self, mock_csv_writer, mock_file_open, mock_makedirs):
        archive_hardware_stats_to_csv([], self.mock_args, "timestamp", "gdrive/db/path")
        mock_file_open.assert_not_called()
        mock_csv_writer.assert_not_called()

# --- Tests for Local-First in main() would be more complex ---
# They would require extensive mocking of os, shutil, and the imported app components.
# Example sketch for one aspect:
class TestRunScriptLocalFirst(unittest.TestCase):
    @patch('apps.daily_market_analyzer.run.argparse.ArgumentParser')
    @patch('apps.daily_market_analyzer.run.DBManager') # Mock the class from db_manager
    @patch('apps.daily_market_analyzer.run.YFinanceClient')
    @patch('apps.daily_market_analyzer.run.AnalysisEngine')
    @patch('apps.daily_market_analyzer.run.ReportGenerator')
    @patch('apps.daily_market_analyzer.run.psutil')
    @patch('apps.daily_market_analyzer.run.os.path.exists')
    @patch('apps.daily_market_analyzer.run.os.makedirs')
    @patch('apps.daily_market_analyzer.run.shutil.copy2')
    @patch('apps.daily_market_analyzer.run.run_data_pipeline') # Mock pipeline functions
    @patch('apps.daily_market_analyzer.run.run_report_generation')
    @patch('apps.daily_market_analyzer.run.archive_hardware_stats_to_csv') # Mock this new function too
    def test_main_local_first_enabled_copy_success(
        self, mock_archive_hw_csv, mock_run_report, mock_run_data, mock_shutil_copy, mock_os_makedirs,
        mock_os_exists, mock_psutil, mock_report_gen, mock_analysis_eng, mock_yf_client,
        mock_db_manager_class, mock_argparse
    ):
        # Setup args parsing
        mock_args = argparse.Namespace(
            tickers="AAPL", start_date="2023-01-01", end_date="2023-01-01",
            data_only=False, report_only=False, report_start_date=None, report_end_date=None,
            db_path="/gdrive/project/data_workspace/main.db", # GDrive path
            db_name="main.db", cache_db_path=None, table_name="ohlcv",
            process_uploads=False, no_data_cooldown_days=7, force_refresh=False,
            enable_local_first=True, # ENABLED
            gdrive_root="/gdrive/",
            project_path_local="/local/project/",
            max_workers=4
        )
        mock_argparse.return_value.parse_args.return_value = mock_args

        # os.path.exists: 1st for local_db_dir, 2nd for gdrive_db_path, 3rd for local_db_path_instance (in finally)
        # 4th for gdrive_db_dir_for_writeback (in finally)
        mock_os_exists.side_effect = [
            False, # local_db_dir does not exist (will be created)
            True,  # gdrive_db_path exists
            True,  # local_db_path_instance exists (after copy, for write-back check)
            False, # gdrive_db_dir_for_writeback does not exist (will be created for write-back)
        ]

        # DBManager instance mock
        mock_db_mgr_instance = MagicMock()
        mock_db_manager_class.return_value = mock_db_mgr_instance

        # Call main
        run_main()

        # Assertions for local-first copy TO local
        expected_local_db_dir = "/local/project/data_workspace/databases_local"
        expected_local_db_path = os.path.join(expected_local_db_dir, "main.db")

        mock_os_makedirs.assert_any_call(expected_local_db_dir, exist_ok=True)
        mock_shutil_copy.assert_any_call(mock_args.db_path, expected_local_db_path) # Copy GDrive -> Local

        # Assert DBManager was initialized with local path
        mock_db_manager_class.assert_called_with(db_path=expected_local_db_path, duckdb_config=unittest.mock.ANY)

        # Assertions for local-first write BACK to GDrive (in finally)
        expected_gdrive_target_dir = os.path.dirname(mock_args.db_path) # /gdrive/project/data_workspace
        mock_os_makedirs.assert_any_call(expected_gdrive_target_dir, exist_ok=True) # For write-back
        mock_shutil_copy.assert_any_call(expected_local_db_path, mock_args.db_path) # Copy Local -> GDrive

        self.assertEqual(mock_shutil_copy.call_count, 2) # Once to local, once back to GDrive

if __name__ == '__main__':
    unittest.main()
