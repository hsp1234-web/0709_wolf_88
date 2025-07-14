# 檔案: src/core/db/evolution_logger.py
import duckdb
from typing import Dict

DB_PATH = "prometheus_fire.duckdb"
TABLE_NAME = "evolution_logs"

def log_generation_stats(generation: int, stats: Dict):
    """
    將單一代的演化統計數據儲存至 DuckDB。
    """
    conn = duckdb.connect(DB_PATH)
    # 確保資料表存在
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            generation INTEGER PRIMARY KEY,
            max_fitness DOUBLE,
            avg_fitness DOUBLE,
            min_fitness DOUBLE,
            std_fitness DOUBLE,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 插入數據
    conn.execute(
        f"""
        INSERT INTO {TABLE_NAME} (generation, max_fitness, avg_fitness, min_fitness, std_fitness)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            generation,
            stats.get("max"),
            stats.get("avg"),
            stats.get("min"),
            stats.get("std")
        ]
    )
    conn.close()

def clear_evolution_logs():
    """安全地清除所有演化日誌。"""
    conn = duckdb.connect(DB_PATH)
    conn.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
    conn.close()
