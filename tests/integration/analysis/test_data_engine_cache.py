# 檔案路徑: tests/integration/analysis/test_data_engine_cache.py
import os  # 導入 os 模組
from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest
import requests_cache

from prometheus.core.analysis.data_engine import DataEngine
from prometheus.core.clients.fred import FredClient

# 獲取 API 金鑰
FRED_API_KEY = os.environ.get(
    "FRED_API_KEY_TEST_ONLY"
)  # 使用不同的環境變數名稱以示區隔


@pytest.fixture(scope="module")
def real_fred_client():
    """創建一個使用暫存快取的真實客戶端實例。"""
    if not FRED_API_KEY:
        pytest.skip(
            "FRED_API_KEY_TEST_ONLY 環境變數未設定，跳過此整合測試。"
        )  # <--- 如果沒有金鑰則跳過
    session = requests_cache.CachedSession(
        "test_cache", backend="sqlite", expire_after=300
    )
    # FredClient 現在接受 api_key 參數，並且我們已修改其 __init__
    return FredClient(api_key=FRED_API_KEY, session=session)


# 清理快取
@pytest.fixture(autouse=True)
def cleanup_cache(real_fred_client):
    # 如果 real_fred_client 被跳過，它不會被執行，所以這裡需要一個保護
    if hasattr(real_fred_client, "session") and real_fred_client.session:
        real_fred_client.session.cache.clear()
    else:
        # 如果 real_fred_client fixture 被跳過，那麼 real_fred_client 可能是一個 SkipMarker 或類似物件
        # 在這種情況下，我們不需要清除快取，因為 client 都沒有被創建。
        pass


@pytest.fixture
def temp_db_data_engine():
    """一個使用內存 DuckDB 的 DataEngine 實ли，確保測試隔離。"""
    import duckdb

    from prometheus.core.clients.fred import FredClient
    from prometheus.core.clients.taifex_db import TaifexDBClient
    from prometheus.core.clients.yfinance import YFinanceClient

    yf_client = YFinanceClient()
    fred_client = FredClient(api_key="fake_key")
    taifex_client = TaifexDBClient()

    engine = DataEngine(
        yf_client=yf_client, fred_client=fred_client, taifex_client=taifex_client
    )
    engine.db_con = duckdb.connect(database=":memory:")
    engine.db_con.execute(CREATE_HOURLY_TABLE_SQL)

    yield engine

    engine.close()


@patch("prometheus.core.analysis.data_engine.DataEngine._calculate_technicals")
@patch(
    "prometheus.core.analysis.data_engine.DataEngine._calculate_approx_credit_spread"
)
@patch("prometheus.core.analysis.data_engine.DataEngine._calculate_proxy_move")
@patch("prometheus.core.analysis.data_engine.DataEngine._calculate_gold_copper_ratio")
@patch("prometheus.core.clients.yfinance.YFinanceClient.fetch_data")  # Mock API 客戶端
def test_cache_miss_and_write(
    mock_fetch_data,
    mock_gold_copper_ratio,
    mock_proxy_move,
    mock_credit_spread,
    mock_technicals,
    temp_db_data_engine,
):
    """
    測試案例：當快取中沒有數據時，應觸發 API 呼叫，並將結果寫回資料庫。
    """
    # Arrange (安排)
    mock_fetch_data.return_value = pd.DataFrame({"Close": [500.0]})
    dt = datetime(2025, 7, 12)

    # Act (行動)
    result1 = temp_db_data_engine.generate_snapshot(dt)

    # Assert (斷言)
    assert not result1.empty

    db_result = temp_db_data_engine.db_con.execute(
        "SELECT * FROM hourly_time_series WHERE timestamp = ?", [dt]
    ).fetch_df()
    assert not db_result.empty
    assert db_result["spy_close"].iloc[0] == 500.0


@patch("core.clients.yfinance.YFinanceClient.fetch_data")  # Mock API 客戶端
def test_cache_hit(mock_fetch_data, temp_db_data_engine):
    """
    測試案例：當數據已存在於快取中，不應再次觸發 API 呼叫。
    """
    # Arrange (安排)
    mock_fetch_data.return_value = pd.DataFrame({"Close": [500.0]})
    dt = datetime(2025, 7, 12)

    # 第一次寫入
    with (
        patch("core.analysis.data_engine.DataEngine._calculate_technicals"),
        patch("core.analysis.data_engine.DataEngine._calculate_approx_credit_spread"),
        patch("core.analysis.data_engine.DataEngine._calculate_proxy_move"),
        patch("core.analysis.data_engine.DataEngine._calculate_gold_copper_ratio"),
    ):
        temp_db_data_engine.generate_snapshot(dt)

    mock_fetch_data.reset_mock()

    # Act (行動)
    result2 = temp_db_data_engine.generate_snapshot(dt)

    # Assert (斷言)
    assert mock_fetch_data.call_count == 0
    assert not result2.empty


CREATE_HOURLY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS hourly_time_series (
    "timestamp" TIMESTAMP PRIMARY KEY,
    spy_open DOUBLE, spy_high DOUBLE, spy_low DOUBLE, spy_close DOUBLE, spy_volume BIGINT,
    qqq_close DOUBLE, tlt_close DOUBLE, btc_usd_close DOUBLE, nq_f_close DOUBLE,
    es_f_close DOUBLE, ym_f_close DOUBLE, cl_f_close DOUBLE, gc_f_close DOUBLE,
    si_f_close DOUBLE, zb_f_close DOUBLE, zn_f_close DOUBLE, zt_f_close DOUBLE,
    zf_f_close DOUBLE, gld_close DOUBLE, shy_close DOUBLE, iei_close DOUBLE,
    aapl_close DOUBLE, msft_close DOUBLE, nvda_close DOUBLE, goog_close DOUBLE,
    tsm_close DOUBLE, "601318_ss_close" DOUBLE, "688981_ss_close" DOUBLE, "0981_hk_close" DOUBLE,
    spy_rsi_14_1h DOUBLE, spy_macd_signal_1h DOUBLE, spy_bbands_width_pct_1h DOUBLE,
    spy_vwap_1h DOUBLE, spy_atr_14_1h DOUBLE, spy_vwap_deviation_pct_1h DOUBLE,
    spy_momentum_1h_100 DOUBLE, spy_bollinger_band_upper_1h DOUBLE,
    spy_bollinger_band_lower_1h DOUBLE, spy_bb_middle_band_20h DOUBLE,
    spy_bb_upper_band_20h DOUBLE, spy_bb_lower_band_20h DOUBLE,
    spy_bb_band_width_pct_20h DOUBLE, spy_bb_percent_b_20h DOUBLE, spy_gex_total DOUBLE,
    spy_gex_flip_level DOUBLE, spy_max_pain DOUBLE, spy_call_wall_strike DOUBLE,
    spy_put_wall_strike DOUBLE, spy_pc_ratio_volume DOUBLE, spy_pc_ratio_oi DOUBLE,
    spy_iv_atm_1m DOUBLE, spy_skew_quantified DOUBLE, spy_vanna_exposure DOUBLE,
    spy_charm_exposure DOUBLE, vvix_close DOUBLE
);
"""
