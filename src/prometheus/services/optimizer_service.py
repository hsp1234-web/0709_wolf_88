# 檔案: core/services/optimizer_service.py
import json

import duckdb
from core.logger import LogManager
from core.queue.base import BaseQueue


class StrategyOptimizer:
    """
    策略優化器，負責分析結果並創造新任務。
    """

    def __init__(self, queue: BaseQueue, log_manager: LogManager):
        self.queue = queue
        self.log = log_manager
        self.db_path = "prometheus_fire.duckdb"
        self.table_name = "backtest_results"

    def run_once(self):
        """
        執行一次優化流程。
        """
        self.log.log("INFO", "優化器啟動，正在分析歷史結果...")

        try:
            conn = duckdb.connect(self.db_path, read_only=True)

            # === 第一道防線：檢查資料表是否存在 ===
            tables = conn.execute("SHOW TABLES").fetchall()
            table_names = [table[0] for table in tables]
            if self.table_name not in table_names:
                self.log.log(
                    "WARNING",
                    f"結果資料表 '{self.table_name}' 不存在，優化器跳過本次執行。",
                )
                conn.close()
                return

            # === 第二道防線：檢查資料表是否為空 ===
            best_result = conn.execute(
                f"SELECT params FROM {self.table_name} ORDER BY crossover_points DESC LIMIT 1"
            ).fetchone()
            conn.close()

            if not best_result:
                self.log.log(
                    "WARNING", "結果資料表中無任何數據可供分析，優化器跳過本次執行。"
                )
                return

            # ... (後續邏輯不變) ...
            best_params_str = best_result[0]
            best_params = json.loads(best_params_str)
            self.log.log("SUCCESS", f"找到當前最優參數: {best_params}")

            mutated_params = {
                "fast": best_params.get("fast", 5) + 1,
                "slow": best_params.get("slow", 10) - 1,
            }
            # 確保慢線週期大於快線週期
            if mutated_params["slow"] <= mutated_params["fast"]:
                mutated_params["slow"] = mutated_params["fast"] + 2

            self.log.log("INFO", f"產生進化後的新參數: {mutated_params}")

            # === 將新任務投入佇列 ===
            new_task = {
                "strategy": "SMA_crossover_mutated",
                "symbol": "OPTIMIZED_STOCK",
                "params": mutated_params,
            }
            self.queue.put(new_task)
            self.log.log("SUCCESS", f"已將進化後的新任務投入佇列: {new_task}")

        except Exception as e:
            self.log.log("ERROR", f"優化過程中發生錯誤: {e}")
