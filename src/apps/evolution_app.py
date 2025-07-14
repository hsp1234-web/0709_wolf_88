from src.core.context import AppContext
from src.core.services.evolution_chamber import EvolutionChamber

def run_evolution(ctx: AppContext):
    chamber = EvolutionChamber(queue=ctx.queue, log_manager=ctx.log_manager)
    chamber.run_evolution_cycle()
