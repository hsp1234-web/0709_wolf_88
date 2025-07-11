# tests/integration/apps/test_refactored_apps.py
import subprocess
import sys

def run_app_script(script_name: str):
    """一個輔助函式，用於在正確的虛擬環境中運行應用腳本"""
    # 使用 sys.executable 確保我們用的是 poetry 的 python 解釋器
    import os # 新增導入
    # 設定 PYTHONPATH 環境變數
    env = os.environ.copy()
    env["PYTHONPATH"] = "." + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(
        [sys.executable, script_name],
        capture_output=True,
        text=True,
        check=True,  # 如果腳本返回非零退出碼，則拋出異常
        env=env # 傳遞更新後的環境變數
    )
    return result.stdout

def test_run_gold_layer_pipeline():
    """測試黃金層數據管線啟動器"""
    output = run_app_script("apps/run_gold_layer.py")
    assert "Gold Layer Pipeline finished" in output
    assert "gold_layer_ok" in output

def test_run_stress_index_pipeline():
    """測試壓力指數計算管線啟動器"""
    output = run_app_script("apps/run_stress_index.py")
    assert "Stress Index Pipeline finished" in output
    assert "stress_index_ok" in output
