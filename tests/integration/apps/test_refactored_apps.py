# tests/integration/apps/test_refactored_apps.py
import subprocess
import sys


def run_app_script(script_name: str):
    """一個輔助函式，用於在正確的虛擬環境中運行應用腳本"""
    # 設定 PYTHONPATH 環境變數以包含專案根目錄
    # 這樣即使是從 tests/integration/apps/ 目錄下執行的 subprocess
    # 也能找到 core 模組
    import os

    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(
        [sys.executable, script_name],
        capture_output=True,
        text=True,
        check=True,
        env=env,  # 傳遞更新後的環境變數
    )
    # 為了日誌驗證，我們同時返回 stdout 和 stderr
    return result.stdout + result.stderr


def test_run_gold_layer_pipeline():
    """測試黃金層數據管線啟動器，並驗證日誌輸出"""
    output = run_app_script("apps/run_gold_layer.py")

    # 驗證日誌格式和內容
    assert "INFO" in output
    assert "Initializing Gold Layer Pipeline..." in output
    assert "Gold Layer Pipeline finished" in output
    assert "gold_layer_ok" in output


def test_run_stress_index_pipeline():
    """測試壓力指數計算管線啟動器，並驗證日誌輸出"""
    output = run_app_script("apps/run_stress_index.py")

    # 驗證日誌格式和內容
    assert "INFO" in output
    assert "Initializing Stress Index Pipeline..." in output
    assert "Stress Index Pipeline finished" in output
    assert "stress_index_ok" in output
