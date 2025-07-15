# 檔案: src/core/db/results_saver.py
import aiosqlite
import json
from typing import Dict, Any

class ResultsSaver:
    """結果儲存器"""
    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn

    async def initialize(self):
        """初始化資料庫，建立結果表。"""
        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS backtest_results (
            genome_id TEXT PRIMARY KEY,
            sharpe_ratio REAL,
            generation INTEGER,
            genome TEXT
        )
        """)
        await self.conn.commit()

    async def save_result(self, genome_id: str, sharpe_ratio: float, generation: int, genome: Dict[str, Any]):
        """儲存單一基因體的回測結果。"""
        genome_str = json.dumps(genome)
        await self.conn.execute(
            "INSERT OR REPLACE INTO backtest_results (genome_id, sharpe_ratio, generation, genome) VALUES (?, ?, ?, ?)",
            (genome_id, sharpe_ratio, generation, genome_str)
        )
        await self.conn.commit()

    async def count_results(self) -> int:
        async with self.conn.execute("SELECT COUNT(*) FROM backtest_results") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def clear_all(self):
        """清空所有回測結果。"""
        await self.conn.execute("DELETE FROM backtest_results")
        await self.conn.commit()
