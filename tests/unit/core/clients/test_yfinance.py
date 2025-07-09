# tests/unit/core/clients/test_yfinance.py
# 針對 core.clients.yfinance 模組的單元測試。

import pytest
import pandas as pd
from pandas.testing import assert_frame_equal
from unittest.mock import patch, MagicMock
from datetime import datetime

# 待測試的模組應在測試執行環境的 PYTHONPATH 中
# 假設專案結構允許直接導入
from core.clients import yfinance # 這是我們自己的 yfinance.py 模組

@pytest.fixture
def mock_yfinance_ticker_class(): # 改名並修改行為
    """
    Mocks the yfinance.Ticker class from the actual yfinance library.
    Yields the mocked Ticker class itself.
    """
    # 我們要 patch 的是 'yfinance.Ticker'，即外部函式庫的路徑
    # core.clients.yfinance 內部會 import yfinance as yf 並使用 yf.Ticker
    with patch('yfinance.Ticker') as MockTickerClass:
        yield MockTickerClass

def create_sample_stock_data(symbol: str, start_date_str: str, end_date_str: str) -> pd.DataFrame:
    """
    輔助函數，用於創建符合 yfinance.history() 輸出格式的假數據 DataFrame。
    """
    # 使用 pd.bdate_range 確保只生成營業日，如果範圍有效
    dates = pd.bdate_range(start=start_date_str, end=end_date_str)
    if dates.empty:
        # 如果日期範圍確實不包含任何營業日 (例如 start > end，或 start=end 且為週末)
        # 為了讓單日測試（即使是週末）也能產生mock數據，如果 start_date == end_date，則強制使用該日期
        if start_date_str == end_date_str:
            dates = pd.DatetimeIndex([pd.to_datetime(start_date_str)])
        else: # 如果是多日範圍但沒有營業日 (例如週六到週日)，則返回空
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

    def test_fetch_single_symbol_success(self, mock_yfinance_ticker_class): # 使用修改後的 fixture
        """測試成功抓取單一商品代碼的數據。"""
        symbol = 'AAPL'
        start_date = '2023-01-02' # 改為營業日
        end_date = '2023-01-05' # 確保 create_sample_stock_data 會產生數據

        # 創建一個 mock Ticker 實例，並設定其 history 方法的返回值
        mock_ticker_instance = MagicMock()
        mock_df = create_sample_stock_data(symbol, start_date, end_date)
        mock_ticker_instance.history.return_value = mock_df.copy()

        # 讓 Ticker 類 (mock_yfinance_ticker_class) 在被調用時返回我們的 mock Ticker 實例
        mock_yfinance_ticker_class.return_value = mock_ticker_instance

        result_df = yfinance.fetch_daily_ohlcv([symbol], start_date, end_date) # yfinance 是 core.clients.yfinance

        # 驗證 yf.Ticker (即 mock_yfinance_ticker_class) 是否以正確的 symbol 被調用
        mock_yfinance_ticker_class.assert_called_once_with(symbol)

        # 驗證 mock Ticker 實例的 history 方法是否以正確的參數被調用
        mock_ticker_instance.history.assert_called_once_with(start=start_date, end=end_date, auto_adjust=False)

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

    def test_fetch_multiple_symbols_success(self, mock_yfinance_ticker_class): # 使用修改後的 fixture
        """測試成功抓取多個商品代碼的數據。"""
        symbols = ['AAPL', 'MSFT']
        start_date = '2023-01-02' # 改為營業日
        end_date = '2023-01-03'   # 確保 create_sample_stock_data 會產生數據

        # 為每個 symbol 準備 mock 數據
        mock_data_aapl = create_sample_stock_data('AAPL', start_date, end_date)
        mock_data_msft = create_sample_stock_data('MSFT', start_date, end_date)

        # 設定 mock Ticker(...).history(...) 針對不同 symbol 的返回值
        # yf.Ticker(symbol).history(...)
        # 我們需要為每個 symbol mock Ticker 類的調用
        mock_ticker_instance_aapl = MagicMock()
        mock_ticker_instance_aapl.history.return_value = mock_data_aapl.copy()
        mock_ticker_instance_msft = MagicMock()
        mock_ticker_instance_msft.history.return_value = mock_data_msft.copy()

        # 當 Ticker 類被調用時，根據 symbol 返回不同的實例
        def ticker_side_effect(symbol_arg):
            if symbol_arg == 'AAPL':
                return mock_ticker_instance_aapl
            elif symbol_arg == 'MSFT':
                return mock_ticker_instance_msft
            return MagicMock() # 預設返回一個通用 mock 實例

        mock_yfinance_ticker_class.side_effect = ticker_side_effect

        result_df = yfinance.fetch_daily_ohlcv(symbols, start_date, end_date)

        # 驗證 Ticker 的調用次數和參數
        assert mock_yfinance_ticker_class.call_count == len(symbols)
        mock_yfinance_ticker_class.assert_any_call('AAPL')
        mock_yfinance_ticker_class.assert_any_call('MSFT')

        # 驗證 history 的調用次數和參數
        assert mock_ticker_instance_aapl.history.call_count == 1
        mock_ticker_instance_aapl.history.assert_called_once_with(start=start_date, end=end_date, auto_adjust=False)
        assert mock_ticker_instance_msft.history.call_count == 1
        mock_ticker_instance_msft.history.assert_called_once_with(start=start_date, end=end_date, auto_adjust=False)

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

    def test_fetch_no_data_for_symbol(self, mock_yfinance_ticker_class): # 使用修改後的 fixture
        """測試當某個商品代碼無數據時的情況。"""
        symbols = ['VALID', 'EMPTY']
        start_date = '2023-01-02' # 改為營業日
        end_date = '2023-01-03'

        mock_data_valid = create_sample_stock_data('VALID', start_date, end_date)
        # EMPTY 代碼返回空 DataFrame
        mock_ticker_instance_valid = MagicMock()
        mock_ticker_instance_valid.history.return_value = mock_data_valid.copy()
        mock_ticker_instance_empty = MagicMock()
        mock_ticker_instance_empty.history.return_value = pd.DataFrame()

        def ticker_side_effect(symbol_arg):
            if symbol_arg == 'VALID':
                return mock_ticker_instance_valid
            elif symbol_arg == 'EMPTY':
                return mock_ticker_instance_empty
            return MagicMock()
        mock_yfinance_ticker_class.side_effect = ticker_side_effect

        result_df = yfinance.fetch_daily_ohlcv(symbols, start_date, end_date)

        # 預期只包含 VALID 的數據
        expected_valid = mock_data_valid.reset_index()
        expected_valid['symbol'] = 'VALID'
        expected_valid.rename(columns={'Adj Close': 'Adj_Close'}, inplace=True)
        expected_valid['Date'] = pd.to_datetime(expected_valid['Date'])

        expected_cols = ['Date', 'symbol', 'Open', 'High', 'Low', 'Close', 'Adj_Close', 'Volume']
        expected_df = expected_valid[expected_cols]

        assert_frame_equal(result_df, expected_df, check_dtype=True)

    def test_fetch_all_symbols_no_data(self, mock_yfinance_ticker_class): # 使用修改後的 fixture
        """測試所有商品代碼均無數據時返回空 DataFrame。"""
        symbols = ['EMPTY1', 'EMPTY2']
        start_date = '2023-01-02'
        end_date = '2023-01-03'

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = pd.DataFrame() # 所有調用都返回空
        mock_yfinance_ticker_class.return_value = mock_ticker_instance

        result_df = yfinance.fetch_daily_ohlcv(symbols, start_date, end_date)

        assert result_df.empty
        assert mock_yfinance_ticker_class.call_count == len(symbols) # Ticker 類被調用兩次
        assert mock_ticker_instance.history.call_count == len(symbols) # 每個 mock 實例的 history 被調用一次

    def test_fetch_yfinance_api_error(self, mock_yfinance_ticker_class): # 使用修改後的 fixture
        """測試 yfinance API 調用引發異常時返回空 DataFrame。"""
        symbols = ['AAPL']
        start_date = '2023-01-02'
        end_date = '2023-01-03'

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.side_effect = Exception("Simulated API Error")
        mock_yfinance_ticker_class.return_value = mock_ticker_instance

        result_df = yfinance.fetch_daily_ohlcv(symbols, start_date, end_date)

        assert result_df.empty
        # 即使發生錯誤，也應該有嘗試調用
        mock_yfinance_ticker_class.assert_called_once_with(symbols[0])
        mock_ticker_instance.history.assert_called_once()


    def test_fetch_empty_symbol_list(self):
        """測試傳入空的商品代碼列表時返回空 DataFrame。"""
        result_df = yfinance.fetch_daily_ohlcv([], '2023-01-01', '2023-01-02')
        assert result_df.empty

    def test_fetch_invalid_symbols_type(self):
        """測試傳入無效的 symbols 參數類型 (非列表) 時返回空 DataFrame。"""
        result_df = yfinance.fetch_daily_ohlcv("AAPL", '2023-01-01', '2023-01-02') # type: ignore
        assert result_df.empty

    def test_fetch_data_with_missing_volume(self, mock_yfinance_ticker_class): # 使用修改後的 fixture
        """測試抓取的數據可能缺少 'Volume' 欄位 (例如指數)。"""
        symbol = '^GSPC' # 指數通常沒有 Volume
        start_date = '2023-01-02' # 改為營業日
        end_date = '2023-01-03'

        mock_data_no_volume = create_sample_stock_data(symbol, start_date, end_date)
        if 'Volume' in mock_data_no_volume.columns: # 確保欄位存在才刪除
            del mock_data_no_volume['Volume'] # 模擬沒有 Volume 的情況

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = mock_data_no_volume.copy()
        mock_yfinance_ticker_class.return_value = mock_ticker_instance

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

    def test_date_column_timezone_conversion(self, mock_yfinance_ticker_class): # 使用修改後的 fixture
        """測試 Date 欄位時區被正確處理 (轉換為 UTC naive)。"""
        symbol = 'AAPL'
        start_date = '2023-01-01' # 週日, create_sample_stock_data 會強制創建此日期的 mock data
        end_date = '2023-01-01'

        # 創建一個帶有時區的 Date 索引的 DataFrame
        raw_date = pd.Timestamp('2023-01-01 00:00:00', tz='US/Eastern')
        mock_data_with_tz = pd.DataFrame({
            'Open': [100], 'High': [105], 'Low': [95], 'Close': [102], 'Adj Close': [101], 'Volume': [1000000]
        }, index=pd.DatetimeIndex([raw_date], name='Date'))

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = mock_data_with_tz.copy()
        mock_yfinance_ticker_class.return_value = mock_ticker_instance

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

        # 根據現有代碼，我們預期 '2023-01-01 00:00:00 US/Eastern' 轉換為 UTC naive 後，
        # 時間部分會根據偏移量改變 (EST is UTC-5, so 00:00 EST becomes 05:00 UTC).
        # 日期部分保持不變。
        # 我們的 create_sample_stock_data 如果 start_date_str == end_date_str，會強制使用該日期，
        # 所以 mock_data_with_tz 中的日期 '2023-01-01' 是有效的。

        assert result_df['Date'].iloc[0] == pd.Timestamp('2023-01-01 05:00:00')

    def test_fetch_data_column_renaming_adj_close(self, mock_yfinance_ticker_class): # 使用修改後的 fixture
        """測試 'Adj Close' 欄位被正確重命名為 'Adj_Close'。"""
        symbol = 'TEST'
        start_date = '2023-01-02' # 改為營業日，確保 create_sample_stock_data 返回數據
        end_date = '2023-01-02'

        # create_sample_stock_data 已經使用了 'Adj Close'
        mock_df = create_sample_stock_data(symbol, start_date, end_date)

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = mock_df.copy()
        mock_yfinance_ticker_class.return_value = mock_ticker_instance

        result_df = yfinance.fetch_daily_ohlcv([symbol], start_date, end_date)

        assert 'Adj_Close' in result_df.columns
        assert 'Adj Close' not in result_df.columns

        # 驗證數據是否正確
        expected_adj_close_value = mock_df['Adj Close'].iloc[0]
        assert result_df['Adj_Close'].iloc[0] == expected_adj_close_value
