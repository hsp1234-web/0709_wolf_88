import pytest
import pandas as pd
from prometheus.core.clients.fred import FredClient
from prometheus.core.config import config

# 檢查 config.yml 中是否存在 FRED_API_KEY
api_key = config.get("clients.fred.api_key")
skip_if_no_key = pytest.mark.skipif(not api_key, reason="FRED_API_KEY not found in config.yml")

@pytest.fixture
def fred_client():
    return FredClient()

def test_fetch_public_series(fred_client):
    """
    測試獲取一個公開的、無需金鑰的數據系列。
    """
    df = fred_client.fetch_data("GDP")
    assert not df.empty
    assert isinstance(df, pd.DataFrame)
    assert "GDP" in df.columns

@skip_if_no_key
def test_fetch_private_series(fred_client):
    """
    測試獲取一個需要金鑰的數據系列。
    """
    df = fred_client.fetch_data("T10Y2Y")
    assert not df.empty
    assert isinstance(df, pd.DataFrame)
    assert "T10Y2Y" in df.columns
