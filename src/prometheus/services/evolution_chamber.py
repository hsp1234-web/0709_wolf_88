import random
import yaml
from deap import base, creator, tools

class EvolutionChamber:
    """
    萬象引擎 (Omniverse Engine) 的演化室。
    負責根據一個可配置的「因子宇宙」來生成、突變和交叉複雜的交易策略基因體。
    基因體是一個條件列表，每個條件都定義了一個交易信號的觸發規則。
    """

    def __init__(self, config_path="config.yml", max_conditions=5):
        """
        初始化演化室。

        :param config_path: 指向設定檔的路徑，需要從中讀取 factor_universe。
        :param max_conditions: 一個基因體中允許存在的最大條件數量。
        """
        self.factor_universe = self._load_factor_universe(config_path)
        self.max_conditions = max_conditions

        # 建立適應度函數，目標是最大化單一目標 (例如夏普比率)
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        # 建立個體 (基因體)，它是一個列表 (代表條件列表)，並帶有適應度屬性
        creator.create("Individual", list, fitness=creator.FitnessMax)

        self.toolbox = base.Toolbox()
        self._register_evolution_operators()

    def _load_factor_universe(self, config_path):
        """從 YAML 設定檔中載入因子宇宙。"""
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        if "factor_universe" not in config:
            raise ValueError("設定檔中未找到 'factor_universe' 區塊。")
        return config["factor_universe"]

    def _register_evolution_operators(self):
        """註冊 DEAP 的演化操作子 (生成、交叉、突變、選擇)。"""
        self.toolbox.register("create_condition", self.create_random_condition)
        self.toolbox.register("individual", self._create_individual)
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)

        self.toolbox.register("evaluate", self._evaluate_fitness)
        self.toolbox.register("mate", self.crossover_individuals)
        self.toolbox.register("mutate", self.mutate_individual)
        self.toolbox.register("select", tools.selTournament, tournsize=3)

    def create_random_condition(self):
        """
        從因子宇宙中隨機選擇一個因子並生成一個完整的條件字典。
        """
        factor_spec = random.choice(self.factor_universe)
        condition = {"factor": factor_spec["name"], "params": {}}

        # 根據規格隨機生成參數
        if "params" in factor_spec:
            for param_name, values in factor_spec["params"].items():
                if isinstance(values, list) and len(values) == 2:
                    condition["params"][param_name] = random.randint(values[0], values[1])
                else:
                    condition["params"][param_name] = random.choice(values)

        # 【核心約束】確保 SMA_cross 的快線永遠小於慢線
        if condition["factor"] == "SMA_cross":
            fast = condition["params"]["fast_window"]
            slow = condition["params"]["slow_window"]
            if fast >= slow:
                # 交換它們
                condition["params"]["fast_window"], condition["params"]["slow_window"] = slow, fast
                # 如果交換後仍然相等 (例如，都從同一個值生成)
                if condition["params"]["fast_window"] == condition["params"]["slow_window"] and condition["params"]["fast_window"] > 1:
                    condition["params"]["fast_window"] -= 1


        # 隨機選擇一個運算子
        condition["operator"] = random.choice(factor_spec["operators"])

        # 如果運算子需要一個比較值 (例如 less_than, greater_than)
        if "value_range" in factor_spec:
            min_val, max_val = factor_spec["value_range"]
            condition["value"] = round(random.uniform(min_val, max_val), 2)

        return condition

    def _create_individual(self):
        """創建一個由多個隨機條件組成的個體 (基因體)。"""
        num_conditions = random.randint(1, self.max_conditions)
        genome = [self.toolbox.create_condition() for _ in range(num_conditions)]
        return creator.Individual(genome)

    def mutate_individual(self, individual):
        """
        對個體進行突變，可能的操作包括：
        1. 新增一個條件。
        2. 移除一個條件。
        3. 修改一個現有條件。
        4. 改變一個條件的運算子。
        """
        if random.random() < 0.2: # 新增條件的機率
            if len(individual) < self.max_conditions:
                individual.append(self.toolbox.create_condition())

        if random.random() < 0.2: # 移除條件的機率
            if len(individual) > 1:
                individual.pop(random.randrange(len(individual)))

        if random.random() < 0.7: # 修改現有條件的機率
            if len(individual) > 0:
                condition_to_mutate = random.choice(individual)
                # 重新生成一個同類型的條件來取代它
                new_condition = self.create_random_condition()
                while new_condition['factor'] != condition_to_mutate['factor']:
                    new_condition = self.create_random_condition()

                # 在列表中替換舊條件
                individual[individual.index(condition_to_mutate)] = new_condition

        return individual,

    def crossover_individuals(self, ind1, ind2):
        """
        對兩個個體進行交叉操作 (單點交叉)。
        隨機選擇一個交叉點，交換兩個基因體的部分條件列表。
        """
        # 複製以避免直接修改原始個體
        ind1, ind2 = creator.Individual(ind1[:]), creator.Individual(ind2[:])

        min_len = min(len(ind1), len(ind2))
        if min_len > 1:
            cx_point = random.randint(1, min_len - 1)
            ind1[cx_point:], ind2[cx_point:] = ind2[cx_point:], ind1[cx_point:]

        return ind1, ind2

    def _evaluate_fitness(self, individual):
        # 佔位符，實際評估由外部回測服務完成
        return (0.0,)

    # --- 公開 API ---
    def create_population(self, n=10):
        return self.toolbox.population(n=n)

    def select_offspring(self, population):
        return self.toolbox.select(population, len(population))

    def apply_mating_and_mutation(self, offspring):
        offspring = list(map(self.toolbox.clone, offspring))

        # 交叉
        for child1, child2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < 0.7: # 交叉機率
                self.toolbox.mate(child1, child2)
                del child1.fitness.values
                del child2.fitness.values

        # 突變
        for mutant in offspring:
            if random.random() < 0.3: # 突變機率
                self.toolbox.mutate(mutant)
                del mutant.fitness.values

        return offspring
