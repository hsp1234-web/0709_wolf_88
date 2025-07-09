# -*- coding: utf-8 -*-
"""
單元測試：因子引擎 (FactorEngine)

本檔案包含針對 apps/factor_engine/engine.py 中 FactorEngine 類別的單元測試。
所有測試均應為「密封測試」，不依賴外部資料庫或檔案系統。
"""
import sys
import os

# --- 標準化「路徑自我校正」樣板碼 START ---
# 取得目前腳本檔案的目錄
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 自動偵測專案根目錄 (假設 .git 在根目錄，或存在 README.md)
project_root = current_script_dir
max_levels_up = 5 # 防止無限迴圈，可根據專案深度調整
for _ in range(max_levels_up):
    # 檢查是否存在 .git 目錄或 AGENTS.md (或 README.md) 作為根目錄標記
    if os.path.isdir(os.path.join(project_root, '.git')) or \
       os.path.isfile(os.path.join(project_root, 'AGENTS.md')) or \
       os.path.isfile(os.path.join(project_root, 'README.md')):
        break
    parent_dir = os.path.dirname(project_root)
    if parent_dir == project_root: # 已達檔案系統頂層
        # 對於在 tests/unit/ 下的腳本，根目錄通常是向上兩層
        project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..'))
        print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑 (tests/unit 腳本): {project_root}")
        break
    project_root = parent_dir
else: # 如果迴圈正常結束 (未 break)
    project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..')) # 後備方案
    print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑 (tests/unit 腳本): {project_root}")

if project_root not in sys.path:
    sys.path.insert(0, project_root)
# print(f"DEBUG: 專案根目錄 {project_root} 已添加到 sys.path")
# --- 標準化「路徑自我校正」樣板碼 END ---

import pandas as pd
import numpy as np
import pytest
from unittest.mock import MagicMock

# 確保 FactorEngine 可以被導入
# 路徑校正通常在執行 pytest 時由 pytest 自動處理，或者由頂層的 conftest.py 處理
# 如果直接執行此檔案，可能需要手動調整 sys.path 或使用計畫中的標準路徑校正樣板
from apps.factor_engine.engine import FactorEngine

# 固定測試數據
@pytest.fixture
def sample_price_data() -> pd.DataFrame:
    """提供一個用於測試的標準價格 DataFrame。"""
    dates = pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05',
                            '2023-01-06', '2023-01-07', '2023-01-08', '2023-01-09', '2023-01-10',
                            '2023-01-11', '2023-01-12', '2023-01-13', '2023-01-14', '2023-01-15',
                            '2023-01-16', '2023-01-17', '2023-01-18', '2023-01-19', '2023-01-20',
                            '2023-01-21', '2023-01-22', '2023-01-23', '2023-01-24', '2023-01-25'])
    data = {
        'open': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 110, 109, 108, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116],
        'high': [102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 112, 111, 110, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118],
        'low': [99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 108, 107, 106, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
        'close': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 111, 110, 109, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117],
        'volume': [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500, 2600, 2700, 2800, 2900, 3000, 3100, 3200, 3300, 3400]
    }
    df = pd.DataFrame(data, index=dates)
    df.index.name = 'datetime'
    return df

@pytest.fixture
def sample_yield_data() -> pd.DataFrame:
    """提供一個用於測試的標準殖利率 DataFrame (寬表)。"""
    dates = pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05'])
    data = {
        '3M': [0.03, 0.031, 0.032, 0.033, 0.034],
        '2Y': [0.025, 0.026, 0.027, 0.028, 0.029],
        '10Y': [0.02, 0.021, 0.022, 0.023, 0.024],
    }
    df = pd.DataFrame(data, index=dates)
    df.index.name = 'date'
    return df

@pytest.fixture
def factor_engine_instance() -> FactorEngine:
    """提供一個 FactorEngine 的實例，其 db_manager 被 Mock掉。"""
    mock_db_manager = MagicMock()
    engine = FactorEngine(db_manager=mock_db_manager)
    return engine

# --- 測試 FactorEngine 方法 ---

def test_calculate_price_volatility(factor_engine_instance: FactorEngine, sample_price_data: pd.DataFrame):
    """測試 calculate_price_volatility 方法。"""
    n_days = 5 # 使用較短的窗口期以簡化預期值計算
    result = factor_engine_instance.calculate_price_volatility(sample_price_data.copy(), n_days=n_days)

    assert isinstance(result, pd.Series), "結果應為 Pandas Series"
    assert not result.empty, "結果 Series 不應為空"
    assert result.name == 'log_return', "Series 的名稱應為 'log_return'，儘管實際返回的是波動率" # FactorEngine 內部計算 log_return 後滾動 std

    # 預期值計算 (簡化):
    # 由於實際計算涉及對數回報率和滾動標準差，手動精確計算較複雜。
    # 此處僅驗證格式和非空，實際項目中應有更精確的預期值。
    # 例如，可以預計算一個小數據集的結果並在此處斷言。
    # 這裡我們檢查是否有 NaN 值 (除了初始窗口期)
    # log_return 使第一個有效數據在索引1。rolling(n_days) 使第一個有效std在索引 n_days。
    assert result.iloc[n_days:].notna().all(), "滾動窗口完全形成後不應有 NaN 值"
    # 簡單檢查數值範圍 (假設波動率不會是負數)
    assert (result.dropna() >= 0).all(), "波動率值不應為負"

    # 處理空 DataFrame 或缺少欄位的情況
    empty_df = pd.DataFrame()
    assert factor_engine_instance.calculate_price_volatility(empty_df.copy(), n_days=n_days) is None, "空 DataFrame 應返回 None"

    no_close_df = sample_price_data.drop(columns=['close'])
    assert factor_engine_instance.calculate_price_volatility(no_close_df.copy(), n_days=n_days) is None, "缺少 'close' 欄位的 DataFrame 應返回 None"

def test_calculate_volume_volatility(factor_engine_instance: FactorEngine, sample_price_data: pd.DataFrame):
    """測試 calculate_volume_volatility 方法。"""
    n_days = 5
    result = factor_engine_instance.calculate_volume_volatility(sample_price_data.copy(), n_days=n_days)

    assert isinstance(result, pd.Series), "結果應為 Pandas Series"
    assert not result.empty, "結果 Series 不應為空"
    assert result.name == 'volume_change_rate', "Series 的名稱應為 'volume_change_rate'"

    assert result.iloc[n_days:].notna().all(), "第二個窗口期之後不應有 NaN 值 (第一個 NaN 是 pct_change 產生)"
    assert (result.dropna() >= 0).all(), "波動率值不應為負"

    empty_df = pd.DataFrame()
    assert factor_engine_instance.calculate_volume_volatility(empty_df.copy(), n_days=n_days) is None, "空 DataFrame 應返回 None"

    no_volume_df = sample_price_data.drop(columns=['volume'])
    assert factor_engine_instance.calculate_volume_volatility(no_volume_df.copy(), n_days=n_days) is None, "缺少 'volume' 欄位的 DataFrame 應返回 None"

def test_calculate_rsi(factor_engine_instance: FactorEngine, sample_price_data: pd.DataFrame):
    """測試 calculate_rsi 方法。"""
    n_days = 14
    # 確保 pandas_ta 擴展已加載 (在 fixture 或頂層導入)
    # 如果 pandas_ta 未正確安裝或版本不兼容，dataframe.ta 可能不存在
    # pytest 執行時，頂層的 import pandas_ta as ta 應該已經處理了擴展註冊

    # 為了讓 .ta 屬性可用，pandas_ta 必須被導入。
    # 在 FactorEngine 類中，頂層導入了 pandas_ta。
    # 在此測試文件中，頂層也導入了 pandas_ta。
    # 因此，sample_price_data 應該具有 .ta 擴展。
    # 如果 FactorEngine 中的頂層導入被移除，則此測試需要在 FactorEngine 實例化之前確保 pandas_ta 已導入，
    # 或者 FactorEngine 內部自行處理導入。但根據計畫1.3，內部導入會被移除。

    result = factor_engine_instance.calculate_rsi(sample_price_data.copy(), n_days=n_days)

    assert isinstance(result, pd.Series), "結果應為 Pandas Series"
    assert not result.empty, "結果 Series 不應為空"
    # pandas-ta 生成的 RSI Series 通常名稱為 RSI_DAYS，例如 RSI_14
    assert result.name == f'RSI_{n_days}', f"Series 的名稱應為 RSI_{n_days}"

    # RSI 值應在 0 到 100 之間 (除去 NaN)
    assert (result.dropna() >= 0).all() and (result.dropna() <= 100).all(), "RSI 值應在 0 到 100 之間"
    assert result.iloc[n_days:].notna().any(), "RSI 在窗口期後應至少有一些非 NaN 值" # RSI 計算需要一定數據量

    # 測試 DataFrame 索引不是 DatetimeIndex 的情況
    non_datetime_index_df = sample_price_data.reset_index(drop=True)
    # FactorEngine 中的實現會打印警告並返回 None，這裡我們斷言 None
    assert factor_engine_instance.calculate_rsi(non_datetime_index_df.copy(), n_days=n_days) is None, "非 DatetimeIndex 的 DataFrame 應返回 None"

    empty_df = pd.DataFrame()
    assert factor_engine_instance.calculate_rsi(empty_df.copy(), n_days=n_days) is None, "空 DataFrame 應返回 None"

def test_calculate_yield_spreads(factor_engine_instance: FactorEngine, sample_yield_data: pd.DataFrame):
    """測試 calculate_yield_spreads 方法。"""
    result_df = factor_engine_instance.calculate_yield_spreads(sample_yield_data.copy())

    assert isinstance(result_df, pd.DataFrame), "結果應為 Pandas DataFrame"
    assert not result_df.empty, "結果 DataFrame 不應為空"

    expected_spread_10y_2y = sample_yield_data['10Y'] - sample_yield_data['2Y']
    expected_spread_10y_3m = sample_yield_data['10Y'] - sample_yield_data['3M']

    pd.testing.assert_series_equal(result_df['spread_10y_2y'], expected_spread_10y_2y.rename('spread_10y_2y'), check_dtype=False)
    pd.testing.assert_series_equal(result_df['spread_10y_3m'], expected_spread_10y_3m.rename('spread_10y_3m'), check_dtype=False)

    # 測試缺少欄位的情況
    missing_2y_df = sample_yield_data.drop(columns=['2Y'])
    result_missing_2y = factor_engine_instance.calculate_yield_spreads(missing_2y_df.copy())
    assert 'spread_10y_2y' in result_missing_2y.columns and result_missing_2y['spread_10y_2y'].isna().all()
    if '3M' in missing_2y_df.columns and '10Y' in missing_2y_df.columns: # 確保 10Y-3M 仍然可以計算
        pd.testing.assert_series_equal(result_missing_2y['spread_10y_3m'], expected_spread_10y_3m.rename('spread_10y_3m'), check_dtype=False)

    empty_df = pd.DataFrame()
    result_empty = factor_engine_instance.calculate_yield_spreads(empty_df.copy())
    assert result_empty.empty, "空 DataFrame 輸入應返回空 DataFrame"

def test_calculate_credit_spread_proxy(factor_engine_instance: FactorEngine):
    """測試 calculate_credit_spread_proxy 方法，Mock get_prices_for_ticker。"""

    # 準備 Mock 返回的 DataFrame
    dates_hyg = pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04'])
    hyg_prices = pd.DataFrame({'close': [10, 11, 12, 13]}, index=dates_hyg)
    hyg_prices.index.name = 'datetime'

    dates_lqd = pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04']) # 保持日期一致以便合併
    lqd_prices = pd.DataFrame({'close': [20, 22, 20, 26]}, index=dates_lqd)
    lqd_prices.index.name = 'datetime'

    # 配置 mock_get_prices_for_ticker
    def mock_get_prices_side_effect(ticker_symbol: str):
        if ticker_symbol == 'HYG':
            return hyg_prices.copy()
        elif ticker_symbol == 'LQD':
            return lqd_prices.copy()
        return pd.DataFrame()

    factor_engine_instance.get_prices_for_ticker = MagicMock(side_effect=mock_get_prices_side_effect)

    result_df = factor_engine_instance.calculate_credit_spread_proxy()

    assert isinstance(result_df, pd.DataFrame), "結果應為 Pandas DataFrame"
    assert not result_df.empty, "結果 DataFrame 不應為空"
    assert 'HYG_LQD_price_ratio' in result_df.columns, "結果應包含 HYG_LQD_price_ratio 欄位"

    expected_ratio_values = [10/20, 11/22, 12/20, 13/26]
    expected_index = pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04'])
    expected_series = pd.Series(expected_ratio_values, index=expected_index, name='HYG_LQD_price_ratio')

    pd.testing.assert_series_equal(result_df['HYG_LQD_price_ratio'], expected_series, check_dtype=False)

    # 測試如果一個 ticker 數據缺失
    factor_engine_instance.get_prices_for_ticker = MagicMock(side_effect=lambda ts: hyg_prices.copy() if ts == 'HYG' else pd.DataFrame())
    result_missing_lqd = factor_engine_instance.calculate_credit_spread_proxy()
    assert result_missing_lqd.empty, "如果 LQD 數據缺失，結果應為空 DataFrame"

    # 測試如果 HYG 數據缺失
    factor_engine_instance.get_prices_for_ticker = MagicMock(side_effect=lambda ts: lqd_prices.copy() if ts == 'LQD' else pd.DataFrame())
    result_missing_hyg = factor_engine_instance.calculate_credit_spread_proxy()
    assert result_missing_hyg.empty, "如果 HYG 數據缺失，結果應為空 DataFrame"

    # 測試日期不匹配導致 merge 後為空的情況
    dates_hyg_alt = pd.to_datetime(['2023-01-05', '2023-01-06'])
    hyg_prices_alt = pd.DataFrame({'close': [10, 11]}, index=dates_hyg_alt)
    hyg_prices_alt.index.name = 'datetime'

    def mock_get_prices_no_overlap(ticker_symbol: str):
        if ticker_symbol == 'HYG':
            return hyg_prices_alt.copy() # 使用不同日期的 HYG
        elif ticker_symbol == 'LQD':
            return lqd_prices.copy()
        return pd.DataFrame()
    factor_engine_instance.get_prices_for_ticker = MagicMock(side_effect=mock_get_prices_no_overlap)
    result_no_overlap = factor_engine_instance.calculate_credit_spread_proxy()
    assert result_no_overlap.empty, "如果日期無重疊，結果應為空 DataFrame"

# 可以添加更多測試案例，例如邊界條件、不同數據類型等。
# 例如：測試 RSI 計算中，如果 close 數據全部相同會發生什麼。
# 例如：測試波動率計算中，如果數據點少於窗口期會發生什麼。
# 確保所有公開的計算方法都被測試到。
# get_prices_for_ticker 和 get_treasury_yields 主要負責數據庫交互，
# 它們的測試更適合放在整合測試中，或者在單元測試中徹底 mock DBManager 的 execute_query 方法。
# 但由於 FactorEngine 的這兩個方法直接返回 DataFrame，它們的輸出格式也可以在此進行簡單驗證，如果需要。
# 不過，根據作戰計畫，單元測試應「嚴禁任何資料庫連接或外部檔案 I/O」，所以這裡不直接測試它們的DB交互。
