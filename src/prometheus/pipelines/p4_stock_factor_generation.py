# src/prometheus/pipelines/p4_stock_factor_generation.py

import logging
import pandas as pd
from typing import List

from src.prometheus.core.config import config
from src.prometheus.core.clients.client_factory import ClientFactory
from src.prometheus.core.db.db_manager import DBManager
from src.prometheus.core.engines.stock_factor_engine import StockFactorEngine
from src.prometheus.core.pipelines.pipeline import Pipeline
from src.prometheus.core.pipelines.steps.loaders import LoadStockDataStep
from src.prometheus.core.pipelines.steps.savers import SaveToWarehouseStep
from src.prometheus.core.pipelines.steps.financial_steps import RunStockFactorEngineStep
from src.prometheus.core.pipelines.steps.splitters import GroupBySymbolStep

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_stock_factor_pipeline(symbols: List[str], db_manager: DBManager, client_factory: ClientFactory) -> Pipeline:
    """
    創建一個用於生成股票因子的標準化 Pipeline。

    :param symbols: 要處理的股票代號列表。
    :param db_manager: 資料庫管理器。
    :param client_factory: 客戶端工廠。
    :return: 一個配置好的 Pipeline 實例。
    """
    # 初始化股票因子引擎
    stock_factor_engine = StockFactorEngine(client_factory)

    from src.prometheus.core.pipelines.steps.normalize_columns_step import NormalizeColumnsStep
    # 定義 Pipeline 的步驟
    steps = [
        LoadStockDataStep(symbols=symbols, client_factory=client_factory),
        NormalizeColumnsStep(),
        GroupBySymbolStep(),
        RunStockFactorEngineStep(engine=stock_factor_engine),
        SaveToWarehouseStep(db_manager=db_manager, table_name="factors"),
    ]

    return Pipeline(steps=steps)


import asyncio

def main():
    """
    主執行函數，設置並運行股票因子生成流程。
    """
    logger.info("===== 開始執行第四號生產線：股票因子生成 =====")

    # --- 配置區 ---
    # 定義目標股票清單
    # 'AAPL' - 美股, '2330.TW' - 台股
    target_symbols = ['AAPL', '2330.TW']

    # 初始化資料庫管理器
    db_manager = DBManager(db_path=config.get('database.main_db_path'))

    # 初始化客戶端工廠
    client_factory = ClientFactory()

    # --- 執行區 ---
    logger.info(f"目標股票: {target_symbols}")

    # 創建 Pipeline
    pipeline = create_stock_factor_pipeline(
        symbols=target_symbols,
        db_manager=db_manager,
        client_factory=client_factory,
    )

    # 執行 Pipeline
    try:
        asyncio.run(pipeline.run())
        logger.info("Pipeline 執行成功。")
    except Exception as e:
        logger.error(f"Pipeline 執行過程中發生錯誤: {e}", exc_info=True)
        # 可以在此處添加錯誤處理邏輯，例如發送通知

    # --- 清理區 ---
    logger.info("===== 第四號生產線執行完畢 =====")


if __name__ == "__main__":
    main()
