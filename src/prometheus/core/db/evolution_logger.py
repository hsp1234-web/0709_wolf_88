# 檔案: src/core/db/evolution_logger.py
from typing import Dict

DB_PATH = "prometheus_fire.duckdb"
TABLE_NAME = "evolution_logs"


def log_generation_stats(generation: int, stats: Dict):
    """
    將單一代的演化統計數據儲存至 DuckDB。
    """
    # This function is now a no-op
    pass


def clear_evolution_logs():
    """安全地清除所有演化日誌。"""
    # This function is now a no-op
    pass
