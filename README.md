# 專案作戰摘要

## 一、專案目錄樹

```
├── app/
    ├── src/
        ├── __init__.py
        ├── utils/
            ├── config_loader.py
            ├── logger.py
            ├── data_validator.py
            ├── __init__.py
            ├── file_handler.py
├── apps/
    ├── taifex_data_pipeline/
        ├── run.py
        ├── stream_unzipper.py
        ├── _test_harness.py
    ├── dossier_generator/
        ├── run.py
        ├── requirements.txt
    ├── taifex_data_transformer/
        ├── run.py
        ├── _test_harness_v35_full_system.py
        ├── _test_harness.py
        ├── __init__.py
    ├── daily_market_analyzer/
        ├── test_yfinance_client.py
        ├── run.py
        ├── yfinance_client.py
        ├── _test_v33_harness.py
        ├── report_generator.py
        ├── db_manager.py
        ├── analysis_engine.py
        ├── requirements.txt
        ├── __init__.py
    ├── pipeline_metadata_manager/
        ├── manager.py
        ├── _test_harness.py
        ├── __init__.py
        ├── config.py
```

## 二、微服務摘要

### 微服務：taifex_data_pipeline

**檔案路徑：** `apps/taifex_data_pipeline/run.py`

```python
# -*- coding: utf-8 -*-
# 高速載入器 (前身：數據精煉廠) v22.0 - 整合指紋驗證與預翻譯
import os
import sys
import argparse
import asyncio
from typing import List, Dict, Optional, Any
import hashlib
import duckdb
import pandas as pd
import io
import zipfile
import pytz
from datetime import datetime

# --- 路徑自我校正樣板碼 ---
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    apps_dir = os.path.dirname(current_dir)
    project_root = os.path.dirname(apps_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
except Exception as e:
    print(f"專案路徑校正時發生錯誤: {e}", file=sys.stderr)
# --- 路徑自我校正樣板碼結束 ---

from apps.pipeline_metadata_manager.manager import MetadataManager, calculate_file_fingerprint

# --- 全域日誌與配置 ---
class SimpleLogger:
    def __init__(self, level="INFO"):
        self.level = level.upper()
        self.levels = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}

    def _log(self, msg, level):
        if self.levels.get(level, 0) >= self.levels.get(self.level, 20):
            timestamp = datetime.now(pytz.timezone('Asia/Taipei')).strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{timestamp}] [{level}] {msg}")

    def debug(self, msg): self._log(msg, "DEBUG")
    def info(self, msg): self._log(msg, "INFO")
    def warning(self, msg): self._log(msg, "WARNING")
    def error(self, msg): self._log(msg, "ERROR")
    def success(self, msg): self._log(f"✅ {msg}", "INFO")

logger = SimpleLogger()

RAW_TABLE_NAME = "raw_import_log"

def get_raw_content_from_zip(file_path: str) -> Optional[Dict[str, bytes]]:
    try:
        contents = {}
        with zipfile.ZipFile(file_path, 'r') as zf:
            for member in zf.infolist():
                if not member.is_dir():
                    contents[member.filename] = zf.read(member.filename)
        return contents
    except zipfile.BadZipFile:
        logger.error(f"檔案不是一個有效的 ZIP 檔案: {file_path}")
        return None
    except Exception as e:
        logger.error(f"讀取 ZIP 檔案時發生錯誤 {file_path}: {e}")
        return None

async def load_raw_data_to_db(db_conn: duckdb.DuckDBPyConnection, file_path: str):
    file_name = os.path.basename(file_path)
    is_zip = file_name.lower().endswith('.zip')

    try:
        def decode_content(content_bytes: bytes) -> Optional[str]:
            for encoding in ['big5', 'ms950', 'utf-8']: # 嘗試常用編碼
                try:
                    return content_bytes.decode(encoding)
                except UnicodeDecodeError:
                    continue
            logger.warning(f"無法使用 BIG5, MS950, UTF-8 解碼檔案內容: {file_name} (部分內容可能無法正確解碼)")
            # 如果所有嘗試都失敗，可以選擇返回 None，或者帶有替換字元的字串
            return content_bytes.decode('utf-8', errors='replace')


        if is_zip:
            zip_contents = get_raw_content_from_zip(file_path) # 已修正：移除 await
            if not zip_contents:
                logger.warning(f"ZIP 檔案為空或無法讀取: {file_name}")
                return

            for member_name, content_bytes in zip_contents.items():
                decoded_text = decode_content(content_bytes)
                db_conn.execute(
                    f"INSERT INTO {RAW_TABLE_NAME} (source_file, member_file, file_content_blob, file_content_as_text, processed_at) VALUES (?, ?, ?, ?, ?)",
                    [file_name, member_name, content_bytes, decoded_text, datetime.now(pytz.utc)]
                )
            logger.info(f"成功將 ZIP 檔案 '{file_name}' 中的 {len(zip_contents)} 個成員載入到原始數據艙。")
        else:
            with open(file_path, 'rb') as f:
                content_bytes = f.read()
            decoded_text = decode_content(content_bytes)
            db_conn.execute(
                f"INSERT INTO {RAW_TABLE_NAME} (source_file, member_file, file_content_blob, file_content_as_text, processed_at) VALUES (?, ?, ?, ?, ?)",
                [file_name, None, content_bytes, decoded_text, datetime.now(pytz.utc)]
            )
            logger.info(f"成功將檔案 '{file_name}' 載入到原始數據艙。")

    except Exception as e:
        logger.error(f"將檔案 '{file_name}' 載入到資料庫時失敗: {e}")
        raise

async def main():
    parser = argparse.ArgumentParser(description="TAIFEX 高速載入器 (v22.0 - 含預翻譯)")
    parser.add_argument("--input-files", nargs='+', required=True, help="要處理的輸入檔案路徑列表。")
    parser.add_argument("--db-output-dir", required=True, help="資料庫檔案的輸出目錄。")
    parser.add_argument("--db-name", default="raw_taifex.duckdb", help="原始數據艙資料庫名稱。")
    parser.add_argument("--metadata-db-path", help="元數據資料庫的完整路徑。")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()
    logger.level = args.log_level.upper()

    db_path = os.path.join(args.db_output_dir, args.db_name)
    metadata_db_path = args.metadata_db_path or os.path.join(args.db_output_dir, "pipeline_metadata.duckdb")

    logger.info("--- TAIFEX 高速載入器 v22.0 (含預翻譯) 啟動 ---")
    logger.info(f"原始數據艙位置: {db_path}")
    logger.info(f"元數據資料庫位置: {metadata_db_path}")

    try:
        raw_db_conn = duckdb.connect(database=db_path)
        # 修正：先建立 SEQUENCE
        raw_db_conn.execute(f"CREATE SEQUENCE IF NOT EXISTS seq_raw_import;")
        raw_db_conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {RAW_TABLE_NAME} (
            id UBIGINT PRIMARY KEY DEFAULT nextval('seq_raw_import'),
            source_file VARCHAR,
            member_file VARCHAR,
            file_content_blob BLOB,
            file_content_as_text TEXT, -- 新增的預翻譯欄位
            processed_at TIMESTAMPTZ
        );
        """)
        meta_manager = MetadataManager(metadata_db_path)
    except Exception as e:
        logger.error(f"資料庫或元數據管理器初始化失敗: {e}")
        return

    total_files = len(args.input_files)
    processed_count = 0
    skipped_count = 0

    for file_path in args.input_files:
        if not os.path.exists(file_path):
            logger.warning(f"檔案不存在，跳過: {file_path}")
            continue
        try:
            fingerprint = calculate_file_fingerprint(file_path) # 已修正
            if meta_manager.check_fingerprint_exists(fingerprint):
                logger.info(f"偵測到已處理檔案 (指紋: {fingerprint[:8]}...), 跳過: {os.path.basename(file_path)}")
                skipped_count += 1
                continue

            logger.info(f"處理新檔案: {os.path.basename(file_path)}")
            await load_raw_data_to_db(raw_db_conn, file_path) # await 保留，因為 load_raw_data_to_db 是 async
            meta_manager.write_fingerprint( # 已修正
                fingerprint=fingerprint,
                filename=os.path.basename(file_path),
                filesize=os.path.getsize(file_path),
                etl_version="v35.0-loader"
            )
            processed_count += 1
        except Exception as e:
            logger.error(f"處理檔案 {file_path} 時發生未預期的嚴重錯誤: {e}")

    raw_db_conn.close()
    logger.info("--- 作戰總結 ---")
    logger.success(f"任務完成。總計檔案: {total_files} | 新處理: {processed_count} | 已跳過: {skipped_count}")

if __name__ == "__main__":
    asyncio.run(main())

```

### 微服務：taifex_data_transformer

**檔案路徑：** `apps/taifex_data_transformer/run.py`

```python
# -*- coding: utf-8 -*-
# 數據轉換器 (Transformer) v1.2 - Python 迭代 + 核心解析
import os
import sys
import argparse
import duckdb
import pandas as pd
from io import StringIO
from datetime import datetime
import pytz
import time
import json

# --- 路徑自我校正樣板碼 ---
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    apps_dir = os.path.dirname(current_dir)
    project_root = os.path.dirname(apps_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
except Exception as e:
    print(f"專案路徑校正時發生錯誤: {e}", file=sys.stderr)
# --- 路徑自我校正樣板碼結束 ---

class SimpleLogger:
    def __init__(self, level="INFO"):
        self.level = level.upper()
        self.levels = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}

    def _log(self, msg, level):
        if self.levels.get(level, 0) >= self.levels.get(self.level, 20):
            timestamp = datetime.now(pytz.timezone('Asia/Taipei')).strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{timestamp}] [{level}] {msg}")

    def debug(self, msg): self._log(msg, "DEBUG")
    def info(self, msg): self._log(msg, "INFO")
    def warning(self, msg): self._log(msg, "WARNING")
    def error(self, msg): self._log(msg, "ERROR")
    def success(self, msg): self._log(f"✅ {msg}", "INFO")

logger = SimpleLogger()

def create_target_table(conn: duckdb.DuckDBPyConnection, table_name: str):
    """確保目標分析表格存在"""
    conn.execute(f"CREATE SEQUENCE IF NOT EXISTS seq_{table_name};")
    conn.execute(f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id UBIGINT PRIMARY KEY DEFAULT nextval('seq_{table_name}'),
        trading_date DATE,
        product_id VARCHAR,
        expiry_month VARCHAR,
        strike_price DOUBLE,
        option_type VARCHAR,
        open DOUBLE,
        high DOUBLE,
        low DOUBLE,
        close DOUBLE,
        settlement_price DOUBLE,
        volume UBIGINT,
        open_interest UBIGINT,
        trading_session VARCHAR,
        source_file VARCHAR,
        member_file VARCHAR,
        transformed_at TIMESTAMPTZ
    );
    """)

def transform_and_load(raw_content_df: pd.DataFrame, target_conn: duckdb.DuckDBPyConnection, target_table: str, enable_status_updates: bool = False):
    """在 Python 中處理文本內容，並將結構化數據載入目標資料庫"""
    all_clean_dfs = []
    total_files = len(raw_content_df)

    for index, row in raw_content_df.iterrows():
        if enable_status_updates:
            status = {
                "progress": index + 1,
                "total": total_files,
                "message": f"正在轉換檔案 {index + 1}/{total_files} ({row.get('source_file', 'N/A')}/{row.get('member_file', 'N/A')})..."
            }
            print(f"##STATUS##{json.dumps(status, ensure_ascii=False)}")
            sys.stdout.flush()

        content_text = row['file_content_as_text']
        source_file = row['source_file']
        member_file = row['member_file']

        if not content_text or not content_text.strip():
            logger.warning(f"跳過空的文本內容 (來源: {source_file}/{member_file})")
            continue

        try:
            # 使用 Pandas 強大的 CSV 解析器
            df = pd.read_csv(
                StringIO(content_text),
                encoding='utf-8', # 此時應為 UTF-8
                thousands=',', # 處理數字中的逗號
                low_memory=False,
                dtype=str # 將所有欄位先讀取為字串，避免 Pandas 自動推斷類型錯誤
            )
            # 清理欄位名中的空格，並將其轉換為標準的 snake_case 或保持原樣以便後續 .get()
            df.columns = [col.strip().replace(' ', '_').replace('(', '').replace(')', '') for col in df.columns]

            # 緊急修復：兼容 '成交日期' 欄位
            # 在 pd.read_csv(...) 之後，且欄位名稱清理之後
            if '成交日期' in df.columns and '交易日期' not in df.columns:
                df.rename(columns={'成交日期': '交易日期'}, inplace=True)
                logger.info(f"成功將欄位 '成交日期' 兼容為 '交易日期' (來源: {source_file}/{member_file})")
            elif '成交日期' in df.columns and '交易日期' in df.columns:
                # 理論上不應該同時存在，但若存在，優先使用 '交易日期'，並記錄警告
                logger.warning(f"欄位 '成交日期' 和 '交易日期' 同時存在於 {source_file}/{member_file}。將優先使用 '交易日期'。")
            # 如果只有 '交易日期'，則什麼都不做，流程正常

            logger.debug(f"DataFrame columns after cleaning and compatibility fix for {source_file}/{member_file}: {list(df.columns)}")
            logger.debug(f"DataFrame head for {source_file}/{member_file}:\n{df.head().to_string()}")

            trading_date_series = df.get('交易日期') # 假設清理後的欄位名仍然是 '交易日期'
            if trading_date_series is None:
                logger.error(f"'交易日期' column not found in df for {source_file}/{member_file} after column cleaning. Available columns: {list(df.columns)}")
                # 嘗試使用原始可能的欄位名（如果清理邏輯有變）
                # trading_date_series = df.get('交易日期') # 這裡的 get 應該基於清理後的名稱
                # 如果真的找不到，就無法繼續處理這個檔案的日期
                continue
            else:
                logger.debug(f"'交易日期' series for {source_file}/{member_file}:\n{trading_date_series.to_string()}")

            # --- 增強日期解析 ---
            original_row_count = len(df)
            parsed_dates_series = pd.Series([None] * len(df), index=df.index, dtype='object')

            # 嘗試標準公元年格式 (YYYY/MM/DD 或 YYYY-MM-DD)
            common_formats = ["%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"]
            for fmt in common_formats:
                if parsed_dates_series.isnull().any(): # 只有當還有未解析的日期時才嘗試
                    attempt = pd.to_datetime(trading_date_series, format=fmt, errors='coerce')
                    parsed_dates_series = parsed_dates_series.fillna(attempt)

            # 嘗試民國年格式 (YYY/MM/DD)
            # 民國年轉換: 年份 + 1911
            roc_date_str_series = trading_date_series.astype(str)
            # 確保是 YYY/MM/DD 格式，避免匹配到 YYYY/MM/DD
            is_roc_format = roc_date_str_series.str.match(r'^\d{3}/\d{1,2}/\d{1,2}$')

            if is_roc_format.any(): # 只處理看起來像民國年的
                roc_dates_to_process = roc_date_str_series[is_roc_format & parsed_dates_series.isnull()]
                if not roc_dates_to_process.empty:
                    try:
                        # 分割日期，轉換年份，然後重新組合
                        parts = roc_dates_to_process.str.split('/', expand=True)
                        year = parts[0].astype(int) + 1911
                        month = parts[1]
                        day = parts[2]
                        # 重新組合為 YYYY/MM/DD 字串，然後讓 pd.to_datetime 處理
                        gregorian_equivalent_str = year.astype(str) + '/' + month + '/' + day
                        roc_parsed = pd.to_datetime(gregorian_equivalent_str, format="%Y/%m/%d", errors='coerce')
                        parsed_dates_series.update(roc_parsed)
                    except Exception as e_roc:
                        logger.warning(f"處理民國年日期時發生錯誤 (來源: {source_file}/{member_file}): {e_roc}")

            # 將成功解析的日期轉換為 .dt.date
            # 先檢查 Series 中的元素是否是 NaT 或 datetime 對象
            mask_not_nat = pd.notna(parsed_dates_series)
            # 僅對非 NaT 的 datetime 對象應用 .dt.date
            parsed_dates_series.loc[mask_not_nat] = parsed_dates_series[mask_not_nat].apply(lambda x: x.date() if pd.notna(x) else None)

            logger.debug(f"parsed_dates_series for {source_file}/{member_file}:\n{parsed_dates_series.to_string()}")

            df['parsed_trading_date'] = parsed_dates_series

            # 過濾掉日期轉換失敗的行 (NaT)
            df_filtered = df.dropna(subset=['parsed_trading_date']).copy()

            dropped_rows = original_row_count - len(df_filtered)
            if dropped_rows > 0:
                logger.warning(f"在 {source_file}/{member_file} 中，由於日期轉換失敗或日期不存在，共捨棄了 {dropped_rows} 行數據。")

            logger.debug(f"df_filtered head for {source_file}/{member_file} (Non-NaT dates):\n{df_filtered.head().to_string()}")

            if df_filtered.empty:
                logger.warning(f"在 {source_file}/{member_file} 中，所有有效數據行都因日期轉換失敗或不存在而被過濾。 (在捨棄 {dropped_rows} 行後)")
                continue

            # 現在 df_transformed 基於 df_filtered 建立
            df_transformed = pd.DataFrame()
            df_transformed['trading_date'] = df_filtered['parsed_trading_date']

            # 後續的 df.get('契約代碼') 應該改為 df_filtered.get('契約代碼')
            df_transformed['product_id'] = df_filtered.get('契約代碼') # 這裡的 get 是從 df_filtered 取值，所以不用改
            df_transformed['expiry_month'] = df_filtered.get('到期月份週別')
            df_transformed['strike_price'] = pd.to_numeric(df_filtered.get('履約價'), errors='coerce')
            df_transformed['option_type'] = df_filtered.get('買賣權')
            df_transformed['open'] = pd.to_numeric(df_filtered.get('開盤價'), errors='coerce')
            df_transformed['high'] = pd.to_numeric(df_filtered.get('最高價'), errors='coerce')
            df_transformed['low'] = pd.to_numeric(df_filtered.get('最低價'), errors='coerce')
            df_transformed['close'] = pd.to_numeric(df_filtered.get('收盤價'), errors='coerce')
            df_transformed['settlement_price'] = pd.to_numeric(df_filtered.get('結算價'), errors='coerce')

            volume_series = df_filtered.get('成交量')
            if volume_series is not None:
                df_transformed['volume'] = pd.to_numeric(volume_series.astype(str).str.replace(',', '', regex=False), errors='coerce').astype('Int64')
            else:
                df_transformed['volume'] = pd.Series(dtype='Int64')

            oi_series = df_filtered.get('未沖銷契約數')
            if oi_series is not None:
                df_transformed['open_interest'] = pd.to_numeric(oi_series.astype(str).str.replace(',', '', regex=False), errors='coerce').astype('Int64')
            else:
                df_transformed['open_interest'] = pd.Series(dtype='Int64')

            df_transformed['trading_session'] = df_filtered.get('交易時段')

            df_transformed['source_file'] = source_file # source_file 和 member_file 是循環變數，不是來自 df_filtered
            df_transformed['member_file'] = member_file
            df_transformed['transformed_at'] = datetime.now(pytz.utc)

            if not df_transformed.empty:
                all_clean_dfs.append(df_transformed)

        except Exception as e:
            logger.error(f"解析文本內容時失敗 (來源: {source_file}/{member_file}): {e}")
            import traceback
            logger.error(traceback.format_exc())


    if all_clean_dfs:
        final_df = pd.concat(all_clean_dfs, ignore_index=True)
        logger.info(f"準備將 {len(final_df)} 筆已轉換的記錄載入到 '{target_table}'...")

        # 確保 final_df 中的欄位順序與目標表一致 (如果使用 BY POSITION)
        # 或者使用 BY NAME (DuckDB 0.7.0+ 支持 INSERT INTO table BY NAME SELECT ...)
        try:
            # 為了最大的相容性和明確性，我們可以明確指定欄位列表
            # DuckDB's executemany is not directly for pandas DataFrames in the same way as to_sql.
            # We use DuckDB's ability to query pandas DataFrames directly.
            target_conn.register('final_df_view', final_df)
            target_conn.execute(f"""
                INSERT INTO {target_table} (
                    trading_date, product_id, expiry_month, strike_price, option_type,
                    open, high, low, close, settlement_price, volume, open_interest,
                    trading_session, source_file, member_file, transformed_at
                ) SELECT
                    trading_date, product_id, expiry_month, strike_price, option_type,
                    open, high, low, close, settlement_price, volume, open_interest,
                    trading_session, source_file, member_file, transformed_at
                FROM final_df_view
            """)
            target_conn.unregister('final_df_view')
            return len(final_df)
        except Exception as e:
            logger.error(f"將數據載入到 DuckDB 時發生錯誤: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return 0

    return 0


def main():
    parser = argparse.ArgumentParser(description="TAIFEX 數據轉換器 (v35.0 - Python 迭代模式)")
    parser.add_argument("--raw-db-path", required=True, help="原始數據艙資料庫的路徑。")
    parser.add_argument("--analytics-db-path", required=True, help="最終分析資料庫的路徑。")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--enable-status-updates", action="store_true", help="啟用狀態更新通訊協議")

    args = parser.parse_args()
    logger.level = args.log_level.upper()

    logger.info("--- TAIFEX 數據轉換器 v35.0 (Python 迭代模式) 啟動 ---")
    logger.info(f"讀取自「原始數據艙」: {args.raw_db_path}")
    logger.info(f"寫入至「分析數據庫」: {args.analytics_db_path}")

    raw_conn = None
    analytics_conn = None
    try:
        # 調整 raw_conn 的連接邏輯，以便處理記憶體資料庫
        if args.raw_db_path.lower() == "memory" or args.raw_db_path == ":memory:":
            logger.info(f"使用記憶體原始數據艙 (非只讀模式初始連接)。")
            raw_conn = duckdb.connect(database=":memory:") # 首次連接記憶體資料庫不能是只讀
        else:
            logger.info(f"從檔案系統連接原始數據艙 (只讀模式): {args.raw_db_path}")
            raw_conn = duckdb.connect(database=args.raw_db_path, read_only=True)

        analytics_conn = duckdb.connect(database=args.analytics_db_path) # 分析資料庫通常需要寫入

        target_table = "daily_ohlc"
        create_target_table(analytics_conn, target_table) # 確保表和序列存在
        logger.success(f"成功連接資料庫並確保目標表 '{target_table}' 存在。")

        logger.info("正在從原始數據艙獲取待處理內容...")
        # 只選擇必要的欄位
        raw_content_df = raw_conn.execute("SELECT source_file, member_file, file_content_as_text FROM raw_import_log WHERE file_content_as_text IS NOT NULL AND file_content_as_text != ''").fetchdf()

        if raw_content_df.empty:
            logger.warning("在原始數據艙中未找到任何待處理的文本內容。")
            inserted_count = 0
        else:
            logger.info(f"發現 {len(raw_content_df)} 筆原始文本記錄，開始轉換與載入...")
            start_time = time.time()
            inserted_count = transform_and_load(raw_content_df, analytics_conn, target_table, args.enable_status_updates)
            duration = time.time() - start_time
            logger.success(f"轉換與載入流程完成，耗時: {duration:.2f} 秒。")

        logger.info(f"驗證：共 {inserted_count} 筆乾淨數據被載入到分析資料庫。")

    except Exception as e:
        logger.error(f"數據轉換過程中發生嚴重錯誤: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if raw_conn: raw_conn.close()
        if analytics_conn: analytics_conn.close()
        logger.info("資料庫連接已關閉。")

    logger.info("--- TAIFEX 數據轉換器任務完成 ---")

if __name__ == "__main__":
    main()

```

### 微服務：daily_market_analyzer

**檔案路徑：** `apps/daily_market_analyzer/run.py`

```python
# -*- coding: utf-8 -*-
"""
每日市場分析儀 主執行入口。

接收命令列參數，協調 YFinanceClient 進行數據擷取與考古，
使用 DBManager 將數據存入資料庫，透過 AnalysisEngine 分析數據，
最後使用 ReportGenerator 生成每日市場洞察報告。
"""
import argparse
import sys
import os
from datetime import datetime
import pandas as pd

import psutil # 新增：用於偵測系統資源

# 設定專案路徑，確保可以正確匯入其他模組
def setup_project_path():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        # print(f"DEBUG: Project root added to sys.path: {project_root}") # 移除調試信息

setup_project_path()

try:
    from apps.daily_market_analyzer.yfinance_client import YFinanceClient
    from apps.daily_market_analyzer.db_manager import DBManager
    from apps.daily_market_analyzer.analysis_engine import AnalysisEngine
    from apps.daily_market_analyzer.report_generator import ReportGenerator
    # print("DEBUG: Successfully imported YFinanceClient, DBManager, AnalysisEngine, ReportGenerator") # 移除調試信息
except ModuleNotFoundError as e:
    print(f"錯誤：導入模組時發生錯誤 (ModuleNotFoundError): {e}") # 中文化
    # print(f"DEBUG: Current sys.path: {sys.path}") # 保留或移除調試信息
    # try:
    #     print(f"DEBUG: Contents of 'apps/': {os.listdir('apps')}")
    #     print(f"DEBUG: Contents of 'apps/daily_market_analyzer/': {os.listdir('apps/daily_market_analyzer')}")
    # except FileNotFoundError:
    #     print("DEBUG: 'apps/' or 'apps/daily_market_analyzer/' directory not found from current working directory.")
    raise

def main():
    """
    主執行函數 for Daily Market Analyzer。
    """
    parser = argparse.ArgumentParser(description="每日市場洞察報告與智能數據考古引擎。")
    # 核心參數
    parser.add_argument("--tickers", help="要分析的標的列表，以逗號分隔 (例如: AAPL,MSFT)。在純報告模式下非必需，但若提供則用於報告。")
    parser.add_argument("--start-date", help="數據分析/獲取的起始日期 (格式: YYYY-MM-DD)。")
    parser.add_argument("--end-date", help="數據分析/獲取的結束日期 (格式: YYYY-MM-DD)。")

    # 流程控制參數
    parser.add_argument("--data-only", action="store_true", help="僅執行數據獲取和存儲流程。")
    parser.add_argument("--report-only", action="store_true", help="僅執行報告生成流程 (需要已存在的數據)。")
    parser.add_argument("--report-start-date", help="報告生成的起始日期 (格式: YYYY-MM-DD)，配合 --report-only 使用。")
    parser.add_argument("--report-end-date", help="報告生成的結束日期 (格式: YYYY-MM-DD)，配合 --report-only 使用。")

    # 資料庫與表格參數
    parser.add_argument("--db-path", default="data_workspace/daily_market_analyzer.duckdb",
                        help="主分析資料庫的完整路徑 (例如: data_workspace/daily_market_analysis.duckdb)。")
    parser.add_argument("--db-name", default="daily_market_analysis.duckdb", # 實際已較少直接使用，db_path 更為主要
                        help="主分析資料庫的檔案名稱 (參考用，主要以 db_path 為準)。")
    parser.add_argument("--cache-db-path",
                        help="DuckDB 快取資料庫的最終存檔路徑 (目前 yfinance_client 直接使用主DB進行快取檢查)。") # 說明其當前用途
    parser.add_argument("--table-name", default="market_ohlcv_data",
                        help="資料庫中儲存 OHLCV 數據的表格名稱。")
    parser.add_argument("--process-uploads", action="store_true",
                        help="若指定，則處理 'uploads' 資料夾 (此功能待實現)。")

    args = parser.parse_args()

    # 參數校驗
    if args.data_only and args.report_only:
        print("錯誤：--data-only 和 --report-only 選項不能同時指定。")
        sys.exit(1)

    if args.report_only:
        if not args.report_start_date or not args.report_end_date:
            print("錯誤：當使用 --report-only 時，必須提供 --report-start-date 和 --report-end-date。")
            sys.exit(1)
        if not args.tickers: # 在報告模式下，tickers 也是需要的，以確定報告內容
            print("錯誤：當使用 --report-only 時，必須提供 --tickers。")
            sys.exit(1)
    elif not args.data_only: # 即完整流程模式
        if not args.tickers or not args.start_date or not args.end_date:
            print("錯誤：在完整流程模式下，必須提供 --tickers, --start-date, 和 --end-date。")
            sys.exit(1)
    elif args.data_only: # 純數據模式
        if not args.tickers or not args.start_date or not args.end_date:
            print("錯誤：當使用 --data-only 時，必須提供 --tickers, --start-date, 和 --end-date。")
            sys.exit(1)


    print("--- 每日市場洞察報告引擎 v33.0 ---")
    overall_start_time = datetime.now()

    print(f"任務開始時間: {overall_start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # --- 「動態資源壓榨」：DuckDB 記憶體動態配置 ---
    db_config = {}
    try:
        available_bytes = psutil.virtual_memory().available
        available_gb = available_bytes / (1024**3)

        # 計算目標記憶體限制：可用記憶體的 70%，上限 12GB，最小 256MB
        mem_limit_gb = min(available_gb * 0.7, 12.0)
        mem_limit_gb = max(mem_limit_gb, 0.25) # 最小 256MB

        memory_limit_mb = int(mem_limit_gb * 1024)
        memory_limit_setting_str = f"{memory_limit_mb}MB"

        db_config = {'memory_limit': memory_limit_setting_str}
        print(f"INFO: 偵測到可用記憶體: {available_gb:.2f} GB。動態設定 DuckDB memory_limit 為: {memory_limit_setting_str}")
    except Exception as e:
        print(f"警告: 偵測系統可用記憶體或設定 DuckDB 組態時發生錯誤: {e}。將使用 DuckDB 預設記憶體配置。")
    # --- 結束 「動態資源壓榨」 ---

    # 初始化通用組件，傳入動態計算的 DB 組態
    db_manager = DBManager(db_path=args.db_path, duckdb_config=db_config)
    analysis_engine = AnalysisEngine(db_manager_instance=db_manager) # ReportGenerator 需要

    overall_execution_log = {}
    tickers_list = []
    if args.tickers: # 即使在 report-only 模式也可能需要解析
        tickers_list = [ticker.strip().upper() for ticker in args.tickers.split(',')]

    task_duration_seconds = 0 # 初始化

    # 根據模式執行不同流程
    if args.data_only:
        print("執行模式：僅數據處理 (--data-only)")
        print(f"執行參數: 標的='{args.tickers}', 起始日='{args.start_date}', 結束日='{args.end_date}', 資料庫='{args.db_path}', 資料表='{args.table_name}'")
        yf_client = YFinanceClient(db_manager=db_manager)
        overall_execution_log, _ = run_data_pipeline(args, db_manager, yf_client, tickers_list)
        # task_duration_seconds 將在 run_data_pipeline 內部計算或在此處計算實際數據處理時間

    elif args.report_only:
        print("執行模式：僅報告生成 (--report-only)")
        print(f"執行參數: 標的='{args.tickers}', 報告起始日='{args.report_start_date}', 報告結束日='{args.report_end_date}', 資料庫='{args.db_path}', 資料表='{args.table_name}'")
        # 注意：overall_execution_log 在此模式下通常為空，因為不執行數據獲取
        # ReportGenerator 將主要基於資料庫中的數據生成報告
        # report_start_date 和 report_end_date 將覆蓋 args.start_date 和 args.end_date 用於報告範圍
        args.start_date = args.report_start_date # 將報告日期賦給主日期參數以供 ReportGenerator 使用
        args.end_date = args.report_end_date
        run_report_generation(args, db_manager, analysis_engine, {}, tickers_list, overall_start_time, 0) # log 為空, duration 0

    else: # 完整流程
        print("執行模式：完整流程 (數據處理與報告生成)")
        print(f"執行參數: 標的='{args.tickers}', 起始日='{args.start_date}', 結束日='{args.end_date}', 資料庫='{args.db_path}', 資料表='{args.table_name}'")
        yf_client = YFinanceClient(db_manager=db_manager)
        data_pipeline_start_time = datetime.now()
        overall_execution_log, _ = run_data_pipeline(args, db_manager, yf_client, tickers_list)
        data_pipeline_end_time = datetime.now()
        task_duration_seconds = (data_pipeline_end_time - data_pipeline_start_time).total_seconds() # 僅數據處理時間

        report_generation_start_time = datetime.now()
        run_report_generation(args, db_manager, analysis_engine, overall_execution_log, tickers_list, overall_start_time, task_duration_seconds)
        report_generation_end_time = datetime.now()
        # 可以選擇是否將報告生成時間也計入總時長，或分開記錄

    final_overall_end_time = datetime.now()
    total_script_duration = (final_overall_end_time - overall_start_time).total_seconds()
    print(f"\n--- 總任務執行完畢 ---")
    print(f"總體結束時間: {final_overall_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"腳本總執行時長: {total_script_duration:.2f} 秒")


def run_data_pipeline(args, db_manager: DBManager, yf_client: YFinanceClient, tickers_list: list):
    """
    執行數據獲取、處理和存儲的流程。
    """
    print("\n--- 開始數據處理流程 ---")
    pipeline_start_time = datetime.now()

    # 確保資料表存在
    db_manager.create_ohlcv_table(table_name=args.table_name)

    current_overall_execution_log = {}

    if not tickers_list: # 應該在 main 校驗過，但以防萬一
        print("警告 (run_data_pipeline): 標的列表為空，無法執行數據流程。")
        return {}, []

    for ticker_symbol in tickers_list:
        print(f"\n--- 開始處理標的 (數據流程): {ticker_symbol} ---")
        hydrated_df, ticker_execution_log = yf_client.hydrate_data_range(
            ticker_symbol, args.start_date, args.end_date,
            db_table_name=args.table_name,
            force_refresh=False # 可考慮添加 force_refresh 參數到命令列
        )

        for date_key, ticker_daily_log_value in ticker_execution_log.items():
            if date_key not in current_overall_execution_log:
                current_overall_execution_log[date_key] = {}
            current_overall_execution_log[date_key].update(ticker_daily_log_value)

        if hydrated_df is not None and not hydrated_df.empty:
            print(f"資訊：標的 {ticker_symbol} 成功擷取 {len(hydrated_df)} 筆數據。準備寫入資料庫...")
            try:
                db_manager.upsert_data(hydrated_df, table_name=args.table_name)
                print(f"資訊：標的 {ticker_symbol} 數據成功寫入資料庫。")
            except Exception as e:
                print(f"錯誤：標的 {ticker_symbol} 數據寫入資料庫失敗: {e}")
                for date_str_key in pd.date_range(args.start_date, args.end_date).strftime('%Y-%m-%d'):
                    if date_str_key in current_overall_execution_log and ticker_symbol in current_overall_execution_log[date_str_key]:
                        current_overall_execution_log[date_str_key][ticker_symbol]['status'] = 'db_upsert_failed'
                        base_message = current_overall_execution_log[date_str_key][ticker_symbol].get('message', "")
                        if not isinstance(base_message, str): base_message = str(base_message)
                        current_overall_execution_log[date_str_key][ticker_symbol]['message'] = base_message + f" 資料庫更新失敗: {str(e)}"
        else:
            print(f"資訊：標的 {ticker_symbol} 未擷取到任何數據。")
        print(f"--- 標的 (數據流程): {ticker_symbol} 處理完畢 ---")

    pipeline_end_time = datetime.now()
    pipeline_duration_seconds = (pipeline_end_time - pipeline_start_time).total_seconds()
    print(f"\n--- 數據處理流程結束 ---")
    print(f"數據流程執行時長: {pipeline_duration_seconds:.2f} 秒")

    return current_overall_execution_log, tickers_list


def run_report_generation(args, db_manager: DBManager, analysis_engine: AnalysisEngine,
                          input_execution_log: dict, report_tickers_list: list,
                          report_overall_start_time: datetime, data_task_duration_seconds: float):
    """
    執行報告生成的流程。
    """
    print("\n--- 開始報告生成流程 ---")
    report_pipeline_start_time = datetime.now()

    # 如果是 report-only 模式，tickers_list 可能需要從 args 重新獲取
    # 但已在 main 函數中將 args.tickers 賦予 tickers_list，並傳遞給 report_tickers_list
    if not report_tickers_list:
         print("警告 (run_report_generation): 標的列表為空，無法生成報告。")
         return

    # ReportGenerator 初始化時可以傳入空的 execution_log，它主要用於記錄數據獲取過程。
    # 在 report-only 模式下，這個 log 可能不包含數據獲取的詳細信息。
    # AnalysisEngine 則直接從 DB 讀取數據。
    report_gen = ReportGenerator(execution_log=input_execution_log, # 可以是空的，或者只包含數據獲取階段的日誌
                                 analysis_engine_instance=analysis_engine)

    # 報告的時間戳使用傳入的 overall_start_time (即腳本開始運行的時間或特定模式的開始時間)
    # 而不是重新生成一個 report_generation_time_for_filename，以保持一致性
    report_filename_dt_str = report_overall_start_time.strftime('%Y%m%d_%H%M%S')

    # 報告的日期範圍應使用 args.start_date 和 args.end_date
    # 在 report-only 模式下，這兩個值已在 main 中被 report_start_date 和 report_end_date 覆蓋
    report_start_d = args.start_date
    report_end_d = args.end_date
    if args.report_only: # 再次確認，以防萬一
        report_start_d = args.report_start_date
        report_end_d = args.report_end_date

    print(f"INFO (run_report_generation): Generating report for tickers: {report_tickers_list} over range [{report_start_d} to {report_end_d}]")

    final_report_str = report_gen.generate_full_report(
        overall_start_date_str=report_start_d,
        overall_end_date_str=report_end_d,
        report_generation_time=datetime.now(), # 使用當前時間作為報告生成時間點
        task_duration_seconds=data_task_duration_seconds, # 這是數據處理時長，或在純報告模式下為0
        target_tickers=report_tickers_list,
        db_table_name=args.table_name
    )

    print("\n--- 市場分析報告內容預覽 ---")
    preview_lines = final_report_str.splitlines()[:30]
    for line in preview_lines:
        print(line)
    if len(final_report_str.splitlines()) > 30:
        print("... (報告內容過長，已截斷預覽) ...")

    report_output_dir = os.path.join("data_workspace", "reports")
    os.makedirs(report_output_dir, exist_ok=True)

    report_filename = f"market_analysis_report_{report_filename_dt_str}.md"
    if args.data_only:
        report_filename = f"data_pipeline_summary_{report_filename_dt_str}.md" # 若未來要為 data-only 生成摘要
    elif args.report_only:
        report_filename = f"on_demand_report_{report_filename_dt_str}.md"

    report_filepath = os.path.join(report_output_dir, report_filename)

    try:
        with open(report_filepath, "w", encoding="utf-8") as f:
            f.write(final_report_str)
        print(f"\n報告已成功儲存至：{report_filepath}")
    except IOError as e:
        print(f"\n錯誤：儲存報告至檔案失敗：{e}")

    report_pipeline_end_time = datetime.now()
    report_duration_seconds = (report_pipeline_end_time - report_pipeline_start_time).total_seconds()
    print(f"報告生成流程執行時長: {report_duration_seconds:.2f} 秒")
    print("--- 報告生成流程結束 ---")


if __name__ == "__main__":
    # print(f"DEBUG: Current CWD for __main__ in daily_market_analyzer/run.py: {os.getcwd()}") # 移除調試信息
    # print(f"DEBUG: Current sys.path for __main__ in daily_market_analyzer/run.py: {sys.path}") # 移除調試信息

    # 移除 __main__ 中的延遲導入，因為已在頂部導入
    # if 'YFinanceClient' not in globals() or 'AnalysisEngine' not in globals(): # 檢查新加入的 AnalysisEngine
    #     try:
    #         # 更新導入路徑以匹配新的應用名稱
    #         from apps.daily_market_analyzer.yfinance_client import YFinanceClient
    #         from apps.daily_market_analyzer.db_manager import DBManager
    #         from apps.daily_market_analyzer.analysis_engine import AnalysisEngine
    #         from apps.daily_market_analyzer.report_generator import ReportGenerator
    #         # print("DEBUG: Late imports in daily_market_analyzer __main__ successful.") # 移除調試信息
    #     except ModuleNotFoundError as e:
    #         print(f"ERROR: Late ModuleNotFoundError in daily_market_analyzer __main__: {e}") # 中文化

    main()

```

### 微服務：pipeline_metadata_manager

未找到 `run.py` 檔案。

## 三、共享模組 (src/utils)

### 模組：config_loader.py

**檔案路徑：** `src/utils/config_loader.py`

```python
import yaml
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def load_project_config(path: str) -> Dict[str, Any]:
    """
    載入並解析 YAML 設定檔。

    Args:
        path (str): 設定檔的路徑。

    Returns:
        Dict[str, Any]: 解析後的設定內容 (字典形式)。

    Raises:
        FileNotFoundError: 如果指定的設定檔路徑未找到。
        yaml.YAMLError: 如果設定檔內容不是有效的 YAML 格式。
        TypeError: 如果解析後的設定檔內容不是一個字典。
    """
    logger.debug(f"嘗試從路徑 '{path}' 載入設定檔...")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        if not isinstance(config_data, dict):
            err_msg = f"設定檔 '{path}' 的內容不是有效的字典格式。"
            logger.error(err_msg)
            raise TypeError(err_msg)

        logger.info(f"設定檔 '{path}' 載入並驗證成功。")
        return config_data
    except FileNotFoundError:
        logger.error(f"設定檔錯誤：在路徑 '{path}' 未找到設定檔。")
        raise
    except yaml.YAMLError as e:
        logger.error(f"設定檔錯誤：解析 YAML 設定檔 '{path}' 失敗: {e}")
        raise
    except Exception as e:
        logger.error(f"載入設定檔 '{path}' 時發生未預期的錯誤: {e}", exc_info=True)
        raise

```

### 模組：logger.py

**檔案路徑：** `src/utils/logger.py`

```python
#
# 檔案: src/utils/logger.py
# 目的: 提供一個中心化的、可同時設定控制台與檔案輸出的日誌記錄器。
#
import logging
import sys
import os # Needed for os.makedirs
from logging.handlers import RotatingFileHandler

def setup_logger(name, log_file_path_str=None, level=logging.INFO):
    """
    設定一個 logger，可選擇性地將日誌輸出到檔案。

    Args:
        name (str): logger 的名稱。
        log_file_path_str (str, optional): 日誌檔案的路徑。若提供，則會啟用檔案日誌。 Defaults to None.
        level (int, optional): 日誌記錄的級別。 Defaults to logging.INFO.

    Returns:
        logging.Logger: 已設定好的 logger 實例。
    """
    # 避免重複添加 handler
    logger = logging.getLogger(name)

    # 檢查是否已經有 handler，如果有，並且日誌級別也相同，則直接返回
    # 這樣可以允許在不同地方用相同的名字和級別獲取logger而不會重複設定或丟失之前的設定
    if logger.hasHandlers() and logger.level == level:
        # 如果提供了新的 log_file_path_str，且之前沒有檔案 handler，或者路徑不同，則可能需要添加
        # 但為了簡化，這裡的邏輯是：一旦設定過，就不再輕易改變 handlers
        # 如果需要動態增減 handler 或改變路徑，需要更複雜的邏輯
        # 此處假設初次設定時決定好 handler

        # 更安全的做法是，如果 logger 已存在但 level 不同，則更新 level
        # 但 handler 的添加應該是冪等的。目前的 if logger.hasHandlers() return logger 策略更簡單。
        # 為了允許後續呼叫（如果首次未設定file handler）能加上 file handler，我們調整一下邏輯：
        # 只在沒有 handler 時設定 level 和 console handler。
        # File handler 可以後續添加（如果提供了 log_file_path_str 且之前未設定過同路徑的 file handler）

        pass # 繼續執行，以便可以按需添加 file handler 或調整


    if not logger.handlers: # 只有在完全沒有 handler 時才設定基礎 level 和 console
        logger.setLevel(level)
        # 建立一個通用的格式化器
        formatter = logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

        # 1. 設定控制台 Handler (總是啟用)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    else: # logger 已有 handler，獲取其 formatter 以便新的 file handler 使用
        # 假設所有 handler 使用相同的 formatter，取第一個 handler 的 formatter
        formatter = logger.handlers[0].formatter
        # 確保 logger level 與請求的 level 一致（允許調低，但不輕易調高已有的）
        if logger.level > level: # 如果現有 level 更高（更不詳細），則更新為請求的更詳細的 level
            logger.setLevel(level)


    # 2. 設定檔案 Handler (如果提供了路徑)
    if log_file_path_str:
        # 檢查是否已存在相同路徑的 FileHandler，避免重複添加
        has_matching_file_handler = False
        for handler in logger.handlers:
            if isinstance(handler, RotatingFileHandler) and handler.baseFilename == os.path.abspath(log_file_path_str):
                has_matching_file_handler = True
                break

        if not has_matching_file_handler:
            try:
                # 確保日誌檔案所在的目錄存在
                log_dir = os.path.dirname(os.path.abspath(log_file_path_str))
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir, exist_ok=True)
                    # logger.info(f"Log directory created: {log_dir}") # 這條日誌可能在 logger 完全設定好之前發出

                # 使用 RotatingFileHandler 避免日誌檔無限增大
                # 這裡設定每個檔案最大 5MB，保留 5 個備份檔
                file_handler = RotatingFileHandler(
                    log_file_path_str, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
                )
                file_handler.setFormatter(formatter) # 使用已有的或新建立的 formatter
                file_handler.setLevel(level) # 確保 file handler 也遵循請求的 level
                logger.addHandler(file_handler)
                # 這條日誌現在應該可以正常工作了
                # logger.info(f"File logging enabled. Log file at: {log_file_path_str}")
                # 為了避免在 setup_logger 內部產生過多日誌，可以考慮由呼叫者記錄此訊息
            except Exception as e:
                # 如果設定檔案日誌失敗，至少控制台日誌還在
                logger.error(f"Failed to set up file handler at {log_file_path_str}: {e}", exc_info=True)
        # else:
            # logger.debug(f"File handler for {log_file_path_str} already exists.")

    return logger

if __name__ == '__main__':
    # 測試 logger 功能
    # 第一次設定，應同時有控制台和檔案
    logger1 = setup_logger("TestApp1", log_file_path_str="logs/app_test1.log", level=logging.DEBUG)
    logger1.debug("Debug message for TestApp1 - to console and file.")
    logger1.info("Info message for TestApp1 - to console and file.")

    # 第二次獲取同一個 logger，不應重複 handler，日誌級別應保持
    logger1_again = setup_logger("TestApp1", log_file_path_str="logs/app_test1.log", level=logging.INFO)
    logger1_again.info("Info message again for TestApp1 - should not have double handlers.")
    logger1_again.debug("Debug message again for TestApp1 - should still appear if level was DEBUG.")


    # 測試只設定控制台
    logger_console_only = setup_logger("ConsoleOnlyApp", level=logging.INFO)
    logger_console_only.info("This message is for console only.")
    # logger_console_only.debug("This debug message for console only should not appear.") #因為 level 是 INFO

    # 測試後續為已有的 console-only logger 添加檔案 handler
    logger_console_only_add_file = setup_logger("ConsoleOnlyApp", log_file_path_str="logs/console_app_now_with_file.log", level=logging.INFO)
    logger_console_only_add_file.info("This message for ConsoleOnlyApp should now also go to file.")
    logger_console_only_add_file.error("An error message for ConsoleOnlyApp - to console and file.")

    # 測試 RotatingFileHandler (手動執行多次並查看 logs/ 目錄)
    logger_rotate = setup_logger("RotateTest", log_file_path_str="logs/rotate_test.log", level=logging.INFO)
    for i in range(10): # 模擬產生一些日誌
        logger_rotate.info(f"Rotation test message {i+1}")

    print("\nLoggers configured. Check 'logs/' directory for output files (app_test1.log, console_app_now_with_file.log, rotate_test.log).")
    print(f"Logger 'TestApp1' handlers: {logging.getLogger('TestApp1').handlers}")
    print(f"Logger 'ConsoleOnlyApp' handlers: {logging.getLogger('ConsoleOnlyApp').handlers}")
    print(f"Logger 'RotateTest' handlers: {logging.getLogger('RotateTest').handlers}")

    # 測試不同 level 的獲取
    logger_info = setup_logger("MultiLevelTest", level=logging.INFO)
    logger_info.info("Info level set for MultiLevelTest.")
    logger_debug_later = setup_logger("MultiLevelTest", level=logging.DEBUG) # 嘗試設定更詳細的 level
    logger_debug_later.debug("Debug level for MultiLevelTest - should appear now.")
    print(f"Logger 'MultiLevelTest' level: {logging.getLogger('MultiLevelTest').level} (expected {logging.DEBUG})")
    print(f"Logger 'MultiLevelTest' handlers: {logging.getLogger('MultiLevelTest').handlers}")

    # 測試路徑不存在時自動建立
    logger_new_dir = setup_logger("NewDirLogger", log_file_path_str="new_log_dir/new_dir_test.log", level=logging.INFO)
    logger_new_dir.info("Testing log creation in a new directory.")
    print(f"Logger 'NewDirLogger' handlers: {logging.getLogger('NewDirLogger').handlers}")
    print("Check for 'new_log_dir/new_dir_test.log'.")

    # 測試設定 file handler 失敗的情況 (例如權限問題，這裡用一個不太可能失敗的路徑模擬)
    # 在沙箱中可能難以模擬真實的權限錯誤，但至少錯誤處理路徑被包含了
    logger_fail_safe = setup_logger("FailSafeLogger", log_file_path_str="/hopefully_non_writable/test.log", level=logging.INFO)
    logger_fail_safe.info("This info message should appear on console even if file logging failed.")
    print(f"Logger 'FailSafeLogger' handlers (should only have StreamHandler if path was bad): {logging.getLogger('FailSafeLogger').handlers}")

# ```

```

### 模組：data_validator.py

**檔案路徑：** `src/utils/data_validator.py`

```python
# src/utils/data_validator.py

def is_valid_data(data: dict) -> bool:
    """
    檢查資料是否有效。
    此為範例函數，具體邏輯需根據實際需求填寫。
    """
    if not isinstance(data, dict):
        return False
    if not data: # 檢查是否為空字典
        return False
    # 添加更多驗證邏輯...
    return True

def format_data(data: dict) -> dict:
    """
    格式化資料。
    此為範例函數。
    """
    # 範例：將所有字串值轉換為小寫
    formatted = {}
    for key, value in data.items():
        if isinstance(value, str):
            formatted[key] = value.lower()
        else:
            formatted[key] = value
    return formatted

```

### 模組：__init__.py

**檔案路徑：** `src/utils/__init__.py`

```python
# This file makes src/utils a Python sub-package.

```

### 模組：file_handler.py

**檔案路徑：** `src/utils/file_handler.py`

```python
# src/utils/file_handler.py
import json

def save_to_json(data: dict, filepath: str) -> bool:
    """
    將字典儲存為 JSON 檔案。

    Args:
        data: 要儲存的字典。
        filepath: JSON 檔案的路徑。

    Returns:
        如果儲存成功則返回 True，否則 False。
    """
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except IOError as e:
        print(f"儲存檔案錯誤 {filepath}: {e}")
        return False
    except Exception as e:
        print(f"儲存 JSON 時發生未知錯誤: {e}")
        return False

def load_from_json(filepath: str) -> dict | None:
    """
    從 JSON 檔案載入字典。

    Args:
        filepath: JSON 檔案的路徑。

    Returns:
        載入的字典，如果失敗則返回 None。
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"錯誤：找不到檔案 {filepath}")
        return None
    except json.JSONDecodeError as e:
        print(f"解碼 JSON 錯誤 {filepath}: {e}")
        return None
    except Exception as e:
        print(f"載入 JSON 時發生未知錯誤: {e}")
        return None

```
