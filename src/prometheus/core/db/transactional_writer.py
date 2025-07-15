import json
import sqlite3
from pathlib import Path


class TransactionalWriter:
    """
    交易型寫入器：專門負責將回測結果安全地寫入 SQLite 資料庫。
    """

    def __init__(self, db_path: str | Path = "output/results.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS backtest_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    params TEXT,
                    crossover_points INTEGER,
                    last_price REAL,
                    batch_id TEXT,
                    timestamp TEXT
                )
            """)

    def save_result(self, result_data: dict):
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO backtest_results
                (symbol, params, crossover_points, last_price, batch_id, timestamp)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                [
                    result_data.get("symbol"),
                    json.dumps(result_data.get("params", {})),
                    result_data.get("crossover_points"),
                    result_data.get("last_price"),
                    result_data.get("batch_id"),
                ],
            )
