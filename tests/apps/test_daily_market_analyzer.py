# -*- coding: utf-8 -*-
import pytest
import os
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime
import traceback # 確保 traceback 被導入

# --- 調試路徑設定 START ---
print(f"DEBUG: test_daily_market_analyzer.py __file__ is {__file__}")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
print(f"DEBUG: Calculated PROJECT_ROOT is {PROJECT_ROOT}")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
    print(f"DEBUG: PROJECT_ROOT {PROJECT_ROOT} was inserted into sys.path")
else:
    print(f"DEBUG: PROJECT_ROOT {PROJECT_ROOT} was already in sys.path")

print(f"DEBUG: Current sys.path is {sys.path}")

# 檢查目標模組檔案是否存在
expected_logic_file_path = os.path.join(PROJECT_ROOT, 'apps', 'daily_market_analyzer', 'logic.py')
print(f"DEBUG: Expecting logic file at {expected_logic_file_path}")
print(f"DEBUG: Does logic file exist? {os.path.exists(expected_logic_file_path)}")

# 檢查 apps/__init__.py 是否存在
expected_apps_init_path = os.path.join(PROJECT_ROOT, 'apps', '__init__.py')
print(f"DEBUG: Expecting apps init file at {expected_apps_init_path}")
print(f"DEBUG: Does apps init file exist? {os.path.exists(expected_apps_init_path)}")

# 檢查 apps/daily_market_analyzer/__init__.py 是否存在
expected_dma_init_path = os.path.join(PROJECT_ROOT, 'apps', 'daily_market_analyzer', '__init__.py')
print(f"DEBUG: Expecting DMA init file at {expected_dma_init_path}")
print(f"DEBUG: Does DMA init file exist? {os.path.exists(expected_dma_init_path)}")
# --- 調試路徑設定 END ---

# 現在可以導入被測試的邏輯
from apps.daily_market_analyzer.logic import daily_market_analyzer_main_logic

TEST_FINMIND_API_TOKEN = os.environ.get("TEST_FINMIND_API_TOKEN", "test_token")
TEST_FMP_API_KEY = os.environ.get("TEST_FMP_API_KEY", "test_fmp_key")

@pytest.fixture(scope="function")
def mock_dependencies():
    with patch('apps.daily_market_analyzer.logic.YFinanceClient') as MockYFClient, \
         patch('apps.daily_market_analyzer.logic.DBManager') as MockDBManager, \
         patch('apps.daily_market_analyzer.logic.AnalysisEngine') as MockAnalysisEngine, \
         patch('apps.daily_market_analyzer.logic.ReportGenerator') as MockReportGenerator, \
         patch('apps.daily_market_analyzer.logic.log_hardware_stats') as MockLogHardware, \
         patch('apps.daily_market_analyzer.logic.archive_hardware_stats_to_csv') as MockArchiveHardware, \
         patch('shutil.copy2') as MockShutilCopy, \
         patch('os.makedirs') as MockOsMakedirs, \
         patch('os.path.exists') as MockOsPathExists:

        def side_effect_os_path_exists(path):
            if "daily_market_analyzer.duckdb" in path or "test_dma.duckdb" in path or "test_dma_report.duckdb" in path:
                return True
            if "data_workspace/reports" in path or \
               "data_workspace/logs/archive" in path or \
               os.path.join("data_workspace", "databases_local") in path:
                return True
            return False
        MockOsPathExists.side_effect = side_effect_os_path_exists

        mock_yf_instance = MockYFClient.return_value
        mock_yf_instance.hydrate_data_range.return_value = (None, {"2023-01-01": {"AAPL": {"status": "mocked_success", "message": "Data mocked"}}})

        mock_db_instance = MockDBManager.return_value
        mock_db_instance.create_ohlcv_table.return_value = None
        mock_db_instance.upsert_data.return_value = None
        mock_db_instance.get_connection_info.return_value = {"path": "mocked_db_path.duckdb"}

        mock_rg_instance = MockReportGenerator.return_value
        mock_rg_instance.generate_full_report.return_value = "Mocked Test Report Content"

        def makedirs_side_effect(name, mode=0o777, exist_ok=False):
            if exist_ok and os.path.isdir(name):
                return
            return
        MockOsMakedirs.side_effect = makedirs_side_effect

        yield {
            "YFClient": MockYFClient,
            "DBManager": MockDBManager,
            "AnalysisEngine": MockAnalysisEngine,
            "ReportGenerator": MockReportGenerator,
            "LogHardware": MockLogHardware,
            "ArchiveHardware": MockArchiveHardware,
            "ShutilCopy": MockShutilCopy,
            "OsMakedirs": MockOsMakedirs,
            "OsPathExists": MockOsPathExists
        }

def test_dma_logic_runs_data_only_mode(mock_dependencies, tmp_path):
    test_db_path = str(tmp_path / "test_dma.duckdb")
    test_project_local_path = str(tmp_path / "local_project")

    os.makedirs(os.path.join(test_project_local_path, "data_workspace", "reports"), exist_ok=True)
    os.makedirs(os.path.join(test_project_local_path, "data_workspace", "logs", "archive"), exist_ok=True)

    original_os_path_exists = mock_dependencies["OsPathExists"].side_effect
    def specific_os_path_exists(path_arg):
        if str(tmp_path) in path_arg:
            return os.path.exists(path_arg)
        return original_os_path_exists(path_arg)
    mock_dependencies["OsPathExists"].side_effect = specific_os_path_exists

    try:
        daily_market_analyzer_main_logic(
            tickers="AAPL,MSFT",
            start_date="2023-01-01",
            end_date="2023-01-05",
            data_only=True,
            report_only=False,
            report_start_date=None,
            report_end_date=None,
            db_path=test_db_path,
            cache_db_path=None,
            table_name="test_market_data",
            no_data_cooldown_days=7,
            force_refresh=False,
            enable_local_first=False,
            gdrive_root=str(tmp_path / "gdrive"),
            project_path_local=test_project_local_path,
            max_workers=2
        )
    except Exception as e:
        pytest.fail(f"daily_market_analyzer_main_logic 在 data_only 模式下拋出異常: {e}\n{traceback.format_exc()}")

    mock_dependencies["YFClient"].assert_called_once()
    mock_dependencies["DBManager"].assert_called_once()
    mock_yf_instance = mock_dependencies["YFClient"].return_value
    assert mock_yf_instance.hydrate_data_range.call_count > 0
    mock_dependencies["ReportGenerator"].assert_not_called()


def test_dma_logic_runs_report_only_mode(mock_dependencies, tmp_path):
    test_db_path = str(tmp_path / "test_dma_report.duckdb")
    test_project_local_path = str(tmp_path / "local_project_report")
    os.makedirs(os.path.join(test_project_local_path, "data_workspace", "reports"), exist_ok=True)
    os.makedirs(os.path.join(test_project_local_path, "data_workspace", "logs", "archive"), exist_ok=True)

    original_os_path_exists = mock_dependencies["OsPathExists"].side_effect
    def specific_os_path_exists(path_arg):
        if str(tmp_path) in path_arg:
            return os.path.exists(path_arg)
        return original_os_path_exists(path_arg)
    mock_dependencies["OsPathExists"].side_effect = specific_os_path_exists

    try:
        daily_market_analyzer_main_logic(
            tickers="GOOG,TSLA",
            start_date=None,
            end_date=None,
            data_only=False,
            report_only=True,
            report_start_date="2023-02-01",
            report_end_date="2023-02-05",
            db_path=test_db_path,
            cache_db_path=None,
            table_name="test_market_data_for_report",
            no_data_cooldown_days=7,
            force_refresh=False,
            enable_local_first=False,
            gdrive_root=str(tmp_path / "gdrive_report"),
            project_path_local=test_project_local_path,
            max_workers=2
        )
    except Exception as e:
        pytest.fail(f"daily_market_analyzer_main_logic 在 report_only 模式下拋出異常: {e}\n{traceback.format_exc()}")

    mock_dependencies["ReportGenerator"].assert_called_once()
    mock_rg_instance = mock_dependencies["ReportGenerator"].return_value
    mock_rg_instance.generate_full_report.assert_called_once()


def test_dma_logic_parameter_validation_data_and_report_only(mock_dependencies, tmp_path):
    """測試同時指定 data_only 和 report_only 時是否引發 ValueError。"""
    # 從 logic.py 中複製的確切錯誤訊息
    expected_error_msg = "錯誤：--data-only 和 --report-only 不能同時指定。"
    with pytest.raises(ValueError, match=expected_error_msg):
        daily_market_analyzer_main_logic(
            tickers="ANY", start_date="2023-01-01", end_date="2023-01-01",
            data_only=True, report_only=True,
            report_start_date=None, report_end_date=None,
            db_path=str(tmp_path / "dummy.db"),
            cache_db_path=None, # 明確傳遞 None
            table_name="dummy",
            no_data_cooldown_days=7, force_refresh=False, enable_local_first=False,
            gdrive_root=str(tmp_path / "gdrive"), project_path_local=str(tmp_path / "local"), max_workers=1
        )

def test_dma_logic_parameter_validation_report_only_missing_dates(mock_dependencies, tmp_path):
    """測試 report_only 模式缺少報告日期時是否引發 ValueError。"""
    # 從 logic.py 中複製的確切錯誤訊息
    expected_error_msg = "錯誤：純報告模式需指定 --report-start-date 和 --report-end-date。"
    with pytest.raises(ValueError, match=expected_error_msg):
        daily_market_analyzer_main_logic(
            tickers="ANY",
            start_date=None, end_date=None,
            data_only=False, report_only=True,
            report_start_date=None, report_end_date="2023-01-01", # 缺少 report_start_date
            db_path=str(tmp_path / "dummy.db"),
            cache_db_path=None, # 明確傳遞 None
            table_name="dummy",
            no_data_cooldown_days=7, force_refresh=False, enable_local_first=False,
            gdrive_root=str(tmp_path / "gdrive"), project_path_local=str(tmp_path / "local"), max_workers=1
        )

if __name__ == "__main__":
    pytest.main([__file__])
