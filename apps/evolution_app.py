# 檔案: apps/evolution_app.py
from core.services.evolution_chamber import EvolutionChamber
from core.logger import LogManager

def run_evolution(log_manager: LogManager):
    """
    初始化並執行一次策略演化流程。
    """
    chamber = EvolutionChamber(log_manager=log_manager)
    chamber.run_evolution_cycle()
