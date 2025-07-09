# tests/unit/core/clients/test_yfinance.py
# 針對 core.clients.yfinance 模組的單元測試。

import pytest
import pandas as pd
from pandas.testing import assert_frame_equal
from unittest.mock import patch, MagicMock
from datetime import datetime

# 待測試的模組應在測試執行環境的 PYTHONPATH 中
# 假設專案結構允許直接導入
from core.clients import yfinance

@pytest.fixture
def mock_yfinance_ticker():
    """
    提供一個 yfinance.Ticker 的 mock 物件。
    這個 fixture 將模擬 Ticker(...).history(...) 的行為。
    """
    with patch('yfinance.Ticker') as mock_ticker_constructor:
        mock_ticker_instance = MagicMock()
        mock_ticker_constructor.return_value = mock_ticker_instance
        yield mock_ticker_instance # 返回 mock Ticker instance 給測試函數使用

def create_sample_stock_data(symbol: str, start_date_str: str, end_date_str: str) -> pd.DataFrame:
    """
    輔助函數，用於創建符合 yfinance.history() 輸出格式的假數據 DataFrame。
    """
    dates = pd.to_datetime(pd.date_range(start=start_date_str, end=end_date_str, freq='B')) # Business days
    if dates.empty:
        return pd.DataFrame()

    data = {
        'Open': [100 + i for i in range(len(dates))],
        'High': [105 + i for i in range(len(dates))],
        'Low': [95 + i for i in range(len(dates))],
        'Close': [102 + i for i in range(len(dates))],
        'Adj Close': [101 + i for i in range(len(dates))], # yfinance 使用 'Adj Close'
        'Volume': [1000000 + i*10000 for i in range(len(dates))]
    }
    df = pd.DataFrame(data, index=dates)
    df.index.name = 'Date' # yfinance 的 history() 返回的 DataFrame 索引是 'Date'
    return df

class TestFetchDailyOhlcv:
    """
    測試 fetch_daily_ohlcv 函數的各種情境。
    """

    def test_fetch_single_symbol_success(self, mock_yfinance_ticker):
        """測試成功抓取單一商品代碼的數據。"""
        symbol = 'AAPL'
        start_date = '2023-01-01'
        end_date = '2023-01-05'

        # 設定 mock Ticker(...).history(...) 的返回值
        mock_df = create_sample_stock_data(symbol, start_date, end_date)
        mock_yfinance_ticker.history.return_value = mock_df.copy() # 確保返回副本

        result_df = yfinance.fetch_daily_ohlcv([symbol], start_date, end_date)

        # 驗證 yf.Ticker 是否以正確的 symbol 被調用
        mock_yfinance_ticker_constructor = yfinance.Ticker # 這是在 patch 裝飾器中傳入的 mock
        mock_yfinance_ticker_constructor.assert_called_once_with(symbol)

        # 驗證 history 方法是否以正確的參數被調用
        mock_yfinance_ticker.history.assert_called_once_with(start=start_date, end=end_date, auto_adjust=False)

        # 準備預期結果 DataFrame
        expected_df = mock_df.reset_index()
        expected_df['symbol'] = symbol
        expected_df.rename(columns={'Adj Close': 'Adj_Close'}, inplace=True)
        # 確保 Date 欄位是 datetime64[ns] 型別 (create_sample_stock_data 已處理 index，reset_index 後保持)
        expected_df['Date'] = pd.to_datetime(expected_df['Date'])

        # 欄位順序
        expected_cols = ['Date', 'symbol', 'Open', 'High', 'Low', 'Close', 'Adj_Close', 'Volume']
        expected_df = expected_df[expected_cols]

        assert_frame_equal(result_df, expected_df, check_dtype=True)

    def test_fetch_multiple_symbols_success(self, mock_yfinance_ticker):
        """測試成功抓取多個商品代碼的數據。"""
        symbols = ['AAPL', 'MSFT']
        start_date = '2023-01-01'
        end_date = '2023-01-03'

        # 為每個 symbol 準備 mock 數據
        mock_data_aapl = create_sample_stock_data('AAPL', start_date, end_date)
        mock_data_msft = create_sample_stock_data('MSFT', start_date, end_date)

        # 設定 mock Ticker(...).history(...) 針對不同 symbol 的返回值
        # yf.Ticker(symbol).history(...)
        # 第一次調用 Ticker('AAPL').history(...)
        # 第二次調用 Ticker('MSFT').history(...)
        mock_yfinance_ticker.history.side_effect = [mock_data_aapl.copy(), mock_data_msft.copy()]

        result_df = yfinance.fetch_daily_ohlcv(symbols, start_date, end_date)

        # 驗證 Ticker 的調用次數和參數
        mock_yfinance_ticker_constructor = yfinance.Ticker
        assert mock_yfinance_ticker_constructor.call_count == len(symbols)
        mock_yfinance_ticker_constructor.assert_any_call('AAPL')
        mock_yfinance_ticker_constructor.assert_any_call('MSFT')

        # 驗證 history 的調用次數
        assert mock_yfinance_ticker.history.call_count == len(symbols)
        mock_yfinance_ticker.history.assert_any_call(start=start_date, end=end_date, auto_adjust=False)

        # 準備預期結果 DataFrame
        expected_aapl = mock_data_aapl.reset_index()
        expected_aapl['symbol'] = 'AAPL'
        expected_msft = mock_data_msft.reset_index()
        expected_msft['symbol'] = 'MSFT'

        expected_df = pd.concat([expected_aapl, expected_msft], ignore_index=True)
        expected_df.rename(columns={'Adj Close': 'Adj_Close'}, inplace=True)
        expected_df['Date'] = pd.to_datetime(expected_df['Date'])

        expected_cols = ['Date', 'symbol', 'Open', 'High', 'Low', 'Close', 'Adj_Close', 'Volume']
        expected_df = expected_df[expected_cols]

        # 比較時可能需要排序，因為 concat 的順序可能不保證
        result_df = result_df.sort_values(by=['symbol', 'Date']).reset_index(drop=True)
        expected_df = expected_df.sort_values(by=['symbol', 'Date']).reset_index(drop=True)

        assert_frame_equal(result_df, expected_df, check_dtype=True)

    def test_fetch_no_data_for_symbol(self, mock_yfinance_ticker):
        """測試當某個商品代碼無數據時的情況。"""
        symbols = ['VALID', 'EMPTY']
        start_date = '2023-01-01'
        end_date = '2023-01-02'

        mock_data_valid = create_sample_stock_data('VALID', start_date, end_date)
        mock_data_empty = pd.DataFrame() # EMPTY 代碼返回空 DataFrame

        mock_yfinance_ticker.history.side_effect = [mock_data_valid.copy(), mock_data_empty.copy()]

        result_df = yfinance.fetch_daily_ohlcv(symbols, start_date, end_date)

        # 預期只包含 VALID 的數據
        expected_valid = mock_data_valid.reset_index()
        expected_valid['symbol'] = 'VALID'
        expected_valid.rename(columns={'Adj Close': 'Adj_Close'}, inplace=True)
        expected_valid['Date'] = pd.to_datetime(expected_valid['Date'])

        expected_cols = ['Date', 'symbol', 'Open', 'High', 'Low', 'Close', 'Adj_Close', 'Volume']
        expected_df = expected_valid[expected_cols]

        assert_frame_equal(result_df, expected_df, check_dtype=True)

    def test_fetch_all_symbols_no_data(self, mock_yfinance_ticker):
        """測試所有商品代碼均無數據時返回空 DataFrame。"""
        symbols = ['EMPTY1', 'EMPTY2']
        start_date = '2023-01-01'
        end_date = '2023-01-02'

        mock_yfinance_ticker.history.return_value = pd.DataFrame() # 所有調用都返回空

        result_df = yfinance.fetch_daily_ohlcv(symbols, start_date, end_date)

        assert result_df.empty
        assert mock_yfinance_ticker.history.call_count == len(symbols)

    def test_fetch_yfinance_api_error(self, mock_yfinance_ticker):
        """測試 yfinance API 調用引發異常時返回空 DataFrame。"""
        symbols = ['AAPL']
        start_date = '2023-01-01'
        end_date = '2023-01-02'

        mock_yfinance_ticker.history.side_effect = Exception("Simulated API Error")

        result_df = yfinance.fetch_daily_ohlcv(symbols, start_date, end_date)

        assert result_df.empty
        # 即使發生錯誤，也應該有嘗試調用
        mock_yfinance_ticker_constructor = yfinance.Ticker
        mock_yfinance_ticker_constructor.assert_called_once_with(symbols[0])
        mock_yfinance_ticker.history.assert_called_once()


    def test_fetch_empty_symbol_list(self):
        """測試傳入空的商品代碼列表時返回空 DataFrame。"""
        result_df = yfinance.fetch_daily_ohlcv([], '2023-01-01', '2023-01-02')
        assert result_df.empty

    def test_fetch_invalid_symbols_type(self):
        """測試傳入無效的 symbols 參數類型 (非列表) 時返回空 DataFrame。"""
        result_df = yfinance.fetch_daily_ohlcv("AAPL", '2023-01-01', '2023-01-02') # type: ignore
        assert result_df.empty

    def test_fetch_data_with_missing_volume(self, mock_yfinance_ticker):
        """測試抓取的數據可能缺少 'Volume' 欄位 (例如指數)。"""
        symbol = '^GSPC' # 指數通常沒有 Volume
        start_date = '2023-01-01'
        end_date = '2023-01-03'

        mock_data_no_volume = create_sample_stock_data(symbol, start_date, end_date)
        del mock_data_no_volume['Volume'] # 模擬沒有 Volume 的情況

        mock_yfinance_ticker.history.return_value = mock_data_no_volume.copy()

        result_df = yfinance.fetch_daily_ohlcv([symbol], start_date, end_date)

        expected_df = mock_data_no_volume.reset_index()
        expected_df['symbol'] = symbol
        expected_df.rename(columns={'Adj Close': 'Adj_Close'}, inplace=True)
        expected_df['Date'] = pd.to_datetime(expected_df['Date'])

        # 預期結果中不應包含 'Volume'
        expected_cols = ['Date', 'symbol', 'Open', 'High', 'Low', 'Close', 'Adj_Close']
        expected_df = expected_df[expected_cols]

        assert_frame_equal(result_df, expected_df, check_dtype=True)
        assert 'Volume' not in result_df.columns

    def test_date_column_timezone_conversion(self, mock_yfinance_ticker):
        """測試 Date 欄位時區被正確處理 (轉換為 UTC naive)。"""
        symbol = 'AAPL'
        start_date = '2023-01-01'
        end_date = '2023-01-01' # 單日測試

        # 創建一個帶有時區的 Date 索引的 DataFrame
        raw_date = pd.Timestamp('2023-01-01 00:00:00', tz='US/Eastern')
        mock_data_with_tz = pd.DataFrame({
            'Open': [100], 'High': [105], 'Low': [95], 'Close': [102], 'Adj Close': [101], 'Volume': [1000000]
        }, index=pd.DatetimeIndex([raw_date], name='Date'))

        mock_yfinance_ticker.history.return_value = mock_data_with_tz.copy()

        result_df = yfinance.fetch_daily_ohlcv([symbol], start_date, end_date)

        # 預期 Date 欄位是 datetime64[ns] 且沒有時區信息
        assert result_df['Date'].dtype == 'datetime64[ns]'
        assert result_df['Date'].dt.tz is None
        # 驗證日期是否正確轉換 (假設 yfinance 返回的日期部分是正確的)
        # 此處 mock_data_with_tz 的索引已經是轉換後的日期，所以 reset_index() 後的 Date 欄位值應該是 '2023-01-01'
        # tz_convert(None) 會移除時區，但保持時間戳的"絕對時間點" (如果原始時間是 00:00 EST，轉換後會是 05:00 UTC naive)
        # 但 yfinance 通常返回的是市場日期，不帶時間部分，或時間部分為00:00:00
        # 這裡的 create_sample_stock_data 和 yfinance 實際行為可能略有差異
        # 我們的 fetch_daily_ohlcv 邏輯是： if hist_data['Date'].dt.tz is not None: hist_data['Date'] = hist_data['Date'].dt.tz_convert(None)
        # 如果 yf 返回的 Date 是 '2023-01-01 00:00:00-05:00' (EST)，tz_convert(None) 會變成 '2023-01-01 05:00:00' (UTC naive)
        # 這可能不是我們想要的"日期"部分。但目前代碼就是這樣寫的。
        # 更好的做法可能是 hist_data['Date'] = hist_data['Date'].dt.normalize().dt.tz_localize(None)
        # 但我們現在是測試現有代碼。

        # 根據現有代碼，我們預期 '2023-01-01 00:00:00 US/Eastern' 轉換為 UTC naive 後，日期部分不應改變，時間部分會根據偏移量改變
        # 然而，yfinance 返回的通常是日期，時間部分為午夜。如果它返回的是 '2023-01-01' (日期對象)，則 reset_index 後變為 Timestamp('2023-01-01 00:00:00')
        # 如果它返回的是帶時區的 Timestamp('2023-01-01 00:00:00-0500')，則 .dt.tz_convert(None) 會變成 Timestamp('2023-01-01 05:00:00')
        # 由於我們的 create_sample_stock_data 使用的是 pd.date_range，它創建的是無時區的 Timestamp，
        # 所以這個特定測試主要驗證 mock 的歷史數據若帶有時區，會被移除。

        # 簡化驗證：只檢查時區被移除
        assert result_df['Date'].iloc[0] == pd.Timestamp('2023-01-01 05:00:00') # 00:00 EST -> 05:00 UTC

    def test_fetch_data_column_renaming_adj_close(self, mock_yfinance_ticker):
        """測試 'Adj Close' 欄位被正確重命名為 'Adj_Close'。"""
        symbol = 'TEST'
        start_date = '2023-01-01'
        end_date = '2023-01-01'

        # create_sample_stock_data 已經使用了 'Adj Close'
        mock_df = create_sample_stock_data(symbol, start_date, end_date)
        mock_yfinance_ticker.history.return_value = mock_df.copy()

        result_df = yfinance.fetch_daily_ohlcv([symbol], start_date, end_date)

        assert 'Adj_Close' in result_df.columns
        assert 'Adj Close' not in result_df.columns

        # 驗證數據是否正確
        expected_adj_close_value = mock_df['Adj Close'].iloc[0]
        assert result_df['Adj_Close'].iloc[0] == expected_adj_close_value
