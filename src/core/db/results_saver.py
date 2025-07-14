# 檔案: src/core/db/results_saver.py
import aiosqlite
import json
from typing import Dict, Any

class ResultsSaver:
    """結果儲存器 v3.0 (非同步版)"""
    def __init__(self, connection: aiosqlite.Connection):
        self.conn = connection

    async def setup_database(self):
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id TEXT UNIQUE,
                strategy_name TEXT,
                parameters TEXT,
                metrics TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self.conn.commit()

    async def save_result(self, backtest_id: str, strategy_name: str, parameters: Dict, metrics: Dict):
        params_json = json.dumps(parameters)
        metrics_json = json.dumps(metrics)
        await self.conn.execute("""
            INSERT INTO backtest_results (backtest_id, strategy_name, parameters, metrics)
            VALUES (?, ?, ?, ?)
        """, (backtest_id, strategy_name, params_json, metrics_json))
        await self.conn.commit()

    async def count_results(self) -> int:
        async with self.conn.execute("SELECT COUNT(*) FROM backtest_results") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0
