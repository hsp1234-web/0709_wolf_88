# 檔案路徑: tests/integration/test_data_engine_cache.py
import pytest
import requests_cache
from unittest.mock import patch, MagicMock # 增加了 MagicMock
import pandas as pd # 增加了 pandas

from core.clients.base import BaseAPIClient # 我們需要監控它的請求方法
from core.clients.fred import FredClient
from core.analysis.data_engine import DataEngine

# 為了簡化，這裡只測試 FredClient 的快取
# 在真實場景中，需要為每個客戶端都進行類似設置
@pytest.fixture(scope="module")
def real_fred_client():
    """創建一個使用暫存快取的真實客戶端實例。"""
    session = requests_cache.CachedSession('test_cache', backend='sqlite', expire_after=300)
    return FredClient(api_key="YOUR_FRED_API_KEY", session=session) # 注意：需要一個真實或假的API Key

# 清理快取
@pytest.fixture(autouse=True)
def cleanup_cache(real_fred_client):
    real_fred_client.session.cache.clear()

def test_data_engine_caching(real_fred_client, mocker): # mocker 是 pytest-mock 的 fixture
    """
    【演習場測試】
    驗證快取機制是否能避免重複的 API 呼叫。
    """
    # 1. 準備 (Arrange)
    # 監控 BaseAPIClient 的核心請求方法
    spy = mocker.spy(BaseAPIClient, '_perform_request')

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
