import os
import sys
import argparse
import duckdb
import pandas as pd
import requests
from datetime import datetime
from pathlib import Path # 導入 Path

# --- 新版 pathlib 標準化路徑定義 ---
# 路徑自我校正樣板碼
try:
    # 使用 Path 物件來獲取專案根目錄
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except Exception as e:
    print(f"專案路徑校正時發生錯誤: {e}", file=sys.stderr)
    sys.exit(1)
# --- 標準化路徑定義結束 ---

# 模擬 core.utils.setup_logger，因為我們沒有這個檔案
# 在真實環境中，請確保 core.utils.setup_logger 可用
import logging
def setup_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    return logger
# --- 模擬 setup_logger 結束 ---


# 設定日誌
logger = setup_logger('fred_client')

# --- 常數定義 ---
FRED_API_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
DATABASE_PATH = project_root / 'market_data.duckdb' # 使用 pathlib
TABLE_NAME = 'fred_data'

def get_fred_api_key():
    """安全地從環境變數獲取 FRED API 金鑰"""
    api_key = os.getenv('FRED_API_KEY')
    if not api_key:
        logger.error("環境變數 FRED_API_KEY 未設定。")
        raise ValueError("缺少 FRED API 金鑰，請設定環境變數 FRED_API_KEY。")
    return api_key

def fetch_fred_data(series_id: str, api_key: str) -> pd.DataFrame:
    """從 FRED API 獲取指定 series_id 的數據"""
    params = {
        'series_id': series_id,
        'api_key': api_key,
        'file_type': 'json',
    }
    logger.info(f"正在從 FRED 獲取數據，ID: {series_id}...")
    try:
        response = requests.get(FRED_API_BASE_URL, params=params)
        response.raise_for_status()  # 如果請求失敗 (如 404)，則拋出異常
        data = response.json()

        if not data.get('observations'):
            logger.warning(f"FRED API 未返回 ID '{series_id}' 的觀測數據。可能是無效的 ID 或該日期範圍無數據。")
            return pd.DataFrame()

        df = pd.DataFrame(data['observations'])
        df = df[['date', 'value']]
        df['date'] = pd.to_datetime(df['date'])
        # 將 '.' 或其他非數值轉換為 NaN，然後進行插值或填充
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df.dropna(subset=['value'], inplace=True) # 移除無法轉換為數值的行

        df['series_id'] = series_id # 新增 series_id 欄位

        logger.info(f"成功獲取 {len(df)} 筆 ID '{series_id}' 的數據。")
        return df[['date', 'series_id', 'value']]

    except requests.exceptions.RequestException as e:
        logger.error(f"請求 FRED API 時發生錯誤 (ID: {series_id}): {e}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"處理 FRED 數據時發生未知錯誤 (ID: {series_id}): {e}")
        return pd.DataFrame()


def save_to_duckdb(df: pd.DataFrame, db_path: str, table_name: str):
    """將 DataFrame 數據增量寫入 DuckDB"""
    if df.empty:
        logger.info("數據為空，無需寫入資料庫。")
        return

    try:
        # 確保 db_path 是字串路徑
        db_path_str = str(db_path) if not isinstance(db_path, str) else db_path
        with duckdb.connect(database=db_path_str, read_only=False) as con:
            # 創建表如果不存在
            con.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    date DATE,
                    series_id VARCHAR,
                    value DOUBLE,
                    PRIMARY KEY (date, series_id)
                );
            """)

            # 使用暫存表和 INSERT ON CONFLICT (UPSERT) 來避免重複
            # DuckDB v0.9.0+ 支持 ON CONFLICT
            con.register('temp_df', df)
            con.execute(f"""
                INSERT INTO {table_name}
                SELECT * FROM temp_df
                ON CONFLICT (date, series_id) DO UPDATE SET value = excluded.value;
            """)

            count = len(df)
            logger.info(f"成功將 {count} 筆數據寫入或更新至資料庫 '{db_path}' 的 '{table_name}' 表。")

    except Exception as e:
        logger.error(f"寫入數據到 DuckDB 時發生錯誤: {e}")


def main():
    parser = argparse.ArgumentParser(description="從 FRED API 下載經濟數據並存入 DuckDB。")
    parser.add_argument(
        '--series_ids',
        nargs='+',
        required=True,
        help="一個或多個要下載的 FRED Series ID (例如: DGS10 T10Y2Y)。"
    )
    parser.add_argument(
        '--db_path',
        type=str,
        default=str(DATABASE_PATH), # 使用 pathlib 定義的 DATABASE_PATH，並轉為字串
        help=f"DuckDB 資料庫檔案路徑 (預設: {str(DATABASE_PATH)})"
    )
    args = parser.parse_args()

    try:
        api_key = get_fred_api_key()
        all_data = []
        for series_id in args.series_ids:
            df = fetch_fred_data(series_id, api_key)
            if not df.empty:
                all_data.append(df)

        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            save_to_duckdb(combined_df, args.db_path, TABLE_NAME)
        else:
            logger.warning("未獲取到任何有效數據。")

    except ValueError as e:
        logger.error(f"任務中止: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"發生未預期的嚴重錯誤: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
