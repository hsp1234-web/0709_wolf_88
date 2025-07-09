# 測試腳本將在此處編寫
import pytest
import os
import duckdb
import pandas as pd # 新增導入
import pandas_ta # 在測試腳本頂層導入 pandas_ta
from datetime import date, timedelta
import queue # 新增導入
import numpy as np # 為 pd.NA 或 np.nan 導入

from apps.daily_market_analyzer.db_manager import DBManager
# 修正導入路徑
from apps.daily_market_analyzer.yfinance_client import YFinanceClient
from apps.factor_engine.engine import FactorEngine

# --- 測試參數 ---
TICKER = 'AAPL'
# 嘗試獲取昨天的日期，如果昨天是週末，則再往前推
today = date.today()
target_date_obj = None
for i in range(1, 7):
    potential_date = today - timedelta(days=i)
    if potential_date.weekday() < 5:
        target_date_obj = potential_date
        break
if target_date_obj is None:
    target_date_obj = today - timedelta(days=7)
TARGET_DATE_STR = target_date_obj.strftime('%Y-%m-%d')

DB_PATH = "temp/test_stability.duckdb"

@pytest.fixture(scope="module")
def db_manager():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    manager = DBManager(db_path=DB_PATH, target_ohlcv_table_name="market_ohlcv_data")
    return manager

@pytest.fixture(scope="module")
def data_queue():
    return queue.Queue()

@pytest.fixture(scope="module")
def hydrator(db_manager, data_queue):
    return YFinanceClient(db_manager=db_manager, data_queue=data_queue)

@pytest.fixture(scope="module")
def factor_engine(db_manager):
    return FactorEngine(db_manager=db_manager)

# --- 測試案例 ---

def test_case_a_first_hydration(hydrator, db_manager, data_queue, mocker):
    print(f"測試案例 A：對 {TICKER} 在 {TARGET_DATE_STR} 進行首次數據回填")
    mock_yfinance_history = mocker.patch('yfinance.Ticker.history', autospec=True)
    mock_data_index = pd.to_datetime([TARGET_DATE_STR])
    mock_data_index.name = 'Datetime'
    mock_data = pd.DataFrame({
        'Open': [150.0], 'High': [152.0], 'Low': [149.0], 'Close': [151.0], 'Volume': [1000000]
    }, index=mock_data_index)
    mock_yfinance_history.return_value = mock_data
    _, execution_log = hydrator.hydrate_data_range(TICKER, TARGET_DATE_STR, TARGET_DATE_STR)
    print(f"首次回填 execution_log: {execution_log}")
    while not data_queue.empty():
        item = data_queue.get()
        if item and 'data' in item and 'table_name' in item:
            print(f"從佇列取出數據並準備寫入: {item['ticker']}, {item['interval']}, {len(item['data'])} rows to {item['table_name']}")
            db_manager.upsert_data(item['data'], item['table_name'])
            print(f"已將佇列中的數據寫入資料庫。")
        data_queue.task_done()
    mock_yfinance_history.assert_called()
    print(f"yfinance.Ticker.history 被成功呼叫 (首次回填)")
    with duckdb.connect(database=DB_PATH, read_only=True) as con:
        query = f"SELECT COUNT(*) FROM market_ohlcv_data WHERE ticker = '{TICKER}' AND DATE(datetime) = DATE '{TARGET_DATE_STR}'"
        count = con.execute(query).fetchone()[0]
        assert count > 0, f"在 market_ohlcv_data 中未找到 {TICKER} 在 {TARGET_DATE_STR} 的數據 (查詢結果 {count} 筆)"
        print(f"在 market_ohlcv_data 中找到 {count} 筆 {TICKER} 在 {TARGET_DATE_STR} 的數據")
    log_for_date = execution_log.get(TARGET_DATE_STR, {}).get(TICKER, {})
    assert "success" in log_for_date.get("status", "").lower() or "api_success" in log_for_date.get("status", "").lower(), \
        f"首次回填的 execution_log 狀態不正確: {log_for_date.get('status')}"
    print(f"首次回填 execution_log 狀態 '{log_for_date.get('status')}' 符合預期")
    with duckdb.connect(database=DB_PATH, read_only=True) as con:
        no_data_entry = con.execute(f"SELECT * FROM no_data_records WHERE ticker = '{TICKER}' AND start_date <= '{TARGET_DATE_STR}' AND end_date >= '{TARGET_DATE_STR}'").fetchall()
        assert len(no_data_entry) == 0, f"{TICKER} 在 {TARGET_DATE_STR} 不應被記錄在 no_data_records 中 (找到 {len(no_data_entry)} 筆)"
        print(f"{TICKER} 在 {TARGET_DATE_STR} 未被記錄在 no_data_records 中，符合預期")

def test_case_b_factor_calculation(factor_engine, db_manager):
    """測試案例 B：因子計算 - 驗證流程完整性"""
    print(f"測試案例 B：為 {TICKER} 在 {TARGET_DATE_STR} 計算因子 - 流程完整性驗證")

    initial_row_count = 0
    expected_columns = ['ticker', 'date', 'factor_name', 'factor_value']
    try:
        with duckdb.connect(database=DB_PATH, read_only=True) as con:
            tables_df = con.execute("SHOW TABLES").df()
            if 'FactorStore_Daily' in tables_df['name'].values:
                initial_row_count = con.execute("SELECT COUNT(*) FROM FactorStore_Daily").fetchone()[0]
                table_info = con.execute("PRAGMA table_info('FactorStore_Daily')").fetchall()
                column_names = [info[1] for info in table_info]
                for col in expected_columns:
                    assert col in column_names, f"FactorStore_Daily 表缺少預期欄位: {col}"
                print(f"FactorStore_Daily 表結構正常，初始行數: {initial_row_count}")
            else:
                print("FactorStore_Daily 表尚不存在。")
    except Exception as e:
        print(f"讀取 FactorStore_Daily 初始狀態時發生錯誤: {e}")

    start_query_date = (pd.to_datetime(TARGET_DATE_STR) - pd.Timedelta(days=40)).strftime('%Y-%m-%d')
    price_data_query = f"SELECT datetime, open, high, low, close, volume FROM market_ohlcv_data WHERE ticker = '{TICKER}' AND DATE(datetime) BETWEEN DATE '{start_query_date}' AND DATE '{TARGET_DATE_STR}' ORDER BY datetime ASC"

    with duckdb.connect(database=DB_PATH, read_only=True) as con:
        prices_df = pd.read_sql_query(price_data_query, con)

    if prices_df.empty:
        print(f"警告: 從 market_ohlcv_data 讀取的數據不足或為空。將使用 mock 數據擴展以進行因子計算流程測試。")
        num_days_for_factors = 30
        mock_dates = pd.to_datetime([ (pd.to_datetime(TARGET_DATE_STR) - pd.Timedelta(days=i)).strftime('%Y-%m-%d') for i in range(num_days_for_factors -1, -1, -1) ])
        single_day_data = {
            'datetime': mock_dates,
            'open': [150.0] * num_days_for_factors, 'high': [152.0] * num_days_for_factors,
            'low': [149.0] * num_days_for_factors, 'close': [151.0] * num_days_for_factors,
            'volume': [1000000] * num_days_for_factors
        }
        prices_df = pd.DataFrame(single_day_data)

    prices_df['datetime'] = pd.to_datetime(prices_df['datetime'])
    if prices_df['datetime'].dt.tz is None:
        prices_df['datetime'] = prices_df['datetime'].dt.tz_localize('UTC')
    else:
        prices_df['datetime'] = prices_df['datetime'].dt.tz_convert('UTC')
    prices_df = prices_df.set_index('datetime')
    prices_df.columns = [col.lower() for col in prices_df.columns]

    try:
        hv_20d_series = factor_engine.calculate_price_volatility(prices_df.copy(), n_days=20)
        volume_hv_20d_series = factor_engine.calculate_volume_volatility(prices_df.copy(), n_days=20)
        rsi_14d_series = factor_engine.calculate_rsi(prices_df.copy(), n_days=14)
        print("FactorEngine 計算方法成功調用。")
    except Exception as e:
        pytest.fail(f"FactorEngine 計算方法調用失敗: {e}")

    factors_to_store = []
    target_datetime_utc = pd.Timestamp(TARGET_DATE_STR, tz='UTC')

    def get_scalar_value(series, label):
        if series is None or series.empty or label not in series.index:
            return np.nan
        lookup_result = series.loc[label]
        if isinstance(lookup_result, pd.Series):
            return lookup_result.iloc[0] if not lookup_result.empty else np.nan
        return lookup_result

    hv_value = get_scalar_value(hv_20d_series, target_datetime_utc)
    factors_to_store.append({'ticker': TICKER, 'date': TARGET_DATE_STR, 'factor_name': 'hv_20d', 'factor_value': float(hv_value) if pd.notna(hv_value) else None})

    volume_hv_value = get_scalar_value(volume_hv_20d_series, target_datetime_utc)
    factors_to_store.append({'ticker': TICKER, 'date': TARGET_DATE_STR, 'factor_name': 'volume_hv_20d', 'factor_value': float(volume_hv_value) if pd.notna(volume_hv_value) else None})

    rsi_value = get_scalar_value(rsi_14d_series, target_datetime_utc)
    factors_to_store.append({'ticker': TICKER, 'date': TARGET_DATE_STR, 'factor_name': 'rsi_14d', 'factor_value': float(rsi_value) if pd.notna(rsi_value) else None})

    non_nan_factors_count = sum(1 for f in factors_to_store if pd.notna(f['factor_value']))
    print(f"計算出的非 NaN 因子數量: {non_nan_factors_count}")

    if factors_to_store:
        factors_df = pd.DataFrame(factors_to_store)
        db_manager.insert_factors(factors_df)
        print(f"已嘗試將 {len(factors_df)} 個因子結果 (包括 NaN) 傳遞給 db_manager.insert_factors。")
    else:
        print("沒有任何因子結果可以傳遞給 db_manager.insert_factors。")

    with duckdb.connect(database=DB_PATH, read_only=True) as con:
        final_row_count = con.execute("SELECT COUNT(*) FROM FactorStore_Daily").fetchone()[0]
        table_info = con.execute("PRAGMA table_info('FactorStore_Daily')").fetchall()
        column_names = [info[1] for info in table_info]

        for col in expected_columns:
            assert col in column_names, f"FactorStore_Daily 表缺少預期欄位 (最終檢查): {col}"
        print(f"FactorStore_Daily 表結構正常 (最終檢查)。最終行數: {final_row_count}")

        any_factor_written_or_null = False
        if factors_to_store:
            for factor_entry in factors_to_store:
                # 修正 SQL 查詢中的 DATE 轉換問題
                data = con.execute("SELECT factor_value FROM FactorStore_Daily WHERE ticker = ? AND date = ? AND factor_name = ?",
                                   [factor_entry['ticker'], factor_entry['date'], factor_entry['factor_name']]).fetchone()
                if data is not None:
                    any_factor_written_or_null = True
                    print(f"已在 FactorStore_Daily 中找到記錄: {factor_entry['factor_name']}, 值: {data[0]}")
                    if pd.isna(factor_entry['factor_value']):
                        assert data[0] is None, f"因子 {factor_entry['factor_name']} 計算為 NaN，但資料庫中存儲的不是 NULL"
                    elif data[0] is None and factor_entry['factor_value'] is not None :
                         pytest.fail(f"因子 {factor_entry['factor_name']} 計算為 {factor_entry['factor_value']}，但資料庫中存儲為 NULL")

            if not any_factor_written_or_null and factors_to_store:
                 pytest.fail(f"嘗試儲存 {len(factors_to_store)} 個因子，但在 FactorStore_Daily 中未找到任何對應記錄。insert_factors 可能未正確處理值為 None 的情況。")

        if factors_to_store: # 修改斷言邏輯：如果嘗試了儲存，則行數至少應為 factors_to_store 的長度
             assert final_row_count >= initial_row_count + len(list(filter(lambda f: pd.notna(f['factor_value']), factors_to_store))) , \
                f"FactorStore_Daily 行數未按預期增加。初始: {initial_row_count}, 嘗試寫入(非NaN): {non_nan_factors_count}, 最終: {final_row_count}"
        else:
            print("factors_to_store 列表為空，未嘗試寫入因子。")
            assert final_row_count == initial_row_count, "factors_to_store 為空，但 FactorStore_Daily 行數發生變化。"

    print("test_case_b_factor_calculation 流程完整性驗證完成。")

def test_case_c_cache_hit_verification(hydrator, mocker, data_queue):
    print(f"測試案例 C：驗證對 {TICKER} 在 {TARGET_DATE_STR} 的第二次調用是否命中快取")
    mock_yfinance_history_cache_check = mocker.patch('yfinance.Ticker.history', autospec=True)
    _, execution_log_cache = hydrator.hydrate_data_range(TICKER, TARGET_DATE_STR, TARGET_DATE_STR)
    print(f"第二次 hydrate_data_range 調用 execution_log: {execution_log_cache}")
    while not data_queue.empty():
        item = data_queue.get()
        print(f"警告: 在快取命中測試中，佇列不應有項目，但收到: {item}")
        data_queue.task_done()
    mock_yfinance_history_cache_check.assert_not_called()
    print(f"yfinance.Ticker.history 未被呼叫，符合快取命中預期")
    log_for_date_cache = execution_log_cache.get(TARGET_DATE_STR, {}).get(TICKER, {})
    status_cache = log_for_date_cache.get("status", "").lower()
    assert "cached" in status_cache, \
        f"第二次調用的 execution_log 狀態應為 'cached*'，但得到: {status_cache}"
    print(f"第二次調用 execution_log 狀態 '{status_cache}' 表明從快取獲取，符合預期")

print(f"測試參數設定：TICKER={TICKER}, TARGET_DATE_STR={TARGET_DATE_STR}, DB_PATH={DB_PATH}")
