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
from pathlib import Path # 標準樣板碼需要 Path
import logging # 確保 logging 已導入

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
    print(f"專案路徑校正時發生錯誤 (apps/taifex_data_transformer/run.py): {e}", file=sys.stderr)
# --- 標準化「路徑自我校正」樣板碼 END ---

from core.utils import setup_logger # 導入標準日誌模組 (已更新路徑)

RAW_TABLE_NAME = "raw_import_log" # 雖然此腳本不直接用，但保持一致性

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

def transform_and_load(raw_content_df: pd.DataFrame, target_conn: duckdb.DuckDBPyConnection, target_table: str, logger: logging.Logger, enable_status_updates: bool = False):
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

        # 內容類型初步判斷
        file_ext = Path(source_file).suffix.lower()
        if file_ext not in ['.csv', '.txt']:
            logger.warning(f"跳過非 CSV/TXT 檔案類型: {source_file}/{member_file} (副檔名: {file_ext})")
            continue

        try:
            # 使用 Pandas 強大的 CSV 解析器
            logger.debug(f"準備使用 pd.read_csv 解析檔案: {source_file}/{member_file}")
            logger.debug(f"傳遞給 StringIO 的文本內容 (前500字符): {content_text[:500]}")
            df = pd.read_csv(
                StringIO(content_text),
                encoding='utf-8', # 此時應為 UTF-8
                thousands=',', # 處理數字中的逗號
                low_memory=False,
                dtype=str, # 將所有欄位先讀取為字串，避免 Pandas 自動推斷類型錯誤
                index_col=False # 確保第一列不被當作索引
            )
            logger.debug(f"pd.read_csv 完成 for {source_file}/{member_file}. DataFrame info:")
            # StringIO() 用於捕獲 df.info() 的輸出到日誌
            buffer = StringIO()
            df.info(buf=buffer)
            logger.debug(buffer.getvalue())
            logger.debug(f"DataFrame head (解析後，清理前) for {source_file}/{member_file}:\n{df.head().to_string()}")
            if '交易日期' in df.columns:
                logger.debug(f"df['交易日期'] (解析後，清理前) for {source_file}/{member_file}:\n{df['交易日期'].head().to_string()}")
            logger.debug(f"df.iloc[:,0] (解析後，清理前) for {source_file}/{member_file}:\n{df.iloc[:,0].head().to_string()}")

            # 清理欄位名中的空格，並將其轉換為標準的 snake_case 或保持原樣以便後續 .get()
            original_columns = list(df.columns)
            df.columns = [col.strip().replace(' ', '_').replace('(', '').replace(')', '') for col in df.columns]
            cleaned_columns = list(df.columns)
            logger.debug(f"原始欄位名 for {source_file}/{member_file}: {original_columns}")
            logger.debug(f"清理後欄位名 for {source_file}/{member_file}: {cleaned_columns}")
            logger.debug(f"DataFrame head (清理後) for {source_file}/{member_file}:\n{df.head().to_string()}")
            # date_col_name 在這裡還未賦值，所以下面這幾行調試會出錯，先註解或移到後面
            # if '交易日期' in df.columns:
            #      logger.debug(f"df['交易日期'] (清理後) for {source_file}/{member_file}:\n{df['交易日期'].head().to_string()}")
            # if date_col_name and date_col_name in df.columns:
            #      logger.debug(f"df[date_col_name] (清理後, date_col_name='{date_col_name}') for {source_file}/{member_file}:\n{df[date_col_name].head().to_string()}")
            logger.debug(f"df.iloc[:,0] (清理後) for {source_file}/{member_file}:\n{df.iloc[:,0].head().to_string()}")


            # 欄位名稱靈活性：處理日期欄位
            date_col_name = None # 初始化 date_col_name
            # 優先使用 '交易日期' (清理後的)
            if '交易日期' in df.columns:
                date_col_name = '交易日期'
            # 如果 '交易日期' 不存在，嘗試 '日期' (清理後的)
            elif '日期' in df.columns:
                date_col_name = '日期'
            # 如果 '成交日期' (清理後的) 存在且上述兩者都不存在，則重命名並使用
            elif '成交日期' in df.columns:
                df.rename(columns={'成交日期': '交易日期'}, inplace=True) # 標準化為 '交易日期'
                date_col_name = '交易日期' # 更新 date_col_name 以反映重命名
                logger.info(f"成功將欄位 '成交日期' 兼容為 '交易日期' (來源: {source_file}/{member_file})")

            logger.debug(f"DataFrame columns after cleaning and date compatibility fix for {source_file}/{member_file}: {list(df.columns)}")
            logger.debug(f"DataFrame head for {source_file}/{member_file}:\n{df.head().to_string()}")

            if not date_col_name:
                logger.error(f"未找到有效的日期欄位 ('交易日期' 或 '日期') in df for {source_file}/{member_file}. Available columns: {list(df.columns)}")
                continue

            trading_date_series = df[date_col_name]
            logger.debug(f"選定的日期欄位 '{date_col_name}' series for {source_file}/{member_file} (前5行):\n{trading_date_series.head().to_string()}")
            logger.debug(f"選定的日期欄位 '{date_col_name}' series name: {trading_date_series.name}, dtype: {trading_date_series.dtype}, index: {trading_date_series.index}")


            # --- 增強日期解析 ---
            original_row_count = len(df)
            # 初始化 parsed_dates_series，確保其索引與 trading_date_series 一致
            parsed_dates_series = pd.Series([None] * len(trading_date_series), index=trading_date_series.index, dtype='object')

            common_formats = ["%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"]
            for fmt in common_formats:
                if parsed_dates_series.isnull().any():
                    # 確保 to_datetime 操作在原始 trading_date_series 上進行
                    attempt = pd.to_datetime(trading_date_series, format=fmt, errors='coerce')
                    parsed_dates_series = parsed_dates_series.fillna(attempt)

            # 嘗試民國年格式 (YYY/MM/DD)
            # 只處理前面 common_formats 未成功解析的日期
            roc_candidate_series = trading_date_series[parsed_dates_series.isnull()]
            if not roc_candidate_series.empty:
                roc_date_str_series = roc_candidate_series.astype(str)
                is_roc_format = roc_date_str_series.str.match(r'^\d{3}/\d{1,2}/\d{1,2}$')

                if is_roc_format.any():
                    roc_dates_to_process = roc_date_str_series[is_roc_format]
                    if not roc_dates_to_process.empty:
                        try:
                            parts = roc_dates_to_process.str.split('/', expand=True)
                            year = parts[0].astype(int) + 1911
                            month = parts[1]
                            day = parts[2]
                            gregorian_equivalent_str = year.astype(str) + '/' + month + '/' + day
                            roc_parsed = pd.to_datetime(gregorian_equivalent_str, format="%Y/%m/%d", errors='coerce')
                            parsed_dates_series.update(roc_parsed) # update 會基於索引更新
                        except Exception as e_roc:
                            logger.warning(f"處理民國年日期時發生錯誤 (來源: {source_file}/{member_file}): {e_roc}")

            mask_not_nat = pd.notna(parsed_dates_series)
            # Convert Timestamp objects to date objects for non-NaT values
            # After pd.to_datetime(errors='coerce'), non-NaT values are Timestamps
            for idx in parsed_dates_series[mask_not_nat].index:
                if isinstance(parsed_dates_series[idx], pd.Timestamp):
                    parsed_dates_series[idx] = parsed_dates_series[idx].date()
                # If it's already a date object (e.g. from a previous successful conversion in a loop), leave it.
                # If it's something else that's not NaT and not Timestamp, it's an unexpected state here.

            logger.debug(f"parsed_dates_series for {source_file}/{member_file} (前5行):\n{parsed_dates_series.head().to_string()}")

            # 將解析後的日期賦值給 DataFrame 的新欄位，確保索引對齊
            df['parsed_trading_date'] = parsed_dates_series

            df_filtered = df.dropna(subset=['parsed_trading_date']).copy() # dropna 基於 parsed_trading_date

            dropped_rows = original_row_count - len(df_filtered)
            if dropped_rows > 0:
                logger.warning(f"在 {source_file}/{member_file} 中，由於日期轉換失敗或日期不存在，共捨棄了 {dropped_rows} 行數據。")

            logger.debug(f"df_filtered head for {source_file}/{member_file} (Non-NaT dates):\n{df_filtered.head().to_string()}")

            if df_filtered.empty:
                logger.warning(f"在 {source_file}/{member_file} 中，所有有效數據行都因日期轉換失敗或不存在而被過濾。 (在捨棄 {dropped_rows} 行後)")
                continue

            df_transformed = pd.DataFrame()
            df_transformed['trading_date'] = df_filtered['parsed_trading_date']

            # 確保從 df_filtered 中獲取欄位
            # For product_id, try '契約' then '商品'
            if '契約' in df_filtered.columns:
                 df_transformed['product_id'] = df_filtered.get('契約')
            elif '商品' in df_filtered.columns: # Fallback for files like utf8_bom_fut_daily.csv
                 df_transformed['product_id'] = df_filtered.get('商品')
            else:
                 df_transformed['product_id'] = None


            df_transformed['expiry_month'] = df_filtered.get('到期月份週別') # 根據 large_ms950_options_sample.csv 標頭 (已清理)
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
            df_transformed['source_file'] = source_file
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
        try:
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
            logger.info(f"成功將 {len(final_df)} 筆數據載入到 '{target_table}'。")
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

    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR
    }
    logger = setup_logger(__name__, level=log_level_map.get(args.log_level.upper(), logging.INFO))

    logger.info("--- TAIFEX 數據轉換器 v35.0 (Python 迭代模式) 啟動 ---")
    logger.info(f"讀取自「原始數據艙」: {args.raw_db_path}")
    logger.info(f"寫入至「分析數據庫」: {args.analytics_db_path}")

    raw_conn = None
    analytics_conn = None
    try:
        if args.raw_db_path.lower() == "memory" or args.raw_db_path == ":memory:":
            logger.info(f"使用記憶體原始數據艙 (非只讀模式初始連接)。")
            raw_conn = duckdb.connect(database=":memory:")
        else:
            logger.info(f"從檔案系統連接原始數據艙 (只讀模式): {args.raw_db_path}")
            raw_conn = duckdb.connect(database=args.raw_db_path, read_only=True)

        analytics_conn = duckdb.connect(database=args.analytics_db_path)

        target_table = "daily_ohlc"
        create_target_table(analytics_conn, target_table)
        logger.info(f"成功連接資料庫並確保目標表 '{target_table}' 存在。")

        logger.info("正在從原始數據艙獲取待處理內容...")
        raw_content_df = raw_conn.execute("SELECT source_file, member_file, file_content_as_text FROM raw_import_log WHERE file_content_as_text IS NOT NULL AND file_content_as_text != ''").fetchdf()

        if raw_content_df.empty:
            logger.warning("在原始數據艙中未找到任何待處理的文本內容。")
            inserted_count = 0
        else:
            logger.info(f"發現 {len(raw_content_df)} 筆原始文本記錄，開始轉換與載入...")
            start_time = time.time()
            inserted_count = transform_and_load(raw_content_df, analytics_conn, target_table, logger, args.enable_status_updates) # Pass logger
            duration = time.time() - start_time
            logger.info(f"轉換與載入流程完成，耗時: {duration:.2f} 秒。")

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
