# 檔案: core/services/evolution_chamber.py
import random
import time
import uuid
import json
import duckdb
import numpy as np
from deap import base, creator, tools
from src.core.logger import LogManager
from src.core.queue.base import BaseQueue
from src.core.db.evolution_logger import log_generation_stats, clear_evolution_logs # 導入

class EvolutionChamber:
    def __init__(self, queue: BaseQueue, log_manager: LogManager, db_connection: duckdb.DuckDBPyConnection):
        self.log = log_manager
        self.queue = queue
        self.db_conn = db_connection
        self.table_name = "backtest_results"

        # --- 基因與工具箱設定 ---
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

        # === 新增：建立統計工具箱 ===
        self.stats = tools.Statistics(lambda ind: ind.fitness.values)
        self.stats.register("avg", np.mean)
        self.stats.register("std", np.std)
        self.stats.register("min", np.min)
        self.stats.register("max", np.max)

        # Logbook 用於在終端機中打印日誌
        self.logbook = tools.Logbook()
        self.logbook.header = "gen", "evals", "max", "avg", "std"

    def _evaluate_and_assign_fitness(self, individuals_to_eval):
        """
        評估一個「子族群」的適應度，並將結果賦值回去。
        這是一個阻塞操作，會等待所有回測完成。
        """
        if not individuals_to_eval:
            return

        batch_id = str(uuid.uuid4())
        self.log.log("INFO", f"開始新一批次評估，批次 ID: {batch_id}，待評估個體數: {len(individuals_to_eval)}")

        num_dispatched = 0
        for i, individual in enumerate(individuals_to_eval):
            fast, slow = individual[0], individual[1]
            if slow <= fast:
                individual.fitness.values = (0,)
                continue

            task = {
                "strategy": "SMA_crossover_evolved",
                "symbol": f"IND_{batch_id}_{i}",
                "params": {"fast": fast, "slow": slow},
                "batch_id": batch_id
            }
            self.queue.put(task)
            num_dispatched += 1

        if num_dispatched == 0:
            self.log.log("WARNING", "沒有任何有效任務被派發。")
            return

        self.log.log("INFO", f"等待 {num_dispatched} 個回測結果...")
        start_time = time.time()
        while True:
            try:
                completed_count = self.db_conn.execute(
                    f"SELECT COUNT(*) FROM {self.table_name} WHERE batch_id = ?", [batch_id]
                ).fetchone()[0]
            except (duckdb.CatalogException, TypeError):
                completed_count = 0

            if completed_count >= num_dispatched:
                self.log.log("SUCCESS", f"批次 {batch_id} 所有結果已收到。")
                break
            time.sleep(2)
            if time.time() - start_time > 120:
                self.log.log("ERROR", "等待回測結果超時！")
                break

        try:
            results_df = self.db_conn.execute(
                f"SELECT params, crossover_points FROM {self.table_name} WHERE batch_id = ?", [batch_id]
            ).fetchdf()
            fitness_map = {row['params']: (row['crossover_points'],) for _, row in results_df.iterrows()}
        except duckdb.CatalogException:
            fitness_map = {}

        for ind in individuals_to_eval:
            if not ind.fitness.valid:
                params_str = json.dumps({"fast": ind[0], "slow": ind[1]})
                fitness = fitness_map.get(params_str, (-1,))
                ind.fitness.values = fitness

    def run_evolution_cycle(self, population_size=10, generations=3, cxpb=0.5, mutpb=0.2):
        self.log.log("INFO", "演化室啟動...")
        # === 新增：在演化開始前，清空舊的演化日誌 ===
        clear_evolution_logs()

        population = self.toolbox.population(n=population_size)

        self.log.log("INFO", "--- 第 0 代：初始評估 ---")
        self._evaluate_and_assign_fitness(population)

        # === 新增：記錄第 0 代的統計數據 ===
        record = self.stats.compile(population)
        log_generation_stats(generation=0, stats=record)
        self.logbook.record(gen=0, evals=len(population), **record)
        self.log.log("INFO", self.logbook.stream)

        for g in range(1, generations + 1):
            self.log.log("INFO", f"--- 第 {g} 代：開始演化 ---")

            offspring = self.toolbox.select(population, len(population))
            offspring = list(map(self.toolbox.clone, offspring))

            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < cxpb:
                    self.toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values

            for mutant in offspring:
                if random.random() < mutpb:
                    self.toolbox.mutate(mutant)
                    del mutant.fitness.values

            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            self._evaluate_and_assign_fitness(invalid_ind)

            population[:] = offspring

            # === 新增：記錄每一代的統計數據 ===
            record = self.stats.compile(population)
            log_generation_stats(generation=g, stats=record)
            self.logbook.record(gen=g, evals=len(invalid_ind), **record)
            self.log.log("INFO", self.logbook.stream)

        best_individual = tools.selBest(population, k=1)[0]
        self.log.log("SUCCESS", f"演化完成！找到的最佳策略參數為: {best_individual}")
        if best_individual.fitness.valid:
            self.log.log("DATA", f"  - 最終最佳適應度分數: {best_individual.fitness.values[0]:.2f}")
        else:
            self.log.log("DATA", "  - 最終最佳適應度分數: N/A")
        return best_individual
