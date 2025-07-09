# -*- coding: utf-8 -*-
"""
TAIFEX 情報轉換器核心模組

此模組包含用於處理從 TAIFEX 下載的原始數據 ZIP 檔案，
並將其轉換為可用格式（例如 Parquet）的核心邏輯。
"""

import zipfile
import pandas as pd
from pathlib import Path
import logging
from typing import Optional, Tuple, List
import re # 用於正則表達式匹配 CSV 檔名

# 預設的日誌記錄器，如果沒有提供外部 logger
DEFAULT_LOGGER = logging.getLogger(__name__)
if not DEFAULT_LOGGER.handlers:
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stream_handler.setFormatter(formatter)
    DEFAULT_LOGGER.addHandler(stream_handler)
    DEFAULT_LOGGER.setLevel(logging.INFO)

def _find_target_csv_in_zip(zip_file: zipfile.ZipFile, logger: logging.Logger) -> Optional[Tuple[str, bytes]]:
    """
    在 ZIP 檔案中尋找目標 CSV 檔案。
    目標 CSV 檔案通常命名為 Daily_YYYYMMDD.csv 或 Daily_YYYY_MM_DD.csv。
    此函數將嘗試匹配這些模式。

    返回：一個包含 (檔名, 檔案內容位元組) 的元組，如果找到；否則返回 None。
    """
    # 正則表達式匹配類似 'Daily_20231220.csv' 或 'Daily_2023_12_20.csv'
    # 以及其他一些 TAIFEX 可能的 CSV 檔名，例如 RHF_TO മാനУΜΑ_YYYYMMDD.csv (雖然這個比較特殊)
    # 為了通用性，我們先專注於 'Daily_*.csv'
    # 修正：根據實際的測試案例，我們可能需要一個更精確或更寬鬆的模式。
    # 目前，我們假設一個比較常見的模式，例如 'Daily_*.csv' 或直接尋找唯一的 .csv 檔。
    # 為了簡化初始版本，我們將尋找 ZIP 檔案中第一個副檔名為 .csv 的檔案。
    # 後續可以根據需求調整為更精確的檔名匹配 logique。

    csv_files: List[Tuple[str, bytes]] = []
    for member_name in zip_file.namelist():
        if member_name.lower().endswith('.csv'):
            try:
                content = zip_file.read(member_name)
                csv_files.append((member_name, content))
            except Exception as e:
                logger.warning(f"讀取 ZIP 成員 '{member_name}' 時發生錯誤: {e}")
                continue

    if not csv_files:
        logger.error("在情報包中未找到任何 CSV 檔案。")
        return None

    if len(csv_files) > 1:
        # 如果有多個 CSV，我們需要一個策略來選擇。
        # 1. 尋找檔名中包含 "Daily" 的。
        # 2. 如果還是有多個，或者沒有包含 "Daily" 的，則記錄警告並選擇第一個。
        daily_csv_files = [ (name, content) for name, content in csv_files if "daily" in name.lower() ]
        if daily_csv_files:
            if len(daily_csv_files) > 1:
                logger.warning(f"找到多個包含 'Daily' 的 CSV 檔案: {[name for name, _ in daily_csv_files]}。將使用第一個: {daily_csv_files[0][0]}")
            return daily_csv_files[0]
        else:
            logger.warning(f"找到多個 CSV 檔案，但沒有明確的 'Daily' CSV: {[name for name, _ in csv_files]}。將使用第一個: {csv_files[0][0]}")
            return csv_files[0]

    return csv_files[0]


def process_zip_file(zip_path_str: str, output_dir_str: str, logger: Optional[logging.Logger] = None) -> None:
    """
    處理單個 TAIFEX ZIP 檔案，解壓縮、轉換並儲存為 Parquet。

    參數:
        zip_path_str (str): 輸入的 ZIP 檔案路徑。
        output_dir_str (str): 儲存 Parquet 檔案的目錄路徑。
        logger (Optional[logging.Logger]): 用於日誌記錄的記錄器實例。如果為 None，則使用 stdout。
    """
    effective_logger = logger if logger else DEFAULT_LOGGER
    zip_path = Path(zip_path_str)
    output_dir = Path(output_dir_str)

    if not zip_path.exists() or not zip_path.is_file():
        effective_logger.error(f"[ERROR] ZIP 檔案不存在或不是一個檔案。檔案路徑: {zip_path}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            target_csv_info = _find_target_csv_in_zip(zf, effective_logger)

            if target_csv_info is None:
                # _find_target_csv_in_zip 內部已經記錄了錯誤
                effective_logger.error(f"[ERROR] 情報包內容與預期不符，未找到目標 CSV 檔案。檔案路徑: {zip_path}")
                return

            csv_filename, csv_content_bytes = target_csv_info
            effective_logger.info(f"在 '{zip_path.name}' 中找到目標 CSV: '{csv_filename}'")

            decoded_csv_string: Optional[str] = None
            try:
                # 步驟 1: 解碼 CSV 內容
                decoded_csv_string = csv_content_bytes.decode('utf-8')
            except UnicodeDecodeError as ude:
                effective_logger.error(f"[ERROR] 情報編碼錯誤，無法使用標準 UTF-8 解碼。檔案路徑: {zip_path}, CSV 檔案: {csv_filename}。錯誤: {ude}")
                return # 終止執行

            # 確保 decoded_csv_string 在此處已賦值 (理論上如果上面 return 就不會到這裡)
            if decoded_csv_string is None: # 防禦性檢查
                effective_logger.error(f"[ERROR] 未知原因導致 CSV 字串未能成功解碼 (但未捕獲 UnicodeDecodeError)。檔案路徑: {zip_path}")
                return

            df: Optional[pd.DataFrame] = None
            try:
                # 步驟 2: 解析 CSV 為 DataFrame
                from io import StringIO
                effective_logger.debug(f"嘗試解析 CSV 檔案: {csv_filename} from {zip_path.name}")
                df = pd.read_csv(StringIO(decoded_csv_string)) # 預設 on_bad_lines='error'
                effective_logger.debug(f"成功解析 CSV。DataFrame shape: {df.shape if df is not None else 'N/A'}")

            except pd.errors.ParserError as pe:
                effective_logger.error(f"[ERROR] 情報內部格式錯亂，欄位數量不一致或解析錯誤。檔案路徑: {zip_path}, CSV 檔案: {csv_filename}。錯誤: {pe}")
                return
            except Exception as e_parse: # 捕獲其他可能的解析階段錯誤
                effective_logger.error(f"[ERROR] 解析 CSV 時發生未預期錯誤。檔案路徑: {zip_path}, CSV 檔案: {csv_filename}。錯誤: {e_parse}")
                return

            if df is None: # 如果解析失敗且未被上面捕獲 (理論上不太可能)
                 effective_logger.error(f"[ERROR] DataFrame 未能生成，原因未知但解析器未明確拋出 ParserError。檔案路徑: {zip_path}, CSV 檔案: {csv_filename}")
                 return

            # 步驟 3: 檢查 DataFrame 是否為空 (根據測試需求，空 DataFrame 可能不應輸出)
            # 指令中未明確說明空 CSV 的處理，但通常空 CSV 轉空 Parquet 是允許的。
            # 測試案例中也沒有專門針對空 CSV 但有效 ZIP 的情況。
            # 暫時假設：如果 CSV 解析成功但 DataFrame 為空，我們仍然嘗試轉換。
            # 如果測試要求空 CSV 不輸出，則應在此處添加 return。
            if df.empty:
                effective_logger.warning(f"[WARNING] 從 '{csv_filename}' 讀取的 DataFrame 為空。檔案路徑: {zip_path}。將嘗試轉換為空的 Parquet 檔案。")

            # 步驟 4: 轉換並儲存為 Parquet
            try:
                parquet_filename = Path(csv_filename).stem + ".parquet"
                output_parquet_path = output_dir / parquet_filename

                df.to_parquet(output_parquet_path, index=False)
                effective_logger.info(f"成功將 '{csv_filename}' 從 '{zip_path.name}' 轉換並儲存為 '{output_parquet_path}'")
            except Exception as e_to_parquet:
                effective_logger.error(f"[ERROR] 將 DataFrame 儲存為 Parquet 時發生錯誤。檔案路徑: {zip_path}, CSV 檔案: {csv_filename}。錯誤: {e_to_parquet}")
                # 如果儲存失敗，我們也應該確保沒有部分 Parquet 檔案殘留 (如果可能)
                # 並且此時 process_zip_file 應被視為失敗，不應有輸出。
                # 由於測試會檢查輸出目錄是否為空，這裡的 return 不是絕對必要，
                # 但為了邏輯清晰，如果 to_parquet 失敗，也應該算作處理失敗。
                return

    except zipfile.BadZipFile:
        effective_logger.error(f"[ERROR] 情報包毀損，無法解碼。檔案路徑: {zip_path}")
        return
    except FileNotFoundError: # 理論上，zip_path.exists() 已經檢查過了，但以防萬一
        effective_logger.error(f"[ERROR] ZIP 檔案未找到 (執行期間)。檔案路徑: {zip_path}")
        return
    except Exception as e:
        effective_logger.error(f"[ERROR] 處理 ZIP 檔案時發生未預期錯誤。檔案路徑: {zip_path}。錯誤: {e}")
        return

# 將 run_transformation 函數添加到檔案末尾，以便可以從 run.py 中調用
def run_transformation(argv: Optional[List[str]] = None):
    """
    為 transformer 模組設計的命令行介面入口點。
    注意：此處的 argv 是 parse_known_args() 之後的剩餘參數。
    """
    parser = argparse.ArgumentParser(description="TAIFEX Data Transformation Sub-module")
    parser.add_argument("--zipfile", required=True, help="Path to the input ZIP file.")
    parser.add_argument("--output", required=True, help="Path to the output directory for Parquet file.")
    parser.add_argument("--loglevel", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

    # 如果 argv 為 None (例如直接調用而非透過 argparse 鏈)，則使用 sys.argv[1:]
    # 但在我們的 ETL pipeline run.py 設計中，它應該總是 List[str]
    args = parser.parse_args(argv) # 解析剩餘參數

    cli_logger = logging.getLogger("TRANSFORMER_ETL")
    cli_logger.setLevel(getattr(logging, args.loglevel.upper()))
    if not cli_logger.handlers:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        cli_logger.addHandler(ch)

    cli_logger.info(f"ETL Transformer: 處理 ZIP 檔案 '{args.zipfile}', 輸出到 '{args.output}'")
    process_zip_file(args.zipfile, args.output, logger=cli_logger)
    cli_logger.info("ETL Transformer: 任務完成。")

if __name__ == '__main__':
    # 原始的 __main__ 區塊保持不變，用於獨立測試
    import argparse # 確保 argparse 已導入 (雖然上面 run_transformation 也導入了)
    parser_main = argparse.ArgumentParser(description="TAIFEX Data Transformer CLI (Test Only)")
    parser_main.add_argument("--zipfile", required=True, help="Path to the input ZIP file.")
    parser_main.add_argument("--output", required=True, help="Path to the output directory for Parquet file.")
    parser_main.add_argument("--loglevel", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

    args_main = parser_main.parse_args() # 這裡使用預設的 sys.argv

    main_logger = logging.getLogger("CLI_MAIN_TEST")
    main_logger.setLevel(getattr(logging, args_main.loglevel.upper()))
    if not main_logger.handlers:
        mh = logging.StreamHandler()
        mh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        main_logger.addHandler(mh)

    main_logger.info(f"獨立手動測試: 處理 ZIP 檔案 '{args_main.zipfile}', 輸出到 '{args_main.output}'")
    process_zip_file(args_main.zipfile, args_main.output, logger=main_logger)
    main_logger.info("獨立手動測試完成。")
