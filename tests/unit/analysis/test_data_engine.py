import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from prometheus.core.analysis.data_engine import DataEngine


@pytest.fixture
def mock_clients():
    """提供一組模擬的數據客戶端。"""
    mock_yf = MagicMock()
    mock_yf.get_history = MagicMock()
    mock_fred = MagicMock()
    mock_taifex = MagicMock()
    return mock_yf, mock_fred, mock_taifex


def create_mock_history_df(data, index_name="Date"):
    """輔助函數：創建一個模擬的歷史數據 DataFrame。"""
    df = pd.DataFrame(data)
    df[index_name] = pd.to_datetime(df[index_name])
    df.set_index(index_name, inplace=True)
    return df


@patch("src.prometheus.core.clients.client_factory.ClientFactory.get_client")
def test_data_engine_logic(mock_get_client, mock_clients):
    """
    【實驗室測試】
    驗證 DataEngine 的核心計算邏輯。
    """
    import asyncio
    from unittest.mock import AsyncMock
    mock_yf, mock_fred, mock_taifex = mock_clients
    mock_get_client.side_effect = [mock_yf, mock_fred, mock_taifex]
    # 1. 準備 (Arrange): 建立一個模擬的 DuckDB 連線
    mock_db_conn = MagicMock()
    # 模擬快取未命中
    mock_db_conn.execute.return_value.fetch_df.return_value = pd.DataFrame()

    # 使用模擬客戶端和模擬 DB 連線初始化數據引擎
    engine = DataEngine(db_connection=mock_db_conn)
    engine.yf_client.fetch_data = AsyncMock(return_value=pd.DataFrame({'close': [1.0]}))

    # 2. 執行 (Act): 生成快照
    dt = datetime(2025, 7, 12)
    snapshot = engine.generate_snapshot(dt)

    # 3. 斷言 (Assert):
    # 斷言快取查詢被調用
    mock_db_conn.execute.assert_any_call(
        "SELECT * FROM hourly_time_series WHERE timestamp = ?", [dt]
    )
    # 斷言快取寫入被調用
    mock_db_conn.append.assert_called_once()
    # 斷言返回的快照是一個 DataFrame
    assert isinstance(snapshot, pd.DataFrame)
    assert not snapshot.empty
    assert snapshot["timestamp"].iloc[0] == dt


def test_calculate_approx_credit_spread_with_mock_data():
    """測試 _calculate_approx_credit_spread 方法的邏輯。"""
    import asyncio
    from unittest.mock import AsyncMock
    engine = DataEngine(db_connection=MagicMock())

    with patch.object(engine, 'yf_client', new_callable=MagicMock) as mock_yf_client:
        mock_yf_client.fetch_data = AsyncMock(side_effect=[
            create_mock_history_df({"Date": ["2025-07-11"], "close": [75.0]}),  # HYG
            create_mock_history_df({"Date": ["2025-07-11"], "close": [100.0]}),  # IEF
        ])

        credit_spread = engine._calculate_approx_credit_spread()
        assert credit_spread == 0.7500


@patch("src.prometheus.core.clients.client_factory.ClientFactory.get_client")
def test_calculate_proxy_move_with_mock_data(mock_get_client, mock_clients):
    """測試 _calculate_proxy_move 方法的邏輯。"""
    import asyncio
    from unittest.mock import AsyncMock
    mock_yf, mock_fred, mock_taifex = mock_clients
    mock_get_client.side_effect = [mock_yf, mock_fred, mock_taifex]
    engine = DataEngine(db_connection=MagicMock())

    # 創建足夠的數據來計算 20 天滾動標準差
    dates = pd.to_datetime(pd.date_range(start="2025-06-01", periods=60, freq="D"))
    closes = list(range(60))
    mock_tlt_data = create_mock_history_df({"Date": dates, "close": closes})
    mock_yf.fetch_data = AsyncMock(return_value=mock_tlt_data)

    proxy_move = engine._calculate_proxy_move()
    assert isinstance(proxy_move, float)


def test_calculate_gold_copper_ratio_with_mock_data():
    """測試 _calculate_gold_copper_ratio 方法的邏輯。"""
    import asyncio
    from unittest.mock import AsyncMock
    engine = DataEngine(db_connection=MagicMock())

    with patch.object(engine, 'yf_client', new_callable=MagicMock) as mock_yf_client:
        mock_yf_client.fetch_data = AsyncMock(side_effect=[
            create_mock_history_df({"Date": ["2025-07-11"], "close": [200.0]}),  # GLD
            create_mock_history_df({"Date": ["2025-07-11"], "close": [4.0]}),  # HG=F
        ])

        gold_copper_ratio = engine._calculate_gold_copper_ratio()
        assert gold_copper_ratio == 50.0


if __name__ == "__main__":
    pytest.main()
