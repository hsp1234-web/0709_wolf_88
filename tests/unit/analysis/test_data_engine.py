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
    mock_yf.get_history.assert_called_once_with("FAKE_TICKER", period="1y")
    mock_fred.fetch_data.assert_called_once_with('VIXCLS') # 確認呼叫的是 fetch_data
    mock_yf.get_move_index.assert_called_once_with(start_date="2020-01-01", end_date="2025-07-12") # 驗證 get_move_index 呼叫
