import logging
import os  # For potential db cleanup, though steps should manage their test dbs

from prometheus.core.pipelines.pipeline import DataPipeline
from prometheus.core.pipelines.steps.aggregators import TimeAggregatorStep
from prometheus.core.pipelines.steps.loaders import TaifexTickLoaderStep

# 配置基本的日誌記錄，以便觀察管線執行過程
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()  # Ensure logs go to console
    ],
)


def test_full_data_pipeline_run_without_errors():
    logger = logging.getLogger(__name__)
    logger.info("--- [開始執行驗證用數據管線] ---")

    # 為了確保測試的冪等性，如果 loader step 創建了數據庫，我們可能希望在測試前清理它。
    # TaifexTickLoaderStep 的 __init__ 有 db_path 參數。
    # 假設使用預設路徑 "market_data_loader_step.duckdb"
    # 注意：在測試函數中，直接操作外部檔案系統（如刪除 market_data_loader_step.duckdb）
    # 可能不是最佳實踐，因為這可能影響其他測試或造成副作用。
    # 更好的方法是讓每個測試步驟管理其自己的臨時測試數據庫，
    # 或者使用 pytest fixtures 來處理測試環境的 setup 和 teardown。
    # 這裡暫時保留原始邏輯，但標記為一個潛在的改進點。

    # 由於此測試是針對 "pipeline_test_loader.duckdb"，我們應該清理這個檔案。
    pipeline_loader_db_path = "pipeline_test_loader.duckdb"
    if os.path.exists(pipeline_loader_db_path):
        logger.info(f"清理舊的 pipeline loader 測試數據庫: {pipeline_loader_db_path}")
        os.remove(pipeline_loader_db_path)
    if os.path.exists(f"{pipeline_loader_db_path}.wal"):
        logger.info(f"清理舊的 pipeline loader 測試 WAL: {pipeline_loader_db_path}.wal")
        os.remove(f"{pipeline_loader_db_path}.wal")

    # 1. 定義我們的ETL步驟實例
    # 使用特定的數據庫名稱 "pipeline_test_loader.duckdb"
    tick_loader = TaifexTickLoaderStep(
        db_path=pipeline_loader_db_path, table_name="pipeline_test_ticks"
    )

    # TimeAggregatorStep 接收 aggregation_level
    time_aggregator = TimeAggregatorStep(aggregation_level="1Min")

    # 2. 創建一個數據管線，將步驟按順序組合起來
    my_pipeline = DataPipeline(
        steps=[
            tick_loader,
            time_aggregator,
        ]
    )

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
        # 為了讓 Pytest 認為這是一個有效的測試，我們至少需要一個斷言。
        # 即使只是 assert True，也比沒有好。
        assert True, "管線執行應該無錯誤完成"

    except Exception as e:
        logger.error(f"執行數據管線時發生頂層錯誤: {e}", exc_info=True)
        assert False, f"管線執行時發生錯誤: {e}"  # 如果發生例外，測試應失敗

    logger.info("--- [驗證用數據管線執行完畢] ---")
