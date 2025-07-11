# _test_data_pipeline.py
import logging
import os # For potential db cleanup, though steps should manage their test dbs
from core.pipelines.pipeline import DataPipeline
from core.pipelines.steps.loaders import TaifexTickLoaderStep
from core.pipelines.steps.aggregators import TimeAggregatorStep

# 配置基本的日誌記錄，以便觀察管線執行過程
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler() # Ensure logs go to console
    ]
)

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.info("--- [開始執行驗證用數據管線] ---")

    # 為了確保測試的冪等性，如果 loader step 創建了數據庫，我們可能希望在測試前清理它。
    # TaifexTickLoaderStep 的 __init__ 有 db_path 參數。
    # 假設使用預設路徑 "market_data_loader_step.duckdb"
    loader_db_path = "market_data_loader_step.duckdb"
    if os.path.exists(loader_db_path):
        logger.info(f"清理舊的 loader 測試數據庫: {loader_db_path}")
        os.remove(loader_db_path)
    if os.path.exists(f"{loader_db_path}.wal"):
        logger.info(f"清理舊的 loader 測試 WAL: {loader_db_path}.wal")
        os.remove(f"{loader_db_path}.wal")

    # 1. 定義我們的ETL步驟實例
    # 使用不同的數據庫名稱以避免與 loader 的獨立測試衝突
    tick_loader = TaifexTickLoaderStep(db_path="pipeline_test_loader.duckdb", table_name="pipeline_test_ticks")

    # TimeAggregatorStep 接收 aggregation_level
    time_aggregator = TimeAggregatorStep(aggregation_level="1Min")

    # 2. 創建一個數據管線，將步驟按順序組合起來
    my_pipeline = DataPipeline(steps=[
        tick_loader,
        time_aggregator,
    ])

    # 3. 執行管線
    logger.info("準備執行 DataPipeline...")
    try:
        my_pipeline.run()
        logger.info("DataPipeline.run() 方法執行完畢。")

        # 這裡可以加入對最終結果的檢查（如果有的話）
        # DataPipeline.run() 本身不返回數據，數據是在步驟間傳遞
        # 如果需要驗證最終輸出的 DataFrame，需要在 DataPipeline 中增加回傳機制
        # 或設計一個 "OutputStep" 來捕獲並驗證數據。
        # 目前，我們只驗證管線是否無錯誤運行。

    except Exception as e:
        logger.error(f"執行數據管線時發生頂層錯誤: {e}", exc_info=True)

    logger.info("--- [驗證用數據管線執行完畢] ---")
