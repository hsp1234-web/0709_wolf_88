import numpy as np
import pandas as pd


def test_environment_works():
    """一個簡單的點火測試，確保核心函式庫可以被導入並使用。"""
    s = pd.Series([1, 3, 5, np.nan, 6, 8])
    assert s.sum() == 23.0, "Pandas 或 NumPy 的基本計算出錯！"
    print("\n[PASS] Core libraries (pandas, numpy) imported and used successfully.")
