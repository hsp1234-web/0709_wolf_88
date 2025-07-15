import json
import duckdb
from prometheus.core.logging.log_manager import LogManager
from prometheus.core.db import get_db_connection
from prometheus.core.config import config

class OptimizerService:
    def __init__(self, db_path=None, table_name="optimized_strategies"):
        self.db_path = db_path or config.get("database.main_db_path")
        self.table_name = table_name
        self.log_manager = LogManager(session_name="optimizer_service")
        self._initialize_db()

    def _initialize_db(self):
        with get_db_connection(self.db_path) as conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    strategy_id VARCHAR PRIMARY KEY,
                    params VARCHAR,
                    fitness_score FLOAT,
                    crossover_points INTEGER
                )
            """)

    def get_best_strategy(self):
        with get_db_connection(self.db_path) as conn:
            try:
                best_result = conn.execute(
                    f"SELECT params FROM {self.table_name} ORDER BY crossover_points DESC LIMIT 1"
                ).fetchone()
                if best_result:
                    return json.loads(best_result[0])
            except duckdb.CatalogException:
                self.log_manager.log_error(f"Table {self.table_name} not found.")
            return None

    def save_strategy(self, strategy_id, params, fitness_score, crossover_points):
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO {self.table_name} VALUES (?, ?, ?, ?)",
                (strategy_id, json.dumps(params), fitness_score, crossover_points)
            )
        self.log_manager.log_info(f"Strategy {strategy_id} saved successfully.")

if __name__ == "__main__":
    service = OptimizerService()
    # Example usage:
    # service.save_strategy("strategy_1", {"param1": 10}, 0.95, 5)
    # best_params = service.get_best_strategy()
    # print(f"Best strategy params: {best_params}")
