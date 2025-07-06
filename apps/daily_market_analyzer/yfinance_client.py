# -*- coding: utf-8 -*-
"""
YFinanceClient for Data Hydrator
================================

負責從 yfinance 下載指定時間範圍內的歷史數據，核心功能包括：
1.  **時間分塊 (Chunking)**：將長的時間範圍切成 yfinance API 允許的小塊。
2.  **迭代降級 (Fallback)**：從最精細的數據顆粒度開始嘗試，如果失敗則自動嘗試更粗的顆粒度。
3.  **數據標準化**：統一欄位名、處理缺失的 volume、確保時區為 UTC。
4.  **快取整合**：利用 DBManager 檢查快取，只請求缺失數據。
5.  **強制刷新**：提供選項以忽略快取並重新獲取所有數據。

設計思路：
- `hydrate_data_range` 是主要的外部接口，它協調整個數據回填過程。
- `_get_chunk_size_for_interval` 和 `_split_date_range_into_chunks` 是時間分塊的輔助方法。
- `fetch_single_chunk` 負責抓取單個時間區塊的特定顆粒度數據。
- 降級邏輯在 `hydrate_data_range` 中實現，遍歷 `FALLBACK_INTERVALS`。
- `_convert_missing_dates_to_ranges` 用於將離散的缺失日期合併為連續區間。
"""
import yfinance as yf
import pandas as pd
import time
import os
from datetime import datetime, timedelta
import queue
import duckdb
from .db_manager import DBManager

def _convert_missing_dates_to_ranges(missing_dates: list[str]) -> list[tuple[str, str]]:
    if not missing_dates:
        return []
    sorted_missing_dates = sorted(list(set(missing_dates)), key=lambda d: datetime.strptime(d, "%Y-%m-%d"))
    ranges = []
    if not sorted_missing_dates:
        return ranges
    start_of_range = sorted_missing_dates[0]
    end_of_range = sorted_missing_dates[0]
    for i in range(1, len(sorted_missing_dates)):
        current_date_obj = datetime.strptime(sorted_missing_dates[i], "%Y-%m-%d").date()
        prev_date_obj = datetime.strptime(end_of_range, "%Y-%m-%d").date()
        if (current_date_obj - prev_date_obj).days == 1:
            end_of_range = sorted_missing_dates[i]
        else:
            ranges.append((start_of_range, end_of_range))
            start_of_range = sorted_missing_dates[i]
            end_of_range = sorted_missing_dates[i]
    ranges.append((start_of_range, end_of_range))
    return ranges

class YFinanceClient:
    def __init__(self, db_manager: DBManager, data_queue: queue.Queue, cache_dir="data_workspace/cache/yfinance_hydrator", no_data_cooldown_days: int = 7):
        self.db_manager = db_manager
        self.data_queue = data_queue
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.FALLBACK_INTERVALS = ['1m', '5m', '15m', '30m', '1h', '1d', '1wk', '1mo']
        self.HISTORICAL_FALLBACK = ['1d', '1wk', '1mo']
        self.no_data_cooldown_days = no_data_cooldown_days
        print(f"INFO: YFinanceClient (Producer-Consumer Arch) 初始化完畢。標準 Fallback: {self.FALLBACK_INTERVALS}, 歷史 Fallback: {self.HISTORICAL_FALLBACK}, 無數據冷卻期: {self.no_data_cooldown_days} 天。")

    def _get_chunk_size_for_interval(self, interval: str) -> int:
        if interval == '1m': return 6
        elif interval in ['2m', '5m', '15m', '30m']: return 55
        elif interval in ['60m', '90m', '1h']: return 700
        elif interval in ['1d', '5d', '1wk']: return 365 * 2
        elif interval in ['1mo', '3mo']: return 365 * 5
        else:
            print(f"警告: 未知的 interval '{interval}'，預設 chunk_size_days 為 30。")
            return 30

    def _split_date_range_into_chunks(self, start_date_str: str, end_date_str: str, chunk_size_days: int) -> list[tuple[str, str]]:
        chunks = []
        try:
            current_start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            final_end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        except ValueError as e:
            print(f"錯誤: 日期格式錯誤 ({start_date_str}, {end_date_str})。請使用 YYYY-MM-DD 格式。 {e}")
            return []
        while current_start_date <= final_end_date:
            chunk_actual_end_date = current_start_date + timedelta(days=chunk_size_days - 1)
            if chunk_actual_end_date > final_end_date:
                chunk_actual_end_date = final_end_date
            yfinance_end_date = chunk_actual_end_date + timedelta(days=1)
            chunks.append((current_start_date.strftime("%Y-%m-%d"), yfinance_end_date.strftime("%Y-%m-%d")))
            current_start_date = chunk_actual_end_date + timedelta(days=1)
        return chunks

    def fetch_single_chunk(self, ticker: str, chunk_start_date_str: str, chunk_end_date_str: str, interval: str) -> pd.DataFrame | None:
        print(f"INFO: fetch_single_chunk: Ticker={ticker}, Interval={interval}, Start={chunk_start_date_str}, End(Exclusive)={chunk_end_date_str}")
        max_retries = 3
        base_delay_seconds = 1
        data = None
        for attempt in range(max_retries):
            try:
                stock = yf.Ticker(ticker)
                data = stock.history(start=chunk_start_date_str, end=chunk_end_date_str, interval=interval, auto_adjust=True, prepost=False)
                if data is not None and not data.empty: break
                if data is None: print(f"警告 (fetch_single_chunk attempt {attempt+1}/{max_retries}): yfinance returned None for {ticker} ({interval}, {chunk_start_date_str}-{chunk_end_date_str}).")
                if data is not None and data.empty:
                    print(f"INFO (fetch_single_chunk): Ticker={ticker}, Interval={interval} returned empty DataFrame. Assuming no data for this period/interval.")
                    break
            except Exception as e:
                print(f"錯誤 (fetch_single_chunk attempt {attempt+1}/{max_retries}):抓取 {ticker} ({interval}, {chunk_start_date_str}-{chunk_end_date_str}) 失敗: {type(e).__name__} - {e}")
                if attempt < max_retries - 1:
                    delay = base_delay_seconds * (attempt + 1)
                    print(f"INFO: fetch_single_chunk: Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                else:
                    print(f"錯誤: fetch_single_chunk: Max retries reached for {ticker} ({interval}).")
                    return None
            if data is None and attempt == max_retries -1:
                print(f"錯誤: fetch_single_chunk: Max retries reached, yfinance consistently returned None for {ticker} ({interval}).")
                return None
        try:
            if data is None or data.empty:
                try:
                    actual_chunk_end_date_obj = datetime.strptime(chunk_end_date_str, "%Y-%m-%d") - timedelta(days=1)
                    actual_chunk_end_date_str_for_record = actual_chunk_end_date_obj.strftime("%Y-%m-%d")
                except ValueError:
                    actual_chunk_end_date_str_for_record = "INVALID_CHUNK_END_DATE"
                    print(f"錯誤 (fetch_single_chunk): 無法從 chunk_end_date_str '{chunk_end_date_str}' 計算實際結束日期。")
                if actual_chunk_end_date_str_for_record != "INVALID_CHUNK_END_DATE":
                    self.db_manager.record_no_data_range(ticker=ticker, interval=interval, start_date=chunk_start_date_str, end_date=actual_chunk_end_date_str_for_record)
                    print(f"INFO: fetch_single_chunk: [情報] {ticker} 於 {chunk_start_date_str} 至 {actual_chunk_end_date_str_for_record} ({interval}) 無交易數據。此區塊已被記錄為無數據。")
                else:
                    print(f"INFO: fetch_single_chunk: [情報] {ticker} 於 {chunk_start_date_str} 至 {chunk_end_date_str} (excl.) ({interval}) 無交易數據。因結束日期計算問題未記錄。")
                return None # Return None if data is empty, so hydrate_data_range knows it's "no data" vs "error"
            if isinstance(data.index, pd.DatetimeIndex): data = data.reset_index()
            data.columns = [col.lower() for col in data.columns]
            if 'date' in data.columns and 'datetime' not in data.columns: data.rename(columns={'date': 'datetime'}, inplace=True)
            elif 'Datetime' in data.columns and 'datetime' not in data.columns: data.rename(columns={'Datetime': 'datetime'}, inplace=True)
            if 'datetime' not in data.columns:
                print(f"錯誤: fetch_single_chunk: 標準化後 DataFrame 中缺少 'datetime' 欄位。股票: {ticker}, 間隔: {interval}。可用欄位: {data.columns.tolist()}")
                return None
            try:
                data['datetime'] = pd.to_datetime(data['datetime'])
                if data['datetime'].dt.tz is None: data['datetime'] = data['datetime'].dt.tz_localize('UTC')
                else: data['datetime'] = data['datetime'].dt.tz_convert('UTC')
            except Exception as e:
                print(f"錯誤: fetch_single_chunk: 轉換 'datetime' 欄位時出錯: {e}. 股票: {ticker}, 間隔: {interval}.")
                return None
            if 'volume' not in data.columns: data['volume'] = 0
            data['volume'] = data['volume'].fillna(0).astype('int64')
            data['interval'] = interval
            data['ticker'] = ticker
            final_columns = ['datetime', 'ticker', 'interval', 'open', 'high', 'low', 'close', 'volume']
            missing_ohlc_cols = [col for col in ['open', 'high', 'low', 'close'] if col not in data.columns]
            if missing_ohlc_cols:
                print(f"警告: fetch_single_chunk: DataFrame 缺少部分OHLC欄位: {missing_ohlc_cols}。股票: {ticker}, 間隔: {interval}。將嘗試填充為0。")
                for col in missing_ohlc_cols: data[col] = 0.0
            try:
                data = data[final_columns]
            except KeyError as e:
                print(f"錯誤: fetch_single_chunk: 選取最終欄位時發生 KeyError: {e}。股票: {ticker}, 間隔: {interval}。可用欄位: {data.columns.tolist()}")
                return None
            print(f"INFO: fetch_single_chunk: 成功獲取並標準化 {len(data)} 筆數據。")
            return data
        except Exception as e:
            print(f"錯誤: fetch_single_chunk: 抓取或處理 {ticker} ({interval}, {chunk_start_date_str}-{chunk_end_date_str}) 失敗: {type(e).__name__} - {e}")
            return None

    def check_cache(self, ticker: str, start_date_str: str, end_date_str: str, interval: str, table_name: str | None = None) -> tuple[pd.DataFrame, list[str]]:
        effective_table_name = table_name if table_name is not None else self.db_manager.ohlcv_table_name
        print(f"DEBUG [CACHE_CHECK_ENTRY]: Ticker: {ticker}, Interval: {interval}, Range: [{start_date_str} to {end_date_str}], Table: {effective_table_name}")

        cached_df = pd.DataFrame()
        missing_dates = []

        try:
            start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date_obj = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError as e:
            print(f"ERROR [CACHE_CHECK_ERROR]: Invalid date format for ticker {ticker} ({interval}): {e}. Requested range: [{start_date_str}-{end_date_str}]")
            return pd.DataFrame(), []

        requested_dates_set = set()
        current_date_iter = start_date_obj
        while current_date_iter <= end_date_obj:
            requested_dates_set.add(current_date_iter.strftime("%Y-%m-%d"))
            current_date_iter += timedelta(days=1)

        query_start_ts = f"{start_date_str} 00:00:00"
        query_end_ts = (end_date_obj + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")

        query = f"""
        SELECT datetime, ticker, interval, open, high, low, close, volume FROM {effective_table_name}
        WHERE ticker = ? AND interval = ?
          AND datetime >= CAST(? AS TIMESTAMPTZ)
          AND datetime < CAST(? AS TIMESTAMPTZ)
        ORDER BY datetime ASC
        """

        num_found_rows = 0
        latest_timestamp_in_cache_str = 'N/A'

        try:
            with duckdb.connect(database=self.db_manager.db_path, config=self.db_manager.duckdb_config) as con:
                result_df = con.execute(query, [ticker, interval, query_start_ts, query_end_ts]).fetchdf()

            num_found_rows = len(result_df)
            if not result_df.empty and 'datetime' in result_df.columns:
                result_df['datetime'] = pd.to_datetime(result_df['datetime'])
                if result_df['datetime'].dt.tz is None:
                    result_df['datetime'] = result_df['datetime'].dt.tz_localize('UTC')
                else:
                    result_df['datetime'] = result_df['datetime'].dt.tz_convert('UTC')

                cached_df = result_df
                if not cached_df.empty:
                    latest_timestamp_in_cache = cached_df['datetime'].max()
                    latest_timestamp_in_cache_str = latest_timestamp_in_cache.strftime('%Y-%m-%d %H:%M:%S %Z') if pd.notnull(latest_timestamp_in_cache) else 'N/A'

                cached_dates_set = set(cached_df['datetime'].dt.strftime('%Y-%m-%d').unique())
                missing_dates_set = requested_dates_set - cached_dates_set
                missing_dates = sorted(list(missing_dates_set))
            else:
                missing_dates = sorted(list(requested_dates_set))

        except Exception as e:
            print(f"ERROR [CACHE_CHECK_DB_QUERY_FAILED]: DB query failed for ticker {ticker} ({interval}), table {effective_table_name}: {e}")
            missing_dates = sorted(list(requested_dates_set))
            cached_df = pd.DataFrame()
            num_found_rows = 0

        print(f"DEBUG [CACHE_CHECK_DB_RESULT]: Ticker: {ticker}, Interval: {interval}. Found {num_found_rows} existing rows. Latest timestamp in cache for this query: {latest_timestamp_in_cache_str}.")

        next_fetch_start_date_decision = min(missing_dates) if missing_dates else "N/A (no missing dates)"
        print(f"DEBUG [CACHE_CHECK_DECISION]: Ticker: {ticker}, Interval: {interval}. Missing {len(missing_dates)} dates ({missing_dates[:3]}{'...' if len(missing_dates)>3 else ''}). Decision: next fetch for this interval should target dates starting from: {next_fetch_start_date_decision}.")
        if not missing_dates:
             print(f"DEBUG [CACHE_CHECK_DECISION_DETAIL]: Ticker: {ticker}, Interval: {interval}. All requested dates [{start_date_str} to {end_date_str}] are present in cache for this interval.")

        return cached_df, missing_dates

    def hydrate_data_range(self, ticker: str, start_date_str: str, end_date_str: str, db_table_name: str = "market_ohlcv_data", force_refresh: bool = False) -> tuple[pd.DataFrame | None, dict]:
        print(f"===== 開始數據生產任務 (Producer): Ticker={ticker}, Range=[{start_date_str} to {end_date_str}], ForceRefresh={force_refresh}, Table={db_table_name} =====")
        overall_execution_log = {}
        try:
            start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date_obj = datetime.strptime(end_date_str, "%Y-%m-%d")
            request_date_objects = pd.date_range(start_date_obj, end_date_obj)
            request_date_range_str_list = [d.strftime("%Y-%m-%d") for d in request_date_objects]
        except ValueError as e:
            print(f"錯誤 (hydrate_data_range): 無效的 start_date_str 或 end_date_str: {e}")
            overall_execution_log["error"] = f"Invalid date range: {start_date_str} to {end_date_str}. Details: {e}"
            return None, overall_execution_log

        for date_str_in_range in request_date_range_str_list:
            overall_execution_log.setdefault(date_str_in_range, {}).setdefault(ticker, {
                "status": "pending", "interval": None, "count": 0, "message": "Awaiting processing"
            })

        if (end_date_obj - start_date_obj).days > 30:
            print(f"INFO: hydrate_data_range: Ticker={ticker}. Performing existence pre-flight check for historical range [{start_date_str} to {end_date_str}] (requested >30 days).")
            preflight_end_date_str = (end_date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
            preflight_data_1mo = self.fetch_single_chunk(ticker, start_date_str, preflight_end_date_str, '1mo')
            if preflight_data_1mo is None or preflight_data_1mo.empty:
                print(f"INFO: Pre-flight check for {ticker} from {start_date_str} to {end_date_str} (1mo) failed. Attempting secondary pre-flight with '1d'.")
                preflight_data_1d = self.fetch_single_chunk(ticker, start_date_str, preflight_end_date_str, '1d')
                if preflight_data_1d is None or preflight_data_1d.empty:
                    print(f"INFO: Secondary pre-flight check for {ticker} from {start_date_str} to {end_date_str} (1d) also failed. Skipping all intervals.")
                    for date_str_in_log_range in request_date_range_str_list:
                        overall_execution_log[date_str_in_log_range][ticker].update({
                            "status": "preflight_failed_empty_1mo_1d", "interval": "1mo_then_1d_preflight", "count": 0,
                            "message": f"Pre-flight checks for {ticker} over [{start_date_str}-{end_date_str}] returned no data with '1mo' and '1d'. Assuming no data in this historical range."})
                    print(f"===== 數據生產任務結束 (預檢 '1mo' 及 '1d' 均失敗): Ticker={ticker} =====")
                    return None, overall_execution_log
                else:
                    print(f"INFO: Secondary pre-flight check for {ticker} from {start_date_str} to {end_date_str} (1d) successful. Proceeding with detailed fetch using HISTORICAL_FALLBACK.")
            else:
                print(f"INFO: Pre-flight check for {ticker} from {start_date_str} to {end_date_str} (1mo) successful. Proceeding with detailed fetch.")

        request_start_date_actual = start_date_obj.date()
        thirty_days_ago_date = (datetime.now() - timedelta(days=30)).date()
        current_fallback_intervals = self.HISTORICAL_FALLBACK if request_start_date_actual < thirty_days_ago_date else self.FALLBACK_INTERVALS
        if request_start_date_actual < thirty_days_ago_date:
             print(f"INFO: hydrate_data_range: Ticker={ticker}. Request for historical data (start date {start_date_str} is older than 30 days). Using HISTORICAL_FALLBACK: {self.HISTORICAL_FALLBACK}")
        else:
             print(f"INFO: hydrate_data_range: Ticker={ticker}. Request for recent data (start date {start_date_str} is within 30 days). Using FALLBACK_INTERVALS: {self.FALLBACK_INTERVALS}")

        for interval in current_fallback_intervals:
            print(f"\nINFO: hydrate_data_range: Ticker={ticker}. 正在評估顆粒度 '{interval}' for range [{start_date_str} to {end_date_str}]...")
            if self.db_manager.check_no_data_record_exists(ticker=ticker, interval=interval, start_date=start_date_str, end_date=end_date_str, cooldown_days=self.no_data_cooldown_days):
                print(f"INFO: [數據偵查] Ticker={ticker}, Interval={interval} 的數據獲取已跳過 (請求範圍: {start_date_str} 至 {end_date_str})，因在最近 {self.no_data_cooldown_days} 天內曾記錄為無數據區塊。")
                for date_str_in_log_range in request_date_range_str_list:
                    if date_str_in_log_range in overall_execution_log and ticker in overall_execution_log[date_str_in_log_range]:
                        overall_execution_log[date_str_in_log_range][ticker].update({"status": "skipped_no_data_record", "interval": interval, "count": 0, "message": f"Skipped due to no-data record for interval {interval} covering range [{start_date_str}-{end_date_str}]."})
                continue

            chunk_size_days = self._get_chunk_size_for_interval(interval)
            if chunk_size_days <= 0: continue

            cached_df, missing_dates_list_for_current_interval = self.check_cache(ticker=ticker, start_date_str=start_date_str, end_date_str=end_date_str, interval=interval, table_name=db_table_name)

            missing_dates_list = []
            if force_refresh:
                print(f"INFO: hydrate_data_range: Ticker={ticker}, Interval={interval}. Force refresh ENABLED. Ignoring cache and fetching all dates in range.")
                missing_dates_list = request_date_range_str_list[:]
            else:
                truly_missing_dates = []
                if missing_dates_list_for_current_interval:
                    for date_to_check in missing_dates_list_for_current_interval:
                        if not self.db_manager.check_data_exists_for_date_and_ticker(ticker, date_to_check, table_name=db_table_name):
                            truly_missing_dates.append(date_to_check)
                        else:
                            print(f"INFO [HYDRATE_SKIP_DATE_PRE_EXISTING]: Ticker: {ticker}, Date: {date_to_check}. Data already exists (any interval). Skipping fetch for this date with interval {interval}.")
                            if date_to_check in overall_execution_log and ticker in overall_execution_log[date_to_check]:
                                overall_execution_log[date_to_check][ticker].update({"status": "cached_any_interval", "interval": interval, "message": f"Data for {date_to_check} already exists in DB (any interval), skipped for {interval}."})
                missing_dates_list = truly_missing_dates

                if cached_df is not None and not cached_df.empty:
                     if 'datetime' in cached_df.columns and pd.api.types.is_datetime64_any_dtype(cached_df['datetime']):
                        unique_cached_dates_current_interval = cached_df['datetime'].dt.normalize().unique()
                        for date_obj_in_cached_df in unique_cached_dates_current_interval:
                            log_date_str = date_obj_in_cached_df.strftime('%Y-%m-%d')
                            if log_date_str in overall_execution_log and ticker in overall_execution_log[log_date_str]:
                                if overall_execution_log[log_date_str][ticker].get("status") not in ["cached_any_interval"]:
                                    daily_rows_cached = cached_df[cached_df['datetime'].dt.date == date_obj_in_cached_df.date()]
                                    overall_execution_log[log_date_str][ticker].update({"status": "cached_current_interval", "interval": interval, "count": len(daily_rows_cached), "message": f"Data for {log_date_str} found in cache for current interval {interval} ({len(daily_rows_cached)} rows)."})

            if not force_refresh and not missing_dates_list:
                print(f"成功: hydrate_data_range: Ticker={ticker}, Interval={interval}. 所有請求數據 ({start_date_str} to {end_date_str}) 均已在快取中 (任何 interval) 或此 interval 無需獲取。")
                for log_date_str in request_date_range_str_list:
                    if overall_execution_log[log_date_str][ticker]['status'] not in ["cached_any_interval", "cached_current_interval", "cached_full_range_verified_after_filter", "success_producer"]: # Avoid overwriting more specific cache statuses
                         overall_execution_log[log_date_str][ticker].update({"status": "cached_full_range_verified_after_filter", "interval": interval, "count": 0, "message": f"Verified full cache hit for {log_date_str} with {interval} after checking for any existing data."})
                print(f"===== 數據生產任務結束 (完全快取命中或無需獲取): Ticker={ticker}, Interval={interval} =====")
                return None, overall_execution_log

            if missing_dates_list:
                if not force_refresh: print(f"INFO: hydrate_data_range: Ticker={ticker}, Interval={interval}. 過濾後仍缺失 {len(missing_dates_list)} 天的數據 ({missing_dates_list[:3]}{'...' if len(missing_dates_list)>3 else ''})。準備從 API 獲取...")
            else:
                 if not force_refresh:
                    for log_date_str in request_date_range_str_list:
                        if overall_execution_log[log_date_str][ticker]['status'] in ['pending']:
                             overall_execution_log[log_date_str][ticker].update({"status": "no_data_for_interval_final", "interval": interval, "count": 0, "message": f"No data ultimately found or fetched for {log_date_str} with {interval} (empty cache, no missing dates reported after filter)."})
                    print(f"===== 數據生產任務結束 (無數據): Ticker={ticker}, Interval={interval} =====")
                    return None, overall_execution_log

            missing_date_ranges = _convert_missing_dates_to_ranges(missing_dates_list)
            all_missing_ranges_processed_successfully_for_interval = True

            for range_idx, (range_start_str, range_end_str) in enumerate(missing_date_ranges):
                print(f"INFO: hydrate_data_range: Ticker={ticker}, Interval={interval}. Fetching missing range {range_idx+1}/{len(missing_date_ranges)}: [{range_start_str} to {range_end_str}]")
                date_chunks_for_missing_range = self._split_date_range_into_chunks(range_start_str, range_end_str, chunk_size_days)
                if not date_chunks_for_missing_range:
                    print(f"警告: hydrate_data_range: Ticker={ticker}, Interval={interval}. 無法為缺失日期範圍 [{range_start_str}-{range_end_str}] 生成有效日期區塊。此顆粒度嘗試終止。")
                    all_missing_ranges_processed_successfully_for_interval = False; break

                current_range_all_chunks_dfs = [] # Collect DFs for current range before putting to queue
                current_range_fetch_ok_for_all_chunks = True

                for chunk_idx, (chunk_start_str, chunk_end_exclusive_str) in enumerate(date_chunks_for_missing_range):
                    print(f"INFO: hydrate_data_range: Ticker={ticker}, Interval={interval}. Processing chunk {chunk_idx+1}/{len(date_chunks_for_missing_range)} for missing range: [{chunk_start_str} to {chunk_end_exclusive_str} exclusive]")
                    chunk_start_date_obj_for_check = datetime.strptime(chunk_start_str, "%Y-%m-%d").date()
                    if interval == '1m' and chunk_start_date_obj_for_check < thirty_days_ago_date:
                        print(f"INFO: hydrate_data_range: Ticker={ticker}. Chunk [{chunk_start_str} to {chunk_end_exclusive_str}) for '1m' data is outside 30-day window. Skipping this chunk for '1m'.")
                        # This chunk is skipped, but it doesn't mean the whole range or interval fails.
                        # Log skip for affected dates in chunk
                        temp_log_date = datetime.strptime(chunk_start_str, "%Y-%m-%d")
                        temp_log_end_date_obj = datetime.strptime(chunk_end_exclusive_str, "%Y-%m-%d") - timedelta(days=1)
                        while temp_log_date.date() <= temp_log_end_date_obj.date():
                            log_d_str = temp_log_date.strftime("%Y-%m-%d")
                            if log_d_str in overall_execution_log and ticker in overall_execution_log[log_d_str] and \
                               overall_execution_log[log_d_str][ticker]['status'] not in ['success_producer', 'cached_any_interval', 'cached_current_interval', 'cached_full_range_verified_after_filter']:
                                overall_execution_log[log_d_str][ticker].update({"status": "skipped_1m_api_due_to_30day_limit", "interval": "1m", "count": 0, "message": f"API fetch for 1m data on {log_d_str} skipped (30-day limit)."})
                            temp_log_date += timedelta(days=1)
                        continue # Skip this chunk, proceed to next chunk in the same range

                    chunk_df = self.fetch_single_chunk(ticker, chunk_start_str, chunk_end_exclusive_str, interval)

                    temp_log_date = datetime.strptime(chunk_start_str, "%Y-%m-%d")
                    temp_log_end_date_obj = datetime.strptime(chunk_end_exclusive_str, "%Y-%m-%d") - timedelta(days=1)
                    while temp_log_date.date() <= temp_log_end_date_obj.date():
                        log_d_str = temp_log_date.strftime("%Y-%m-%d")
                        if log_d_str in overall_execution_log and ticker in overall_execution_log[log_d_str] and \
                           overall_execution_log[log_d_str][ticker]['status'] not in ['success_producer', 'cached_any_interval', 'cached_current_interval', 'cached_full_range_verified_after_filter', 'skipped_1m_api_due_to_30day_limit'] :
                            if chunk_df is not None and not chunk_df.empty:
                                daily_rows_in_fetched_chunk = chunk_df[chunk_df['datetime'].dt.date == temp_log_date.date()]
                                overall_execution_log[log_d_str][ticker].update({"status": "api_success_chunk_data_found", "interval": interval, "count": len(daily_rows_in_fetched_chunk), "message": f"API fetched {len(daily_rows_in_fetched_chunk)} rows for {log_d_str} with {interval}."})
                            else:
                                overall_execution_log[log_d_str][ticker].update({"status": "api_chunk_no_data", "interval": interval, "count": 0, "message": f"API fetch for chunk covering {log_d_str} with {interval} returned no data or failed."})
                        temp_log_date += timedelta(days=1)

                    if chunk_df is not None and not chunk_df.empty:
                        current_range_all_chunks_dfs.append(chunk_df)
                    elif chunk_df is None: # fetch_single_chunk indicated an unrecoverable error for this chunk
                        print(f"ERROR: hydrate_data_range: Fetching chunk for {ticker} ({interval}) from {chunk_start_str} to {chunk_end_exclusive_str} failed (returned None). Aborting this interval for this range.")
                        current_range_fetch_ok_for_all_chunks = False
                        break

                if not current_range_fetch_ok_for_all_chunks:
                    all_missing_ranges_processed_successfully_for_interval = False
                    break

                if current_range_all_chunks_dfs:
                    single_missing_range_df = pd.concat(current_range_all_chunks_dfs, ignore_index=True)
                    if not single_missing_range_df.empty:
                        print(f"INFO: hydrate_data_range: Ticker={ticker}, Interval={interval}. 將 {len(single_missing_range_df)} 筆新獲取的數據放入佇列，針對合併後的範圍 [{range_start_str}-{range_end_str}]。")
                        data_to_queue = {'ticker': ticker, 'interval': interval, 'data': single_missing_range_df, 'table_name': db_table_name}
                        self.data_queue.put(data_to_queue)
                elif current_range_fetch_ok_for_all_chunks and not current_range_all_chunks_dfs:
                     print(f"INFO: hydrate_data_range: Ticker={ticker}, Interval={interval}. Missing range [{range_start_str}-{range_end_str}] processed, all chunks yielded no data (likely weekends/holidays for this interval).")

            if not all_missing_ranges_processed_successfully_for_interval:
                 print(f"INFO: hydrate_data_range: Ticker={ticker}. 顆粒度 '{interval}' 未能成功獲取所有缺失數據。嘗試下一個更粗的顆粒度。")
                 for log_date_str in request_date_range_str_list:
                    log_entry = overall_execution_log.get(date_str_in_log_range, {}).get(ticker, {})
                    current_status = log_entry.get("status", "pending")
                    if force_refresh or current_status not in ['success_producer', 'cached_any_interval', 'cached_full_range_verified_after_filter', 'skipped_no_data_record']:
                        existing_message = log_entry.get("message", "")
                        failure_message_part = f" Interval {interval} failed to provide complete data for {log_date_str}."
                        if failure_message_part not in existing_message : existing_message += failure_message_part
                        overall_execution_log[log_date_str][ticker].update({"status": f"failed_interval_{interval}", "message": existing_message })
                 time.sleep(0.5)
                 continue

            # If we reach here, all_missing_ranges_processed_successfully_for_interval is True for the current interval
            print(f"INFO: hydrate_data_range: Ticker={ticker}, Interval={interval}. All missing date ranges for this interval processed successfully (data queued or confirmed no data). Ending attempts for this ticker.")
            for date_str_in_log_range in request_date_range_str_list:
                log_entry = overall_execution_log.get(date_str_in_log_range, {}).get(ticker, {})
                current_status = log_entry.get("status", "pending")
                # If status is still related to API fetching for this interval, or pending, mark as success_producer
                if "api_success" in current_status or current_status == "pending" or "cached_current_interval" == current_status :
                    if not log_entry.get("message","").startswith("Data for"):
                        overall_execution_log[date_str_in_log_range][ticker].update({
                            "status": "success_producer",
                            "interval": log_entry.get("interval", interval),
                            "count": log_entry.get("count", ">0"),
                            "message": f"Data for {date_str_in_log_range} with {log_entry.get('interval', interval)} ({log_entry.get('count',0 if current_status == 'api_chunk_no_data' else '>0')} rows) processed by producer (queued or cached)."
                        })
            print(f"===== 數據生產任務 (Producer) 結束 (成功或已處理): Ticker={ticker}, Interval={interval} =====")
            return None, overall_execution_log

        print(f"錯誤: hydrate_data_range: Ticker={ticker}. 所有降級顆粒度 {current_fallback_intervals} 均無法為 [{start_date_str} to {end_date_str}] 回填完整數據。")
        print(f"===== 數據生產任務結束 (所有 Interval 均失敗): Ticker={ticker} =====")
        for log_date_str in request_date_range_str_list:
            log_entry = overall_execution_log.get(date_str_in_log_range, {}).get(ticker, {})
            final_status = log_entry.get("status", "unknown")
            if 'success_producer' not in final_status and 'cached_any_interval' not in final_status and 'cached_full_range_verified_after_filter' not in final_status and 'skipped_no_data_record' not in final_status and 'preflight_failed' not in final_status:
                 current_message = log_entry.get("message","")
                 all_fail_msg_part = f" All intervals failed for {log_date_str}."
                 if all_fail_msg_part not in current_message: current_message += all_fail_msg_part
                 overall_execution_log[log_date_str][ticker].update({ "status": "failed_all_intervals", "interval": None, "count": 0, "message": current_message})
        return None, overall_execution_log

if __name__ == '__main__':
    print("--- YFinanceClient (Daily Market Analyzer) 測試 ---")
    # Example usage (requires DBManager instance and a queue)
    # from db_manager import DBManager
    # test_q = queue.Queue()
    # db_man = DBManager("data_workspace/temp/test_yfc_main.duckdb", target_ohlcv_table_name="test_market_data")
    # client = YFinanceClient(db_manager=db_man, data_queue=test_q)
    # _, log = client.hydrate_data_range("AAPL", "2024-07-01", "2024-07-02", db_table_name="test_market_data")
    # print("Execution Log:", log)
    # while not test_q.empty():
    #    print("Queued item:", test_q.get())
    print("INFO: __main__ 測試部分需要 DBManager 實例和佇列。請通過整合測試來驗證 YFinanceClient。")
    print("--- YFinanceClient (Daily Market Analyzer) __main__ 測試部分已簡化/跳過 ---")
