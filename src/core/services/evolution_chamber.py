import random
import time
import uuid
import json
import sqlite3
import pandas as pd
import numpy as np
from deap import base, creator, tools, algorithms
from src.core.logger import LogManager
from src.core.queue.base import BaseQueue
from src.core.db.evolution_logger import log_generation_stats, clear_evolution_logs

class EvolutionChamber:
    def __init__(self, queue: BaseQueue, log_manager: LogManager):
        self.log = log_manager
        self.queue = queue
        self.results_db_path = "output/results.sqlite"
        self.results_table_name = "backtest_results"

        if not hasattr(creator, "FitnessMax"):
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        if not hasattr(creator, "Individual"):
            creator.create("Individual", list, fitness=creator.FitnessMax)

        self.toolbox = base.Toolbox()
        self.toolbox.register("attr_int", random.randint, 1, 50)
        self.toolbox.register("individual", tools.initRepeat, creator.Individual, self.toolbox.attr_int, n=2)
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)
        self.toolbox.register("mate", tools.cxTwoPoint)
        self.toolbox.register("mutate", tools.mutUniformInt, low=1, up=50, indpb=0.2)
        self.toolbox.register("select", tools.selTournament, tournsize=3)
        self.stats = tools.Statistics(lambda ind: ind.fitness.values)
        self.stats.register("avg", np.mean)
        self.stats.register("std", np.std)
        self.stats.register("min", np.min)
        self.stats.register("max", np.max)
        self.logbook = tools.Logbook()
        self.logbook.header = "gen", "evals", "max", "avg", "std"

    def _evaluate_and_assign_fitness(self, individuals_to_eval):
        batch_id = str(uuid.uuid4())
        dispatched_tasks = {}

        for i, ind in enumerate(individuals_to_eval):
            if not ind.fitness.valid:
                task_id = f"IND_{batch_id}_{i}"
                params = {"fast": ind[0], "slow": ind[1]}
                if params['slow'] <= params['fast']:
                    ind.fitness.values = (0,)
                    continue
                task = {"_task_id": task_id, "symbol": task_id, "strategy": "SMA_crossover_evolved", "params": params, "batch_id": batch_id}
                self.queue.put(task)
                dispatched_tasks[task_id] = ind

        num_dispatched = len(dispatched_tasks)
        if num_dispatched == 0:
            self.log.log("WARNING", "沒有任何有效任務被派發。")
            return

        self.log.log("INFO", f"等待 {num_dispatched} 個回測結果從 SQLite 返回...")
        start_time = time.time()
        while True:
            try:
                conn = sqlite3.connect(self.results_db_path)
                df = pd.read_sql_query(f"SELECT * FROM {self.results_table_name} WHERE batch_id = ?", conn, params=(batch_id,))
                conn.close()
                completed_count = len(df)
            except Exception:
                completed_count = 0

            if completed_count >= num_dispatched:
                self.log.log("SUCCESS", f"批次 {batch_id} 所有結果已收到。")
                break
            time.sleep(2)
            if time.time() - start_time > 120:
                self.log.log("ERROR", "等待回測結果超時！")
                break

        try:
            conn = sqlite3.connect(self.results_db_path)
            results_df = pd.read_sql_query(f"SELECT params, crossover_points FROM {self.results_table_name} WHERE batch_id = ?", conn, params=(batch_id,))
            conn.close()
            fitness_map = {row['params']: (row['crossover_points'],) for _, row in results_df.iterrows()}
        except Exception:
            fitness_map = {}

        for ind in individuals_to_eval:
            params_str = json.dumps({"fast": ind[0], "slow": ind[1]})
            if params_str in fitness_map:
                ind.fitness.values = fitness_map[params_str]
            else:
                if not ind.fitness.valid:
                    ind.fitness.values = (0,)

    def run_evolution_cycle(self, population_size=10, generations=3, cxpb=0.5, mutpb=0.2):
        self.log.log("INFO", "演化室啟動...")
        clear_evolution_logs()
        population = self.toolbox.population(n=population_size)
        self.logbook = tools.Logbook()
        self.logbook.header = "gen", "evals", "max", "avg", "std", "min"

        self.log.log("INFO", "--- 第 0 代：初始評估 ---")
        self._evaluate_and_assign_fitness(population)
        record = self.stats.compile(population)
        log_generation_stats(generation=0, stats=record)
        self.logbook.record(gen=0, evals=len(population), **record)
        self.log.log("INFO", self.logbook.stream)

        for gen in range(1, generations + 1):
            self.log.log("INFO", f"--- 第 {gen} 代：開始演化 ---")
            offspring = algorithms.varAnd(population, self.toolbox, cxpb, mutpb)
            self._evaluate_and_assign_fitness(offspring)
            population[:] = offspring
            record = self.stats.compile(population)
            log_generation_stats(generation=gen, stats=record)
            self.logbook.record(gen=gen, evals=len(offspring), **record)
            self.log.log("INFO", self.logbook.stream)

        best_ind = tools.selBest(population, 1)[0]
        self.log.log("SUCCESS", "演化完成！找到的最佳策略參數為: " + str(best_ind))
        self.log.log("DATA", f"  - 最終最佳適應度分數: {best_ind.fitness.values[0]:.2f}")
