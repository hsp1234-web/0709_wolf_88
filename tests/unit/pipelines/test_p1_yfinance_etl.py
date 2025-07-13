import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# 由於 tasks.py 已經被修改，我們需要從新的位置導入
from pipelines import p1_yfinance_etl

@pytest.fixture
def mock_db_manager():
    """提供一個模擬的 DBManager"""
    with patch('pipelines.p1_yfinance_etl.DBManager') as mock:
        instance = mock.return_value
        instance.write_dataframe = MagicMock()
        yield instance

@pytest.fixture
def mock_yfinance_download():
    """提供一個模擬的 yf.download"""
    with patch('pipelines.p1_yfinance_etl.yf.download') as mock_download:
        mock_data = {
            ('SPY', 'Open'): [100], ('SPY', 'Close'): [101],
            ('SPY', 'High'): [102], ('SPY', 'Low'): [99],
            ('SPY', 'Volume'): [1000]
        }
        mock_df = pd.DataFrame(mock_data, index=[pd.to_datetime("2025-01-01")])
        mock_download.return_value = mock_df
        yield mock_download

def test_run_pipeline_success(mock_db_manager, mock_yfinance_download):
    """
    測試 run_pipeline 在成功情境下的行為。
    """
    p1_yfinance_etl.run_pipeline(tickers=["SPY"])

    mock_yfinance_download.assert_called_once_with(
        ["SPY"], period="5y", group_by='ticker', auto_adjust=True
    )

    mock_db_manager.write_dataframe.assert_called_once()

    called_df = mock_db_manager.write_dataframe.call_args[0][0]
    assert isinstance(called_df, pd.DataFrame)
    assert not called_df.empty
    assert 'ticker' in called_df.columns
    assert called_df['ticker'].iloc[0] == 'SPY'
    assert list(called_df.columns) == ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']
