import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from pipelines.p2_fred_etl import run

@pytest.fixture
def mock_db_manager():
    """Fixture to mock DBManager."""
    with patch('pipelines.p2_fred_etl.DBManager') as mock:
        instance = mock.return_value
        instance.write_data = MagicMock()
        yield instance

@pytest.fixture
def mock_fred_api():
    """Fixture to mock Fred API."""
    with patch('pipelines.p2_fred_etl.Fred') as mock:
        instance = mock.return_value

        # 模擬 API 返回的數據
        gdp_data = pd.Series([28000.0, 28500.0], index=pd.to_datetime(['2023-01-01', '2023-04-01']), name='GDP')
        unrate_data = pd.Series([3.5, 3.6], index=pd.to_datetime(['2023-01-01', '2023-02-01']), name='UNRATE')

        def get_series_side_effect(series_id):
            if series_id == 'GDP':
                return gdp_data
            if series_id == 'UNRATE':
                return unrate_data
            return pd.Series() # Return empty series for others

        instance.get_series = MagicMock(side_effect=get_series_side_effect)
        yield instance

def test_run_fred_etl_success(mock_db_manager, mock_fred_api):
    """
    測試 run 函數成功執行的情況。
    """
    with patch('pipelines.p2_fred_etl.get_api_key', return_value='test_key'):
        run()

    # 驗證是否正確調用 DBManager 的 write_data
    assert mock_db_manager.write_data.call_count == 1

    # 驗證寫入數據庫的 DataFrame 內容
    call_args, _ = mock_db_manager.write_data.call_args
    table_name, df = call_args

    assert table_name == 'macro_daily_fred'
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert 'series' in df.columns
    # 4 rows = 2 for GDP + 2 for UNRATE
    assert len(df) == 4

def test_run_fred_etl_no_api_key():
    """
    測試未配置 API 金鑰時是否會引發 ValueError。
    """
    with patch('pipelines.p2_fred_etl.get_api_key', return_value=None):
        with pytest.raises(ValueError, match="FRED API key not found in config.yml"):
            run()

def test_run_fred_etl_api_failure(mock_db_manager, mock_fred_api):
    """
    測試當 API 調用失敗時，不會寫入數據。
    """
    # 模擬 API 異常
    mock_fred_api.get_series.side_effect = Exception("API Error")

    with patch('pipelines.p2_fred_etl.get_api_key', return_value='test_key'):
        run()

    # 驗證 write_data 未被調用
    mock_db_manager.write_data.assert_not_called()
