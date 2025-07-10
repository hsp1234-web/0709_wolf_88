# -*- coding: utf-8 -*-
"""
對 `apps.daily_market_analyzer` 的 CLI 命令 (`analyze-market`) 的單元測試。
"""
import pytest
from click.testing import CliRunner
from unittest.mock import patch, call # Import call for checking multiple calls or specific args

# 為了讓測試能夠找到 main (CLI 入口)
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

try:
    from main import cli as main_cli
except ImportError as e:
    pytest.fail(f"無法導入 main.py 中的 CLI 應用: {e}。請確保 pytest 從專案根目錄執行，或 sys.path 配置正確。")

@pytest.fixture
def runner():
    """提供一個 Click CliRunner 實例。"""
    return CliRunner()

# 基本的成功案例 - Mock run_daily_analysis
@patch('apps.daily_market_analyzer.cli_interface.run_daily_analysis')
def test_analyze_market_success_minimum_params(mock_run_daily_analysis, runner):
    """
    測試 `analyze-market` 命令在提供最小必要參數（對於完整流程）時的成功調用。
    """
    mock_run_daily_analysis.return_value = {"status": "success", "message": "模擬分析完成"}

    # 假設 tickers, start-date, end-date 是完整流程的最小必要CLI參數
    # db-path 等有預設值
    result = runner.invoke(main_cli, [
        'analyze-market',
        '--tickers', 'AAPL,MSFT',
        '--start-date', '2023-01-01',
        '--end-date', '2023-01-31'
    ])

    assert result.exit_code == 0, f"CLI 命令執行失敗: {result.output}"
    mock_run_daily_analysis.assert_called_once()

    # 驗證傳遞給 mock 的參數 - 關注我們在命令中指定的參數
    args, kwargs = mock_run_daily_analysis.call_args
    assert kwargs.get('tickers') == 'AAPL,MSFT'
    assert kwargs.get('start_date_str') == '2023-01-01'
    assert kwargs.get('end_date_str') == '2023-01-31'
    # 檢查其他參數是否使用了預設值
    assert kwargs.get('data_only') is False
    assert kwargs.get('report_only') is False
    assert kwargs.get('db_path') == 'data_workspace/daily_market_analyzer.duckdb' # Click default
    assert kwargs.get('force_refresh') is False


@patch('apps.daily_market_analyzer.cli_interface.run_daily_analysis')
def test_analyze_market_all_boolean_flags(mock_run_daily_analysis, runner):
    """
    測試所有布林型 flag 參數的傳遞。
    """
    mock_run_daily_analysis.return_value = {"status": "success"}
    result = runner.invoke(main_cli, [
        'analyze-market',
        '--tickers', 'GOOG', '--start-date', '2023-02-01', '--end-date', '2023-02-28', # 必要參數
        '--data-only',
        '--force-refresh',
        '--enable-local-first'
        # --report-only 不能與 --data-only 同時使用，這由 run_daily_analysis 內部邏輯處理
    ])
    assert result.exit_code == 0, f"CLI 命令執行失敗: {result.output}"
    mock_run_daily_analysis.assert_called_once()
    args, kwargs = mock_run_daily_analysis.call_args
    assert kwargs.get('data_only') is True
    assert kwargs.get('force_refresh') is True
    assert kwargs.get('enable_local_first') is True
    assert kwargs.get('report_only') is False # 未指定，應為 False

@patch('apps.daily_market_analyzer.cli_interface.run_daily_analysis')
def test_analyze_market_report_only_params(mock_run_daily_analysis, runner):
    """
    測試 --report-only 模式及其相關日期參數的傳遞。
    """
    mock_run_daily_analysis.return_value = {"status": "success"}
    result = runner.invoke(main_cli, [
        'analyze-market',
        '--tickers', 'TSLA', # 在 report_only 模式下，tickers 也是必需的
        '--report-only',
        '--report-start-date', '2023-03-01',
        '--report-end-date', '2023-03-15'
    ])
    assert result.exit_code == 0, f"CLI 命令執行失敗: {result.output}"
    mock_run_daily_analysis.assert_called_once()
    args, kwargs = mock_run_daily_analysis.call_args
    assert kwargs.get('tickers') == 'TSLA'
    assert kwargs.get('report_only') is True
    assert kwargs.get('report_start_date_str') == '2023-03-01'
    assert kwargs.get('report_end_date_str') == '2023-03-15'
    assert kwargs.get('data_only') is False # 未指定，應為 False

@patch('apps.daily_market_analyzer.cli_interface.run_daily_analysis')
def test_analyze_market_custom_paths_and_numbers(mock_run_daily_analysis, runner):
    """
    測試自訂路徑和數值參數的傳遞。
    """
    mock_run_daily_analysis.return_value = {"status": "success"}
    result = runner.invoke(main_cli, [
        'analyze-market',
        '--tickers', 'AMZN', '--start-date', '2023-04-01', '--end-date', '2023-04-30', # 必要參數
        '--db-path', '/custom/path/to/db.duckdb',
        '--table-name', 'custom_ohlcv',
        '--no-data-cooldown-days', '3',
        '--gdrive-root', '/gdrive_custom/',
        '--project-path-local', '/local_project_custom/',
        '--max-workers', '8'
    ])
    assert result.exit_code == 0, f"CLI 命令執行失敗: {result.output}"
    mock_run_daily_analysis.assert_called_once()
    args, kwargs = mock_run_daily_analysis.call_args
    assert kwargs.get('db_path') == '/custom/path/to/db.duckdb'
    assert kwargs.get('table_name') == 'custom_ohlcv'
    assert kwargs.get('no_data_cooldown_days') == 3
    assert kwargs.get('gdrive_root') == '/gdrive_custom/'
    assert kwargs.get('project_path_local') == '/local_project_custom/'
    assert kwargs.get('max_workers') == 8

@patch('apps.daily_market_analyzer.cli_interface.run_daily_analysis')
def test_analyze_market_run_daily_analysis_exception(mock_run_daily_analysis, runner):
    """
    測試當 run_daily_analysis 內部拋出異常時，CLI 的行為。
    """
    mock_run_daily_analysis.side_effect = Exception("內部邏輯發生嚴重錯誤！")
    result = runner.invoke(main_cli, [
        'analyze-market',
        '--tickers', 'ERR', '--start-date', '2023-01-01', '--end-date', '2023-01-02'
    ])
    # main.py 中的 analyze_market_command 會捕獲通用 Exception
    assert result.exit_code == 0 # Click 命令本身不應因業務邏輯錯誤而失敗退出 (除非 Abort)
    assert "錯誤：執行每日市場分析時發生未預期錯誤：內部邏輯發生嚴重錯誤！" in result.output
    mock_run_daily_analysis.assert_called_once()

@patch('apps.daily_market_analyzer.cli_interface.run_daily_analysis')
def test_analyze_market_run_daily_analysis_click_abort(mock_run_daily_analysis, runner):
    """
    測試當 run_daily_analysis 內部拋出 click.Abort 時，CLI 的行為。
    """
    # click.Abort 通常會導致非零退出碼，並且 Click 會打印 "Aborted!" 或自訂訊息
    mock_run_daily_analysis.side_effect = click.Abort("由內部邏輯中止操作。")
    result = runner.invoke(main_cli, [
        'analyze-market',
        '--tickers', 'ABORT', '--start-date', '2023-01-01', '--end-date', '2023-01-02'
    ])
    assert result.exit_code != 0 # click.Abort 應該導致非零退出碼
    assert "由內部邏輯中止操作。" in result.output # Abort 訊息應該被打印
    mock_run_daily_analysis.assert_called_once()

def test_analyze_market_help_message(runner):
    """
    測試 `analyze-market --help` 是否能正常顯示所有選項。
    """
    result = runner.invoke(main_cli, ['analyze-market', '--help'])
    assert result.exit_code == 0
    # 抽查幾個參數
    assert "--tickers TEXT" in result.output
    assert "--start-date TEXT" in result.output
    assert "--db-path PATH" in result.output
    assert "--max-workers INTEGER" in result.output
    assert "--data-only" in result.output
    assert "--report-only" in result.output
    assert "執行每日市場分析、數據獲取和報告生成。" in result.output # 命令的幫助文本

# 測試 run_daily_analysis 導入失敗的情況 (已在 main.py 中處理)
@patch('main.run_daily_analysis', None) # 直接將 main 模組中的變數 patch 為 None
def test_analyze_market_module_import_failure(mock_placeholder, runner):
    """
    測試當 main.py 中 run_daily_analysis 變數為 None (模擬導入失敗) 時的行為。
    """
    result = runner.invoke(main_cli, ['analyze-market'])
    assert result.exit_code == 0 # 命令應優雅處理
    assert "錯誤：每日市場分析器功能由於導入失敗而無法使用。" in result.output
    # mock_placeholder 在這裡只是為了符合 @patch 的語法，因為我們 patch 的是 main.run_daily_analysis
    # run_daily_analysis (即 mock_placeholder) 不應該被調用
    # 但由於它是 None，所以不會有 call 屬性。
    # 這裡的關鍵是檢查輸出訊息。

# 更多關於參數互斥的測試，依賴於 run_daily_analysis 內部的驗證邏輯
# 例如，--data-only 和 --report-only 不能同時為 True
@patch('apps.daily_market_analyzer.cli_interface.run_daily_analysis')
def test_analyze_market_data_only_and_report_only_conflict(mock_run_daily_analysis, runner):
    """
    測試當 --data-only 和 --report-only 同時提供時，
    run_daily_analysis 內部拋出 click.Abort 的情況。
    """
    # 模擬 run_daily_analysis 檢測到衝突並中止
    mock_run_daily_analysis.side_effect = click.Abort("錯誤：--data-only 和 --report-only 選項不能同時指定。")

    result = runner.invoke(main_cli, [
        'analyze-market',
        '--tickers', 'CONFLICT', '--start-date', '2023-01-01', '--end-date', '2023-01-02',
        '--data-only',
        '--report-only'
    ])

    assert result.exit_code != 0 # click.Abort 應該導致非零退出碼
    assert "錯誤：--data-only 和 --report-only 選項不能同時指定。" in result.output
    # 確保 run_daily_analysis 被調用一次 (即使它立即拋出 Abort)
    mock_run_daily_analysis.assert_called_once()
    args, kwargs = mock_run_daily_analysis.call_args
    assert kwargs.get('data_only') is True
    assert kwargs.get('report_only') is True

# 測試 report-only 模式下缺少必要日期參數的情況
@patch('apps.daily_market_analyzer.cli_interface.run_daily_analysis')
def test_analyze_market_report_only_missing_dates(mock_run_daily_analysis, runner):
    """
    測試 --report-only 模式下，如果缺少 --report-start-date 或 --report-end-date，
    run_daily_analysis 內部應拋出 click.Abort。
    """
    mock_run_daily_analysis.side_effect = click.Abort("錯誤：當使用 --report-only 時，必須提供 --report-start-date 和 --report-end-date。")

    result = runner.invoke(main_cli, [
        'analyze-market',
        '--tickers', 'TSLA',
        '--report-only'
        # 故意不提供 --report-start-date 和 --report-end-date
    ])

    assert result.exit_code != 0
    assert "錯誤：當使用 --report-only 時，必須提供 --report-start-date 和 --report-end-date。" in result.output
    mock_run_daily_analysis.assert_called_once()

# 測試完整流程模式下缺少必要參數的情況
@patch('apps.daily_market_analyzer.cli_interface.run_daily_analysis')
def test_analyze_market_full_flow_missing_params(mock_run_daily_analysis, runner):
    """
    測試完整流程模式下，如果缺少 --tickers, --start-date, 或 --end-date，
    run_daily_analysis 內部應拋出 click.Abort。
    """
    mock_run_daily_analysis.side_effect = click.Abort("錯誤：在完整流程模式下，必須提供 --tickers, --start-date, 和 --end-date。")

    # 情況1: 缺少 tickers
    result_no_tickers = runner.invoke(main_cli, [
        'analyze-market',
        # '--tickers', 'AAPL',
        '--start-date', '2023-01-01',
        '--end-date', '2023-01-31'
    ])
    assert result_no_tickers.exit_code != 0
    assert "錯誤：在完整流程模式下，必須提供 --tickers, --start-date, 和 --end-date。" in result_no_tickers.output

    # 情況2: 缺少 start-date (tickers 和 end-date 提供)
    # 為了單獨測試，我們需要重置 mock 的 call_count 或使用不同的 mock 實例
    # 這裡簡單地假設 runner.invoke 可以多次調用，mock 會被再次調用
    # 但要注意 side_effect 是一樣的
    mock_run_daily_analysis.reset_mock() # 重置 mock 狀態
    mock_run_daily_analysis.side_effect = click.Abort("錯誤：在完整流程模式下，必須提供 --tickers, --start-date, 和 --end-date。")
    result_no_start_date = runner.invoke(main_cli, [
        'analyze-market',
        '--tickers', 'AAPL',
        # '--start-date', '2023-01-01',
        '--end-date', '2023-01-31'
    ])
    assert result_no_start_date.exit_code != 0
    assert "錯誤：在完整流程模式下，必須提供 --tickers, --start-date, 和 --end-date。" in result_no_start_date.output

    # 確保 mock 至少被調用了（每個失敗的案例一次）
    assert mock_run_daily_analysis.call_count >= 2 # 至少兩次調用
