# 檔案: src/core/services/evolution_chamber.py
import random
import copy
import asyncio
from deap import base, creator, tools
from typing import Dict, Any, List
from src.core.queue.async_event_bus import AsyncEventBus

# --- DEAP Global Setup ---
creator.create("FitnessMax", base.Fitness, weights=(1.0,))
creator.create("Individual", dict, fitness=creator.FitnessMax)

def create_rsi_genome(strategy_name: str = "RSI Crossover") -> creator.Individual:
    genome_dict = {
        "strategy_name": strategy_name,
        "indicators": [{"name": "RSI", "params": {"window": random.randint(5, 20)}}],
        "entry_rules": [{"indicator": "RSI", "operator": "less_than", "value": random.randint(20, 40)}],
        "exit_rules": [{"indicator": "RSI", "operator": "greater_than", "value": random.randint(60, 80)}],
    }
    return creator.Individual(genome_dict)

def mutate_genome(individual: creator.Individual) -> tuple:
    # 使用 DEAP 內建的工具進行更穩健的變異
    params = individual["indicators"][0]["params"]
    # Create a list for mutation
    window = [params["window"]]
    tools.mutGaussian(window, mu=14, sigma=5, indpb=1.0)
    params["window"] = max(2, int(window[0])) # 確保窗口為正整數
    return individual,

def mate_genomes(ind1: creator.Individual, ind2: creator.Individual) -> tuple:
    """交叉兩個基因組的參數"""
    # 交換整個參數字典，因為 cxTwoPoint 需要至少兩個元素
    ind1["indicators"][0]["params"], ind2["indicators"][0]["params"] = \
        ind2["indicators"][0]["params"], ind1["indicators"][0]["params"]
    return ind1, ind2

class EvolutionChamber:
    def __init__(self, queue: AsyncEventBus):
        self.queue = queue
        self.toolbox = base.Toolbox()
        self.toolbox.register("individual", create_rsi_genome)
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)
        self.toolbox.register("mate", mate_genomes)
        self.toolbox.register("mutate", mutate_genome)
        self.toolbox.register("select", tools.selTournament, tournsize=3)

    async def _submit_for_evaluation(self, individual: creator.Individual) -> str:
        task_payload = dict(individual)
        backtest_id = f"backtest_{random.randint(1000, 9999)}_{random.randint(1000, 9999)}"
        task = {"individual": task_payload, "backtest_id": backtest_id}
        await self.queue.put(task)
        return backtest_id

    async def _evaluate_and_assign_fitness(self, individuals: List[creator.Individual]):
        if not individuals:
            return

        id_to_individual = {await self._submit_for_evaluation(ind): ind for ind in individuals}

        await self.queue.join()

        num_results = len(id_to_individual)
        for _ in range(num_results):
            result = await self.queue.get_result()
            if result and result['backtest_id'] in id_to_individual:
                individual = id_to_individual[result['backtest_id']]
                individual.fitness.values = (result['fitness'],)

    async def evolve(self, generations=5, population_size=10):
        population = self.toolbox.population(n=population_size)

        print(f"第 0 代：評估 {len(population)} 個初始個體...")
        await self._evaluate_and_assign_fitness(population)

        for gen in range(1, generations + 1):
            print(f"--- 第 {gen} 代演化 ---")
            offspring = self.toolbox.select(population, len(population))
            offspring = [self.toolbox.clone(ind) for ind in offspring]

            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < 0.7:
                    self.toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values

            for mutant in offspring:
                if random.random() < 0.3:
                    self.toolbox.mutate(mutant)
                    del mutant.fitness.values

            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            if invalid_ind:
                print(f"評估 {len(invalid_ind)} 個新個體...")
                await self._evaluate_and_assign_fitness(invalid_ind)

            population[:] = offspring

        return population
