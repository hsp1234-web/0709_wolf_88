# -*- coding: utf-8 -*-
# TAIFEX 智慧情報下載器 v23.0 - 情境感知與實彈測試
import os
import sys
import argparse
import asyncio
import aiohttp
from typing import List, Dict, Optional, Any
import hashlib
import logging
import duckdb
import pandas as pd
import io
import zipfile
import pytz
from datetime import datetime, date as datetime_date
from pathlib import Path

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    project_root = Path(os.getcwd())
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    print(f"警告：__file__ 未定義，專案路徑校正可能不準確。已將 {project_root} 加入 sys.path。", file=sys.stderr)
except Exception as e:
    print(f"專案路徑校正時發生錯誤 (apps/taifex_data_pipeline/run.py): {e}", file=sys.stderr)
# --- 標準化「路徑自我校正」樣板碼 END ---

from apps.pipeline_metadata_manager.manager import MetadataManager, calculate_file_fingerprint
from core.utils import setup_logger

# --- 全域日誌與配置 ---
RAW_TABLE_NAME = "raw_import_log"
TAIFEX_DOWNLOAD_URL_TEMPLATE = "https://www.taifex.com.tw/file/taifex/Dailydownload/DailydownloadCSV/Data_{date_str}.zip"

# --- 自定義異常 ---
class TaifexDownloadError(Exception):
    """針對 TAIFEX 下載過程中發生的特定錯誤。"""
    pass

# --- Exit Codes ---
EXIT_CODE_SUCCESS = 0
EXIT_CODE_NO_DATA_AVAILABLE = 0
EXIT_CODE_DOWNLOAD_ERROR = 1
EXIT_CODE_DB_ERROR = 2
EXIT_CODE_GENERIC_ERROR = 3

def get_raw_content_from_zip(file_path: str, logger: logging.Logger) -> Optional[Dict[str, bytes]]:
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

async def load_raw_data_to_db(db_conn: duckdb.DuckDBPyConnection, file_path: str, logger: logging.Logger):
    file_name = os.path.basename(file_path)
    is_zip = file_name.lower().endswith('.zip')
    try:
        def decode_content(content_bytes: bytes, current_file_name: str, logger_instance: logging.Logger) -> Optional[str]:
            for encoding in ['big5', 'ms950', 'utf-8']:
                try:
                    return content_bytes.decode(encoding)
                except UnicodeDecodeError:
                    continue
            logger_instance.warning(f"無法使用 BIG5, MS950, UTF-8 解碼檔案內容: {current_file_name} (部分內容可能無法正確解碼)")
            return content_bytes.decode('utf-8', errors='replace')

        if is_zip:
            zip_contents = get_raw_content_from_zip(file_path, logger)
            if not zip_contents:
                logger.warning(f"ZIP 檔案為空或無法讀取: {file_name}")
                return
            for member_name, content_bytes in zip_contents.items():
                decoded_text = decode_content(content_bytes, f"{file_name}/{member_name}", logger)
                db_conn.execute(
                    f"INSERT INTO {RAW_TABLE_NAME} (source_file, member_file, file_content_blob, file_content_as_text, processed_at) VALUES (?, ?, ?, ?, ?)",
                    [file_name, member_name, content_bytes, decoded_text, datetime.now(pytz.utc)]
                )
            logger.info(f"成功將 ZIP 檔案 '{file_name}' 中的 {len(zip_contents)} 個成員載入到原始數據艙。")
        else:
            with open(file_path, 'rb') as f:
                content_bytes = f.read()
            decoded_text = decode_content(content_bytes, file_name, logger)
            db_conn.execute(
                f"INSERT INTO {RAW_TABLE_NAME} (source_file, member_file, file_content_blob, file_content_as_text, processed_at) VALUES (?, ?, ?, ?, ?)",
                [file_name, None, content_bytes, decoded_text, datetime.now(pytz.utc)]
            )
            logger.info(f"成功將檔案 '{file_name}' 載入到原始數據艙。")
    except Exception as e:
        logger.error(f"將檔案 '{file_name}' 載入到資料庫時失敗: {e}")
        raise

async def download_taifex_data(
    target_date: datetime_date,
    download_dir: Path,
    logger: logging.Logger,
    session: aiohttp.ClientSession
) -> Optional[Path]:
    date_str_yyyymmdd = target_date.strftime("%Y%m%d")
    date_str_yyyy_mm_dd = target_date.strftime("%Y-%m-%d")
    download_url = TAIFEX_DOWNLOAD_URL_TEMPLATE.format(date_str=date_str_yyyymmdd)
    output_filename = f"Data_{date_str_yyyymmdd}.zip"
    output_path = download_dir / output_filename
    logger.info(f"準備從 {download_url} 下載 {date_str_yyyy_mm_dd} 的資料...")
    try:
        async with session.get(download_url) as response:
            if response.status == 200:
                content_type = response.headers.get('Content-Type', '').lower()
                if 'application/zip' not in content_type and 'application/x-zip-compressed' not in content_type:
                    preview = await response.content.read(1024)
                    preview_text = preview.decode('utf-8', errors='ignore').lower()
                    if 'html' in preview_text or 'error' in preview_text or '查無資料' in preview_text:
                        logger.info(f"[INFO] No data available for {date_str_yyyy_mm_dd} (Holiday/No Trading Day/Out of Range). Server returned 200 but content is not ZIP (likely an HTML error page). This is a successful run with zero records.")
                        return None
                download_dir.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    while True:
                        chunk = await response.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                if not zipfile.is_zipfile(output_path) or os.path.getsize(output_path) == 0:
                    logger.warning(f"[WARNING] Downloaded file for {date_str_yyyy_mm_dd} from {download_url} is not a valid or non-empty ZIP file. It might be an error page or corrupted data. Treating as no data.")
                    if output_path.exists():
                        output_path.unlink()
                    logger.info(f"[INFO] No data available for {date_str_yyyy_mm_dd} (Invalid ZIP). This is a successful run with zero records.")
                    return None
                logger.info(f"[INFO] Successfully downloaded data for {date_str_yyyy_mm_dd} to {output_path}.")
                return output_path
            elif response.status == 404:
                logger.info(f"[INFO] No data available for {date_str_yyyy_mm_dd} (Holiday/No Trading Day/Out of Range). Server responded with 404 Not Found. This is a successful run with zero records.")
                return None
            else:
                error_message = f"Failed to download data for {date_str_yyyy_mm_dd}. HTTP Status: {response.status}. URL: {download_url}"
                logger.error(f"[ERROR] {error_message}")
                raise TaifexDownloadError(error_message)
    except aiohttp.ClientConnectorError as e:
        error_message = f"Network connection error for {date_str_yyyy_mm_dd}: {e}. URL: {download_url}"
        logger.error(f"[ERROR] {error_message}")
        raise TaifexDownloadError(error_message) from e
    except asyncio.TimeoutError as e:
        error_message = f"Timeout during download for {date_str_yyyy_mm_dd}. URL: {download_url}"
        logger.error(f"[ERROR] {error_message}")
        raise TaifexDownloadError(error_message) from e
    except aiohttp.ClientError as e:
        error_message = f"A client error occurred during download for {date_str_yyyy_mm_dd}: {e}. URL: {download_url}"
        logger.error(f"[ERROR] {error_message}")
        raise TaifexDownloadError(error_message) from e
    except Exception as e:
        error_message = f"An unexpected error occurred during download for {date_str_yyyy_mm_dd}: {e}. URL: {download_url}"
        logger.error(f"[ERROR] {error_message}")
        raise TaifexDownloadError(error_message) from e

async def main():
    parser = argparse.ArgumentParser(description="TAIFEX 智慧情報下載器 (v23.0 - 加固版)")
    parser.add_argument("--date", required=True, help="要下載資料的日期 (格式: YYYY-MM-DD 或 YYYYMMDD)。")
    parser.add_argument("--output-dir", required=True, help="下載檔案的儲存目錄以及資料庫檔案的輸出目錄。")
    parser.add_argument("--db-name", default="raw_taifex.duckdb", help="原始數據艙資料庫名稱。")
    parser.add_argument("--metadata-db-path", help="元數據資料庫的完整路徑 (可選，若提供則啟用指紋檢查)。")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("--load-to-db", action='store_true', help="下載成功後，將資料載入到 DuckDB 資料庫。")

    args, unknown = parser.parse_known_args()
    if unknown:
        print(f"[INFO] 忽略未知參數: {unknown}", file=sys.stderr)

    log_level_map = {
        "DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING,
        "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL
    }
    logger = setup_logger("taifex_downloader", level=log_level_map.get(args.log_level.upper(), logging.INFO))

    target_date_obj: Optional[datetime_date] = None
    try:
        if '-' in args.date:
            target_date_obj = datetime.strptime(args.date, "%Y-%m-%d").date()
        else:
            target_date_obj = datetime.strptime(args.date, "%Y%m%d").date()
    except ValueError:
        logger.error(f"日期格式錯誤: '{args.date}'。請使用 YYYY-MM-DD 或 YYYYMMDD 格式。")
        sys.exit(EXIT_CODE_GENERIC_ERROR)

    output_dir_path = Path(args.output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    db_path = output_dir_path / args.db_name

    effective_metadata_db_path: Optional[str] = None
    if args.metadata_db_path:
        if os.path.isabs(args.metadata_db_path):
            effective_metadata_db_path = args.metadata_db_path
            Path(effective_metadata_db_path).parent.mkdir(parents=True, exist_ok=True)
        else:
            effective_metadata_db_path = str(output_dir_path / args.metadata_db_path)
            Path(effective_metadata_db_path).parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"--- TAIFEX 智慧情報下載器 v23.0 啟動 (目標日期: {target_date_obj.strftime('%Y-%m-%d')}) ---")
    logger.info(f"輸出目錄: {output_dir_path}")
    if args.load_to_db:
        logger.info(f"原始數據艙位置: {db_path}")
        if effective_metadata_db_path:
            logger.info(f"元數據資料庫位置: {effective_metadata_db_path}")
        else:
            logger.info("元數據資料庫未配置，將不進行指紋檢查或寫入元數據。")
    else:
        logger.info("僅執行下載任務，不載入資料庫。")

    exit_code = EXIT_CODE_GENERIC_ERROR
    downloaded_file_path: Optional[Path] = None

    try:
        async with aiohttp.ClientSession() as session:
            downloaded_file_path = await download_taifex_data(target_date_obj, output_dir_path, logger, session)

        if downloaded_file_path:
            exit_code = EXIT_CODE_SUCCESS
            if args.load_to_db:
                logger.info(f"準備將檔案 {downloaded_file_path.name} 載入資料庫...")
                meta_manager: Optional[MetadataManager] = None
                if effective_metadata_db_path:
                    try:
                        meta_manager = MetadataManager(effective_metadata_db_path)
                    except Exception as e:
                        logger.error(f"元數據管理器初始化失敗: {e}")
                        exit_code = EXIT_CODE_DB_ERROR

                if exit_code != EXIT_CODE_DB_ERROR:
                    if meta_manager:
                        try:
                            fingerprint = calculate_file_fingerprint(str(downloaded_file_path))
                            if meta_manager.check_fingerprint_exists(fingerprint):
                                logger.info(f"偵測到已處理檔案 (指紋: {fingerprint[:8]}...), 跳過資料庫載入: {downloaded_file_path.name}")
                            else:
                                try:
                                    raw_db_conn = duckdb.connect(database=str(db_path))
                                    raw_db_conn.execute(f"CREATE SEQUENCE IF NOT EXISTS seq_raw_import;")
                                    raw_db_conn.execute(f"""
                                    CREATE TABLE IF NOT EXISTS {RAW_TABLE_NAME} (
                                        id UBIGINT PRIMARY KEY DEFAULT nextval('seq_raw_import'),
                                        source_file VARCHAR,
                                        member_file VARCHAR,
                                        file_content_blob BLOB,
                                        file_content_as_text TEXT,
                                        processed_at TIMESTAMPTZ
                                    );
                                    """)
                                    await load_raw_data_to_db(raw_db_conn, str(downloaded_file_path), logger)
                                    raw_db_conn.close()
                                    meta_manager.write_fingerprint(
                                        fingerprint=fingerprint,
                                        filename=downloaded_file_path.name,
                                        filesize=downloaded_file_path.stat().st_size,
                                        etl_version="v23.0-downloader"
                                    )
                                    logger.info(f"檔案 {downloaded_file_path.name} 成功載入資料庫並記錄元數據。")
                                except Exception as e:
                                    logger.error(f"處理檔案 {downloaded_file_path.name} 載入資料庫時發生錯誤: {e}")
                                    exit_code = EXIT_CODE_DB_ERROR
                        except Exception as e:
                            logger.error(f"處理檔案 {downloaded_file_path.name} 的元數據時發生錯誤: {e}")
                            exit_code = EXIT_CODE_DB_ERROR
                    elif not effective_metadata_db_path :
                        try:
                            raw_db_conn = duckdb.connect(database=str(db_path))
                            raw_db_conn.execute(f"CREATE SEQUENCE IF NOT EXISTS seq_raw_import;")
                            raw_db_conn.execute(f"""
                            CREATE TABLE IF NOT EXISTS {RAW_TABLE_NAME} (
                                id UBIGINT PRIMARY KEY DEFAULT nextval('seq_raw_import'),
                                source_file VARCHAR,
                                member_file VARCHAR,
                                file_content_blob BLOB,
                                file_content_as_text TEXT,
                                processed_at TIMESTAMPTZ
                            );
                            """)
                            await load_raw_data_to_db(raw_db_conn, str(downloaded_file_path), logger)
                            raw_db_conn.close()
                            logger.info(f"檔案 {downloaded_file_path.name} 成功載入資料庫 (未記錄元數據)。")
                        except Exception as e:
                            logger.error(f"處理檔案 {downloaded_file_path.name} 載入資料庫時發生錯誤 (無元數據): {e}")
                            exit_code = EXIT_CODE_DB_ERROR
        elif downloaded_file_path is None:
            exit_code = EXIT_CODE_NO_DATA_AVAILABLE

    except TaifexDownloadError as e:
        logger.error(f"捕獲到 TAIFEX 下載錯誤: {e}")
        exit_code = EXIT_CODE_DOWNLOAD_ERROR
    except Exception as e:
        logger.critical(f"發生未預期的嚴重錯誤: {e}", exc_info=True)
        exit_code = EXIT_CODE_GENERIC_ERROR

    if exit_code == EXIT_CODE_SUCCESS:
        logger.info(f"--- TAIFEX 智慧情報下載器任務成功 (日期: {target_date_obj.strftime('%Y-%m-%d')}) ---")
    elif exit_code == EXIT_CODE_NO_DATA_AVAILABLE:
         logger.info(f"--- TAIFEX 智慧情報下載器任務完成，當日無可用資料 (日期: {target_date_obj.strftime('%Y-%m-%d')}) ---")
    elif exit_code == EXIT_CODE_DOWNLOAD_ERROR:
        logger.error(f"--- TAIFEX 智慧情報下載器任務失敗 (下載錯誤) (日期: {target_date_obj.strftime('%Y-%m-%d')})，退出碼: {exit_code} ---")
    elif exit_code == EXIT_CODE_DB_ERROR:
        logger.error(f"--- TAIFEX 智慧情報下載器任務失敗 (資料庫錯誤) (日期: {target_date_obj.strftime('%Y-%m-%d')})，退出碼: {exit_code} ---")
    else:
        logger.error(f"--- TAIFEX 智慧情報下載器任務失敗 (通用或未知錯誤) (日期: {target_date_obj.strftime('%Y-%m-%d')})，退出碼: {exit_code} ---")

    sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main())
