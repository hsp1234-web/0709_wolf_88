# apps/etl_pipeline/aggregator.py

import duckdb
import pandas as pd
import argparse
import os
from pathlib import Path
import sys

# --- 標準化「路徑自我校正」樣板碼 START ---
# 在模組化後，這個路徑校正可能需要調整或依賴於統一的 ETL 入口點來設定 sys.path
# 暫時保留，但需注意其在被調用時的行為
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    project_root = Path(os.getcwd())
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    # print(f"警告：__file__ 未定義於 aggregator.py，專案路徑校正可能不準確。", file=sys.stderr)
except Exception as e:
    print(f"專案路徑校正時發生錯誤 (apps/etl_pipeline/aggregator.py): {e}", file=sys.stderr)
# --- 標準化「路徑自我校正」樣板碼 END ---

DEFAULT_SOURCE_TICKS_DB_PATH = project_root / "taifex_ticks.duckdb"
DEFAULT_ANALYTICS_DB_PATH = project_root / "analytics_mart.duckdb"

TIME_PERIODS = {
    "1min": "1T",
    "5min": "5T",
    "15min": "15T",
    "30min": "30T",
    "1h": "1H",
    "4h": "4H",
    "12h": "12H",
    "1d": "1D",
    "1w": "W-MON",
    "1m": "MS"
}

def create_ohlcv_tables(con: duckdb.DuckDBPyConnection, analytics_db_name_for_log: str):
    """
    在指定的分析資料庫中為每個時間週期創建 OHLCV 資料表。
    """
    for period_name in TIME_PERIODS.keys():
        table_name = f"ohlcv_{period_name}"
        try:
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
            # print(f"資料表 '{table_name}' (在 {analytics_db_name_for_log}) 已創建或已存在。")
        except Exception as e:
            print(f"在 {analytics_db_name_for_log} 中創建資料表 '{table_name}' 時發生錯誤: {e}")
            raise

def _aggregate_ticks_to_ohlcv_internal( # 將原 aggregate_ticks_to_ohlcv 更名為內部函數
    source_db_path_str: str,
    analytics_db_path_str: str,
    product_id: str,
    start_date_str: str,
    end_date_str: str
):
    """
    內部核心邏輯：讀取 Tick 數據，聚合成多時間尺度 OHLCV，並存儲。
    """
    source_db_path = Path(source_db_path_str)
    analytics_db_path = Path(analytics_db_path_str)

    if not source_db_path.exists():
        print(f"錯誤：來源資料庫 '{source_db_path}' 不存在。聚合中止。")
        return False

    # print(f"聚合引擎內部：來源資料庫: {source_db_path}")
    # print(f"聚合引擎內部：分析資料庫: {analytics_db_path}")
    # print(f"聚合引擎內部：商品ID: {product_id}, 時間範圍: {start_date_str} 至 {end_date_str}")

    try:
        analytics_db_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"錯誤：無法創建分析資料庫目錄 {analytics_db_path.parent}: {e}")
        return False

    try:
        with duckdb.connect(database=str(analytics_db_path), read_only=False) as analytics_con:
            # print(f"成功連接到分析資料庫 '{analytics_db_path}' 並準備創建資料表。")
            create_ohlcv_tables(analytics_con, str(analytics_db_path))

            with duckdb.connect(database=str(source_db_path), read_only=True) as source_con:
                # print(f"成功連接到來源資料庫 '{source_db_path}' (唯讀模式)。")
                query = f"""
                SELECT timestamp, price, volume
                FROM ticks
                WHERE product_id = ?
                AND timestamp >= ?
                AND timestamp < ?
                ORDER BY timestamp;
                """
                ticks_df = source_con.execute(query, [product_id, start_date_str, end_date_str]).fetchdf()

                if ticks_df.empty:
                    print(f"在指定日期範圍內沒有找到商品 '{product_id}' 的 Tick 數據。")
                    return True

                # print(f"成功讀取 {len(ticks_df)} 筆商品 '{product_id}' 的 Tick 數據。")
                if not pd.api.types.is_datetime64_any_dtype(ticks_df['timestamp']):
                    ticks_df['timestamp'] = pd.to_datetime(ticks_df['timestamp'])
                ticks_df.set_index('timestamp', inplace=True)

                for period_name, period_code in TIME_PERIODS.items():
                    # print(f"商品 '{product_id}': 正在聚合 {period_name} ({period_code}) 的 OHLCV 數據...")
                    agg_rules = {
                        'price': ['first', 'max', 'min', 'last'],
                        'volume': 'sum'
                    }
                    resampled_data = ticks_df.resample(period_code).agg(agg_rules)

                    # 檢查是否為 MultiIndex columns，這是 agg 正常輸出的情況
                    if isinstance(resampled_data.columns, pd.MultiIndex):
                        resampled_data.columns = ['_'.join(col).strip() for col in resampled_data.columns.values]
                        resampled_data.rename(columns={
                            'price_first': 'open',
                            'price_max': 'high',
                            'price_min': 'low',
                            'price_last': 'close',
                            'volume_sum': 'volume'
                        }, inplace=True)
                    # 如果不是 MultiIndex (例如在某些 mock 的情況下，或者 agg 結果不符合預期)
                    # 則假設欄位名可能已經是 'open', 'high', etc. 或者需要進一步處理
                    # 這裡我們依賴 dropna 來驗證欄位是否存在

                    ohlcv_df = resampled_data.dropna(subset=['open', 'high', 'low', 'close'], how='all')

                    if ohlcv_df.empty:
                        # print(f"商品 '{product_id}' 在聚合週期 '{period_name}' 後沒有有效數據。")
                        continue

                    ohlcv_df.reset_index(inplace=True)
                    ohlcv_df['product_id'] = product_id
                    ohlcv_df = ohlcv_df[['timestamp', 'product_id', 'open', 'high', 'low', 'close', 'volume']]

                    table_name = f"ohlcv_{period_name}"
                    # print(f"商品 '{product_id}': 準備將數據寫入資料表 '{table_name}' (位於 {analytics_db_path})...")

                    if not ohlcv_df.empty:
                        min_ts_to_delete = ohlcv_df['timestamp'].min()
                        max_ts_to_delete = ohlcv_df['timestamp'].max()
                        delete_query = f"""
                        DELETE FROM {table_name}
                        WHERE product_id = ?
                        AND timestamp >= ? AND timestamp <= ?;
                        """
                        analytics_con.execute(delete_query, [product_id, min_ts_to_delete, max_ts_to_delete])
                        # print(f"商品 '{product_id}': 已從 '{table_name}' 清理時間範圍 [{min_ts_to_delete} 至 {max_ts_to_delete}] 的舊數據。")
                        analytics_con.append(table_name, ohlcv_df)
                        # print(f"商品 '{product_id}': 成功將 {len(ohlcv_df)} 筆數據寫入 '{table_name}'。")
                    # else:
                        # print(f"商品 '{product_id}': 沒有聚合後的數據可寫入 '{table_name}'。")
        # print(f"商品 '{product_id}': 所有時間序列聚合完成。")
        return True
    except duckdb.Error as e:
        print(f"商品 '{product_id}': DuckDB 處理過程中發生錯誤: {e}")
        return False
    except pd.errors.EmptyDataError:
        print(f"商品 '{product_id}': Pandas 處理時遇到空數據錯誤。")
        return True
    except Exception as e:
        print(f"商品 '{product_id}': 聚合過程中發生未預期錯誤: {e}")
        return False

def _ensure_db_directory_exists(db_path: Path):
    db_dir = db_path.parent
    try:
        db_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"創建目錄 {db_dir} 時發生錯誤: {e}")
        raise

def _create_dummy_source_db_if_needed(db_path: Path, product_id_for_dummy: str):
    if not db_path.exists():
        print(f"警告：指定的來源資料庫 {db_path} 不存在。將創建一個包含範例數據的假資料庫。")
        _ensure_db_directory_exists(db_path)
        try:
            with duckdb.connect(str(db_path)) as con:
                con.execute("CREATE TABLE IF NOT EXISTS ticks (timestamp TIMESTAMP, product_id VARCHAR, price DOUBLE, qty BIGINT);")
                sample_data = [
                    ('2023-01-01 08:45:00', product_id_for_dummy, 14000.0, 10),
                    ('2023-01-01 08:45:01', product_id_for_dummy, 14001.0, 5),
                    ('2023-01-01 10:00:00', product_id_for_dummy, 14050.0, 30),
                    ('2023-01-01 13:00:00', product_id_for_dummy, 14000.0, 50),
                    ('2023-01-02 09:00:00', product_id_for_dummy, 14100.0, 20),
                    ('2023-01-08 09:00:00', product_id_for_dummy, 14200.0, 25),
                    ('2023-01-15 09:00:00', product_id_for_dummy, 14250.0, 10),
                    ('2023-02-01 08:45:00', product_id_for_dummy, 14300.0, 15),
                    ('2023-02-10 10:30:00', product_id_for_dummy, 14350.0, 20),
                    ('2023-03-01 08:45:00', product_id_for_dummy, 14400.0, 10),
                ]
                current_time = pd.Timestamp('2023-01-01 08:45:00')
                price = 14000.0
                for _ in range(1000): # 生成約16小時的1分鐘數據
                    sample_data.append((current_time.strftime('%Y-%m-%d %H:%M:%S'), product_id_for_dummy, price, 10))
                    current_time += pd.Timedelta(minutes=1)
                    price += 0.1
                con.executemany("INSERT INTO ticks VALUES (?, ?, ?, ?)", sample_data)
                # print(f"已創建包含範例數據的假資料庫: {db_path} (針對商品 {product_id_for_dummy})")
        except Exception as e:
            print(f"創建假資料庫 {db_path} 時發生錯誤: {e}")
            raise RuntimeError(f"無法創建測試用的來源資料庫 {db_path}: {e}")

def run_aggregation(argv: list[str] | None = None):
    """
    時間序列聚合模組主函數。
    argv: 從命令行傳遞的參數列表 (不含程式名稱本身)。
          如果為 None，則 argparse 會自動使用 sys.argv[1:]。
    """
    # 從環境變數讀取資料庫路徑，如果設定了話
    SOURCE_TICKS_DB_PATH_ENV = os.getenv("KRONOS_SOURCE_TICKS_DB_PATH")
    ANALYTICS_DB_PATH_ENV = os.getenv("KRONOS_ANALYTICS_DB_PATH")

    if SOURCE_TICKS_DB_PATH_ENV:
        # print(f"INFO (aggregator): 從環境變數 KRONOS_SOURCE_TICKS_DB_PATH 使用來源 Tick 資料庫路徑: {SOURCE_TICKS_DB_PATH_ENV}")
        cfg_source_ticks_db_path = Path(SOURCE_TICKS_DB_PATH_ENV)
    else:
        cfg_source_ticks_db_path = DEFAULT_SOURCE_TICKS_DB_PATH

    if ANALYTICS_DB_PATH_ENV:
        # print(f"INFO (aggregator): 從環境變數 KRONOS_ANALYTICS_DB_PATH 使用分析資料庫路徑: {ANALYTICS_DB_PATH_ENV}")
        cfg_analytics_db_path = Path(ANALYTICS_DB_PATH_ENV)
    else:
        cfg_analytics_db_path = DEFAULT_ANALYTICS_DB_PATH

    parser = argparse.ArgumentParser(
        description="Time Aggregation Module: 將 Tick 數據聚合成多時間尺度 OHLCV。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("product_id", type=str, help="要處理的商品代碼 (例如：MXF1 或 2330)。")
    parser.add_argument("start_date", type=str, help="開始日期 (YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD)。")
    parser.add_argument("end_date", type=str, help="結束日期 (YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD) (不包含此日/時間點)。")
    parser.add_argument("--source_db", type=str, default=str(cfg_source_ticks_db_path),
                        help="來源 Tick 資料庫路徑。")
    parser.add_argument("--analytics_db", type=str, default=str(cfg_analytics_db_path),
                        help="分析結果資料庫路徑。")
    # 可選：增加一個日誌級別參數，如果需要更細緻的日誌控制
    # parser.add_argument("--loglevel", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

    args = parser.parse_args(argv) # argv 由調用者 (如 etl_pipeline/run.py) 傳入

    print(f"--- 時間聚合模組：商品 {args.product_id}，從 {args.start_date} 到 {args.end_date} ---")

    try:
        _ensure_db_directory_exists(Path(args.source_db))
        _ensure_db_directory_exists(Path(args.analytics_db))
    except Exception as e:
        print(f"錯誤：準備資料庫目錄時失敗: {e}")
        # 在模組化調用中，我們通常不直接 sys.exit()，而是可以考慮拋出異常或返回狀態
        return False # 或 raise

    if args.source_db == str(DEFAULT_SOURCE_TICKS_DB_PATH) and not Path(args.source_db).exists():
        try:
            # print(f"提示 (aggregator)：由於預設來源資料庫 {args.source_db} 不存在，將嘗試創建一個包含 '{args.product_id}' 範例數據的假資料庫。")
            _create_dummy_source_db_if_needed(Path(args.source_db), args.product_id)
        except RuntimeError as e:
            print(f"錯誤 (aggregator)：{e}")
            return False # 或 raise

    success = _aggregate_ticks_to_ohlcv_internal(
        args.source_db,
        args.analytics_db,
        args.product_id,
        args.start_date,
        args.end_date
    )

    if success:
        print(f"商品 {args.product_id} 的時間序列聚合成功。")
        return True
    else:
        print(f"商品 {args.product_id} 的時間序列聚合失敗。")
        return False

# 注意：舊的 if __name__ == "__main__": 區塊已被移除，
# 因為此檔案現在作為模組被調用。
# 獨立測試可以通過直接調用 run_aggregation(["MXF1", "2023-01-01", "2023-03-02"]) 等方式進行，
# 或者建立一個單獨的測試腳本。
