# -*- coding: utf-8 -*-
"""
【神諭儀】 - 全時域洞察引擎 v1.0
====================================
按需報告生成器主執行腳本。
接收用戶指令，調用 YFinanceHydrator 回填最高頻數據，
然後使用 TimeAggregator 聚合成目標時間顆粒度，
接著送入 FactorEngine 計算因子，最終生成並展示分析報告。
"""
import argparse
import pandas as pd
from datetime import datetime, timedelta

# 假設各模組可以從PYTHONPATH找到
# 實際部署時可能需要調整路徑或使用 setup.py
try:
    from apps.daily_market_analyzer.db_manager import DBManager
    from apps.yfinance_hydrator.hydrator import YFinanceHydrator
    from apps.time_aggregator.aggregator import TimeAggregator
    from apps.factor_engine.engine import FactorEngine
except ImportError as e:
    print(f"錯誤：導入必要模組失敗，請確保 apps 目錄在 PYTHONPATH 中。詳細錯誤: {e}")
    # 可以嘗試從相對路徑導入，適用於直接在項目根目錄執行此腳本的情況
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
    from apps.daily_market_analyzer.db_manager import DBManager
    from apps.yfinance_hydrator.hydrator import YFinanceHydrator
    from apps.time_aggregator.aggregator import TimeAggregator
    from apps.factor_engine.engine import FactorEngine


def generate_report(ticker: str, start_date_str: str, end_date_str: str, target_interval: str,
                    source_interval: str = '1m', db_path: str = "data_workspace/market_analysis.duckdb"):
    """
    生成按需分析報告的核心函數。

    Args:
        ticker (str): 目標商品代碼 (e.g., "AAPL", "SPY")。
        start_date_str (str): 分析開始日期 (YYYY-MM-DD)。
        end_date_str (str): 分析結束日期 (YYYY-MM-DD)。
        target_interval (str): 報告的目標時間精細度 (e.g., '15m', '1h', '1d')。
        source_interval (str, optional): 用於回填的最高頻數據的 interval。預設為 '1m'。
        db_path (str, optional): 資料庫檔案路徑。預設為 "data_workspace/market_analysis.duckdb"。
    """
    print(f"===== 【神諭儀】開始生成報告 =====")
    print(f"指令參數: Ticker={ticker}, StartDate={start_date_str}, EndDate={end_date_str}, TargetInterval={target_interval}, SourceInterval={source_interval}")

    # --- 0. 初始化核心組件 ---
    # 重要：DBManager 初始化時，target_ohlcv_table_name 應與 FactorEngine 等下游組件期望的表名一致。
    # FactorEngine.get_prices_for_ticker 查詢的是 'MarketPrices_Daily'。
    # YFinanceHydrator.hydrate_range 和 TimeAggregator.aggregate_ohlcv 使用 db_manager.ohlcv_table_name。
    # 因此，DBManager 初始化時 target_ohlcv_table_name 必須設為 'MarketPrices_Daily'。
    db_manager = DBManager(db_path=db_path, target_ohlcv_table_name="MarketPrices_Daily")
    yfinance_hydrator = YFinanceHydrator(db_manager=db_manager)
    time_aggregator = TimeAggregator(db_manager=db_manager)
    factor_engine = FactorEngine(db_manager=db_manager) # FactorEngine 也需要 DBManager

    print("\n--- 1. 數據回填 (YFinanceHydrator) ---")
    # a. 調用升級後的 YFinanceHydrator，確保所需時間範圍內的、最高頻率的原始數據已被回填至資料庫。
    # 我們使用 source_interval (例如 '1m') 來回填。
    try:
        yfinance_hydrator.hydrate_range(
            ticker=ticker,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
            interval=source_interval,
            force_refresh=False # 通常情況下不需要強制刷新，除非明確指示
        )
        print(f"INFO: {ticker} 在 [{start_date_str} - {end_date_str}] 範圍內以 {source_interval} 精度回填完成 (或已是最新)。")
    except Exception as e_hydrate:
        print(f"錯誤: YFinanceHydrator 在回填數據時發生錯誤: {e_hydrate}")
        # 根據策略，這裡可以選擇終止或繼續嘗試後續步驟 (如果部分數據已存在)
        # 目前選擇繼續，因為聚合器和因子引擎可能會使用已有的數據
        # return # 如果希望嚴格失敗，則取消註釋此行

    print("\n--- 2. 時間聚合 (TimeAggregator) ---")
    # b. 將原始數據交給【時間熔爐】(TimeAggregator)，生成指定精細度的 OHLCV 數據。
    aggregated_ohlcv_df = pd.DataFrame()
    try:
        aggregated_ohlcv_df = time_aggregator.aggregate_ohlcv(
            ticker=ticker,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
            base_interval=source_interval, # 從 source_interval 開始聚合
            target_interval=target_interval
        )
        if aggregated_ohlcv_df.empty:
            print(f"警告: TimeAggregator未能生成 {ticker} 的 {target_interval} 聚合數據。後續因子計算可能受影響。")
        else:
            print(f"INFO: 成功將 {ticker} 的數據聚合成 {target_interval} 顆粒度，共 {len(aggregated_ohlcv_df)} 筆。")
            print("聚合後 OHLCV 數據預覽 (前5筆):")
            print(aggregated_ohlcv_df.head())
    except Exception as e_agg:
        print(f"錯誤: TimeAggregator 在聚合數據時發生錯誤: {e_agg}")
        # 同樣，可以選擇終止或繼續
        # return # 如果希望嚴格失敗

    print("\n--- 3. 因子計算 (FactorEngine) ---")
    # c. 將聚合後的數據，送入我們現有的 FactorEngine 進行即時的因子計算。
    # 注意：FactorEngine 的現有方法 (如 get_prices_for_ticker, calculate_price_volatility)
    # 可能設計為直接從DB讀取日線數據，或接收一個已準備好的 DataFrame。
    # 我們需要將 aggregated_ohlcv_df (它已經是目標 interval) 傳遞給因子計算方法。
    # FactorEngine 目前沒有一個統一的 calculate_factors(df) 方法。
    # 我們需要逐個調用其計算函數，並將結果合併。

    all_factors_df = pd.DataFrame()
    if not aggregated_ohlcv_df.empty:
        # 準備一個 DataFrame 用於因子計算，FactorEngine 的方法可能期望特定的索引和欄位名
        # aggregated_ohlcv_df 已經有 'datetime' 索引 (如果 TimeAggregator 正確設置)
        # 欄位名也應該是小寫的 'open', 'high', 'low', 'close', 'volume'

        # 確保 aggregated_ohlcv_df 的 'datetime' 是索引，如果不是則設置
        # TimeAggregator 返回的 df 中 'datetime' 已經是欄位，因子引擎方法可能期望它是索引
        calc_df = aggregated_ohlcv_df.copy()
        if 'datetime' in calc_df.columns and not isinstance(calc_df.index, pd.DatetimeIndex):
            calc_df = calc_df.set_index('datetime')

        # 確保欄位名是小寫 (TimeAggregator 應該已經處理，但再次確認)
        calc_df.columns = [col.lower() for col in calc_df.columns]


        print(f"INFO: 準備傳送給 FactorEngine 的 DataFrame (索引類型: {type(calc_df.index)}, 前幾行):")
        print(calc_df.head())

        # 示例：計算價格波動率和RSI (假設這些因子適用於任意 interval)
        try:
            price_vol = factor_engine.calculate_price_volatility(calc_df, n_days=20) # n_days 可能需要根據 interval 調整
            if price_vol is not None:
                all_factors_df['price_volatility_20'] = price_vol
                print("INFO: 價格波動率計算完成。")

            rsi_14 = factor_engine.calculate_rsi(calc_df, n_days=14) # n_days 同上
            if rsi_14 is not None:
                all_factors_df['rsi_14'] = rsi_14
                print("INFO: RSI 計算完成。")

            # 可以添加更多因子計算...
            # 例如，如果 target_interval 是 '1d'，可以嘗試計算殖利率利差等宏觀因子
            # 但這些因子通常不依賴於單一股票的 OHLCV
            # FactorEngine 的 get_treasury_yields 和 calculate_yield_spreads 是獨立的
            # 這裡主要演示基於傳入 OHLCV 的因子

            if all_factors_df.empty:
                print("警告: 未能計算任何技術因子。")
            else:
                print(f"INFO: 成功計算 {len(all_factors_df.columns)} 個因子。")
                print("計算出的因子數據預覽 (前5筆非空值):")
                print(all_factors_df.dropna(how='all').head())

        except Exception as e_factors:
            print(f"錯誤: FactorEngine 在計算因子時發生錯誤: {e_factors}")
    else:
        print("INFO: 由於聚合數據為空，跳過因子計算。")


    print("\n--- 4. 報告匯總與展示 ---")
    # d. 最終，將所有結果匯總，在螢幕上生成報告。
    print(f"\n===== 【神諭儀】按需分析報告 for {ticker} =====")
    print(f"分析範圍: {start_date_str} to {end_date_str}")
    print(f"報告時間顆粒度: {target_interval} (來源數據顆粒度: {source_interval})")
    print(f"數據庫: {db_path}")
    print("--------------------------------------------------")

    if not aggregated_ohlcv_df.empty:
        print("\n【聚合後 OHLCV 數據】(最近5筆):")
        print(aggregated_ohlcv_df.tail())
    else:
        print("\n【聚合後 OHLCV 數據】: 無法生成或無數據。")

    if not all_factors_df.empty:
        # 合併 OHLCV 和因子數據以供展示
        # 確保索引一致 (都應為 datetime)
        report_df = aggregated_ohlcv_df.copy()
        if 'datetime' in report_df.columns and not isinstance(report_df.index, pd.DatetimeIndex):
             report_df = report_df.set_index('datetime')

        # all_factors_df 的索引也應是 datetime
        # 如果 all_factors_df 索引不是 datetime，需要處理
        if not isinstance(all_factors_df.index, pd.DatetimeIndex) and 'datetime' in all_factors_df.columns:
            all_factors_df = all_factors_df.set_index('datetime')

        # 合併時，要確保索引是相同類型 (例如都是 UTC 時區的 DatetimeIndex)
        # TimeAggregator 和 FactorEngine 的計算方法內部應確保時區一致性
        try:
            if isinstance(report_df.index, pd.DatetimeIndex) and isinstance(all_factors_df.index, pd.DatetimeIndex):
                # 檢查時區是否一致，如果不一致，嘗試轉換 all_factors_df 的時區以匹配 report_df
                if report_df.index.tz != all_factors_df.index.tz:
                    print(f"警告: OHLCV數據時區 ({report_df.index.tz}) 與因子數據時區 ({all_factors_df.index.tz}) 不匹配。嘗試轉換因子數據時區。")
                    if all_factors_df.index.tz is None and report_df.index.tz is not None:
                        all_factors_df = all_factors_df.tz_localize(report_df.index.tz)
                    elif all_factors_df.index.tz is not None and report_df.index.tz is not None:
                        all_factors_df = all_factors_df.tz_convert(report_df.index.tz)
                    # 其他情況可能更複雜，暫不處理

                final_report_df = pd.merge(report_df, all_factors_df, left_index=True, right_index=True, how='left')
                print("\n【因子數據】(與OHLCV合併後，最近5筆含因子數據):")
                # 顯示包含任何因子值的尾部數據
                print(final_report_df.dropna(subset=all_factors_df.columns, how='all').tail())
            else:
                print("\n【因子數據】: 無法與OHLCV數據合併 (索引問題)。原始因子數據預覽:")
                print(all_factors_df.dropna(how='all').tail())

        except Exception as e_merge:
            print(f"錯誤: 合併OHLCV與因子數據時發生錯誤: {e_merge}")
            print("\n【因子數據】(原始，最近5筆含因子數據):")
            print(all_factors_df.dropna(how='all').tail())

    elif not aggregated_ohlcv_df.empty: # 有OHLCV但沒有因子
        print("\n【因子數據】: 未計算或無有效因子數據。")
    else: # OHLCV也為空
        pass # 已在上面報告過OHLCV無數據

    print("\n===== 【神諭儀】報告生成完畢 =====")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="【神諭儀】全時域洞察引擎 - 按需報告生成器")
    parser.add_argument("ticker", type=str, help="目標商品代碼 (e.g., AAPL, ^GSPC)")
    parser.add_argument("start_date", type=str, help="分析開始日期 (YYYY-MM-DD)")
    parser.add_argument("end_date", type=str, help="分析結束日期 (YYYY-MM-DD)")
    parser.add_argument("target_interval", type=str, help="報告的目標時間精細度 (e.g., '15m', '1h', '1d')")

    parser.add_argument("--source_interval", type=str, default="1m", help="用於回填的最高頻數據的 interval (預設: '1m')")
    parser.add_argument("--db_path", type=str, default="data_workspace/market_analysis.duckdb", help="資料庫檔案路徑 (預設: data_workspace/market_analysis.duckdb)")
    parser.add_argument("--force_hydrate", action="store_true", help="強制 YFinanceHydrator 重新獲取數據，即使已有快取。") # 未在 generate_report 中使用，但可擴展

    args = parser.parse_args()

    # 簡單的日期格式驗證
    try:
        datetime.strptime(args.start_date, "%Y-%m-%d")
        datetime.strptime(args.end_date, "%Y-%m-%d")
    except ValueError:
        print("錯誤: 日期格式無效。請使用 YYYY-MM-DD 格式。")
        parser.print_help()
        exit(1)

    # 創建 data_workspace 目錄（如果不存在）
    db_dir = os.path.dirname(args.db_path)
    if db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
            print(f"INFO: 已創建資料庫目錄: {db_dir}")
        except OSError as e:
            print(f"錯誤: 無法創建資料庫目錄 {db_dir}: {e}")
            # exit(1) # 根據情況決定是否終止

    # 執行報告生成
    generate_report(
        ticker=args.ticker,
        start_date_str=args.start_date,
        end_date_str=args.end_date,
        target_interval=args.target_interval,
        source_interval=args.source_interval,
        db_path=args.db_path
        # 可以考慮將 args.force_hydrate 傳入 yfinance_hydrator.hydrate_range
    )

    # 範例執行命令 (在終端機中):
    # python generate_on_demand_report.py SPY 2024-07-01 2024-07-03 1h --source_interval 1m --db_path data_workspace/test_spy_report.duckdb
    # python generate_on_demand_report.py AAPL 2024-06-20 2024-07-01 1d --source_interval 5m
    # (如果使用預設 db_path)
    # python generate_on_demand_report.py BTC-USD 2024-07-10 2024-07-15 15m
</tbody>
</table>
