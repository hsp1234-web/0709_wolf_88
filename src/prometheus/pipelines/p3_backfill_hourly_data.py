# In pipelines/p3_backfill_hourly_data/run.py
import sys
from pathlib import Path

import pandas as pd

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))


def run_backfill(start_date_str, end_date_str):
    from prometheus.core.analysis.data_engine import DataEngine
    from prometheus.core.clients.client_factory import ClientFactory
    from src.prometheus.core.logging.log_manager import LogManager

    logger = LogManager.get_instance().get_logger("P3-Backfill")

    """
    執行歷史數據回填管線。
    """
    logger.info(f"--- 開始執行數據回填作業：從 {start_date_str} 到 {end_date_str} ---")

    data_engine = DataEngine()
    hourly_timestamps = pd.date_range(start=start_date_str, end=end_date_str, freq="H")
    total_tasks = len(hourly_timestamps)

    for i, ts in enumerate(hourly_timestamps):
        logger.debug(f"--- 正在處理 ({i + 1}/{total_tasks}): {ts} ---")
        try:
            data_engine.generate_snapshot(ts)
        except Exception as e:
            logger.error(f"❌ 處理 {ts} 時發生錯誤: {e}", exc_info=True)

    data_engine.close()
    ClientFactory.close_all()
    logger.info("--- 數據回填作業完成 ---")


def main():
    """主執行函數"""
    # 範例：回填過去三天的數據
    # 實際使用時，可以透過 argparse 等方式傳入參數
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.Timedelta(days=3)
    run_backfill(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))


if __name__ == "__main__":
    main()
