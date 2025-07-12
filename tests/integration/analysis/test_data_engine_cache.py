# 檔案路徑: tests/integration/analysis/test_data_engine_cache.py
import pytest
import requests_cache
import os # 導入 os 模組
from unittest.mock import MagicMock # <--- 修正導入 (已存在，確認無誤)
import pandas as pd
import fredapi # <--- 導入 fredapi 以便 spy

from core.clients.fred import FredClient
from core.analysis.data_engine import DataEngine

# 獲取 API 金鑰
FRED_API_KEY = os.environ.get("FRED_API_KEY_TEST_ONLY") # 使用不同的環境變數名稱以示區隔

@pytest.fixture(scope="module")
def real_fred_client():
    """創建一個使用暫存快取的真實客戶端實例。"""
    if not FRED_API_KEY:
        pytest.skip("FRED_API_KEY_TEST_ONLY 環境變數未設定，跳過此整合測試。") # <--- 如果沒有金鑰則跳過
    session = requests_cache.CachedSession('test_cache', backend='sqlite', expire_after=300)
    # FredClient 現在接受 api_key 參數，並且我們已修改其 __init__
    return FredClient(api_key=FRED_API_KEY, session=session)

# 清理快取
@pytest.fixture(autouse=True)
def cleanup_cache(real_fred_client):
    # 如果 real_fred_client 被跳過，它不會被執行，所以這裡需要一個保護
    if hasattr(real_fred_client, 'session') and real_fred_client.session:
        real_fred_client.session.cache.clear()
    else:
        # 如果 real_fred_client fixture 被跳過，那麼 real_fred_client 可能是一個 SkipMarker 或類似物件
        # 在這種情況下，我們不需要清除快取，因為 client 都沒有被創建。
        pass


@pytest.mark.skipif(not FRED_API_KEY, reason="FRED_API_KEY_TEST_ONLY is not set") # <--- 在測試函數層級也加入跳過條件
def test_data_engine_caching(real_fred_client, mocker): # mocker 是 pytest-mock 的 fixture
    """
    【演習場測試】
    驗證快取機制是否能避免重複的 API 呼叫。
    """
    # 1. 準備 (Arrange)
    # 監控 fredapi.Fred 類的 get_series 方法
    spy = mocker.spy(fredapi.Fred, 'get_series')

    # 創建一個假的 yfinance 客戶端，因為我們只想測試 FRED 的快取
    mock_yf = MagicMock()
    mock_yf.get_history.return_value = pd.DataFrame({'Close': [100]})
    mock_taifex = MagicMock()

    engine = DataEngine(yf_client=mock_yf, fred_client=real_fred_client, taifex_client=mock_taifex)

    # 2. 第一次打擊 (Act 1): 應觸發 API 呼叫
    print("\n第一次呼叫 (應觸發 API)...")
    snapshot1 = engine.generate_snapshot("SPY", "2025-07-12")
    assert spy.call_count == 1 # 確認 API 被呼叫了一次

    # 3. 第二次打擊 (Act 2): 應使用快取，不觸發 API 呼叫
    print("第二次呼叫 (應使用快取)...")
    snapshot2 = engine.generate_snapshot("SPY", "2025-07-12")

    # 4. 斷言 (Assert)
    # 驗證 _perform_request 方法沒有被再次呼叫
    assert spy.call_count == 1, "快取未生效，API 被重複呼叫！"

    # 驗證兩次結果相同
    assert snapshot1['macro_section']['VIX'] == snapshot2['macro_section']['VIX']
    print("快取驗證成功！")
