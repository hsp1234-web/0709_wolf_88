# -*- coding: utf-8 -*-
"""
【時間熔爐】 - 按需聚合引擎
==============================
負責將高頻率的原始市場數據（例如分鐘級），
聚合成用戶指定的任意時間週期的 OHLCV 數據。
"""
import pandas as pd
from datetime import datetime

# 假設 DBManager 從 apps.daily_market_analyzer.db_manager 導入
# from apps.daily_market_analyzer.db_manager import DBManager
# 為了類型提示，可以這樣寫，實際運行時依賴於PYTHONPATH或環境配置
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from apps.daily_market_analyzer.db_manager import DBManager

class TimeAggregator:
    """
    時間聚合器 (TimeAggregator) 類別。
    從資料庫讀取高頻數據，並將其按需聚合成目標時間週期的 OHLCV 數據。
    """
    def __init__(self, db_manager: 'DBManager'):
        """
        初始化 TimeAggregator。

        Args:
            db_manager (DBManager): DBManager 的實例，用於資料庫操作。
        """
        self.db_manager = db_manager
        print("INFO: TimeAggregator (奧丁之眼 v1.0 - 時間熔爐) 初始化完畢。")

    def aggregate_ohlcv(self, ticker: str, start_date_str: str, end_date_str: str,
                        base_interval: str, target_interval: str) -> pd.DataFrame:
        """
        從資料庫讀取指定基礎頻率的數據，並將其聚合成目標頻率的 OHLCV 數據。

        Args:
            ticker (str): 股票代碼。
            start_date_str (str): 開始日期 (YYYY-MM-DD)。
            end_date_str (str): 結束日期 (YYYY-MM-DD)。
            base_interval (str): 從資料庫讀取的原始數據的頻率 (e.g., '1m', '5m')。
            target_interval (str): 要聚合到的目標數據頻率 (e.g., '15m', '1h', '1d')。

        Returns:
            pd.DataFrame: 包含聚合後 OHLCV 數據的 DataFrame。
                          欄位包括: 'datetime', 'open', 'high', 'low', 'close', 'volume'。
                          如果無法聚合或無數據，則返回空的 DataFrame。
        """
        print(f"INFO (TimeAggregator): 開始聚合任務 for Ticker={ticker}, Range=[{start_date_str} - {end_date_str}], BaseInterval={base_interval}, TargetInterval={target_interval}")

        # 1. 從 DBManager 讀取原始數據
        # 構建查詢日期範圍，確保包含 end_date_str 當天的所有數據
        try:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
            # 查詢時，我們需要 end_dt 當天的數據，所以查詢的結束時間應為 end_dt + 1 天的開始
            query_end_dt_exclusive = end_dt + pd.Timedelta(days=1)

            query_start_ts_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
            query_end_ts_exclusive_str = query_end_dt_exclusive.strftime("%Y-%m-%d %H:%M:%S")

        except ValueError as e:
            print(f"錯誤 (TimeAggregator): 日期格式錯誤 ({start_date_str}, {end_date_str})。應為 YYYY-MM-DD。 {e}")
            return pd.DataFrame()

        # 使用 DBManager 的 ohlcv_table_name 屬性
        ohlcv_table = self.db_manager.ohlcv_table_name
        query = f"""
        SELECT datetime, open, high, low, close, volume
        FROM {ohlcv_table}
        WHERE ticker = ?
          AND interval = ?
          AND datetime >= CAST(? AS TIMESTAMPTZ)
          AND datetime < CAST(? AS TIMESTAMPTZ)
        ORDER BY datetime ASC
        """
        params = [ticker, base_interval, query_start_ts_str, query_end_ts_exclusive_str]

        print(f"DEBUG (TimeAggregator): 執行查詢: {query} với params: {params}")
        base_data_df = self.db_manager.execute_query(query, params=params)

        if base_data_df.empty:
            print(f"INFO (TimeAggregator): Ticker={ticker}, BaseInterval={base_interval} 在範圍 [{start_date_str} - {end_date_str}] 內未找到原始數據。")
            return pd.DataFrame()

        print(f"INFO (TimeAggregator): 從資料庫成功讀取 {len(base_data_df)} 筆 {base_interval} 原始數據 for {ticker}。")

        # 2. 準備數據進行 resample
        # 確保 'datetime' 是 DatetimeIndex 且已本地化到 UTC (DBManager 應已處理)
        if not pd.api.types.is_datetime64_any_dtype(base_data_df['datetime']):
            base_data_df['datetime'] = pd.to_datetime(base_data_df['datetime'])

        if base_data_df['datetime'].dt.tz is None:
            print(f"警告 (TimeAggregator): 從DB讀取的 datetime 欄位無時區信息，將本地化到 UTC。")
            base_data_df['datetime'] = base_data_df['datetime'].dt.tz_localize('UTC')
        elif base_data_df['datetime'].dt.tz.zone != 'UTC': # 防禦性程式碼，儘管DBManager應已轉為UTC
            base_data_df['datetime'] = base_data_df['datetime'].dt.tz_convert('UTC')

        base_data_df = base_data_df.set_index('datetime')

        # 確保 OHLCV 欄位是數值類型
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in base_data_df.columns:
                base_data_df[col] = pd.to_numeric(base_data_df[col], errors='coerce')
            else:
                print(f"錯誤 (TimeAggregator): 原始數據缺少欄位 '{col}'。")
                return pd.DataFrame()

        # 3. 執行聚合
        aggregation_rules = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }

        try:
            print(f"DEBUG (TimeAggregator): Resampling to target_interval='{target_interval}'")
            aggregated_df = base_data_df.resample(target_interval).agg(aggregation_rules)
        except ValueError as e_resample:
            # pandas resample 對於 target_interval 的格式有要求
            # 例如 '1D', '1H', '5min', '1Min' (注意大小寫和 'min')
            # yfinance interval 通常是 '1d', '1h', '1m'
            # 我們需要確保 target_interval 與 pandas 兼容
            # 常見的轉換： '1m' -> '1Min', '1h' -> '1H', '1d' -> '1D'
            pandas_compatible_target_interval = target_interval
            if target_interval.endswith('m'):
                pandas_compatible_target_interval = target_interval[:-1] + 'Min'
            elif target_interval.endswith('h'):
                pandas_compatible_target_interval = target_interval[:-1] + 'H'
            elif target_interval.endswith('d'):
                 pandas_compatible_target_interval = target_interval[:-1] + 'D'

            if pandas_compatible_target_interval != target_interval:
                print(f"INFO (TimeAggregator): 嘗試使用 Pandas 相容的 target_interval='{pandas_compatible_target_interval}' (原為 '{target_interval}')")
                try:
                    aggregated_df = base_data_df.resample(pandas_compatible_target_interval).agg(aggregation_rules)
                except ValueError as e_resample_compat:
                    print(f"錯誤 (TimeAggregator): 使用 Pandas 相容 interval '{pandas_compatible_target_interval}' 進行 resample 時失敗: {e_resample_compat}")
                    return pd.DataFrame()
            else: # 如果轉換前後相同，表示原始錯誤就是主要問題
                print(f"錯誤 (TimeAggregator): Pandas resample 失敗: {e_resample}")
                return pd.DataFrame()


        # resample 可能會產生所有值都是 NaN 的行 (如果原始數據在該聚合區間內沒有數據)
        # 根據作戰計畫，我們要生成 OHLCV，所以dropna()是合適的
        aggregated_df.dropna(how='all', inplace=True)

        if aggregated_df.empty:
            print(f"INFO (TimeAggregator): Ticker={ticker}。聚合到 {target_interval} 後無有效數據。")
            return pd.DataFrame()

        # 重設索引，使 'datetime' 成為一個欄位
        aggregated_df = aggregated_df.reset_index()

        # 確保輸出欄位的順序和作戰計畫一致 (datetime, open, high, low, close, volume)
        # 並添加 ticker 和 interval 欄位
        aggregated_df['ticker'] = ticker
        aggregated_df['interval'] = target_interval # 記錄這是聚合後的 interval

        final_columns = ['datetime', 'ticker', 'interval', 'open', 'high', 'low', 'close', 'volume']
        # 確保所有 final_columns 都存在，以防萬一
        for col in final_columns:
            if col not in aggregated_df.columns:
                # 這不應該發生，如果發生表示聚合邏輯有問題
                print(f"警告 (TimeAggregator): 聚合結果缺少預期欄位 '{col}'。")
                # 可以考慮填充預設值或直接返回錯誤
                aggregated_df[col] = pd.NA # 或適合的預設值

        aggregated_df = aggregated_df[final_columns]


        print(f"INFO (TimeAggregator): 成功將 {ticker} 的數據從 {base_interval} 聚合成 {len(aggregated_df)} 筆 {target_interval} 數據。")
        return aggregated_df

# --- 命令行測試接口 (可選) ---
if __name__ == '__main__':
    print("--- TimeAggregator 命令行測試介面 ---")
    # 要運行此測試，你需要一個 DBManager 實例和一些預先填充的數據。
    # from apps.daily_market_analyzer.db_manager import DBManager
    # import os

    # # 準備一個測試資料庫和一些數據
    # test_db_agg_path = "data_workspace/temp/test_aggregator.duckdb"
    # if os.path.exists(test_db_agg_path):
    #     os.remove(test_db_agg_path)

    # db_man_agg = DBManager(db_path=test_db_agg_path, target_ohlcv_table_name="MarketPrices_AggTest")
    # time_agg = TimeAggregator(db_manager=db_man_agg)

    # # 準備一些分鐘級數據存入資料庫
    # sample_ticker = "AGGR_TEST"
    # sample_start_datetime = datetime(2024, 1, 1, 9, 30, 0)
    # num_minutes = 120 # 2 小時的數據
    # minute_data = []
    # for i in range(num_minutes):
    #     ts = sample_start_datetime + pd.Timedelta(minutes=i)
    #     minute_data.append({
    #         'datetime': ts,
    #         'ticker': sample_ticker,
    #         'interval': '1m', # 基礎頻率
    #         'open': 100.0 + i*0.01,
    #         'high': 100.0 + i*0.01 + 0.05,
    #         'low': 100.0 + i*0.01 - 0.05,
    #         'close': 100.0 + i*0.01 + (0.01 if i%2==0 else -0.01),
    #         'volume': 100 + i*10
    #     })
    # minute_df = pd.DataFrame(minute_data)
    # # 將 datetime 轉為 UTC (假設原始數據是 naive, 代表 UTC)
    # minute_df['datetime'] = pd.to_datetime(minute_df['datetime']).dt.tz_localize('UTC')

    # db_man_agg.upsert_data(minute_df, table_name=db_man_agg.ohlcv_table_name)
    # print(f"已將 {len(minute_df)} 筆 '1m' 測試數據存入 {db_man_agg.ohlcv_table_name}")

    # # 測試聚合到 '5m'
    # print("\n--- 測試聚合到 '5m' ---")
    # aggregated_5m_df = time_agg.aggregate_ohlcv(
    #     ticker=sample_ticker,
    #     start_date_str="2024-01-01",
    #     end_date_str="2024-01-01",
    #     base_interval='1m',
    #     target_interval='5m' # pandas resample 使用 '5Min'
    # )
    # if not aggregated_5m_df.empty:
    #     print(f"成功聚合到 '5m'，共 {len(aggregated_5m_df)} 筆數據。")
    #     print(aggregated_5m_df.head())
    #     # 預期 num_minutes / 5 = 120 / 5 = 24 筆數據
    #     assert len(aggregated_5m_df) == num_minutes / 5
    # else:
    #     print("聚合到 '5m' 失敗或無數據。")

    # # 測試聚合到 '15m'
    # print("\n--- 測試聚合到 '15m' ---")
    # aggregated_15m_df = time_agg.aggregate_ohlcv(
    #     ticker=sample_ticker,
    #     start_date_str="2024-01-01",
    #     end_date_str="2024-01-01",
    #     base_interval='1m',
    #     target_interval='15m' # pandas resample 使用 '15Min'
    # )
    # if not aggregated_15m_df.empty:
    #     print(f"成功聚合到 '15m'，共 {len(aggregated_15m_df)} 筆數據。")
    #     print(aggregated_15m_df.head())
    #     # 預期 120 / 15 = 8 筆數據
    #     assert len(aggregated_15m_df) == num_minutes / 15
    # else:
    #     print("聚合到 '15m' 失敗或無數據。")

    # # 測試聚合到 '1h'
    # print("\n--- 測試聚合到 '1h' ---")
    # aggregated_1h_df = time_agg.aggregate_ohlcv(
    #     ticker=sample_ticker,
    #     start_date_str="2024-01-01",
    #     end_date_str="2024-01-01",
    #     base_interval='1m',
    #     target_interval='1h' # pandas resample 使用 '1H'
    # )
    # if not aggregated_1h_df.empty:
    #     print(f"成功聚合到 '1h'，共 {len(aggregated_1h_df)} 筆數據。")
    #     print(aggregated_1h_df.head())
    #     # 預期 120 / 60 = 2 筆數據
    #     assert len(aggregated_1h_df) == num_minutes / 60
    # else:
    #     print("聚合到 '1h' 失敗或無數據。")

    # # 測試聚合到 '1d' (只有一天數據，所以應該只有一筆)
    # print("\n--- 測試聚合到 '1d' ---")
    # aggregated_1d_df = time_agg.aggregate_ohlcv(
    #     ticker=sample_ticker,
    #     start_date_str="2024-01-01",
    #     end_date_str="2024-01-01",
    #     base_interval='1m',
    #     target_interval='1d' # pandas resample 使用 '1D'
    # )
    # if not aggregated_1d_df.empty:
    #     print(f"成功聚合到 '1d'，共 {len(aggregated_1d_df)} 筆數據。")
    #     print(aggregated_1d_df.head())
    #     assert len(aggregated_1d_df) == 1
    # else:
    #     print("聚合到 '1d' 失敗或無數據。")

    # print("\n--- TimeAggregator 測試完畢 ---")
    # if os.path.exists(test_db_agg_path):
    #     os.remove(test_db_agg_path)
    pass # 保持 __main__ 區塊可執行，但實際測試代碼需取消註釋並配置環境
