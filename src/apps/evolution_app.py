from src.core.context import AppContext
from src.core.services.evolution_chamber import EvolutionChamber

def run_evolution(ctx: AppContext):
    chamber = EvolutionChamber(
        queue=ctx.queue,
        log_manager=ctx.log_manager
    )
    # 暫時硬編碼族群大小和世代數
    chamber.run_evolution_cycle(population_size=10, generations=2)
