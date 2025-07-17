# tests/unit/core/clients/test_yfinance.py
# 針對 core.clients.yfinance 模組的單元測試。

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# from datetime import datetime # 可能不需要了
import requests  # 導入 requests 以修復 NameError
from pandas.testing import assert_frame_equal

# 更新導入以反映重構後的客戶端
from prometheus.core.clients.yfinance import YFinanceClient


@pytest.fixture
def yfinance_client_fixture():
    """提供一個 YFinanceClient 實例。"""
    client = YFinanceClient()
    return client


@pytest.fixture
def mock_yfinance_ticker():
    """
    提供 yfinance.Ticker 的 mock 建構函式和 mock 實例。
    """
    with patch("yfinance.Ticker") as mock_ticker_constructor:
        mock_ticker_instance = MagicMock()
        mock_ticker_constructor.return_value = mock_ticker_instance
        yield mock_ticker_constructor, mock_ticker_instance


def create_sample_stock_data_for_test(
    start_date_str: str, end_date_str: str, has_volume: bool = True, tz_info=None
) -> pd.DataFrame:
    """
    輔助函數，創建符合 yfinance.history() 輸出格式的假數據 DataFrame。
    """
    dates = pd.to_datetime(
        pd.date_range(start=start_date_str, end=end_date_str, freq="B")
    )
    if dates.empty:
        return pd.DataFrame()

    data = {
        "Open": [100 + i for i in range(len(dates))],
        "High": [105 + i for i in range(len(dates))],
        "Low": [95 + i for i in range(len(dates))],
        "Close": [102 + i for i in range(len(dates))],
        # yfinance.history(auto_adjust=False) 會包含 'Adj Close'
        "Adj Close": [101 + i for i in range(len(dates))],
    }
    if has_volume:
        data["Volume"] = [1000000 + i * 10000 for i in range(len(dates))]

    df = pd.DataFrame(data, index=dates)
    df.index.name = "Date"
    if tz_info:
        df = df.tz_localize(tz_info)
    return df


class TestYFinanceClientInitialization:
    """測試 YFinanceClient 的初始化。"""

    def test_init_success(self, yfinance_client_fixture: YFinanceClient):
        assert yfinance_client_fixture.api_key is None
        assert yfinance_client_fixture.base_url is None
        assert isinstance(
            yfinance_client_fixture._session, requests.Session
        )  # From BaseAPIClient


class TestYFinanceClientFetchData:
    """測試 YFinanceClient.fetch_data 方法。"""

    @pytest.mark.asyncio
    async def test_fetch_single_symbol_success(
        self, yfinance_client_fixture: YFinanceClient, mock_yfinance_ticker
    ):
        mock_ticker_constructor, mock_ticker_instance = mock_yfinance_ticker
        symbol = "AAPL"
        start_date = "2023-01-02"  # Monday
        end_date = "2023-01-03"  # Tuesday

        mock_df_from_yf = create_sample_stock_data_for_test(start_date, end_date)
        mock_ticker_instance.history.return_value = mock_df_from_yf.copy()

        result_df = await yfinance_client_fixture.fetch_data(
            symbol=symbol, start_date=start_date, end_date=end_date
        )

        mock_ticker_constructor.assert_called_once_with(symbol)
        mock_ticker_instance.history.assert_called_once_with(
            start=start_date,
            end=end_date,
            auto_adjust=False,
            # progress=False, # 根據客戶端代碼，此參數不應被傳遞
            interval="1d",
            actions=False,
        )

        expected_df = mock_df_from_yf.reset_index()
        expected_df["symbol"] = symbol
        expected_df.rename(columns={"Date": "date", "Adj Close": "Adj_Close"}, inplace=True)
        expected_df["date"] = pd.to_datetime(expected_df["date"])

        expected_cols = [
            "date",
            "symbol",
            "Open",
            "High",
            "Low",
            "Close",
            "Adj_Close",
            "Volume",
        ]
        expected_df = expected_df[expected_cols]

        assert_frame_equal(result_df, expected_df, check_dtype=True)

    @pytest.mark.asyncio
    async def test_fetch_data_with_period_instead_of_dates(
        self, yfinance_client_fixture: YFinanceClient, mock_yfinance_ticker
    ):
        mock_ticker_constructor, mock_ticker_instance = mock_yfinance_ticker
        symbol = "MSFT"
        period = "5d"
        # 當使用 period 時，yfinance 會自動計算 start/end，所以我們的 mock 數據日期不那麼重要
        mock_df_from_yf = create_sample_stock_data_for_test(
            "2023-01-02", "2023-01-06"
        )  # 5 business days
        mock_ticker_instance.history.return_value = mock_df_from_yf.copy()

        result_df = await yfinance_client_fixture.fetch_data(symbol=symbol, period=period)

        mock_ticker_instance.history.assert_called_once_with(
            period=period,
            auto_adjust=False,
            # progress=False, # 根據客戶端代碼，此參數不應被傳遞
            interval="1d",
            actions=False,
            # start 和 end 不應在 history_params 中
        )
        # 後續的 DataFrame 轉換和斷言邏輯與上面的測試類似
        assert not result_df.empty
        assert result_df["symbol"].iloc[0] == symbol

    @pytest.mark.asyncio
    async def test_fetch_data_no_data_returned_by_yfinance(
        self, yfinance_client_fixture: YFinanceClient, mock_yfinance_ticker
    ):
        _, mock_ticker_instance = mock_yfinance_ticker
        mock_ticker_instance.history.return_value = (
            pd.DataFrame()
        )  # yf.Ticker().history() 返回空 DataFrame

        result_df = await yfinance_client_fixture.fetch_data(
            symbol="EMPTY", start_date="2023-01-01", end_date="2023-01-01"
        )
        assert result_df.empty

    @pytest.mark.asyncio
    async def test_fetch_data_yfinance_raises_exception(
        self, yfinance_client_fixture: YFinanceClient, mock_yfinance_ticker
    ):
        _, mock_ticker_instance = mock_yfinance_ticker
        mock_ticker_instance.history.side_effect = Exception("Simulated yfinance error")

        result_df = await yfinance_client_fixture.fetch_data(
            symbol="ERROR", start_date="2023-01-01", end_date="2023-01-01"
        )
        assert result_df.empty  # 錯誤應被捕獲並返回空 DataFrame

    @pytest.mark.asyncio
    async def test_fetch_data_missing_dates_or_period_raises_value_error(
        self, yfinance_client_fixture: YFinanceClient
    ):
        with pytest.raises(
            ValueError,
            match="必須提供 'period' 或 'start_date' 與 'end_date' 其中之一。",
        ):
            await yfinance_client_fixture.fetch_data(symbol="AAPL")  # 缺少所有日期/期間參數

        with pytest.raises(
            ValueError,
            match="必須提供 'period' 或 'start_date' 與 'end_date' 其中之一。",
        ):
            await yfinance_client_fixture.fetch_data(
                symbol="AAPL", start_date="2023-01-01"
            )  # 缺少 end_date

    @pytest.mark.asyncio
    async def test_fetch_data_handles_datetime_column(
        self, yfinance_client_fixture: YFinanceClient, mock_yfinance_ticker
    ):
        """測試當 yfinance 返回 'Datetime' 而不是 'Date' 時 (通常是 intraday)。"""
        _, mock_ticker_instance = mock_yfinance_ticker
        symbol = "SPY"
        # 創建一個帶 'Datetime' 索引的 mock DataFrame
        dates = pd.to_datetime(
            pd.date_range(start="2023-01-02 09:30:00", periods=2, freq="1min")
        )
        mock_data = pd.DataFrame({"Open": [100, 101]}, index=dates)
        mock_data.index.name = "Datetime"  # yfinance 對 intraday 可能用 'Datetime'
        mock_ticker_instance.history.return_value = mock_data.copy()

        result_df = await yfinance_client_fixture.fetch_data(
            symbol=symbol, period="1d", interval="1m"
        )

        assert "date" in result_df.columns
        assert "Datetime" not in result_df.columns
        assert result_df["date"].iloc[0] == pd.Timestamp("2023-01-02 09:30:00")

    @pytest.mark.asyncio
    async def test_fetch_data_timezone_handling(
        self, yfinance_client_fixture: YFinanceClient, mock_yfinance_ticker
    ):
        _, mock_ticker_instance = mock_yfinance_ticker
        symbol = "MSFT"
        # 創建帶時區的數據
        mock_df_tz = create_sample_stock_data_for_test(
            "2023-01-02", "2023-01-02", tz_info="US/Eastern"
        )
        mock_ticker_instance.history.return_value = mock_df_tz.copy()

        result_df = await yfinance_client_fixture.fetch_data(
            symbol=symbol, start_date="2023-01-02", end_date="2023-01-02"
        )

        assert result_df["date"].dt.tz is None  # 確保時區被移除
        # 驗證 tz_localize(None) 的效果，它會保留 "絕對" 時間點，然後移除時區標記
        # '2023-01-02 00:00:00-05:00' (EST) -> '2023-01-02 05:00:00' (naive UTC)
        assert result_df["date"].iloc[0] == pd.Timestamp("2023-01-02 05:00:00")


class TestYFinanceClientFetchMultipleSymbolsData:
    """測試 YFinanceClient.fetch_multiple_symbols_data 方法。"""

    @pytest.mark.asyncio
    @patch.object(YFinanceClient, "fetch_data")  # Mock YFinanceClient.fetch_data
    async def test_fetch_multiple_success(
        self, mock_single_fetch, yfinance_client_fixture: YFinanceClient
    ):
        symbols = ["AAPL", "MSFT"]
        df_aapl = pd.DataFrame({"symbol": ["AAPL"], "Close": [150]})
        df_msft = pd.DataFrame({"symbol": ["MSFT"], "Close": [300]})

        async def side_effect_for_fetch(symbol, **kwargs):
            if symbol == "AAPL":
                return df_aapl
            if symbol == "MSFT":
                return df_msft
            return pd.DataFrame()

        mock_single_fetch.side_effect = side_effect_for_fetch

        result_df = await yfinance_client_fixture.fetch_multiple_symbols_data(
            symbols=symbols, start_date="2023-01-01", end_date="2023-01-01"
        )

        expected_df = pd.concat([df_aapl, df_msft], ignore_index=True)
        assert_frame_equal(result_df, expected_df)
        assert mock_single_fetch.call_count == 2
        mock_single_fetch.assert_any_call(
            symbol="AAPL", start_date="2023-01-01", end_date="2023-01-01"
        )
        mock_single_fetch.assert_any_call(
            symbol="MSFT", start_date="2023-01-01", end_date="2023-01-01"
        )

    @pytest.mark.asyncio
    @patch.object(YFinanceClient, "fetch_data")
    async def test_fetch_multiple_one_symbol_fails(
        self, mock_single_fetch, yfinance_client_fixture: YFinanceClient
    ):
        symbols = ["GOOG", "FAIL", "AMZN"]
        df_goog = pd.DataFrame({"symbol": ["GOOG"], "Close": [2000]})
        df_amzn = pd.DataFrame({"symbol": ["AMZN"], "Close": [100]})

        async def side_effect_for_fetch(symbol, **kwargs):
            if symbol == "GOOG":
                return df_goog
            if symbol == "FAIL":
                raise Exception(
                    "Simulated error for FAIL symbol"
                )  # fetch_data 內部會捕獲並返回空 DF
            if symbol == "AMZN":
                return df_amzn
            return pd.DataFrame()

        # 調整：由於 fetch_data 內部捕獲異常並返回空 DF，這裡 side_effect 應返回空 DF 代表失敗
        async def side_effect_for_fetch_adjusted(symbol, **kwargs):
            if symbol == "GOOG":
                return df_goog
            if symbol == "FAIL":
                return pd.DataFrame()  # fetch_data 內部捕獲異常並返回空 DF
            if symbol == "AMZN":
                return df_amzn
            return pd.DataFrame()

        mock_single_fetch.side_effect = side_effect_for_fetch_adjusted

        result_df = await yfinance_client_fixture.fetch_multiple_symbols_data(
            symbols=symbols, period="1d"
        )

        expected_df = pd.concat([df_goog, df_amzn], ignore_index=True)
        assert_frame_equal(result_df, expected_df)
        assert mock_single_fetch.call_count == 3  # 每個都會嘗試

    @pytest.mark.asyncio
    async def test_fetch_multiple_empty_symbol_list(
        self, yfinance_client_fixture: YFinanceClient
    ):
        result_df = await yfinance_client_fixture.fetch_multiple_symbols_data(symbols=[])
        assert result_df.empty

    @pytest.mark.asyncio
    async def test_fetch_multiple_invalid_symbols_type(
        self, yfinance_client_fixture: YFinanceClient
    ):
        result_df = await yfinance_client_fixture.fetch_multiple_symbols_data(
            symbols="NOTALIST"
        )  # type: ignore
        assert result_df.empty


# pytest tests/unit/core/clients/test_yfinance.py -v
