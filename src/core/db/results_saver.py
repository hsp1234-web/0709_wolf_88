import duckdb
import json
from src.core.logger import LogManager

class ResultsSaver:
    """
    結果儲存器 v2.0
    負責將回測結果寫入 DuckDB 資料庫。
    """
    def __init__(self, db_path: str = "prometheus_fire.duckdb", log_manager: LogManager = None):
        self.db_path = db_path
        self.table_name = "backtest_results"
        self.log_manager = log_manager if log_manager else LogManager()
        self._initialize_db()

    def _initialize_db(self):
        """確保資料庫和資料表存在。"""
        try:
            with duckdb.connect(self.db_path) as conn:
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_name} (
                        backtest_id VARCHAR,
                        strategy_name VARCHAR,
                        parameters VARCHAR,
                        metrics VARCHAR,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            self.log_manager.log("INFO", f"資料庫 '{self.db_path}' 及資料表 '{self.table_name}' 初始化成功。")
        except Exception as e:
            self.log_manager.log("CRITICAL", f"資料庫初始化失敗: {e}")
            raise

    def save_result(self, backtest_id: str, strategy_name: str, parameters: dict, metrics: dict):
        """
        將單筆回測結果儲存至 DuckDB。

        Args:
            backtest_id: 回測的唯一識別碼。
            strategy_name: 策略名稱。
            parameters: 策略使用的參數 (字典)。
            metrics: 回測產生的績效指標 (字典)。
        """
        try:
            with duckdb.connect(self.db_path) as conn:
                conn.execute(
                    f"INSERT INTO {self.table_name} (backtest_id, strategy_name, parameters, metrics) VALUES (?, ?, ?, ?)",
                    [
                        backtest_id,
                        strategy_name,
                        json.dumps(parameters),
                        json.dumps(metrics)
                    ]
                )
            self.log_manager.log("INFO", f"成功儲存回測結果至資料庫: ID {backtest_id}")
        except Exception as e:
            self.log_manager.log("ERROR", f"儲存回測結果 (ID: {backtest_id}) 時發生錯誤: {e}")

    def clear_results(self):
        """清除所有回測結果。"""
        try:
            with duckdb.connect(self.db_path) as conn:
                conn.execute(f"DELETE FROM {self.table_name}")
            self.log_manager.log("INFO", f"成功清除資料表 '{self.table_name}' 的所有結果。")
        except Exception as e:
            self.log_manager.log("ERROR", f"清除結果時發生錯誤: {e}")

    def count_results(self) -> int:
        """計算回測結果的總數。"""
        try:
            with duckdb.connect(self.db_path) as conn:
                result = conn.execute(f"SELECT COUNT(*) FROM {self.table_name}").fetchone()
                return result[0] if result else 0
        except Exception as e:
            self.log_manager.log("ERROR", f"計算結果數量時發生錯誤: {e}")
            return 0
