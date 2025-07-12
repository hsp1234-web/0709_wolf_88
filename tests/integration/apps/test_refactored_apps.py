# tests/integration/apps/test_refactored_apps.py
import subprocess
import sys
import os

def run_app_script(script_name: str):
    """一個輔助函式，用於在正確的虛擬環境中運行應用腳本"""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(
        [sys.executable, script_name],
        capture_output=True,
        text=True,
        check=False,  # We will check the output manually
        env=env,
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


def test_run_stress_index_pipeline():
    """測試壓力指數計算管線啟動器，並驗證日誌輸出"""
    output = run_app_script("apps/run_stress_index.py")

    # 驗證日誌格式和內容
    assert "INFO" in output
    assert "Initializing Stress Index Pipeline..." in output
    assert "Stress Index Pipeline finished" in output
    assert "壓力指數計算成功" in output
