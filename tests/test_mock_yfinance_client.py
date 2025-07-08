# tests/test_mock_yfinance_client.py
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch # patch 也可以直接從 pytest_mock 的 mocker 取得

# --- 標準化「路徑自我校正」樣板碼 START ---
import sys
import os
from pathlib import Path
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    tests_dir = current_script_path.parent
    if str(tests_dir) not in sys.path:
        sys.path.insert(0, str(tests_dir))
    apps_dir = project_root / "apps"
    if str(apps_dir) not in sys.path: # 確保 apps 目錄也在路徑中，以便 yfinance_client 可以導入其依賴
        sys.path.insert(0, str(apps_dir))


except NameError:
    project_root = Path(os.getcwd())
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    tests_dir = project_root / "tests"
    if str(tests_dir) not in sys.path:
         sys.path.insert(0, str(tests_dir))
    apps_dir = project_root / "apps"
    if str(apps_dir) not in sys.path:
        sys.path.insert(0, str(apps_dir))
    print(f"警告：__file__ 未定義，專案路徑校正可能不準確 (test_mock_yfinance_client.py)。")
except Exception as e:
    print(f"專案路徑校正時發生錯誤 (test_mock_yfinance_client.py): {e}", file=sys.stderr)
# --- 標準化「路徑自我校正」樣板碼 END ---

from mock_data_utils import generate_mock_ohlcv_data
# 實際要測試的模組
from apps.yfinance_client import client as yfinance_client_module

# 獲取預先生成的模擬 OHLCV 數據
MOCK_OHLCV_DATA_STORE = generate_mock_ohlcv_data()

@pytest.fixture
def mock_yfinance_ticker(mocker):
    """
    Fixture to mock yfinance.Ticker.
    The mocked Ticker().history() will return pre-defined DataFrames.
    """
    mock_ticker_instance = MagicMock()

    def mock_history(start=None, end=None, auto_adjust=False, **kwargs):
        # self 在這裡是 mock_ticker_instance
        # 我們需要知道是哪個 ticker 被調用了。
        # yf.Ticker(symbol) 中的 symbol 需要被捕獲。
        # MagicMock 的 name 屬性可以用來存儲 ticker symbol，如果我們在 patch yf.Ticker 時設置它。
        # 或者，更簡單的方式是，讓 mock_history 函數的行為依賴於 self.ticker_symbol (假設我們賦值了)

        # 由於 yf.Ticker(symbol) 後才調用 .history()，
        # 我們需要在 patch yf.Ticker 本身時，讓它返回一個配置好的 MagicMock。
        # 這個 MagicMock 的 history 方法將使用它被創建時關聯的 symbol。

        # 為了簡單起見，我們假設 mock_ticker_instance 有一個 'symbol' 屬性
        # 這個屬性會在 mock_yf_ticker_class 中被賦值
        symbol_key = mock_ticker_instance.symbol

        print(f"Mocked Ticker.history() called for symbol: {symbol_key}, start: {start}, end: {end}")

        if symbol_key in MOCK_OHLCV_DATA_STORE:
            df = MOCK_OHLCV_DATA_STORE[symbol_key].copy()
            # yfinance Ticker().history() 返回的 DataFrame 索引是 Date，欄位有 Open, High, Low, Close, Volume, Dividends, Stock Splits
            # 我們的模擬數據目前沒有 Dividends, Stock Splits，這通常是 OK 的
            # 如果 yfinance_client.py 中 auto_adjust=False，則返回的欄位名應為 'Adj Close' (如果存在)
            # 我們的模擬數據有 'Adj Close'

            # 篩選日期 (如果提供了 start/end)
            # 注意：MOCK_OHLCV_DATA_STORE 的 Date 索引是 Timestamp
            # yfinance 的 start/end 通常是 'YYYY-MM-DD' 字串
            if start:
                df = df[df.index >= pd.to_datetime(start)]
            if end: # yfinance 的 end 是包含的，但通常傳入的是下一天的日期來表示不包含當天
                    # 不過，簡單起見，我們這裡做包含篩選
                df = df[df.index <= pd.to_datetime(end)]

            print(f"Mocked Ticker.history() for {symbol_key} returning DataFrame with {len(df)} rows.")
            return df
        else:
            print(f"Mocked Ticker.history() for unknown symbol {symbol_key} returning empty DataFrame.")
            return pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume'])

    mock_ticker_instance.history = MagicMock(side_effect=mock_history)

    # 模擬其他可能被 yfinance_client.py 使用的 Ticker 屬性或方法，如果有的話
    # 例如，如果 client.py 檢查 ticker.info:
    # mock_ticker_instance.info = {"shortName": "Mocked Ticker Inc."}

    # 這個 fixture 返回配置好的 Ticker *實例* mock
    # 但我們需要 patch yf.Ticker *類別*，使其在被調用時返回這個 mock_ticker_instance
    # 所以這個 fixture 本身不直接使用 mocker.patch，而是在測試函數中與 mocker.patch('...yf.Ticker') 結合
    # 更佳的做法是，這個 fixture 直接執行 patch 並返回 mock_ticker_instance 的創建者 (類 mock)

    # 重構：讓 fixture patch yf.Ticker 類
    mock_ticker_class = mocker.patch('apps.yfinance_client.client.yf.Ticker', autospec=True)

    def new_ticker_init(symbol_arg):
        # 當 yf.Ticker(symbol_arg) 被調用時，這個函數會被執行
        # 我們需要返回一個配置好的 mock_ticker_instance
        # 並將 symbol_arg 儲存起來，以便 history 能用
        instance = MagicMock() # 每次調用 yf.Ticker() 都創建一個新的 mock 實例
        instance.symbol = symbol_arg # 儲存 symbol
        instance.history = MagicMock(side_effect=lambda start=None, end=None, auto_adjust=False, **kwargs: \
            mock_history_for_class_patch(instance.symbol, start, end, auto_adjust, **kwargs)
        )
        # 如果需要模擬 .options 等其他方法，在這裡添加
        # instance.options = MagicMock(return_value=('2024-07-01', '2024-07-08')) # 模擬選擇權日期
        # instance.option_chain = MagicMock(return_value=...) # 模擬選擇權鏈數據
        return instance

    def mock_history_for_class_patch(symbol_key, start_str, end_str, auto_adjust_val, **kwargs_val):
        # 這個內部函數現在可以訪問 symbol_key
        print(f"Mocked Ticker CLASS's instance.history() called for symbol: {symbol_key}, start: {start_str}, end: {end_str}")
        if symbol_key in MOCK_OHLCV_DATA_STORE:
            df = MOCK_OHLCV_DATA_STORE[symbol_key].copy()
            if start_str:
                df = df[df.index >= pd.to_datetime(start_str)]
            if end_str: # yfinance 的 end 是不包含的，所以比較時應該是 < end_date
                        # 或者，如果 yfinance_client 傳入的是 end_date + 1 day，則 <= end_date
                        # yfinance_client.py 的 fetch_daily_ohlcv 傳的是 end_date
                        # yf.Ticker.history(start=start_date, end=end_date) end_date is exclusive for daily data if time is not specified.
                        # Let's assume our mock data is daily and yf client requests specific dates.
                        # For simplicity, our mock data matches exact dates.
                        # The yfinance client uses end_date in history call, so we should filter up to and including that date.
                df = df[df.index < pd.to_datetime(end_str)] # yfinance end is exclusive
            return df
        return pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume'])

    mock_ticker_class.side_effect = new_ticker_init
    return mock_ticker_class # 返回被 patch 的類本身，以便驗證調用等

# --- 測試 yfinance_client.py 的函數 ---

def test_fetch_daily_ohlcv_mocked(mock_yfinance_ticker):
    """
    測試 fetch_daily_ohlcv 在 yf.Ticker 被模擬時的行為。
    """
    print("\n--- test_fetch_daily_ohlcv_mocked ---")
    # 測試的股票代碼應存在於 MOCK_OHLCV_DATA_STORE
    test_symbols = ["MOCK_AAPL", "0050"]
    start_date = "2024-01-01"
    # yfinance .history() end is exclusive. So if we want data up to 2024-01-03 (inclusive),
    # we should pass "2024-01-04" as end date.
    # Our mock data for MOCK_AAPL is from 2024-01-01 to 2024-01-07.
    # If yfinance_client passes "2024-01-03" as end_date, it means it wants data for 01, 02.
    # Let's align with how yfinance_client calls it.
    # yfinance_client.fetch_daily_ohlcv calls ticker_obj.history(start=start_date, end=end_date)
    # Let's assume end_date in yfinance_client is inclusive for its own logic,
    # but yfinance lib itself might treat it as exclusive.
    # The mock_history_for_class_patch now filters df.index < pd.to_datetime(end_str)
    # So, if we pass end_date = "2024-01-03", we should get data for 2024-01-01, 2024-01-02.
    end_date = "2024-01-03"

    # 呼叫我們要測試的函數
    result_df = yfinance_client_module.fetch_daily_ohlcv(test_symbols, start_date, end_date)

    assert not result_df.empty
    # 驗證返回的 DataFrame 包含來自模擬數據的內容
    # 預期 MOCK_AAPL 有2筆 (01-01, 01-02), 0050 有2筆 (01-01, 01-02)
    # Total 4 rows.
    expected_rows = 2 * len(test_symbols)
    assert len(result_df) == expected_rows

    assert "MOCK_AAPL" in result_df['symbol'].unique()
    assert "0050" in result_df['symbol'].unique()

    # 驗證欄位，yfinance_client.py 會添加 'symbol' 並重命名 'Adj Close' -> 'Adj_Close'
    expected_cols = ['Date', 'symbol', 'Open', 'High', 'Low', 'Close', 'Adj_Close', 'Volume']
    assert all(col in result_df.columns for col in expected_cols)

    # 驗證 mock_yfinance_ticker (即 mock_ticker_class) 是否被以預期的方式調用
    # mock_yfinance_ticker.assert_any_call("MOCK_AAPL") # yf.Ticker("MOCK_AAPL")
    # mock_yfinance_ticker.assert_any_call("0050")    # yf.Ticker("0050")
    # 由於 side_effect 返回的是一個新的 MagicMock 實例，對類本身的調用次數檢查更直接
    assert mock_yfinance_ticker.call_count == len(test_symbols)

    # 檢查返回的 Ticker 實例上的 history 方法是否被調用
    # mock_yfinance_ticker.return_value.history.assert_called() # 這適用於只mock一個symbol的情況
    # 對於多個 symbol，每個 mock instance 的 history 都會被調用
    for call_arg in mock_yfinance_ticker.call_args_list:
        symbol_called_with = call_arg[0][0] # yf.Ticker(symbol)
        # 獲取對應的 mock instance (這是比較複雜的部分，因為 side_effect 每次都創建新實例)
        # 一個簡化的方法是假設 history 被正確調用了，如果上面的數據斷言通過的話。
        # 或者，讓 new_ticker_init 返回的 instance 加入一個列表，然後檢查列表中的每個 instance。
        # 目前，數據本身的驗證更為重要。

    print("test_fetch_daily_ohlcv_mocked PASSED.")

def test_fetch_daily_ohlcv_mocked_nonexistent_symbol(mock_yfinance_ticker):
    """
    測試 fetch_daily_ohlcv 在請求不存在於模擬數據中的股票代碼時的行為。
    """
    print("\n--- test_fetch_daily_ohlcv_mocked_nonexistent_symbol ---")
    test_symbols = ["NONEXISTENT_XYZ"]
    start_date = "2024-01-01"
    end_date = "2024-01-03"

    result_df = yfinance_client_module.fetch_daily_ohlcv(test_symbols, start_date, end_date)

    assert result_df.empty # 預期返回空的 DataFrame
    mock_yfinance_ticker.assert_called_with("NONEXISTENT_XYZ")
    print("test_fetch_daily_ohlcv_mocked_nonexistent_symbol PASSED.")

# 更多測試可以在這裡添加，例如測試 store_data_to_duckdb (下一步)

if __name__ == '__main__':
    # 允許直接運行此文件進行初步測試 (儘管 pytest 是首選)
    # 需要手動設置 mocker，或者使用 unittest.mock
    print("請使用 pytest 運行此測試文件: pytest tests/test_mock_yfinance_client.py")

    # 簡易手動測試 (不使用 pytest fixture)
    class MockArgs:
        def __init__(self, symbol):
            self.symbol = symbol
            self.history_calls = []

        def history(self, start=None, end=None, auto_adjust=False, **kwargs):
            self.history_calls.append({'start': start, 'end': end})
            print(f"MANUAL Mocked Ticker.history() for {self.symbol}, start: {start}, end: {end}")
            if self.symbol in MOCK_OHLCV_DATA_STORE:
                df = MOCK_OHLCV_DATA_STORE[self.symbol].copy()
                if start: df = df[df.index >= pd.to_datetime(start)]
                if end: df = df[df.index < pd.to_datetime(end)] # end is exclusive
                return df
            return pd.DataFrame()

    with patch('apps.yfinance_client.client.yf.Ticker', side_effect=lambda s: MockArgs(s)) as manual_mock_ticker:
        print("\n--- Manual Test: fetch_daily_ohlcv ---")
        res_manual = yfinance_client_module.fetch_daily_ohlcv(["MOCK_AAPL"], "2024-01-01", "2024-01-02")
        print(f"Manual test result (MOCK_AAPL, 1 day):\n{res_manual}")
        assert len(res_manual) == 1 # 2024-01-01 data only
        assert manual_mock_ticker.call_count == 1
        # 檢查 history 是否被調用 (manual_mock_ticker.return_value 是 MockArgs 實例)
        assert len(manual_mock_ticker.return_value.history_calls) > 0

        print("\n--- Manual Test: fetch_daily_ohlcv (non-existent) ---")
        res_manual_non = yfinance_client_module.fetch_daily_ohlcv(["XYZ"], "2024-01-01", "2024-01-02")
        print(f"Manual test result (XYZ):\n{res_manual_non}")
        assert res_manual_non.empty
        assert manual_mock_ticker.call_count == 2 # Total calls to yf.Ticker
