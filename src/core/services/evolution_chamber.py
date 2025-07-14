# 檔案: core/services/evolution_chamber.py
import random
import time
import uuid
import json
import duckdb
from deap import base, creator, tools
# 移除 algorithms 的導入，我們將不再使用它
from src.core.logger import LogManager
from src.core.queue.base import BaseQueue

class EvolutionChamber:
    def __init__(self, queue: BaseQueue, log_manager: LogManager, db_connection: duckdb.DuckDBPyConnection):
        self.log = log_manager
        self.queue = queue
        self.db_conn = db_connection
        self.table_name = "backtest_results"

        # --- 基因與工具箱設定 (與之前相同，但移除 evaluate 註冊) ---
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
        # 不再向 toolbox 註冊 evaluate，我們將手動調用它

    def _get_initial_population(self, population_size):
        return self.toolbox.population(n=population_size)

    def _select_survivors(self, population, k):
        return self.toolbox.select(population, k)

    def _crossover_and_mutate(self, offspring, cxpb, mutpb):
        # 交叉 (交配)
        for child1, child2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < cxpb:
                self.toolbox.mate(child1, child2)
                del child1.fitness.values
                del child2.fitness.values

        # 突變
        for mutant in offspring:
            if random.random() < mutpb:
                self.toolbox.mutate(mutant)
                del mutant.fitness.values

        return offspring

    def _evaluate_and_assign_fitness(self, individuals_to_eval):
        """
        評估一個「子族群」的適應度，並將結果賦值回去。
        這是一個阻塞操作，會等待所有回測完成。
        """
        if not individuals_to_eval:
            return # 如果沒有需要評估的個體，直接返回

        batch_id = str(uuid.uuid4())
        self.log.log("INFO", f"開始新一批次評估，批次 ID: {batch_id}，待評估個體數: {len(individuals_to_eval)}")

        # 1. 派發任務
        num_dispatched = 0
        for i, individual in enumerate(individuals_to_eval):
            # 確保個體合法性
            fast, slow = individual[0], individual[1]
            if slow <= fast:
                individual.fitness.values = (0,) # 直接賦予無效個體 0 分
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

        # 2. 等待結果
        self.log.log("INFO", f"等待 {num_dispatched} 個回測結果...")
        start_time = time.time()
        while True:
            with self.db_conn.cursor() as cursor:
                try:
                    completed_count = cursor.execute(
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
                break # 超時後繼續，未完成的個體將得到 0 分

        # 3. 分配適應度
        with self.db_conn.cursor() as cursor:
            try:
                results_df = cursor.execute(
                    f"SELECT params, crossover_points FROM {self.table_name} WHERE batch_id = ?", [batch_id]
                ).fetchdf()
                fitness_map = {row['params']: (row['crossover_points'],) for _, row in results_df.iterrows()}
            except duckdb.CatalogException:
                fitness_map = {}

        for ind in individuals_to_eval:
            if not ind.fitness.valid: # 只更新需要評估的個體
                params_str = json.dumps({"fast": ind[0], "slow": ind[1]})
                fitness = fitness_map.get(params_str, (-1,)) # 超時或未找到結果的個體適應度為 -1
                ind.fitness.values = fitness

    def run_evolution_cycle(self, population_size: int, generations: int, cxpb=0.5, mutpb=0.2):
        """
        執行一次完整的、手動控制的演化週期。
        """
        self.log.log("INFO", "演化室啟動：正在初始化族群...")
        population = self._get_initial_population(population_size)

        # 初始評估整個族群
        self.log.log("INFO", "--- 第 0 代：初始評估 ---")
        self._evaluate_and_assign_fitness(population)

        for g in range(1, generations + 1):
            self.log.log("INFO", f"--- 第 {g} 代：開始演化 ---")

            # 1. 選擇
            offspring = self._select_survivors(population, len(population))
            offspring = list(map(self.toolbox.clone, offspring))

            # 2. 交叉 (交配) and 3. 突變
            offspring = self._crossover_and_mutate(offspring, cxpb, mutpb)

            # 4. 評估所有適應度無效的新生代
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            self._evaluate_and_assign_fitness(invalid_ind)

            # 5. 新生代取代舊族群
            population[:] = offspring

            # 打印當代最佳
            best_ind = tools.selBest(population, 1)[0]
            if best_ind.fitness.valid:
                self.log.log("DATA", f"第 {g} 代最佳個體: {best_ind}, 適應度: {best_ind.fitness.values[0]:.2f}")
            else:
                self.log.log("DATA", f"第 {g} 代最佳個體: {best_ind}, 適應度: N/A")

        best_individual = tools.selBest(population, k=1)[0]
        self.log.log("SUCCESS", f"演化完成！找到的最佳策略參數為: {best_individual}")
        if best_individual.fitness.valid:
            self.log.log("DATA", f"  - 最終最佳適應度分數: {best_individual.fitness.values[0]:.2f}")
        else:
            self.log.log("DATA", "  - 最終最佳適應度分數: N/A")
        return best_individual
