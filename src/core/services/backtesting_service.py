import time
import json
from src.core.queue.base import BaseQueue
from src.core.logger import LogManager
from src.core.db.transactional_writer import TransactionalWriter

# 模擬一個計算函數
def calculate_sma_crossover(symbol: str, fast: int, slow: int) -> dict:
    # 這是個模擬計算，實際應用中會是複雜的金融計算
    if slow <= fast:
        return {"crossover_points": 0, "last_price": 100.0}
    crossover_points = (slow - fast) * 10
    last_price = 100.0 + (slow - fast)
    return {"symbol": symbol, "crossover_points": crossover_points, "last_price": last_price}

class BacktestingService:
    def __init__(self, queue: BaseQueue, log_manager: LogManager):
        self.queue = queue
        self.log = log_manager
        # === 核心變更：初始化新的寫入器 ===
        self.writer = TransactionalWriter()

    def run(self):
        self.log.log("INFO", "[BacktestingService] Worker is running and waiting for tasks.")
        while True:
            task = self.queue.get()
            if task:
                task_id = task.get('_task_id')
                symbol = task.get('symbol')
                params = task.get('params', {})

                self.log.log("INFO", f"  [處理中] 任務 {task_id} for {symbol} with params {params}")
                try:
                    # 模擬的計算
                    result = calculate_sma_crossover(symbol=symbol, **params)
                    result['params'] = params
                    result['batch_id'] = task.get('batch_id')

                    self.log.log("DATA", f"  [計算結果] {result}")

                    # === 核心變更：使用新的寫入器儲存結果 ===
                    self.writer.save_result(result)
                    self.log.log("INFO", f"  [結果已寫入 SQLite] 任務 {task_id}")

                except Exception as e:
                    self.log.log("ERROR", f"  [計算失敗] 任務 {task_id} 發生錯誤: {e}")

                self.queue.task_done(task.get('_task_id'))
            else:
                time.sleep(1)
