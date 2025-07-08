# -*- coding: utf-8 -*-
"""
YFinanceHydrator - 新一代數據回填引擎
======================================

核心功能：
1.  本地快取優先：基於 CacheIndex 判斷是否需要請求數據。
2.  時間分塊 (Chunking)：將長的時間範圍切為 API 允許的小塊。
3.  智能降級回溯：從最精細的數據顆粒度開始嘗試，失敗則嘗試更粗的顆粒度。
4.  失敗記憶：將 API 的失敗或無數據結果記錄到 CacheIndex。
5.  與 DBManager 整合，進行數據存儲和快取狀態管理。
"""
import yfinance as yf
import pandas as pd
import time
import os
import hashlib
from datetime import datetime, timedelta, date as date_obj
# 假設 DBManager 在同一級目錄或PYTHONPATH可找到
# from apps.daily_market_analyzer.db_manager import DBManager
# 為了在目前結構下直接引用，可能需要調整路徑或依賴注入方式
# 暫時假設 db_manager 會被正確傳入

class YFinanceHydrator:
    """
    YFinanceHydrator 類別，負責高效回填 yfinance 數據。
    """
    # 參考 YFinanceClient，但這裡的 FALLBACK_INTERVALS 是給 hydrate_day 使用的
    # 我們可以只定義一個標準的回溯列表，因為 hydrate_day 是針對單日數據
    # 歷史或近期數據的判斷可以在調用 hydrate_day 之前處理，或者 hydrate_day 內部根據日期智能選擇策略
    FALLBACK_INTERVALS = ['1m', '5m', '15m', '30m', '1h', '1d']
    # HISTORICAL_FALLBACK = ['1d', '1wk', '1mo'] # 考慮是否在 hydrate_day 內部根據日期切換

    def __init__(self, db_manager, yf_ticker_override: yf.Ticker | None = None):
        """
        初始化 YFinanceHydrator。

        Args:
            db_manager (DBManager): DBManager 的實例，用於資料庫操作。
            yf_ticker_override (yf.Ticker | None, optional): 用於測試時注入 mock 的 yf.Ticker。
        """
        self.db_manager = db_manager
        self._yf_ticker_override = yf_ticker_override # 用於測試注入
        print(f"INFO: YFinanceHydrator (普羅米修斯·重生 v33.0) 初始化完畢。回溯精度列表: {self.FALLBACK_INTERVALS}")

    def _create_request_hash(self, ticker: str) -> str:
        """
        為給定的 ticker 生成 request_hash (用於 CacheIndex)。
        目前採用 md5(ticker)。
        """
        return hashlib.md5(ticker.encode()).hexdigest()

    def _get_chunk_size_for_interval(self, interval: str) -> int:
        """
        (移植自 YFinanceClient)
        根據數據顆粒度 (interval) 返回 yfinance API 建議的單次請求最大天數 (chunk size)。
        注意：這些值是基於 yfinance 的限制，可能需要根據實際情況調整。
        '1m' data is limited to 7 days.
        '2m', '5m', '15m', '30m' data is limited to 60 days.
        '60m', '1h' data is limited to 730 days.
        '1d' and greater can be unlimited historically but practically chunked for stability.
        """
        if interval == '1m': return 7 # yfinance '1m' data is limited to 7 days for a single request
        elif interval in ['2m', '5m', '15m', '30m']: return 60 # Limited to 60 days
        elif interval in ['60m', '90m', '1h']: return 730 # Limited to 730 days
        # For daily and above, yfinance doesn't have a strict small limit like intraday.
        # However, chunking large historical requests is still a good practice.
        elif interval in ['1d', '5d', '1wk']: return 365 * 2 # e.g., 2 years of daily data
        elif interval in ['1mo', '3mo']: return 365 * 10 # e.g., 10 years of monthly data
        else:
            print(f"警告 (YFinanceHydrator): 未知的 interval '{interval}'，預設 chunk_size_days 為 30。")
            return 30

    def _split_date_range_into_chunks(self, start_date_str: str, end_date_str: str, chunk_size_days: int) -> list[tuple[str, str]]:
        """
        (移植自 YFinanceClient)
        將指定的日期範圍，根據 chunk_size_days 切分為多個小的时间區塊。
        yfinance 的 end date 是 exclusive，所以處理時要注意。

        Args:
            start_date_str (str): 開始日期 (YYYY-MM-DD)。
            end_date_str (str): 結束日期 (YYYY-MM-DD)。
            chunk_size_days (int): 每個區塊的天數。

        Returns:
            list[tuple[str, str]]: 一個包含 (chunk_start_date, chunk_end_date_exclusive) 的列表。
                                   chunk_end_date_exclusive 是 yfinance history 所需的結束日期 (不包含)。
        """
        chunks = []
        try:
            current_start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            final_end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError as e:
            print(f"錯誤 (YFinanceHydrator - _split_date_range_into_chunks): 日期格式錯誤 ({start_date_str}, {end_date_str})。應為 YYYY-MM-DD。 {e}")
            return []

        if chunk_size_days <= 0:
            print(f"錯誤 (YFinanceHydrator - _split_date_range_into_chunks): chunk_size_days ({chunk_size_days}) 必須為正數。")
            return []

        while current_start_date <= final_end_date:
            # chunk_end_date is inclusive for the period we want data for
            chunk_end_date_inclusive = current_start_date + timedelta(days=chunk_size_days - 1)
            if chunk_end_date_inclusive > final_end_date:
                chunk_end_date_inclusive = final_end_date

            # yfinance end_date is exclusive, so add one day to the inclusive end_date
            yfinance_exclusive_end_date = chunk_end_date_inclusive + timedelta(days=1)

            chunks.append((current_start_date.strftime("%Y-%m-%d"),
                           yfinance_exclusive_end_date.strftime("%Y-%m-%d")))
            current_start_date = chunk_end_date_inclusive + timedelta(days=1)
        return chunks

    def _fetch_data_for_day_and_interval(self, ticker_str: str, target_date_str: str, interval: str) -> tuple[str, pd.DataFrame | None, str | None]:
        """
        為指定的 ticker、單獨一天 (target_date_str) 和 interval 獲取數據。

        Args:
            ticker_str (str): 股票代碼。
            target_date_str (str): 目標日期 (YYYY-MM-DD)。
            interval (str): 數據精度 (e.g., '1m', '1d')。

        Returns:
            tuple[str, pd.DataFrame | None, str | None]: 包含狀態、數據和訊息的元組。
                - status (str): 'SUCCESS', 'NO_DATA_API', 'API_ERROR', 'INVALID_DATE_FORMAT', 'RESTRICTION_SKIP'.
                - data (pd.DataFrame | None): 成功時為 DataFrame，否則為 None。
                - message (str | None): 相關訊息，特別是錯誤時。
        """
        try:
            target_d = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except ValueError:
            msg = f"無效的日期格式 {target_date_str} for ticker {ticker_str}。"
            print(f"錯誤 (YFinanceHydrator - _fetch_data_for_day_and_interval): {msg}")
            return "INVALID_DATE_FORMAT", None, msg

        if interval == '1m':
            # 考慮到 yfinance 的限制，1m 數據通常只在最近30-60天內可用
            # 此處使用30天作為一個較為保守的閾值
            # 注意：yf.Ticker().history() 对于非常久遠的1m數據會直接返回空，而不是拋錯
            # 所以這個檢查主要是為了提前告知並減少不必要的API調用
            limit_days = 30
            # 如果 target_d 是 datetime.date, datetime.now() 是 datetime.datetime
            # 需要將 datetime.now() 轉換為 date 進行比較
            if target_d < (datetime.now().date() - timedelta(days=limit_days)):
                msg = f"Ticker {ticker_str} 的 '1m' 數據請求日期 {target_date_str} 超過 {limit_days} 天限制，通常無法獲取。跳過此 API 請求。"
                print(f"資訊 (YFinanceHydrator - _fetch_data_for_day_and_interval): {msg}")
                return "RESTRICTION_SKIP", None, msg

        fetch_start_date = target_d.strftime("%Y-%m-%d")
        fetch_end_date = (target_d + timedelta(days=1)).strftime("%Y-%m-%d") # yfinance end is exclusive

        print(f"INFO (YFinanceHydrator): 正在嘗試獲取 {ticker_str} 在 {target_date_str} 的 {interval} 數據 (API請求範圍: {fetch_start_date} to {fetch_end_date})")

        try:
            if self._yf_ticker_override: # 主要用於測試
                stock = self._yf_ticker_override
            else:
                stock = yf.Ticker(ticker_str)

            data = stock.history(start=fetch_start_date, end=fetch_end_date, interval=interval,
                                 auto_adjust=True, prepost=False, raise_errors=False) # raise_errors=False 讓yfinance返回空df而不是拋錯

            if data is None or data.empty:
                msg = f"yfinance回報 {ticker_str} 在 {target_date_str} ({interval}) 無交易數據。可能原因：市場假日、非交易時段或該精度無數據。"
                print(f"INFO (YFinanceHydrator): {msg}")
                return "NO_DATA_API", None, msg

            # 標準化 DataFrame (類似 YFinanceClient 中的 fetch_single_chunk)
            if isinstance(data.index, pd.DatetimeIndex):
                data = data.reset_index()

            # 檢查是否有 'Datetime' 或 'Date' 欄位
            if 'Datetime' in data.columns:
                data.rename(columns={'Datetime': 'datetime'}, inplace=True)
            elif 'Date' in data.columns: # 有些 interval (如 '1d') 可能返回 'Date'
                data.rename(columns={'Date': 'datetime'}, inplace=True)

            if 'datetime' not in data.columns:
                msg = f"標準化後 DataFrame 缺少 'datetime' 欄位。Ticker: {ticker_str}, Interval: {interval}。可用欄位: {data.columns.tolist()}"
                print(f"錯誤 (YFinanceHydrator): {msg}")
                return "API_ERROR", None, msg # 視為一種API錯誤，因為數據格式不符預期

            data.columns = [col.lower() for col in data.columns]

            try:
                data['datetime'] = pd.to_datetime(data['datetime'])
                if data['datetime'].dt.tz is None:
                    data['datetime'] = data['datetime'].dt.tz_localize('America/New_York') # 假設為美股時區，然後轉UTC
                data['datetime'] = data['datetime'].dt.tz_convert('UTC')
            except Exception as e:
                msg = f"轉換 'datetime' 欄位時出錯: {e}. Ticker: {ticker_str}, Interval: {interval}."
                print(f"錯誤 (YFinanceHydrator): {msg}")
                return "API_ERROR", None, msg

            if 'volume' not in data.columns: data['volume'] = 0
            data['volume'] = data['volume'].fillna(0).astype('int64')
            data['interval'] = interval
            data['ticker'] = ticker_str # 確保 ticker 欄位存在

            # 確保OHLC欄位存在，如果不存在則填充0 (對於某些非常特殊的case)
            ohlc_cols = ['open', 'high', 'low', 'close']
            for col in ohlc_cols:
                if col not in data.columns:
                    print(f"警告 (YFinanceHydrator): DataFrame 缺少OHLC欄位 '{col}' for {ticker_str} ({interval}) on {target_date_str}. 將填充為0.")
                    data[col] = 0.0

            # 過濾掉非目標日期的數據 (yfinance 有時會返回請求範圍外的數據，特別是對於日線等級)
            data = data[data['datetime'].dt.date == target_d].copy() # 使用 .copy() 避免 SettingWithCopyWarning

            if data.empty:
                msg = f"標準化並過濾日期後，{ticker_str} 在 {target_date_str} ({interval}) 無有效數據 (可能API返回了鄰近日期數據，但目標日無數據)。"
                print(f"INFO (YFinanceHydrator): {msg}")
                return "NO_DATA_API", None, msg

            final_columns = ['datetime', 'ticker', 'interval', 'open', 'high', 'low', 'close', 'volume']
            try:
                data = data[final_columns]
            except KeyError as e:
                msg = f"選取最終欄位時發生 KeyError: {e}。Ticker: {ticker_str}, Interval: {interval}。可用欄位: {data.columns.tolist()}"
                print(f"錯誤 (YFinanceHydrator): {msg}")
                return "API_ERROR", None, msg

            msg = f"成功獲取並標準化 {ticker_str} 在 {target_date_str} ({interval}) 的 {len(data)} 筆數據。"
            print(f"INFO (YFinanceHydrator): {msg}")
            return "SUCCESS", data, msg

        except Exception as e:
            msg = f"抓取或處理 {ticker_str} ({interval}, {target_date_str}) 時發生未預期異常: {type(e).__name__} - {e}"
            print(f"嚴重錯誤 (YFinanceHydrator - _fetch_data_for_day_and_interval): {msg}")
            # import traceback # 開發時調試用
            # traceback.print_exc()
            return "API_ERROR", None, msg

    def hydrate_day(self, ticker: str, date_str: str, force_refresh: bool = False) -> None:
        """
        核心方法：為指定的 ticker 和 date 回填數據。

        1.  查詢 CacheIndex 檢查狀態。若為 SUCCESS/NO_DATA 且非 force_refresh，則跳過。
        2.  若需獲取，則遍歷 FALLBACK_INTERVALS：
            a.  調用 _fetch_data_for_day_and_interval 獲取數據。
            b.  若成功：
                i.  存入 MarketPrices_Daily (表名根據 DBManager 配置)。
                ii. 更新 CacheIndex (status='SUCCESS', final_interval=current_interval)。
                iii.結束。
            c.  若API回報無數據 (fetch 返回 None 但非 Exception)：繼續下一個 interval。
            d.  若API調用失敗 (fetch 拋出 Exception 或返回 None 代表嚴重錯誤)：
                i.  更新 CacheIndex (status='API_FAILURE', message=error)。
                ii. 可選擇是否繼續下一個 interval (目前策略：是，除非是致命錯誤)。
        3.  若所有 interval 嘗試完畢仍未成功：
            a.  如果所有嘗試都是「無數據」，則 CacheIndex status='NO_DATA'。
            b.  如果中間有 API_FAILURE，則最終狀態可能是 API_FAILURE。
        """
        print(f"===== YFinanceHydrator: 開始回填任務 for Ticker={ticker}, Date={date_str}, ForceRefresh={force_refresh} =====")
        request_hash = self._create_request_hash(ticker)

        # 確保 DBManager 使用的表名是正確的
        # 作戰計畫書指定 MarketPrices_Daily，而 YFinanceClient 範例用的是 market_ohlcv_analyzer
        # 此處假設 DBManager 內部知道要寫入哪個表，或者 YFinanceHydrator 初始化時指定
        ohlcv_table_name = self.db_manager.ohlcv_table_name # 使用 DBManager 實例中配置的表名

        if not force_refresh:
            cached_status_info = self.db_manager.check_request_status(request_hash, date_str)
            if cached_status_info:
                status = cached_status_info['status']
                if status == "SUCCESS":
                    print(f"INFO (YFinanceHydrator): Ticker={ticker}, Date={date_str} 快取命中 (Status: SUCCESS, Interval: {cached_status_info.get('final_interval', 'N/A')})。跳過網路請求。")
                    return
                elif status == "NO_DATA":
                    print(f"INFO (YFinanceHydrator): Ticker={ticker}, Date={date_str} 快取命中 (Status: NO_DATA)。跳過網路請求。")
                    return
                elif status == "API_FAILURE":
                    # 根據策略，API_FAILURE 可能也需要重試，除非時間很近
                    # 這裡簡化為如果存在就先信任，除非 force_refresh
                    # last_attempt_dt = cached_status_info.get('last_attempt')
                    # if last_attempt_dt and (datetime.now(timezone.utc) - last_attempt_dt) < timedelta(hours=1): # 1小時內不再重試
                    #     print(f"INFO (YFinanceHydrator): Ticker={ticker}, Date={date_str} 快取命中 (Status: API_FAILURE within cooldown)。跳過網路請求。")
                    #     return
                    print(f"INFO (YFinanceHydrator): Ticker={ticker}, Date={date_str} 快取狀態為 API_FAILURE。將嘗試重新獲取。")


        attempt_had_api_error = False
        first_api_error_message = None # 用於存儲第一個遇到的 API 錯誤訊息
        last_attempt_message = "未開始嘗試" # 用於記錄最後一次嘗試的訊息（無論成功失敗）

        for interval in self.FALLBACK_INTERVALS:
            print(f"INFO (YFinanceHydrator): Ticker={ticker}, Date={date_str}。嘗試 Interval: {interval}")

            fetch_status, daily_data_df, fetch_message = self._fetch_data_for_day_and_interval(ticker, date_str, interval)

            # 更新 last_attempt_message 以反映當前 interval 的嘗試結果
            current_attempt_summary = fetch_message or f"Interval {interval} 嘗試完成，狀態: {fetch_status}"
            last_attempt_message = current_attempt_summary # 總是更新為最新的嘗試訊息

            if fetch_status == "SUCCESS":
                if daily_data_df is not None and not daily_data_df.empty:
                    print(f"INFO (YFinanceHydrator): Ticker={ticker}, Date={date_str}, Interval={interval}。成功獲取 {len(daily_data_df)} 筆數據。")
                    try:
                        self.db_manager.upsert_data(daily_data_df, table_name=ohlcv_table_name)
                        print(f"INFO (YFinanceHydrator): Ticker={ticker}, Date={date_str}, Interval={interval}。數據成功存入資料庫表 {ohlcv_table_name}。")

                        self.db_manager.update_cache_index(
                            request_hash=request_hash, date_str=date_str, status="SUCCESS",
                            final_interval=interval, message=fetch_message # 使用從 fetch 返回的詳細成功訊息
                        )
                        print(f"INFO (YFinanceHydrator): Ticker={ticker}, Date={date_str}。CacheIndex 更新為 SUCCESS (Interval: {interval})。任務完成。")
                        return
                    except Exception as e_db:
                        error_msg = f"資料庫錯誤 on {interval} for {ticker}@{date_str}: {str(e_db)}"
                        print(f"CRITICAL (YFinanceHydrator): {error_msg}")
                        self.db_manager.update_cache_index(
                            request_hash=request_hash, date_str=date_str, status="API_FAILURE",
                            message=error_msg
                        )
                        print(f"INFO (YFinanceHydrator): Ticker={ticker}, Date={date_str}。因資料庫錯誤，CacheIndex 更新為 API_FAILURE。任務終止。")
                        return
                else:
                    print(f"警告 (YFinanceHydrator): Ticker={ticker}, Date={date_str}, Interval={interval}。Fetch status 為 SUCCESS 但數據為空。視為 API 錯誤。")
                    attempt_had_api_error = True
                    if first_api_error_message is None:
                        first_api_error_message = f"Interval {interval} status SUCCESS but no data."
                    # last_attempt_message 已被 current_attempt_summary 更新

            elif fetch_status == "NO_DATA_API":
                print(f"INFO (YFinanceHydrator): Ticker={ticker}, Date={date_str}, Interval={interval}。API回報無數據。嘗試下一個精度。")
                continue

            elif fetch_status == "API_ERROR":
                print(f"警告 (YFinanceHydrator): Ticker={ticker}, Date={date_str}, Interval={interval}。獲取數據時發生API錯誤: {fetch_message}。嘗試下一個精度。")
                attempt_had_api_error = True
                if first_api_error_message is None: # 只記錄第一個詳細的 API 錯誤訊息
                    first_api_error_message = fetch_message
                continue

            elif fetch_status == "INVALID_DATE_FORMAT":
                # 這種情況通常在 hydrate_day 開始時就應該被 CacheIndex 捕捉 (如果之前已嘗試過)
                # 或者這是首次嘗試就日期格式錯誤，直接更新 CacheIndex 並終止
                self.db_manager.update_cache_index(
                    request_hash=request_hash, date_str=date_str, status="API_FAILURE", # 或更具體的 "INVALID_INPUT"
                    message=fetch_message
                )
                print(f"ERROR (YFinanceHydrator): Ticker={ticker}, Date={date_str}。因日期格式無效，CacheIndex 更新為 API_FAILURE。任務終止。")
                return

            elif fetch_status == "RESTRICTION_SKIP":
                # 例如 '1m' 數據太舊被跳過，這類似於 NO_DATA_API 的情況
                print(f"INFO (YFinanceHydrator): Ticker={ticker}, Date={date_str}, Interval={interval}。因API限制跳過獲取 ({fetch_message})。嘗試下一個精度。")
                # last_attempt_message 已在上面更新
                continue

            else: # 未知 fetch_status
                print(f"警告 (YFinanceHydrator): Ticker={ticker}, Date={date_str}, Interval={interval}。未知的獲取狀態: {fetch_status}。訊息: {fetch_message}。視為API錯誤。")
                attempt_had_api_error = True
                # last_attempt_message 已在上面更新
                continue

        # 循環結束後，如果沒有成功獲取數據 (即沒有在循環中 return)
        final_cache_status = "NO_DATA" # 預設為 NO_DATA
        final_cache_message = f"所有嘗試的精度 ({', '.join(self.FALLBACK_INTERVALS)}) 均未能獲取數據。最後一次嘗試 ({self.FALLBACK_INTERVALS[-1] if self.FALLBACK_INTERVALS else 'N/A'}) 訊息: {last_attempt_message}"

        if attempt_had_api_error:
            final_cache_status = "API_FAILURE"
            if first_api_error_message: # 如果記錄了首個API錯誤，使用它作為主要訊息
                final_cache_message = f"一個或多個精度獲取失敗。首個API錯誤訊息: {first_api_error_message}. 最後嘗試訊息: {last_attempt_message}"
            else: # 應該不會到這裡，因為 attempt_had_api_error=True 意味著 first_api_error_message 應該被設置
                final_cache_message = f"一個或多個精度獲取失敗 (未捕獲到詳細的首個錯誤訊息)。最後嘗試訊息: {last_attempt_message}"

        self.db_manager.update_cache_index(
            request_hash=request_hash,
            date_str=date_str,
            status=final_cache_status,
            message=final_cache_message
        )
        print(f"INFO (YFinanceHydrator): Ticker={ticker}, Date={date_str}。所有精度嘗試完畢。CacheIndex 更新為 {final_cache_status}。")
        print(f"===== YFinanceHydrator: 回填任務結束 for Ticker={ticker}, Date={date_str} =====")

# 命令行測試接口 (可選)
if __name__ == '__main__':
    print("--- YFinanceHydrator 命令行測試介面 ---")
    # 這裡需要一個實際的 DBManager 實例
    # from apps.daily_market_analyzer.db_manager import DBManager # 假設路徑正確
    # test_db_path = "data_workspace/temp/test_hydrator.duckdb"
    # if os.path.exists(test_db_path):
    #     os.remove(test_db_path)
    # print(f"測試資料庫路徑: {test_db_path}")
    # db_man = DBManager(db_path=test_db_path, target_ohlcv_table_name="MarketPrices_Daily_Test")

    # hydrator = YFinanceHydrator(db_manager=db_man)

    # 測試用例:
    # 1. 請求一個最近的交易日 (e.g., AAPL, yesterday)
    #    - 首次請求: 應從 API 獲取，存入 DB，更新 CacheIndex
    #    - 再次請求: 應從 CacheIndex (SUCCESS) 直接返回
    # print("\n--- 測試案例 1: 最近交易日 (AAPL) ---")
    # today = datetime.now().date()
    # # 找到最近的工作日 (粗略，不考慮假日)
    # if today.weekday() == 5: # 週六
    #     recent_trade_date = today - timedelta(days=1)
    # elif today.weekday() == 6: # 週日
    #     recent_trade_date = today - timedelta(days=2)
    # else: # 工作日
    #     recent_trade_date = today - timedelta(days=1) # 假設昨天數據已可用
    # recent_trade_date_str = recent_trade_date.strftime("%Y-%m-%d")

    # print(f"測試日期: {recent_trade_date_str} for AAPL")
    # hydrator.hydrate_day("AAPL", recent_trade_date_str, force_refresh=True) # 首次強制刷新
    # hydrator.hydrate_day("AAPL", recent_trade_date_str) # 第二次應快取命中

    # 2. 請求一個已知的市場假日 (e.g., 2024-01-01 for US markets)
    #    - 首次請求: 應嘗試所有 interval，最終記錄 NO_DATA
    #    - 再次請求: 應從 CacheIndex (NO_DATA) 直接返回
    # print("\n--- 測試案例 2: 市場假日 (GOOG, 2024-01-01) ---")
    # holiday_date_str = "2024-01-01"
    # hydrator.hydrate_day("GOOG", holiday_date_str, force_refresh=True)
    # hydrator.hydrate_day("GOOG", holiday_date_str)

    # 3. 請求一個不存在的 Ticker
    # print("\n--- 測試案例 3: 不存在的 Ticker (NONEXISTENTTICKER) ---")
    # hydrator.hydrate_day("NONEXISTENTTICKER", recent_trade_date_str, force_refresh=True)
    # hydrator.hydrate_day("NONEXISTENTTICKER", recent_trade_date_str)

    # if os.path.exists(test_db_path):
    #     print(f"測試完畢，測試資料庫 {test_db_path} 內容可供檢查。")
    #     # os.remove(test_db_path) # 可以選擇是否在測試後刪除
    print("請注意：YFinanceHydrator 的 __main__ 區塊需要手動配置 DBManager 實例並取消註釋測試代碼才能運行。")
    print("建議使用 pytest 進行單元測試和整合測試。")

# TODO:
# - _convert_missing_dates_to_ranges 的移植 (如果 YFinancePulseEngine 需要)
# - YFinancePulseEngine 的改造
# - 更完善的錯誤處理和日誌記錄
# - 對於 _fetch_data_for_day_and_interval 返回 None 的情況，需要更明確地區分「API無數據」和「API嚴重錯誤」
#   一種可能是讓 _fetch_data_for_day_and_interval 返回一個包含狀態的元組 (data_df, status_enum)
#   或者在拋出特定類型的異常來區分。
# - 考慮 DBManager 的 ohlcv_table_name 是 "market_ohlcv_data" 還是 "MarketPrices_Daily"。
#   作戰計畫書指定 "MarketPrices_Daily"，但 DBManager 內部目前可能是 "market_ohlcv_data"。
#   YFinanceHydrator 初始化時應能處理這個表名，或者 DBManager 應統一。
#   目前 hydrate_day 中使用 self.db_manager.ohlcv_table_name。
