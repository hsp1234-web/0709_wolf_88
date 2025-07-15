from deap import base, creator, tools
from src.core.events.event_types import GenomeGenerated
from src.core.context import AppContext
from src.core.services.checkpoint_manager import CheckpointManager

# DEAP setup
creator.create("FitnessMax", base.Fitness, weights=(1.0,))
creator.create("Individual", dict, fitness=creator.FitnessMax)

class EvolutionChamber:
    def __init__(self, context: AppContext):
        self.context = context
        self.toolbox = base.Toolbox()
        # ... (DEAP registrations can be added here if needed) ...
        self.checkpoint_manager = CheckpointManager()

    async def evolve(self, generations: int, population_size: int = 10, resume: bool = False):
        start_gen = 0
        population = None

        if resume:
            checkpoint = self.checkpoint_manager.load()
            if checkpoint:
                population = checkpoint.get("population")
                start_gen = checkpoint.get("generation", 0) + 1
                print(f"方舟：從第 {start_gen} 代恢復演化。")

        if population is None:
            population = [self._create_dummy_genome() for _ in range(population_size)]

        for gen in range(start_gen, generations):
            # In a real scenario, you'd have selection, crossover, mutation
            for i, ind in enumerate(population):
                genome_id = f"gen_{gen}_ind_{i}"
                event = GenomeGenerated(
                    genome_id=genome_id,
                    genome=ind,
                    generation=gen
                )
                await self.context.event_stream.append(event)

            # Save checkpoint at the end of each generation
            checkpoint_data = {"population": population, "generation": gen}
            self.checkpoint_manager.save(checkpoint_data)

            print(f"第 {gen} 代完成，已發佈 {len(population)} 個基因組。")

        print(f"演化完成。總共執行了 {generations - start_gen} 代。")

    def _create_dummy_genome(self):
        return {
            "strategy": "RSI_Crossover",
            "params": {
                "rsi_period": tools.mutGaussian([14], 7, 1, 1.0)[0][0],
                "buy_threshold": tools.mutGaussian([30], 5, 1, 1.0)[0][0]
            }
        }
