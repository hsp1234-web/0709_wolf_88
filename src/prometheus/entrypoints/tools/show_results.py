import sqlite3
import pandas as pd
from src.prometheus.core.logging.log_manager import LogManager

logger = LogManager.get_instance().get_logger("ShowResults")

DB_PATH = "output/results.sqlite"
TABLE_NAME = "backtest_results"


def show_results():
    logger.info("正在從 SQLite 資料庫查詢結果...")
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
        conn.close()

        if df.empty:
            logger.warning("資料庫中尚無任何結果。")
        else:
            logger.info("查詢完成。")
            # 使用一個 logger 呼叫來顯示整個 DataFrame
            logger.info(f"\n--- 回測結果 ---\n{df.to_string()}\n----------------")

    except Exception as e:
        logger.error(f"查詢結果時發生錯誤: {e}", exc_info=True)
