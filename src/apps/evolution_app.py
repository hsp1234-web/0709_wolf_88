# 檔案: apps/evolution_app.py
from core.services.evolution_chamber import EvolutionChamber
from core.logger import LogManager
from core.queue.sqlite_queue import SQLiteQueue # 導入

QUEUE_DB_PATH = "output/task_queue.db"

def run_evolution(log_manager: LogManager):
    # 建立佇列實例
    queue = SQLiteQueue(db_path=QUEUE_DB_PATH)
    # 將佇列傳入演化室
    chamber = EvolutionChamber(queue=queue, log_manager=log_manager)
    chamber.run_evolution_cycle()
