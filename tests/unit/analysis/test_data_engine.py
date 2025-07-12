# 檔案路徑: tests/unit/analysis/test_data_engine.py
import pytest
import pandas as pd
from unittest.mock import MagicMock

# 導入我們要測試的目標
from core.analysis.data_engine import DataEngine

@pytest.fixture
def mock_clients():
    """創建所有數據客戶端的模擬版本。"""
    mock_yf = MagicMock()
    mock_fred = MagicMock()
    mock_taifex = MagicMock()

    # 設定模擬客戶端的返回值
    # 創建一個價格持續上漲的 DataFrame，以測試 RSI 是否會超買
    price_data = {'Close': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 120]}
    mock_yf.get_history.return_value = pd.DataFrame(price_data)
    # 設定 get_move_index 的返回值
    mock_yf.get_move_index.return_value = pd.Series([120.5], name="^MOVE")

    # 模擬近似指標所需的 yfinance client 數據
    # _calculate_approx_credit_spread
    mock_yf.get_history.side_effect = lambda ticker, period: {
        "FAKE_TICKER": pd.DataFrame(price_data),
        "HYG": pd.DataFrame({'Close': [75.0]}),
        "IEF": pd.DataFrame({'Close': [100.0]}),
        "TLT": pd.DataFrame({'Close': range(100, 160)}), # 60 days for proxy_move
        "GLD": pd.DataFrame({'Close': [180.0]}),
        "HG=F": pd.DataFrame({'Close': [4.5]}),
    }.get(ticker, pd.DataFrame())


    # FredClient.fetch_data 返回 DataFrame，欄位名為 symbol
    mock_fred.fetch_data.return_value = pd.DataFrame({'VIXCLS': [25.5]})

    return mock_yf, mock_fred, mock_taifex

def test_data_engine_logic(mock_clients):
    """
    【實驗室測試】
    驗證 DataEngine 的核心計算邏輯。
    """
    # 1. 準備 (Arrange): 使用模擬客戶端初始化數據引擎
    mock_yf, mock_fred, mock_taifex = mock_clients
    engine = DataEngine(yf_client=mock_yf, fred_client=mock_fred, taifex_client=mock_taifex)

    # 2. 執行 (Act): 生成快照
    snapshot = engine.generate_snapshot(ticker="FAKE_TICKER", as_of_date="2025-07-12")

    # 3. 斷言 (Assert): 驗證快照內容是否符合預期
    # 驗證技術指標計算是否正確 (注意：此處的70是假數據，Jules需要替換為真實計算後的預期值)
    assert snapshot['technicals_section']['RSI_14D'] == 70
    assert snapshot['technicals_section']['RSI_status'] == '超買'

    # 驗證MA20是否被正確計算
    expected_ma20 = pd.Series([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 120]).mean()
    assert snapshot['technicals_section']['MA20'] == round(expected_ma20, 2)

    # 驗證宏觀數據是否被正確提取
    assert snapshot['macro_section']['VIX'] == 25.5
    assert snapshot['macro_section']['MOVE_Index'] == 120.5 # 驗證 MOVE 指數

    # 驗證客戶端的方法是否被正確呼叫
    # mock_yf.get_history.assert_called_once_with("FAKE_TICKER", period="1y") # Cannot use assert_called_once_with due to multiple calls with side_effect
    assert mock_yf.get_history.call_count >= 1 # Ensure it was called at least for FAKE_TICKER
    mock_fred.fetch_data.assert_called_once_with('VIXCLS') # 確認呼叫的是 fetch_data
    mock_yf.get_move_index.assert_called_once_with(start_date="2020-01-01", end_date="2025-07-12") # 驗證 get_move_index 呼叫

    # 驗證近似指標
    assert snapshot['approx_indicators']['approx_credit_spread'] == 0.75
    # Expected proxy_move: TLT prices from 100 to 159. Returns will be (101-100)/100, (102-101)/101 ...
    # For simplicity in mock, let's assume a pre-calculated value or mock the yf_client's get_history for TLT more specifically in its own test
    # For now, we will rely on the specific test for _calculate_proxy_move for exact value validation.
    # Here, we just check if the key exists and is a float.
    assert isinstance(snapshot['approx_indicators']['proxy_move'], float)
    assert snapshot['approx_indicators']['gold_copper_ratio'] == 40.0

def test_calculate_approx_credit_spread_with_mock_data(mock_clients):
    """測試 _calculate_approx_credit_spread 方法的邏輯。"""
    mock_yf, mock_fred, mock_taifex = mock_clients
    engine = DataEngine(yf_client=mock_yf, fred_client=mock_fred, taifex_client=mock_taifex)

    # Override side_effect for this specific test if needed, or ensure general mock is sufficient
    # For this test, the general mock_yf.get_history.side_effect should provide HYG and IEF data
    credit_spread = engine._calculate_approx_credit_spread()
    assert credit_spread == 0.7500

    # Test case: HYG data missing
    mock_yf.get_history.side_effect = lambda ticker, period: {
        "IEF": pd.DataFrame({'Close': [100.0]}),
    }.get(ticker, pd.DataFrame())
    credit_spread_no_hyg = engine._calculate_approx_credit_spread()
    assert pd.isna(credit_spread_no_hyg)

    # Test case: IEF price is zero
    mock_yf.get_history.side_effect = lambda ticker, period: {
        "HYG": pd.DataFrame({'Close': [75.0]}),
        "IEF": pd.DataFrame({'Close': [0.0]}),
    }.get(ticker, pd.DataFrame())
    credit_spread_ief_zero = engine._calculate_approx_credit_spread()
    assert pd.isna(credit_spread_ief_zero)


def test_calculate_proxy_move_with_mock_data(mock_clients):
    """測試 _calculate_proxy_move 方法的邏輯。"""
    mock_yf, mock_fred, mock_taifex = mock_clients
    engine = DataEngine(yf_client=mock_yf, fred_client=mock_fred, taifex_client=mock_taifex)

    # Specific mock for TLT data for this test
    tlt_prices = [100 + i * 0.5 for i in range(60)] # Create a series of prices
    mock_yf.get_history.side_effect = lambda ticker, period: {
        "TLT": pd.DataFrame({'Close': tlt_prices}),
    }.get(ticker, pd.DataFrame())

    proxy_move = engine._calculate_proxy_move()

    # Calculate expected value manually for these specific mock prices
    expected_tlt_returns = pd.Series(tlt_prices).pct_change()
    expected_proxy_move = expected_tlt_returns.rolling(window=20).std().iloc[-1]
    assert proxy_move == round(expected_proxy_move, 4)

    # Test case: Insufficient data
    mock_yf.get_history.side_effect = lambda ticker, period: {
        "TLT": pd.DataFrame({'Close': [100, 101]}), # Not enough data
    }.get(ticker, pd.DataFrame())
    proxy_move_insufficient_data = engine._calculate_proxy_move()
    assert pd.isna(proxy_move_insufficient_data)


def test_calculate_gold_copper_ratio_with_mock_data(mock_clients):
    """測試 _calculate_gold_copper_ratio 方法的邏輯。"""
    mock_yf, mock_fred, mock_taifex = mock_clients
    engine = DataEngine(yf_client=mock_yf, fred_client=mock_fred, taifex_client=mock_taifex)

    # The general mock_yf.get_history.side_effect should provide GLD and HG=F data
    gold_copper_ratio = engine._calculate_gold_copper_ratio()
    assert gold_copper_ratio == 40.0000

    # Test case: Copper price is zero
    mock_yf.get_history.side_effect = lambda ticker, period: {
        "GLD": pd.DataFrame({'Close': [180.0]}),
        "HG=F": pd.DataFrame({'Close': [0.0]}),
    }.get(ticker, pd.DataFrame())
    gold_copper_ratio_copper_zero = engine._calculate_gold_copper_ratio()
    assert pd.isna(gold_copper_ratio_copper_zero)
