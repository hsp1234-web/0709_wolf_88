import time
import json
import duckdb
from src.core.queue.base import BaseQueue
from src.core.logger import LogManager

class BacktestingService:
    def __init__(self, queue: BaseQueue, log_manager: LogManager, db_connection: duckdb.DuckDBPyConnection):
        self.queue = queue
        self.log_manager = log_manager
        self.db_conn = db_connection
        self.table_name = "backtest_results"
        self._setup_database()

    def _setup_database(self):
        # 使用 CREATE TABLE IF NOT EXISTS 確保表存在
        self.db_conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                symbol VARCHAR,
                strategy VARCHAR,
                params VARCHAR,
                crossover_points INTEGER,
                batch_id VARCHAR
            )
        """)

    def run(self):
        self.log_manager.log("INFO", "[BacktestingService] Worker is running and waiting for tasks.")
        while True:
            task = self.queue.get()
            if task:
                self.log_manager.log("INFO", f"[BacktestingService] Received task: {task}")
                self.process_task(task)
            else:
                # 如果佇列是空的，可以短暫休眠一下，避免 CPU 空轉
                time.sleep(0.1)

    def process_task(self, task):
        task_id = task.get('_task_id')
        try:
            strategy = task.get('strategy')
            symbol = task.get('symbol')
            params = task.get('params')
            batch_id = task.get('batch_id')

            if not all([strategy, symbol, params, batch_id]):
                self.log_manager.log("ERROR", f"任務 {task_id} 缺少必要欄位。")
                self.queue.task_done(task_id)
                return

            if strategy in ["SMA_crossover_evolved", "SMA_Crossover", "MACD", "RSI"]:
                # For now, all strategies will be simulated with a simple logic
                fast_period = params.get('fast', 10)
                slow_period = params.get('slow', 20)

                if slow_period <= fast_period:
                    crossover_points = 0
                else:
                    crossover_points = (slow_period - fast_period) * 10

                self.save_results(symbol, strategy, params, crossover_points, batch_id)
                self.log_manager.log("SUCCESS", f"任務 {task_id} ({symbol}) 處理完畢。")
            else:
                self.log_manager.log("WARNING", f"未知的策略: {strategy}")

        except Exception as e:
            self.log_manager.log("ERROR", f"處理任務 {task_id} 時發生錯誤: {e}")
        finally:
            # 確保無論成功或失敗，都標記任務為完成
            self.queue.task_done(task_id)

    def save_results(self, symbol, strategy, params, crossover_points, batch_id):
        params_str = json.dumps(params)
        with self.db_conn.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {self.table_name} (symbol, strategy, params, crossover_points, batch_id) VALUES (?, ?, ?, ?, ?)",
                (symbol, strategy, params_str, crossover_points, batch_id)
            )
