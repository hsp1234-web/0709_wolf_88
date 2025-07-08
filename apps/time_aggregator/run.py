# apps/time_aggregator/run.py

import duckdb
import pandas as pd
import argparse
import os
from pathlib import Path
import sys # 標準樣板碼需要 sys

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    # 獲取目前腳本的絕對路徑
    current_script_path = Path(__file__).resolve()
    # 假設此腳本位於 apps/[app_name] 目錄下，專案根目錄是其再上兩層
    project_root = current_script_path.parent.parent.parent
    # 將專案根目錄加入 sys.path
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError: # __file__ is not defined, common in interactive shells or certain execution contexts
    project_root = Path(os.getcwd())
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    print(f"警告：__file__ 未定義，專案路徑校正可能不準確。已將 {project_root} 加入 sys.path。", file=sys.stderr)
except Exception as e:
    print(f"專案路徑校正時發生錯誤 (apps/time_aggregator/run.py): {e}", file=sys.stderr)
# --- 標準化「路徑自我校正」樣板碼 END ---

# project_root 變數現在由上面的樣板碼定義
DEFAULT_SOURCE_TICKS_DB_PATH = project_root / "taifex_ticks.duckdb"
DEFAULT_ANALYTICS_DB_PATH = project_root / "analytics_mart.duckdb"

# 從環境變數讀取資料庫路徑，如果設定了話
# 在管線中，這些路徑會被 run_daily_pipeline.py 明確傳遞
# 此處的環境變數主要用於獨立運行此腳本時的彈性
SOURCE_TICKS_DB_PATH_ENV = os.getenv("KRONOS_SOURCE_TICKS_DB_PATH")
ANALYTICS_DB_PATH_ENV = os.getenv("KRONOS_ANALYTICS_DB_PATH")

if SOURCE_TICKS_DB_PATH_ENV:
    print(f"INFO: 從環境變數 KRONOS_SOURCE_TICKS_DB_PATH 使用來源 Tick 資料庫路徑: {SOURCE_TICKS_DB_PATH_ENV}")
    CFG_SOURCE_TICKS_DB_PATH = Path(SOURCE_TICKS_DB_PATH_ENV)
else:
    CFG_SOURCE_TICKS_DB_PATH = DEFAULT_SOURCE_TICKS_DB_PATH

if ANALYTICS_DB_PATH_ENV:
    print(f"INFO: 從環境變數 KRONOS_ANALYTICS_DB_PATH 使用分析資料庫路徑: {ANALYTICS_DB_PATH_ENV}")
    CFG_ANALYTICS_DB_PATH = Path(ANALYTICS_DB_PATH_ENV)
else:
    CFG_ANALYTICS_DB_PATH = DEFAULT_ANALYTICS_DB_PATH


TIME_PERIODS = {
    "1min": "1T",
    "5min": "5T",
    "15min": "15T",
    "30min": "30T", # 新增
    "1h": "1H",
    "4h": "4H",
    "12h": "12H", # 新增
    "1d": "1D",
    "1w": "W-MON", # 新增：週一為每週的開始
    "1m": "MS"    # 新增：每月的第一個日曆日為開始 (Month Start)
}

def create_ohlcv_tables(con: duckdb.DuckDBPyConnection, analytics_db_name_for_log: str):
    """
    在指定的分析資料庫中為每個時間週期創建 OHLCV 資料表。
    """
    for period_name in TIME_PERIODS.keys():
        table_name = f"ohlcv_{period_name}"
        try:
            # print(f"DEBUG: 準備在 {analytics_db_name_for_log} 中創建資料表 {table_name}")
            con.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    timestamp TIMESTAMP,
                    product_id VARCHAR,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume BIGINT,
                    PRIMARY KEY (timestamp, product_id)
                );
            """)
            print(f"資料表 '{table_name}' (在 {analytics_db_name_for_log}) 已創建或已存在。")
        except Exception as e:
            print(f"在 {analytics_db_name_for_log} 中創建資料表 '{table_name}' 時發生錯誤: {e}")
            # 根據錯誤的嚴重性，可能需要重新拋出異常
            raise

def aggregate_ticks_to_ohlcv(
    source_db_path_str: str, # 改為接收字串，以便與 pipeline 傳參一致
    analytics_db_path_str: str, # 改為接收字串
    product_id: str,
    start_date_str: str, # 參數名也加上 _str
    end_date_str: str    # 參數名也加上 _str
):
    """
    讀取 Tick 數據 (來自 source_db_path)，聚合成多時間尺度 OHLCV，
    並存儲到 analytics_db_path 中對應的 ohlcv_{period_name} 資料表。
    """
    source_db_path = Path(source_db_path_str)
    analytics_db_path = Path(analytics_db_path_str)

    if not source_db_path.exists():
        print(f"錯誤：來源資料庫 '{source_db_path}' 不存在。聚合中止。")
        return False # 返回失敗狀態

    print(f"聚合引擎：來源資料庫: {source_db_path}")
    print(f"聚合引擎：分析資料庫: {analytics_db_path}")
    print(f"聚合引擎：商品ID: {product_id}, 時間範圍: {start_date_str} 至 {end_date_str}")

    # 確保 analytics_db 的目錄存在 (雖然 create_ohlcv_tables 也會做，但這裡先做一次也無妨)
    try:
        analytics_db_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"錯誤：無法創建分析資料庫目錄 {analytics_db_path.parent}: {e}")
        return False


    try:
        # 建立與分析資料庫的連接，並創建所有時間週期的資料表 (如果不存在)
        # 這個連接會在整個聚合過程中保持開啟
        with duckdb.connect(database=str(analytics_db_path), read_only=False) as analytics_con:
            print(f"成功連接到分析資料庫 '{analytics_db_path}' 並準備創建資料表。")
            create_ohlcv_tables(analytics_con, str(analytics_db_path)) # 傳遞 analytics_db_path 給它

            # 現在才連接來源資料庫，僅用於讀取 ticks
            with duckdb.connect(database=str(source_db_path), read_only=True) as source_con:
                print(f"成功連接到來源資料庫 '{source_db_path}' (唯讀模式)。")

                # 讀取 Tick 資料
                # 時間戳欄位應為 datetime64[ns] 或可轉換的類型
                # 使用參數化查詢以避免 SQL 注入風險
                query = f"""
                SELECT timestamp, price, volume
                FROM ticks
                WHERE product_id = ?
                AND timestamp >= ?
                AND timestamp < ?
                ORDER BY timestamp;
                """
                # print(f"正在執行查詢: SELECT ... FROM ticks WHERE product_id = '{product_id}' AND timestamp >= '{start_date_str}' AND timestamp < '{end_date_str}'")
                ticks_df = source_con.execute(query, [product_id, start_date_str, end_date_str]).fetchdf()

                if ticks_df.empty:
                    print(f"在指定日期範圍內沒有找到商品 '{product_id}' 的 Tick 數據。")
                    return True # 雖然沒有數據，但操作本身是成功的

                print(f"成功讀取 {len(ticks_df)} 筆商品 '{product_id}' 的 Tick 數據。")

                # 將 'timestamp' 轉換為 pandas datetime 物件 (如果尚未轉換)
                # DuckDB fetchdf() 通常會處理好類型，但以防萬一
                if not pd.api.types.is_datetime64_any_dtype(ticks_df['timestamp']):
                    ticks_df['timestamp'] = pd.to_datetime(ticks_df['timestamp'])

                ticks_df.set_index('timestamp', inplace=True)

                for period_name, period_code in TIME_PERIODS.items():
                    print(f"商品 '{product_id}': 正在聚合 {period_name} ({period_code}) 的 OHLCV 數據...")

                    # 使用 Pandas resample 進行聚合
                    # .agg() 方法更靈活，可以一次性定義所有聚合操作
                    agg_rules = {
                        'price': ['first', 'max', 'min', 'last'], # open, high, low, close
                        'volume': 'sum'
                    }
                    resampled_data = ticks_df.resample(period_code).agg(agg_rules)

                    # 重命名欄位以匹配 OHLCV 結構
                    resampled_data.columns = ['open', 'high', 'low', 'close', 'volume']

                    # 移除所有價格欄位 (open, high, low, close) 均為 NaN 的K棒 (表示該時段無交易)
                    ohlcv_df = resampled_data.dropna(subset=['open', 'high', 'low', 'close'], how='all')

                    if ohlcv_df.empty:
                        print(f"商品 '{product_id}' 在聚合週期 '{period_name}' 後沒有有效數據。")
                        continue

                    ohlcv_df.reset_index(inplace=True) # 將 timestamp 從索引變回欄位
                    ohlcv_df['product_id'] = product_id # 添加 product_id 欄位

                    # 確保欄位順序和類型符合資料表定義
                    # timestamp, product_id, open, high, low, close, volume
                    ohlcv_df = ohlcv_df[['timestamp', 'product_id', 'open', 'high', 'low', 'close', 'volume']]

                    # 對於週線(W-MON)和月線(MS)，Pandas resample 的 timestamp 可能是該週/月的第一天
                    # 這通常是我們想要的，符合 DuckDB 的 DATE_TRUNC 功能

                    table_name = f"ohlcv_{period_name}"
                    print(f"商品 '{product_id}': 準備將數據寫入資料表 '{table_name}' (位於 {analytics_db_path})...")

                    # 冪等性處理：先刪除本次聚合時間範圍內的舊數據
                    # 這樣即使重複運行，也不會插入重複數據或導致主鍵衝突
                    # DuckDB 的 PRIMARY KEY 預設是 UNIQUE，所以重複插入會失敗
                    if not ohlcv_df.empty:
                        min_ts_to_delete = ohlcv_df['timestamp'].min()
                        max_ts_to_delete = ohlcv_df['timestamp'].max()

                        # 重要：刪除範圍應基於聚合後的 timestamp，而不是原始 tick 的 start/end date
                        # 因為聚合後的 K 棒 timestamp 可能會略微超出原始 tick 的 start/end date 邊界
                        # （例如，一個橫跨 end_date 的 K 棒）
                        # 更安全的做法是，如果管線保證按順序填充，則僅追加。
                        # 但為了 `--force-refresh` 和獨立運行的穩健性，先刪後插更可靠。

                        delete_query = f"""
                        DELETE FROM {table_name}
                        WHERE product_id = ?
                        AND timestamp >= ? AND timestamp <= ?;
                        """
                        # print(f"DEBUG: 執行刪除查詢 for {table_name}: product_id='{product_id}', min_ts='{min_ts_to_delete}', max_ts='{max_ts_to_delete}'")
                        analytics_con.execute(delete_query, [product_id, min_ts_to_delete, max_ts_to_delete])
                        print(f"商品 '{product_id}': 已從 '{table_name}' 清理時間範圍 [{min_ts_to_delete} 至 {max_ts_to_delete}] 的舊數據。")

                        analytics_con.append(table_name, ohlcv_df)
                        print(f"商品 '{product_id}': 成功將 {len(ohlcv_df)} 筆數據寫入 '{table_name}'。")
                    else:
                        print(f"商品 '{product_id}': 沒有聚合後的數據可寫入 '{table_name}'。")

        print(f"商品 '{product_id}': 所有時間序列聚合完成。")
        return True # 表示成功

    except duckdb.Error as e:
        print(f"商品 '{product_id}': DuckDB 處理過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False # 返回失敗狀態
    except pd.errors.EmptyDataError:
        print(f"商品 '{product_id}': Pandas 處理時遇到空數據錯誤，可能由於 resample 後沒有數據。")
        return True # 視為可接受的無數據情況，非致命錯誤
    except Exception as e:
        print(f"商品 '{product_id}': 聚合過程中發生未預期錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False # 返回失敗狀態

def _ensure_db_directory_exists(db_path: Path):
    """輔助函數，確保資料庫檔案所在的目錄存在。"""
    db_dir = db_path.parent
    try:
        db_dir.mkdir(parents=True, exist_ok=True)
        # print(f"已確認目錄存在: {db_dir}")
    except Exception as e:
        print(f"創建目錄 {db_dir} 時發生錯誤: {e}")
        raise # 重新拋出異常，讓調用者處理

def _create_dummy_source_db_if_needed(db_path: Path, product_id_for_dummy: str):
    """如果指定的來源資料庫不存在，創建一個包含範例數據的假資料庫。"""
    if not db_path.exists():
        print(f"警告：指定的來源資料庫 {db_path} 不存在。將創建一個包含範例數據的假資料庫。")
        _ensure_db_directory_exists(db_path) # 先確保目錄存在
        try:
            with duckdb.connect(str(db_path)) as con:
                con.execute("""
                    CREATE TABLE IF NOT EXISTS ticks (
                        timestamp TIMESTAMP,
                        product_id VARCHAR,
                        price DOUBLE,
                        qty BIGINT
                    );
                """)
                # 插入一些範例數據 (例如 'MXF1' 在 '2023-01-01' 到 '2023-03-01')
                # 擴展數據以測試週和月聚合
                sample_data = [
                    # 2023-01 (跨多日，多週，多月)
                    ('2023-01-01 08:45:00', product_id_for_dummy, 14000.0, 10),
                    ('2023-01-01 08:45:01', product_id_for_dummy, 14001.0, 5),
                    ('2023-01-01 10:00:00', product_id_for_dummy, 14050.0, 30),
                    ('2023-01-01 13:00:00', product_id_for_dummy, 14000.0, 50),
                    ('2023-01-02 09:00:00', product_id_for_dummy, 14100.0, 20),
                    ('2023-01-08 09:00:00', product_id_for_dummy, 14200.0, 25), # 下一週
                    ('2023-01-15 09:00:00', product_id_for_dummy, 14250.0, 10), # 再下一週
                    # 2023-02
                    ('2023-02-01 08:45:00', product_id_for_dummy, 14300.0, 15),
                    ('2023-02-10 10:30:00', product_id_for_dummy, 14350.0, 20),
                    # 2023-03 (僅月初，測試月聚合邊界)
                    ('2023-03-01 08:45:00', product_id_for_dummy, 14400.0, 10),
                ]
                # 增加一些特定時間點的數據以確保所有周期都有數據
                current_time = pd.Timestamp('2023-01-01 08:45:00')
                price = 14000.0
                for _ in range(1000): # 生成約16小時的1分鐘數據
                    sample_data.append((current_time.strftime('%Y-%m-%d %H:%M:%S'), product_id_for_dummy, price, 10))
                    current_time += pd.Timedelta(minutes=1)
                    price += 0.1

                con.executemany("INSERT INTO ticks VALUES (?, ?, ?, ?)", sample_data)
                print(f"已創建包含範例數據的假資料庫: {db_path} (針對商品 {product_id_for_dummy})")
        except Exception as e:
            print(f"創建假資料庫 {db_path} 時發生錯誤: {e}")
            # 如果創建假資料庫失敗，這是一個關鍵問題，應該讓 main 知道
            raise RuntimeError(f"無法創建測試用的來源資料庫 {db_path}: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="時間序列聚合器：將 Tick 數據從來源資料庫聚合成多時間尺度 OHLCV，並儲存到分析資料庫。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # 顯示預設值
    )
    parser.add_argument("product_id", type=str, help="要處理的商品代碼 (例如：MXF1 或 2330)。")
    parser.add_argument("start_date", type=str, help="開始日期 (YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD)。")
    parser.add_argument("end_date", type=str, help="結束日期 (YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD) (不包含此日/時間點)。")

    # 使用 str() 將 Path 物件轉換為字串，因為 argparse 的 default 參數期望字串
    parser.add_argument("--source_db", type=str, default=str(CFG_SOURCE_TICKS_DB_PATH),
                        help="來源 Tick 資料庫路徑。")
    parser.add_argument("--analytics_db", type=str, default=str(CFG_ANALYTICS_DB_PATH),
                        help="分析結果資料庫路徑。")

    args = parser.parse_args()

    # 確保資料庫目錄存在 (主要針對直接運行此腳本時)
    # _ensure_db_directory_exists 會在需要時創建目錄，如果失敗會拋出異常
    try:
        _ensure_db_directory_exists(Path(args.source_db))
        _ensure_db_directory_exists(Path(args.analytics_db))
    except Exception as e:
        print(f"錯誤：準備資料庫目錄時失敗: {e}")
        return 1 # 返回錯誤碼


    # 如果是使用預設的 source_db 路徑 (CFG_SOURCE_TICKS_DB_PATH) 且該檔案不存在，則創建一個假的
    # 這主要用於獨立測試此腳本
    if args.source_db == str(CFG_SOURCE_TICKS_DB_PATH) and not Path(args.source_db).exists():
        try:
            print(f"提示：由於預設來源資料庫 {args.source_db} 不存在，將嘗試創建一個包含 '{args.product_id}' 範例數據的假資料庫。")
            _create_dummy_source_db_if_needed(Path(args.source_db), args.product_id)
        except RuntimeError as e:
            print(f"錯誤：{e}")
            print("聚合流程無法繼續。")
            return 1 # 返回錯誤碼

    success = aggregate_ticks_to_ohlcv(
        args.source_db,
        args.analytics_db,
        args.product_id,
        args.start_date,
        args.end_date
    )

    if success:
        print(f"商品 {args.product_id} 的時間序列聚合流程成功完成。")
        return 0 # 返回成功碼
    else:
        print(f"商品 {args.product_id} 的時間序列聚合流程執行失敗。")
        return 1 # 返回錯誤碼

if __name__ == "__main__":
    # 設定 Pandas 以顯示所有欄位，方便調試
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)

    # 執行 main 函數並捕獲其返回碼
    # 需要 sys 模組來處理 exit code
    import sys
    exit_code = main()
    sys.exit(exit_code) # 將 main 的返回碼作為腳本的退出碼
