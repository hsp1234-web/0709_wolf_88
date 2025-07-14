from src.core.context import AppContext
from src.core.services.evolution_chamber import EvolutionChamber

def run_evolution(ctx: AppContext, population_size: int = 10, generations: int = 3):
    chamber = EvolutionChamber(queue=ctx.queue, log_manager=ctx.log_manager, db_connection=ctx.duckdb_connection)
    chamber.run_evolution_cycle(population_size=population_size, generations=generations)
