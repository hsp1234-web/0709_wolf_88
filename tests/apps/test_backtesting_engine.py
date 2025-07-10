# -*- coding: utf-8 -*-
import pytest
import os
import sys
from unittest.mock import patch, MagicMock

# --- 調試與路徑設定 ---
# 這段程式碼確保測試執行時能找到 apps 目錄下的模組
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
print(f"DEBUG (test_backtesting_engine): PROJECT_ROOT={PROJECT_ROOT}, sys.path prepended.")

# 導入被測試的邏輯
# 注意：我們需要能夠在測試時控制 VECTORBT_AVAILABLE 的狀態
# 因此，我們可能需要 patch 'apps.backtesting_engine.engine.VECTORBT_AVAILABLE'
# 或者 patch 'import vectorbt' 本身
from apps.backtesting_engine.engine import run_backtest_logic


@pytest.fixture
def mock_vectorbt_available(monkeypatch):
    """模擬 vectorbt 可用情況"""
    mock_vbt = MagicMock()
    mock_vbt.__version__ = "0.25.0-mocked" # 模擬版本號

    monkeypatch.setitem(sys.modules, 'vectorbt', mock_vbt) # 任何 'import vectorbt' 都會得到這個 mock

    # 導入或重新導入 engine 模組，以便它能獲取到 sys.modules 中 mock 的 vectorbt
    # 或者直接在已加載的模組上操作
    import importlib
    import apps.backtesting_engine.engine as engine_module
    # importlib.reload(engine_module) # 重新加載可能會導致其他問題，謹慎使用

    # 強制設定 engine 模組內部的狀態
    monkeypatch.setattr(engine_module, "VECTORBT_AVAILABLE", True)
    monkeypatch.setattr(engine_module, "vectorbt", mock_vbt) # 確保 engine.vectorbt 指向 mock

    print("DEBUG: mock_vectorbt_available: Patched sys.modules['vectorbt'], engine.VECTORBT_AVAILABLE, and engine.vectorbt.")
    return mock_vbt

@pytest.fixture
def mock_vectorbt_unavailable(monkeypatch):
    """模擬 vectorbt 不可用情況"""
    if 'vectorbt' in sys.modules:
        monkeypatch.delitem(sys.modules, 'vectorbt') # 從 sys.modules 移除，模擬未安裝

    import apps.backtesting_engine.engine as engine_module
    # import importlib
    # importlib.reload(engine_module) # 重新加載以使其 internal import vectorbt 失敗

    # 強制設定 engine 模組內部的狀態
    monkeypatch.setattr(engine_module, "VECTORBT_AVAILABLE", False)
    # 如果 engine.vectorbt 因導入失敗而不存在，嘗試 setattr 可能會出錯
    # 但 engine.py 的邏輯是如果導入失敗，就不會使用 vectorbt 變數
    # 所以這裡主要確保 VECTORBT_AVAILABLE 為 False
    if hasattr(engine_module, 'vectorbt'): # 如果它之前意外地被設置了
        monkeypatch.delattr(engine_module, 'vectorbt')

    print("DEBUG: mock_vectorbt_unavailable: Patched sys.modules, engine.VECTORBT_AVAILABLE, and ensured no engine.vectorbt.")


def test_run_backtest_logic_success(mock_vectorbt_available, capsys):
    """
    測試當 vectorbt 可用時，run_backtest_logic 成功執行。
    """
    print("DEBUG: Starting test_run_backtest_logic_success")
    result = run_backtest_logic()
    captured = capsys.readouterr()

    assert result["status"] == "success"
    assert "回測執行完畢" in result["message"]
    assert "核心業務邏輯 `run_backtest_logic` 已開始執行..." in captured.out
    assert "核心業務邏輯 `run_backtest_logic` 已成功完成。" in captured.out
    assert "vectorbt 版本: 0.25.0-mocked" in captured.out # 驗證模擬版本被使用
    print("DEBUG: test_run_backtest_logic_success finished.")


def test_run_backtest_logic_vectorbt_missing(mock_vectorbt_unavailable, capsys):
    """
    測試當 vectorbt 不可用時，run_backtest_logic 返回錯誤狀態。
    """
    print("DEBUG: Starting test_run_backtest_logic_vectorbt_missing")
    result = run_backtest_logic()
    captured = capsys.readouterr()

    assert result["status"] == "error"
    assert "必要的 `vectorbt` 模組未找到" in result["message"]
    assert result["missing_dependency"] == "vectorbt"
    assert "錯誤（回測引擎邏輯）：必要的 `vectorbt` 模組未找到。" in captured.out
    print("DEBUG: test_run_backtest_logic_vectorbt_missing finished.")

# --- 針對 CLI 命令的測試 (可選，更偏向整合測試) ---
# 若要測試 Typer CLI 命令本身，通常會使用 Typer 的 CliRunner 或類似工具。
# 這裡先專注於核心邏輯的單元測試。

# from typer.testing import CliRunner
# from main import app # 假設 main.py 中的 Typer app 實例叫做 app

# runner = CliRunner()

# def test_cli_backtest_command_success(mock_vectorbt_available):
#     """
#     測試 CLI 'backtest' 命令在 vectorbt 可用時的行為。
#     """
#     print("DEBUG: Starting test_cli_backtest_command_success")
#     # result = runner.invoke(app, ["backtest", "--strategy", "dummy_strat"]) # 如果有參數
#     result = runner.invoke(app, ["backtest"])
#     print(f"CLI Output: {result.stdout}")
#     print(f"CLI Exception: {result.exc_info}")

#     assert result.exit_code == 0
#     assert "接收到 backtest 命令" in result.stdout
#     assert "回測命令執行完畢" in result.stdout
#     assert "核心業務邏輯 `run_backtest_logic` 已成功完成。" in result.stdout
#     print("DEBUG: test_cli_backtest_command_success finished.")


# def test_cli_backtest_command_vectorbt_missing(mock_vectorbt_unavailable):
#     """
#     測試 CLI 'backtest' 命令在 vectorbt 不可用時的行為。
#     """
#     print("DEBUG: Starting test_cli_backtest_command_vectorbt_missing")
#     # result = runner.invoke(app, ["backtest", "--strategy", "dummy_strat"])
#     result = runner.invoke(app, ["backtest"])
#     print(f"CLI Output: {result.stdout}")
#     print(f"CLI Exception: {result.exc_info}")

#     assert result.exit_code == 0 # 命令本身不應該因為 "可預期的" 依賴缺失而失敗退出 (除非設計如此)
#     assert "接收到 backtest 命令" in result.stdout
#     assert "警告：核心回測依賴 `vectorbt` 模組未在本環境中找到。" in result.stdout
#     assert "回測命令執行失敗" in result.stdout
#     assert "缺少依賴模組 - vectorbt" in result.stdout
#     print("DEBUG: test_cli_backtest_command_vectorbt_missing finished.")

if __name__ == "__main__":
    pytest.main([__file__, "-s", "-v"])
