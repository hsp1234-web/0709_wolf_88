# -*- coding: utf-8 -*-
"""
對 `apps.backtesting_engine` 及其 CLI 命令的單元測試。
"""
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

# 為了讓測試能夠找到 main (CLI 入口) 和 apps (應用模組)
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# 從根目錄的 main.py 導入 CLI 應用實例
try:
    from main import cli as main_cli
except ImportError:
    # 如果直接在 tests/apps/ 目錄下執行 pytest，可能需要調整路徑
    # 這裡假設 pytest 是從根目錄執行的，或者 sys.path 已被正確設置
    pytest.fail("無法導入 main.py 中的 CLI 應用。請確保 pytest 從專案根目錄執行，或 sys.path 配置正確。")


@pytest.fixture
def runner():
    """提供一個 Click CliRunner 實例。"""
    return CliRunner()

def test_backtest_command_success(runner):
    """
    測試 `backtest` CLI 命令在 `vectorbt` 模組存在時的成功執行。
    """
    # 模擬 vectorbt 已被正確導入
    # 由於 vectorbt 的導入是在 apps.backtesting_engine.engine 模組級別
    # 我們需要在該模組加載前 mock 它，或者確保它在測試環境中可用
    # 這裡我們假設它能被正常導入，或者在 engine.py 中 mock 它
    # 更簡單的方式是直接 mock execute_backtest 的行為

    # 模擬 execute_backtest 函式，避免實際執行其內部邏輯
    # 注意：現在 patch 'main.execute_backtest' 因為它是在 main 模組中被查找和調用的
    with patch('main.execute_backtest') as mock_execute:
        mock_execute.return_value = {"status": "success", "message": "模擬回測執行完畢"}

        result = runner.invoke(main_cli, ['backtest'])

        assert result.exit_code == 0
        assert "回測引擎：核心業務邏輯 `execute_backtest` 已開始執行..." not in result.output # 因為我們 mock 了整個函式
        assert "模擬回測執行完畢" in result.output
        assert "'status': 'success'" in result.output # 檢查字典輸出的部分內容

def test_backtest_command_vectorbt_not_found(runner):
    """
    測試 `backtest` CLI 命令在 `vectorbt` 模組缺失時的行為。
    """
    # 關鍵在於模擬 main.execute_backtest (即從 engine.py 導入到 main.py 中的那個函式)
    # 在其執行時拋出 ModuleNotFoundError

    with patch('main.execute_backtest') as mock_execute:
        # 模擬原始的 execute_backtest 函式在執行時，其內部的 import vectorbt (或其使用) 失敗
        # 或者 engine.py 在頂層 import vectorbt 失敗，導致 execute_backtest 拋出此錯誤
        # 需要確保 e.name == 'vectorbt'
        mock_execute.side_effect = ModuleNotFoundError("No module named 'vectorbt'", name='vectorbt')

        result = runner.invoke(main_cli, ['backtest'])

        assert result.exit_code == 0 # Click 命令本身不應因業務邏輯錯誤而失敗退出，除非內部 sys.exit
        assert "錯誤：回測引擎缺少必要的 `vectorbt` 依賴。" in result.output

def test_backtest_command_general_exception(runner):
    """
    測試 `backtest` CLI 命令在發生其他未預期異常時的行為。
    """
    with patch('main.execute_backtest') as mock_execute:
        mock_execute.side_effect = Exception("某個意外的錯誤發生了！")

        result = runner.invoke(main_cli, ['backtest'])

        assert result.exit_code == 0
        assert "錯誤：執行回測時發生未預期錯誤：某個意外的錯誤發生了！" in result.output

# test_backtest_command_vectorbt_import_fails_in_engine_module 已被移除，
# 因為其意圖由 test_backtest_command_import_failure_in_main 和
# main.py 中對 execute_backtest 初始化為 None 的邏輯覆蓋。
# 並且其原始的 patching 方式存在路徑問題。

# 新增測試案例：模擬 main.py 中 execute_backtest 導入失敗
def test_backtest_command_import_failure_in_main(runner):
    """
    測試當 main.py 中 execute_backtest 初始化為 None (模擬導入失敗) 時，
    CLI 如何處理。
    """
    # 我們通過 patch main 模組中的 execute_backtest 變數為 None
    # 這模擬了 try-except ImportError 將其設置為 None 的情況
    with patch('main.execute_backtest', None):
        result = runner.invoke(main_cli, ['backtest'])
        assert result.exit_code == 0 # Click 命令應優雅處理
        assert "錯誤：回測引擎功能由於導入失敗而無法使用。" in result.output
        # 檢查是否打印了來自 main.py 的警告 (這是在模組加載時發生的，可能不會被 runner.invoke 捕獲)
        # 但命令本身的輸出應該是我們期望的錯誤訊息

# 輔助：檢查 CLI 是否能被調用並顯示幫助訊息
def test_cli_invokable_and_shows_help(runner):
    """測試 CLI 是否可調用並能顯示幫助訊息。"""
    result_help = runner.invoke(main_cli, ['--help'])
    assert result_help.exit_code == 0
    assert "蒼穹之心計畫 中央指揮部 (CLI)" in result_help.output
    assert "backtest" in result_help.output # 確認 backtest 命令在幫助訊息中

    result_backtest_help = runner.invoke(main_cli, ['backtest', '--help'])
    assert result_backtest_help.exit_code == 0
    assert "執行回測引擎的核心邏輯" in result_backtest_help.output

# 實際執行 print 的測試
def test_backtest_command_success_with_actual_print(runner):
    """
    測試 `backtest` CLI 命令成功執行並捕獲 `execute_backtest` 內部的 print 語句。
    這次不完全 mock `execute_backtest`，而是讓它實際執行，但 mock `vectorbt`。
    """
    # 模擬 vectorbt 模組，使其可以被 apps.backtesting_engine.engine 導入
    mock_vectorbt = MagicMock()
    sys.modules['vectorbt'] = mock_vectorbt

    # 由於 engine.py 在頂層 `import vectorbt`，
    # 我們需要確保這個 mock 在 `from apps.backtesting_engine.engine import execute_backtest`
    # 在 `main.py` 中發生之前就位。
    # 或者，如果 `main.py` 已經加載，我們需要重新加載 `apps.backtesting_engine.engine`
    # 並讓 `main.py` 重新導入 `execute_backtest`。這很複雜。

    # 更簡單的方法是，如果 `apps.backtesting_engine.engine.execute_backtest`
    # 內部有 `print` 語句，CliRunner 會捕獲它們。
    # 我們的 `main.py` 的 `backtest` 命令會調用 `execute_backtest` 並打印其返回的 `result`。
    # `execute_backtest` 自身也會打印。

    # 假設 test_backtest_command_success 中對 execute_backtest 的 mock 阻止了內部 print。
    # 現在我們讓它部分執行。

    # 為了讓 engine.py 中的 print 被執行，我們不能完全 mock execute_backtest。
    # 我們需要確保 engine.py 中的 import vectorbt 不會失敗。
    # 同時，我們不能 mock 'main.execute_backtest'，因為我們要測試它的實際執行。
    # 但我們需要確保 main.py 能夠成功導入原始的 execute_backtest。
    # 這意味著 apps.backtesting_engine.engine 模組本身及其依賴 (vectorbt) 必須是可導入的。

    # 模擬 vectorbt 模組，使其可以被 apps.backtesting_engine.engine 導入
    # 這個 mock 需要在 main.py 導入 apps.backtesting_engine.engine 之前生效。
    # 這通常比較困難，因為模組可能已經被加載。
    # 一種策略是確保在測試運行開始時，所有相關模組都以期望的狀態（或 mock 狀態）被加載。

    # 由於 CliRunner 會為每個 invoke 創建一個相對乾淨的環境（但不完全隔離 sys.modules），
    # 我們可以嘗試在 invoke 之前設置 mock。

    # 為了讓 `from apps.backtesting_engine.engine import execute_backtest` 在 `main.py` 中成功，
    # 並且 `engine.py` 中的 `import vectorbt` 也成功，我們 mock `sys.modules['vectorbt']`。
    # 然後，我們不 mock `main.execute_backtest`，讓它執行原始邏輯。

    original_vectorbt = sys.modules.get('vectorbt')
    sys.modules['vectorbt'] = MagicMock()

    # 為了確保 main_cli 使用的是最新的 execute_backtest (如果它在模組加載時被捕獲)
    # 我們可能需要重新導入 main 模組，或者依賴 CliRunner 的行為。
    # 假設 CliRunner 會重新評估 main_cli。
    # 或者，更簡單地，如果 main.py 中的 execute_backtest 是全局變數，
    # 並且 main 模組只被導入一次，那麼我們需要在該導入發生之前 mock vectorbt。

    # 考慮到 main.py 的寫法:
    # execute_backtest = None
    # try: from apps.backtesting_engine.engine import execute_backtest
    # except ...
    #
    # 這意味著 execute_backtest 是在 main 模G載入時決定的。
    # 為了讓這個測試通過，我們需要在 `from main import cli as main_cli` 這一行
    # 執行之前，就 mock 好 `vectorbt`。
    # 這通常需要在測試模組的頂層或 fixture 中完成。

    # 為了這個特定測試的簡潔性，我們假設 `main_cli` 已經正確加載了 `execute_backtest`，
    # 並且這個 `execute_backtest` 內部會 `import vectorbt`。
    # 所以我們 patch `apps.backtesting_engine.engine.vectorbt`。
    # 這樣，當 `main.execute_backtest`（即原始的 `engine.execute_backtest`）執行時，
    # 它內部的 `vectorbt` 引用會是我們的 mock。

    with patch('apps.backtesting_engine.engine.vectorbt', MagicMock()) as mock_vbt_in_engine:
        # 確保 main.execute_backtest 是未被 mock 的原始函式
        # 這需要 main.py 成功導入 apps.backtesting_engine.engine.execute_backtest
        # 而這又需要 apps.backtesting_engine.engine 能成功 import vectorbt (現在被 mock 了)

        # 重新導入 main 模組以確保它獲取最新的 apps.backtesting_engine.engine.execute_backtest
        # 這通常不推薦在測試函數內部做，但有時是必要的
        import importlib
        import main as main_module # 獲取 main 模組的引用
        importlib.reload(main_module) # 重新加載 main 模組
        cli_to_test = main_module.cli # 從重新加載的模組獲取 cli

        result = runner.invoke(cli_to_test, ['backtest'])

        assert result.exit_code == 0
        # 檢查來自 engine.py -> execute_backtest() 的 print
        assert "回測引擎：核心業務邏輯 `execute_backtest` 已開始執行..." in result.output
        assert "回測引擎：核心業務邏輯 `execute_backtest` 已成功完成。" in result.output
        # 檢查來自 main.py -> backtest() 命令的 print
        assert "回測結果: {'status': 'success', 'message': '回測執行完畢'}" in result.output

    # 清理 mock，避免影響其他測試
    if original_vectorbt:
        sys.modules['vectorbt'] = original_vectorbt
    elif 'vectorbt' in sys.modules:
        del sys.modules['vectorbt']
