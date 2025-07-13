from core.queue.base import BaseQueue
from core.logger import LogManager
# 導入因子計算函數
from apps.factor_engine.sma_crossover_factor import calculate_sma_crossover

class BacktestingService:
    def __init__(self, queue: BaseQueue, log_manager: LogManager):
        self.queue = queue
        self.log = log_manager
        self.log.log("INFO", "回測服務已啟動，等待任務...")

    def run(self):
        while True:
            task = self.queue.get()
            if task:
                task_id = task.get('_task_id')
                symbol = task.get("symbol", "UNKNOWN")
                self.log.log("INFO", f"  [處理中] 任務 {task_id}: {task}")

                # === 執行真實計算 ===
                try:
                    result = calculate_sma_crossover(symbol=symbol)
                    # 將計算結果記錄下來
                    self.log.log("DATA", f"  [計算結果] {result}")
                except Exception as e:
                    self.log.log("ERROR", f"  [計算失敗] 任務 {task_id} 發生錯誤: {e}")

                self.queue.task_done(task_id)
                self.log.log("SUCCESS", f"  [已完成] 任務 {task_id}")
            else:
                # 在佇列為空時，短暫休眠以降低 CPU 使用率
                import time
                time.sleep(1)
