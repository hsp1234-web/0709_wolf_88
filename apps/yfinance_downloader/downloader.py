# -*- coding: utf-8 -*-
# YFinance 智慧情報下載器 v1.0 - 整合 yfinance
import os
import sys
import argparse
import asyncio
import yfinance as yf
from typing import Optional, List
import logging
import pandas as pd
from datetime import datetime, date as datetime_date, timedelta
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
    print(f"專案路徑校正時發生錯誤 (apps/yfinance_downloader/downloader.py): {e}", file=sys.stderr)
# --- 標準化「路徑自我校正」樣板碼 END ---

from core.utils import setup_logger # 假設 core.utils.setup_logger 存在且功能正確

# --- 自定義異常 ---
class YFinanceDownloadError(Exception):
    """針對 YFinance 下載過程中發生的特定錯誤。"""
    pass

# --- Exit Codes ---
EXIT_CODE_SUCCESS = 0
EXIT_CODE_NO_DATA_AVAILABLE = 0 # yfinance 對於無數據通常返回空 DataFrame，視為成功但無數據
EXIT_CODE_DOWNLOAD_ERROR = 1
EXIT_CODE_INVALID_TICKER = 0 # 按照要求，無效代碼也應正常退出
EXIT_CODE_GENERIC_ERROR = 3

async def download_yfinance_data(
    ticker: str,
    target_date: datetime_date,
    download_dir: Path,
    logger: logging.Logger
) -> Optional[Path]:
    """
    使用 yfinance 下載指定股票代號和日期的市場數據。

    Args:
        ticker: 股票代號 (例如 "AAPL", "GOOG")。
        target_date: 要下載數據的目標日期。
        download_dir: 儲存下載數據的目錄。
        logger: 日誌記錄器。

    Returns:
        如果成功下載並儲存數據，則返回 Parquet 檔案的路徑，否則返回 None。
    """
    start_date_str = target_date.strftime("%Y-%m-%d")
    # yfinance 的 end date 是不包含的，所以要加一天
    end_date_str = (target_date + timedelta(days=1)).strftime("%Y-%m-%d")

    output_filename_parquet = f"{ticker.replace('=F', '_F').replace('^', '_')}_{target_date.strftime('%Y%m%d')}.parquet"
    output_path_parquet = download_dir / output_filename_parquet

    logger.info(f"準備從 Yahoo Finance 下載 {ticker} 在 {start_date_str} 的數據...")

    try:
        # yfinance.download 是同步函數，但在 asyncio 中運行它需要 loop.run_in_executor
        loop = asyncio.get_event_loop()
        # 嘗試下載數據
        # data = yf.download(ticker, start=start_date_str, end=end_date_str, progress=False)
        # 使用 run_in_executor 將 yf.download 移至線程池執行，避免阻塞事件循環
        data = await loop.run_in_executor(
            None,  # 使用默認的 ThreadPoolExecutor
            lambda: yf.download(
                ticker,
                start=start_date_str,
                end=end_date_str,
                progress=False,
                timeout=30,
                auto_adjust=False, # 獲取 'Adj Close'
                back_adjust=False  # 確保 Close 是未調整的
            )
        )

        # 首先，無論 data 是否為空，都嘗試獲取 Ticker info，這有助於識別非常明顯的無效 Ticker
        try:
            ticker_obj = yf.Ticker(ticker)
            ticker_info = await loop.run_in_executor(None, lambda: ticker_obj.info)
            # 檢查 info 是否極度缺乏信息，表明 ticker 無效
            if not ticker_info or ('symbol' not in ticker_info and 'shortName' not in ticker_info and 'exchange' not in ticker_info):
                logger.warning(f"[WARNING] 情報目標 '{ticker}' 極可能不存在或API無法識別 (info check: critical fields missing)，任務已跳過。")
                return None
        except Exception as e:
            # 如果 Ticker() 或 .info 本身就失敗，且 data 也為空，則判定為無效
            if data.empty:
                logger.warning(f"[WARNING] 情報目標 '{ticker}' 檢查有效性時出錯 (error: {e}) 且無下載數據，極可能無效。任務已跳過。")
                return None
            # 如果有數據但 info 失敗，記錄但不立即退出
            logger.warning(f"[WARNING] 情報目標 '{ticker}' 的 .info 查詢失敗 (error: {e})，但已下載數據，將繼續處理。")

        # 處理 yfinance 可能返回 MultiIndex columns 的情況
        if isinstance(data.columns, pd.MultiIndex):
            logger.debug(f"Ticker '{ticker}' 返回了 MultiIndex 欄位: {data.columns.tolist()}。將嘗試展平。")
            # 優先取第一級的列名 (通常是 'Open', 'High', 'Low', etc.)
            # yfinance 對於單個 ticker，即使 group_by="column" (預設)，有時也返回 ('Open', ticker_symbol)
            # 我們需要 'Open'
            original_cols = data.columns
            try:
                # 嘗試移除名為 Ticker 的 level，如果存在
                if ticker.upper() in data.columns.names or (len(data.columns.names) > 1 and ticker.upper() in data.columns.levels[data.columns.names.index(ticker.upper())]):
                     data.columns = data.columns.droplevel(ticker.upper())
                elif len(data.columns.levels) > 1: # 通用地移除第二層級（如果存在）
                     data.columns = data.columns.droplevel(1) # 假設 ticker 名稱在第二層
                else: # 如果只有一層 MultiIndex (例如只有 ('Open',)，取第一級)
                     data.columns = data.columns.get_level_values(0)
                logger.debug(f"Ticker '{ticker}' MultiIndex 欄位展平後: {data.columns.tolist()}")
            except Exception as col_e:
                logger.warning(f"Ticker '{ticker}' MultiIndex 欄位展平失敗: {col_e}. 原始欄位: {original_cols}. 標準化可能失敗。")
                # 如果展平失敗，且 data 為空，則認為無法處理
                if data.empty:
                    logger.warning(f"[WARNING] 情報目標 '{ticker}' MultiIndex 欄位展平失敗且數據為空，任務跳過。")
                    return None

        logger.debug(f"Ticker '{ticker}' 欄位名修正後 (或原樣): {data.columns.tolist()}")

        # 在列名修正後，再次檢查 data 是否為空或全為 NaN
        if data.empty:
            # 如果此時 data 為空，但之前的 info 檢查通過了（或有數據但info失敗），則認為是當日無數據
            logger.info(f"[INFO] 情報目標 '{ticker}' 在日期 {start_date_str} 沒有數據 (data is empty after column processing)。任務已跳過。")
            return None

        # 檢查是否所有數值列都為 NaN (也表示無有效數據)
        # 確保只檢查 DataFrame 中實際存在的列
        price_cols_in_df = [col for col in ['Open', 'High', 'Low', 'Close', 'Adj Close'] if col in data.columns]
        if price_cols_in_df and data[price_cols_in_df].isnull().all().all():
            logger.info(f"[INFO] 情報目標 '{ticker}' 在日期 {start_date_str} 的所有價格數據均為 NaN。任務已跳過。")
            return None

        # 欄位名稱標準化
        # yfinance 在 auto_adjust=False 時返回的欄位名是 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume'
        # 對於單個 ticker，列名應該是扁平的 (經過上述修正)
        column_mapping = {
            'Open': 'open_price',
            'High': 'high_price',
            'Low': 'low_price',
            'Close': 'close_price',
            'Volume': 'trade_volume',
            'Adj Close': 'adj_close_price'
        }
        # 只重命名存在的欄位，以避免錯誤
        data.rename(columns={k: v for k, v in column_mapping.items() if k in data.columns}, inplace=True)

        # 檢查是否所有預期的標準化欄位都存在（如果原始欄位存在的話）
        # 例如，如果原始數據有 'Open'，那麼標準化後應該有 'open_price'
        # 這有助於確保重命名按預期工作
        expected_renamed_columns = [v for k,v in column_mapping.items() if k in data.columns and v not in data.columns]
        if any(col not in data.columns for col in expected_renamed_columns):
             logger.warning(f"欄位標準化可能未完全成功，部分預期欄位缺失。Current columns: {data.columns.tolist()}")


        download_dir.mkdir(parents=True, exist_ok=True)
        data.to_parquet(output_path_parquet)

        logger.info(f"[INFO] 成功下載並標準化 {ticker} 在 {start_date_str} 的數據到 {output_path_parquet}.")
        return output_path_parquet

    except Exception as e:
        # yfinance 可能會針對無效 ticker 拋出多種錯誤，或僅打印到 stderr 並返回空 df
        # 需要更細緻的錯誤處理來區分網絡問題、無效 ticker 等
        logger.error(f"[ERROR] 下載 {ticker} 數據時發生錯誤: {e}")
        # 根據第二階段要求，無效 ticker 不應崩潰，此處暫時不拋出 YFinanceDownloadError
        # 真正的無效 ticker 處理將在第二階段細化
        # raise YFinanceDownloadError(f"下載 {ticker} 數據失敗: {e}") from e
        return None


async def main():
    parser = argparse.ArgumentParser(description="YFinance 智慧情報下載器 (v1.0)")
    parser.add_argument("--ticker", required=True, help="要下載資料的股票代號 (例如 AAPL, ^TWII, NQ=F)。")
    parser.add_argument("--date", required=True, help="要下載資料的日期 (格式: YYYY-MM-DD 或 YYYYMMDD)。")
    parser.add_argument("--output-dir", required=True, help="下載 Parquet 檔案的儲存目錄。")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

    args, unknown = parser.parse_known_args()
    if unknown:
        print(f"[INFO] 忽略未知參數: {unknown}", file=sys.stderr)

    log_level_map = {
        "DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING,
        "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL
    }
    logger = setup_logger("yfinance_downloader", level=log_level_map.get(args.log_level.upper(), logging.INFO))

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

    # 標準化 ticker 名稱，用於檔案命名，移除潛在的非法字元
    # 例如，NQ=F -> NQ_F, ^TWII -> _TWII
    # sanitized_ticker = args.ticker.replace('=', '_').replace('^', '_')

    logger.info(f"--- YFinance 智慧情報下載器 v1.0 啟動 (目標代號: {args.ticker}, 日期: {target_date_obj.strftime('%Y-%m-%d')}) ---")
    logger.info(f"輸出目錄: {output_dir_path}")

    exit_code = EXIT_CODE_GENERIC_ERROR
    downloaded_file_path: Optional[Path] = None

    try:
        downloaded_file_path = await download_yfinance_data(args.ticker, target_date_obj, output_dir_path, logger)

        if downloaded_file_path:
            exit_code = EXIT_CODE_SUCCESS
        else:
            # 根據 download_yfinance_data 的邏輯，返回 None 可能是無數據或 ticker 無效
            # 這裡統一視為 EXIT_CODE_NO_DATA_AVAILABLE 或 EXIT_CODE_INVALID_TICKER，都是 0
            exit_code = EXIT_CODE_NO_DATA_AVAILABLE


    except YFinanceDownloadError as e: # 雖然目前 download_yfinance_data 不會主動拋出這個
        logger.error(f"捕獲到 YFinance 下載錯誤: {e}")
        exit_code = EXIT_CODE_DOWNLOAD_ERROR
    except Exception as e:
        logger.critical(f"發生未預期的嚴重錯誤: {e}", exc_info=True)
        exit_code = EXIT_CODE_GENERIC_ERROR

    if exit_code == EXIT_CODE_SUCCESS:
        logger.info(f"--- YFinance 智慧情報下載器任務成功 (代號: {args.ticker}, 日期: {target_date_obj.strftime('%Y-%m-%d')}) ---")
    elif exit_code == EXIT_CODE_NO_DATA_AVAILABLE: # 包含了 ticker 無效或當日無數據
         logger.info(f"--- YFinance 智慧情報下載器任務完成，目標 '{args.ticker}' 在 {target_date_obj.strftime('%Y-%m-%d')} 無可用資料或目標無效 ---")
    elif exit_code == EXIT_CODE_DOWNLOAD_ERROR: # 理論上目前不會走到這
        logger.error(f"--- YFinance 智慧情報下載器任務失敗 (下載錯誤) (代號: {args.ticker}, 日期: {target_date_obj.strftime('%Y-%m-%d')})，退出碼: {exit_code} ---")
    else: # EXIT_CODE_GENERIC_ERROR
        logger.error(f"--- YFinance 智慧情報下載器任務失敗 (通用或未知錯誤) (代號: {args.ticker}, 日期: {target_date_obj.strftime('%Y-%m-%d')})，退出碼: {exit_code} ---")

    sys.exit(exit_code)

if __name__ == "__main__":
    # yfinance 在某些環境下 (特別是 Windows 上的 asyncio) 可能會有問題
    # 例如 https://github.com/ranaroussi/yfinance/issues/1729
    # 確保在合適的環境中運行，或者考慮 yfinance 的替代方案或更深入的異步整合
    # 此處使用標準的 asyncio.run()
    asyncio.run(main())
