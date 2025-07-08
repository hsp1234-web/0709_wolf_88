# -*- coding: utf-8 -*-
"""
YFinancePulseEngine - 主執行腳本
====================================

此腳本負責：
1. 解析命令行參數 (tickers, 日期範圍, 資料庫配置等)。
2. 初始化 DBManager, YFinanceHydrator, 和 YFinancePulseEngine。
3. 啟動 YFinancePulseEngine 執行數據回填任務。
"""
import argparse
import sys
import os
from datetime import datetime

# --- 設定專案路徑，確保可以正確匯入其他模組 ---
def setup_project_path():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        print(f"DEBUG (run_pulse_engine): Project root added to sys.path: {project_root}")

setup_project_path()
# --- 專案路徑設定結束 ---

try:
    from apps.daily_market_analyzer.db_manager import DBManager
    from apps.yfinance_hydrator.hydrator import YFinanceHydrator
    from apps.yfinance_pulse_engine.pulse_engine import YFinancePulseEngine
except ModuleNotFoundError as e:
    print(f"錯誤：導入核心模組時發生錯誤: {e}")
    print(f"Current sys.path: {sys.path}")
    # 嘗試列出相關目錄內容以幫助調試導入問題
    try:
        print(f"DEBUG: Contents of 'apps/': {os.listdir('apps')}")
        if os.path.exists('apps/daily_market_analyzer'):
            print(f"DEBUG: Contents of 'apps/daily_market_analyzer/': {os.listdir('apps/daily_market_analyzer')}")
        if os.path.exists('apps/yfinance_hydrator'):
            print(f"DEBUG: Contents of 'apps/yfinance_hydrator/': {os.listdir('apps/yfinance_hydrator')}")
        if os.path.exists('apps/yfinance_pulse_engine'):
            print(f"DEBUG: Contents of 'apps/yfinance_pulse_engine/': {os.listdir('apps/yfinance_pulse_engine')}")
    except FileNotFoundError as fe:
        print(f"DEBUG: 列出目錄時發生錯誤: {fe}")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="YFinance Pulse Engine: 數據回填指揮官引擎。")

    parser.add_argument("--tickers", required=True, help="要處理的股票代碼列表，以逗號分隔 (例如: AAPL,MSFT,GOOG)。")
    parser.add_argument("--start-date", required=True, help="數據回填的起始日期 (格式: YYYY-MM-DD)。")
    parser.add_argument("--end-date", required=True, help="數據回填的結束日期 (格式: YYYY-MM-DD)。")

    parser.add_argument("--db-path", default="data_workspace/market_data_lake.duckdb",
                        help="DuckDB 資料庫檔案的路徑 (預設: data_workspace/market_data_lake.duckdb)。")
    parser.add_argument("--table-name", default="MarketPrices_Daily",
                        help="資料庫中儲存 OHLCV 數據的表格名稱 (預設: MarketPrices_Daily)。")

    parser.add_argument("--force-refresh", action="store_true",
                        help="強制刷新數據，忽略 CacheIndex 中的 SUCCESS/NO_DATA 狀態。")
    parser.add_argument("--max-workers", type=int, default=5,
                        help="並行處理 (ticker, date) 任務的最大線程數 (預設: 5)。")

    args = parser.parse_args()

    print("--- YFinance Pulse Engine v1.0 ---")
    print(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"參數配置:")
    print(f"  Tickers: {args.tickers}")
    print(f"  Start Date: {args.start_date}")
    print(f"  End Date: {args.end_date}")
    print(f"  DB Path: {args.db_path}")
    print(f"  Table Name: {args.table_name}")
    print(f"  Force Refresh: {args.force_refresh}")
    print(f"  Max Workers: {args.max_workers}")

    tickers_list = [ticker.strip().upper() for ticker in args.tickers.split(',')]

    if not tickers_list:
        print("錯誤: 未提供任何有效的股票代碼。")
        sys.exit(1)

    # 1. 初始化 DBManager
    #    注意：DBManager 初始化時會嘗試創建其目錄（如果不存在）
    #    並且會執行 _setup_database 來創建包括 CacheIndex 在內的基礎表
    print(f"\nINFO: 初始化 DBManager (資料庫: {args.db_path}, 表格: {args.table_name})...")
    db_manager = DBManager(db_path=args.db_path, target_ohlcv_table_name=args.table_name)
    # DBManager 的 _setup_database 會打印它創建了哪些表，包括 CacheIndex

    # 2. 初始化 YFinanceHydrator
    print("INFO: 初始化 YFinanceHydrator...")
    hydrator = YFinanceHydrator(db_manager=db_manager)

    # 3. 初始化 YFinancePulseEngine
    print("INFO: 初始化 YFinancePulseEngine...")
    pulse_engine = YFinancePulseEngine(hydrator=hydrator, max_workers=args.max_workers)

    # 4. 執行脈衝任務
    try:
        pulse_engine.run(
            tickers=tickers_list,
            start_date_str=args.start_date,
            end_date_str=args.end_date,
            force_refresh=args.force_refresh
        )
    except Exception as e:
        print(f"CRITICAL (run_pulse_engine): YFinancePulseEngine 執行過程中發生未處理的嚴重錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n--- YFinance Pulse Engine 任務執行完畢 ---")

if __name__ == "__main__":
    main()
