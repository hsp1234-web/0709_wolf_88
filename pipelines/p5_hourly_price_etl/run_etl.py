# -*- coding: utf-8 -*-
"""
小時級價格數據 ETL 管線總指揮官 (Orchestrator)
"""
import logging
from typing import Any, Optional

import typer

from pipelines.p5_hourly_price_etl import extract, load, transform

# 設定日誌
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = typer.Typer()

@app.command()
def run(
    mode: str = typer.Option(
        ...,  # '...' 表示此參數為必需
        "--mode",
        "-m",
        help="執行模式，可選值為 'backfill' 或 'update'。",
        case_sensitive=False, # 不區分大小寫
    ),
    log_manager: Optional[Any] = None, # for compatibility with run.py
):
    """
    執行完整的小時級價格數據 ETL (Extract, Transform, Load) 管線。
    """
    if mode not in ["backfill", "update"]:
        logger.error(f"錯誤：模式 '{mode}' 無效。請使用 'backfill' 或 'update'。")
        raise typer.Exit(code=1)

    logger.info(f"========== P5 小時級價格數據 ETL 管線啟動 (模式: {mode}) ==========")

    try:
        # === 第一步: 提取 (Extract) ===
        logger.info("--- [階段 1/3] 數據提取 ---")
        raw_data = extract.run_extraction(mode=mode)
        if not raw_data:
            logger.warning("提取階段未返回任何數據，管線提前終止。")
            logger.info("========== ⚠️ P5 ETL 管線已終止（無數據） ==========")
            return # 正常退出
        logger.info(f"提取階段完成，成功獲取 {len(raw_data)} 檔原始資產數據。")

        # === 第二步: 轉換 (Transform) ===
        logger.info("--- [階段 2/3] 數據轉換 ---")
        transformed_data = transform.run_transformation(raw_data)
        if transformed_data.empty:
            logger.warning("轉換階段未產生任何數據，管線提前終止。")
            logger.info("========== ⚠️ P5 ETL 管線已終止（無數據） ==========")
            return # 正常退出
        logger.info(f"轉換階段完成，成功處理並生成包含 {len(transformed_data)} 行的統一數據集。")

        # === 第三步: 加載 (Load) ===
        logger.info("--- [階段 3/3] 數據加載 ---")
        load.run_load(transformed_data, mode=mode)
        logger.info("加載階段完成。")

        logger.info(f"========== ✅ P5 小時級價格數據 ETL 管線作戰任務圓滿完成 (模式: {mode}) ==========")

    except Exception as e:
        logger.error(f"ETL 管線執行過程中發生嚴重錯誤: {e}", exc_info=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
