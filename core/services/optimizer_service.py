# 檔案: core/services/optimizer_service.py
import duckdb
import json
from core.queue.base import BaseQueue
from core.logger import LogManager

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
            # 找出交叉點最多的那一次執行作為最優結果
            best_result = conn.execute(
                f"SELECT params FROM {self.table_name} ORDER BY crossover_points DESC LIMIT 1"
            ).fetchone()
            conn.close()

            if not best_result:
                self.log.log("WARNING", "資料庫中無任何結果可供分析，優化器跳過本次執行。")
                return

            best_params_str = best_result[0]
            # The params are stored as a string representation of a dictionary, so we need to evaluate it.
            # Using json.loads is safer than eval().
            try:
                best_params = json.loads(best_params_str.replace("'", "\""))
            except json.JSONDecodeError:
                self.log.log("ERROR", f"無法解析參數字串: {best_params_str}")
                return

            self.log.log("SUCCESS", f"找到當前最優參數: {best_params}")

            # === 產生一個進化後的新參數 ===
            mutated_params = {
                "fast": best_params.get("fast", 5) + 1,
                "slow": best_params.get("slow", 10) - 1
            }
            # 確保慢線週期大於快線週期
            if mutated_params["slow"] <= mutated_params["fast"]:
                mutated_params["slow"] = mutated_params["fast"] + 2

            self.log.log("INFO", f"產生進化後的新參數: {mutated_params}")

            # === 將新任務投入佇列 ===
            new_task = {
                "strategy": "SMA_crossover_mutated",
                "symbol": "OPTIMIZED_STOCK",
                "params": mutated_params
            }
            self.queue.put(new_task)
            self.log.log("SUCCESS", f"已將進化後的新任務投入佇列: {new_task}")

        except Exception as e:
            self.log.log("ERROR", f"優化過程中發生錯誤: {e}")
