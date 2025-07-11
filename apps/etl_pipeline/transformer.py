# -*- coding: utf-8 -*-
"""
TAIFEX 情報轉換器核心模組 (ETL Pipeline版)

此模組包含用於處理從 TAIFEX 下載的原始數據 ZIP 檔案，
並將其轉換為可用格式（例如 Parquet）的核心邏輯。
"""

import zipfile
import pandas as pd
from pathlib import Path
import logging
from typing import Optional, Tuple, List
import argparse  # 新增 argparse for run_transformation
import sys  # 新增 sys for logging

# 預設的日誌記錄器，如果沒有提供外部 logger
# 在 ETL Pipeline 中，日誌記錄可能由 Orchestrator 或統一的日誌設定器處理
# 此處保留一個模組級別的 logger 作為備用或直接調用時使用
MODULE_LOGGER = logging.getLogger(__name__)
if not MODULE_LOGGER.handlers:
    stream_handler = logging.StreamHandler(sys.stdout)  # 確保日誌輸出到stdout
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    stream_handler.setFormatter(formatter)
    MODULE_LOGGER.addHandler(stream_handler)
    MODULE_LOGGER.setLevel(logging.INFO)


def _find_target_csv_in_zip(
    zip_file: zipfile.ZipFile, logger: logging.Logger
) -> Optional[Tuple[str, bytes]]:
    """
    在 ZIP 檔案中尋找目標 CSV 檔案。
    """
    csv_files: List[Tuple[str, bytes]] = []
    for member_name in zip_file.namelist():
        if member_name.lower().endswith(".csv"):
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
        daily_csv_files = [
            (name, content) for name, content in csv_files if "daily" in name.lower()
        ]
        if daily_csv_files:
            if len(daily_csv_files) > 1:
                logger.warning(
                    f"找到多個包含 'Daily' 的 CSV 檔案: {[name for name, _ in daily_csv_files]}。將使用第一個: {daily_csv_files[0][0]}"
                )
            return daily_csv_files[0]
        else:
            logger.warning(
                f"找到多個 CSV 檔案，但沒有明確的 'Daily' CSV: {[name for name, _ in csv_files]}。將使用第一個: {csv_files[0][0]}"
            )
            return csv_files[0]
    return csv_files[0]


def _process_zip_file_internal(
    zip_path_str: str, output_dir_str: str, logger: logging.Logger
) -> bool:
    """
    處理單個 TAIFEX ZIP 檔案的核心邏輯，返回 True 表示成功，False 表示失敗。
    """
    zip_path = Path(zip_path_str)
    output_dir = Path(output_dir_str)

    if not zip_path.exists() or not zip_path.is_file():
        logger.error(f"[ERROR] ZIP 檔案不存在或不是一個檔案。檔案路徑: {zip_path}")
        return False

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"創建輸出目錄 {output_dir} 時發生錯誤: {e}")
        return False

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            target_csv_info = _find_target_csv_in_zip(zf, logger)

            if target_csv_info is None:
                logger.error(
                    f"[ERROR] 情報包內容與預期不符，未找到目標 CSV 檔案。檔案路徑: {zip_path}"
                )
                return False

            csv_filename, csv_content_bytes = target_csv_info
            logger.info(f"在 '{zip_path.name}' 中找到目標 CSV: '{csv_filename}'")

            decoded_csv_string: Optional[str] = None
            try:
                decoded_csv_string = csv_content_bytes.decode("utf-8")
            except UnicodeDecodeError as ude:
                logger.error(
                    f"[ERROR] 情報編碼錯誤，無法使用標準 UTF-8 解碼。檔案路徑: {zip_path}, CSV 檔案: {csv_filename}。錯誤: {ude}"
                )
                return False

            if decoded_csv_string is None:
                logger.error(
                    f"[ERROR] 未知原因導致 CSV 字串未能成功解碼。檔案路徑: {zip_path}"
                )
                return False

            df: Optional[pd.DataFrame] = None
            try:
                from io import StringIO

                df = pd.read_csv(StringIO(decoded_csv_string))
            except pd.errors.ParserError as pe:
                logger.error(
                    f"[ERROR] 情報內部格式錯亂或解析錯誤。檔案路徑: {zip_path}, CSV 檔案: {csv_filename}。錯誤: {pe}"
                )
                return False
            except Exception as e_parse:
                logger.error(
                    f"[ERROR] 解析 CSV 時發生未預期錯誤。檔案路徑: {zip_path}, CSV 檔案: {csv_filename}。錯誤: {e_parse}"
                )
                return False

            if df is None:
                logger.error(
                    f"[ERROR] DataFrame 未能生成，原因未知。檔案路徑: {zip_path}, CSV 檔案: {csv_filename}"
                )
                return False

            if df.empty:
                logger.warning(
                    f"[WARNING] 從 '{csv_filename}' 讀取的 DataFrame 為空。檔案路徑: {zip_path}。"
                )
                # 根據需求，空的 DataFrame 可能依然需要產生空的 Parquet，所以不一定返回 False

            try:
                parquet_filename = Path(csv_filename).stem + ".parquet"
                output_parquet_path = output_dir / parquet_filename
                df.to_parquet(output_parquet_path, index=False)
                logger.info(
                    f"成功將 '{csv_filename}' 從 '{zip_path.name}' 轉換並儲存為 '{output_parquet_path}'"
                )
                return True
            except Exception as e_to_parquet:
                logger.error(
                    f"[ERROR] 將 DataFrame 儲存為 Parquet 時發生錯誤。檔案路徑: {zip_path}, CSV 檔案: {csv_filename}。錯誤: {e_to_parquet}"
                )
                return False

    except zipfile.BadZipFile:
        logger.error(f"[ERROR] 情報包毀損，無法解碼。檔案路徑: {zip_path}")
        return False
    except FileNotFoundError:
        logger.error(f"[ERROR] ZIP 檔案未找到 (執行期間)。檔案路徑: {zip_path}")
        return False
    except Exception as e:
        logger.error(
            f"[ERROR] 處理 ZIP 檔案時發生未預期錯誤。檔案路徑: {zip_path}。錯誤: {e}"
        )
        return False


def run_transformation(argv: Optional[List[str]] = None) -> bool:
    """
    TAIFEX 數據轉換模組的命令行介面入口點。
    argv: 從命令行傳遞的參數列表 (不含程式名稱本身)。
    返回 True 表示成功，False 表示失敗。
    """
    parser = argparse.ArgumentParser(
        description="TAIFEX Data Transformation Module (ETL Pipeline)"
    )
    parser.add_argument("--zipfile", required=True, help="Path to the input ZIP file.")
    parser.add_argument(
        "--output", required=True, help="Path to the output directory for Parquet file."
    )
    parser.add_argument(
        "--loglevel",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )

    args = parser.parse_args(argv)

    # 根據傳入的 loglevel 設定此模組的 logger
    # 注意：如果 ETL Orchestrator 有全局日誌設定，這裡的設定可能會被覆蓋或需要與之協調
    current_logger = MODULE_LOGGER  # 使用模組級別的 logger
    log_level_attr = getattr(logging, args.loglevel.upper(), logging.INFO)
    current_logger.setLevel(log_level_attr)

    # 為了確保日誌能輸出，檢查並添加 handler (如果沒有的話)
    # 這在 run_transformation 被獨立調用或在特定環境中可能有用
    if not current_logger.handlers:
        stream_handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        stream_handler.setFormatter(formatter)
        current_logger.addHandler(stream_handler)
        current_logger.info(
            f"為 transformer 模組 logger 新增了 StreamHandler，等級設為 {args.loglevel.upper()}"
        )

    current_logger.info(
        f"ETL Transformer: 處理 ZIP 檔案 '{args.zipfile}', 輸出到 '{args.output}'"
    )

    success = _process_zip_file_internal(
        args.zipfile, args.output, logger=current_logger
    )

    if success:
        current_logger.info(
            f"ETL Transformer: 任務成功完成。ZIP: '{args.zipfile}' -> Parquet Dir: '{args.output}'"
        )
    else:
        current_logger.error(f"ETL Transformer: 任務失敗。ZIP: '{args.zipfile}'")

    return success


# 原有的 if __name__ == '__main__': 區塊已移除
# 獨立測試可通過以下方式：
# if __name__ == '__main__':
#     # 創建一個臨時的 ZIP 和輸出目錄進行測試
#     test_zip_path = Path("./temp_test_transformer.zip")
#     test_output_dir = Path("./temp_transformer_output")
#     test_output_dir.mkdir(exist_ok=True)
#
#     # 創建一個包含假 CSV 的 ZIP 檔案
#     with zipfile.ZipFile(test_zip_path, 'w') as zf:
#         zf.writestr("Daily_20230101.csv", "col1,col2\nval1,val2")
#
#     test_args = [
#         "--zipfile", str(test_zip_path),
#         "--output", str(test_output_dir),
#         "--loglevel", "DEBUG"
#     ]
#     run_transformation(test_args)
#
#     # 清理
#     # test_zip_path.unlink(missing_ok=True)
#     # for item in test_output_dir.iterdir(): item.unlink()
#     # test_output_dir.rmdir()
#     print(f"獨立測試完成。請檢查 {test_output_dir} 並手動清理。")
#
#     # 測試錯誤情況
#     # run_transformation(["--zipfile", "non_existent.zip", "--output", str(test_output_dir)])
#     # run_transformation(["--zipfile", str(test_zip_path)]) # Missing output
#
#     # python -m apps.etl_pipeline.transformer --zipfile ./temp_test_transformer.zip --output ./temp_transformer_output
#
#     # 如要直接執行此腳本進行測試，可取消註解上面的 if __name__ == '__main__' 部分，
#     # 並在命令行中執行：python apps/etl_pipeline/transformer.py --zipfile <path_to_zip> --output <path_to_output_dir>
#     pass
