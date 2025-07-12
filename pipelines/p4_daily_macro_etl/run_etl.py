# -*- coding: utf-8 -*-
"""
數據管線總指揮官 (Orchestrator)
"""

import logging
import os
from typing import Any, Optional

import typer

from pipelines.p4_daily_macro_etl import extract, load, transform

# 設定日誌
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = typer.Typer()


@app.command()
def run(
    force_download: bool = typer.Option(
        False,
        "--force-download",
        "-f",
        help="強制從網路重新下載所有數據，忽略本地快取。",
    ),
    log_manager: Optional[Any] = None,
):
    """
    執行完整的每日宏觀數據 ETL (Extract, Transform, Load) 管線。
    """
    logger.info("========== P4 每日宏觀數據 ETL 管線啟動 ==========")

    try:
        # === 第一步: 提取 (Extract) ===
        logger.info("--- [階段 1/3] 數據提取 ---")
        # 從環境變數或設定檔中獲取 FRED API Key
        fred_api_key = os.getenv("FRED_API_KEY")
        raw_data = extract.run_extraction(
            force_download=force_download, fred_api_key=fred_api_key
        )
        logger.info(f"提取階段完成，成功獲取 {len(raw_data)} 個原始數據集。")

        # === 第二步: 轉換 (Transform) ===
        logger.info("--- [階段 2/3] 數據轉換 ---")
        transformed_data = transform.run_transformation(raw_data)
        logger.info(f"轉換階段完成，成功處理並生成包含 {len(transformed_data)} 行的統一數據集。")

        # === 第三步: 加載 (Load) ===
        # 目前為一個預留位置，待未來實現
        logger.info("--- [階段 3/3] 數據加載 ---")
        # load.run_loading(transformed_data)
        # logger.info("加載階段完成。")
        logger.info("加載邏輯待實現，此階段跳過。")

        logger.info("========== P4 每日宏觀數據 ETL 管線執行成功 ==========")

    except Exception as e:
        logger.error(f"ETL 管線執行過程中發生嚴重錯誤: {e}", exc_info=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
