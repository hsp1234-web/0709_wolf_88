import random
from deap import base, creator, tools

class EvolutionChamber:
    """
    封裝了 DEAP 基因演算法所有核心設定的演化室。
    """
    def __init__(self, min_fast=5, max_fast=50, min_slow=10, max_slow=100):
        # 建立適應度函數，目標是最大化單一目標 (夏普比率)
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        # 建立個體 (基因體)，它是一個列表，並帶有適應度屬性
        creator.create("Individual", list, fitness=creator.FitnessMax)

        self.toolbox = base.Toolbox()

        # --- 基因 (Gene) 的定義 ---
        # 基因0: 快速均線窗口，整數，範圍在 min_fast 到 max_fast
        self.toolbox.register("attr_fast", random.randint, min_fast, max_fast)
        # 基因1: 慢速均線窗口，整數，範圍在 min_slow 到 max_slow
        self.toolbox.register("attr_slow", random.randint, min_slow, max_slow)

        # --- 個體 (Individual) 的定義 ---
        # 一個個體由 2 個基因組成
        self.toolbox.register("individual", tools.initCycle, creator.Individual,
                              (self.toolbox.attr_fast, self.toolbox.attr_slow), n=1)

        # --- 族群 (Population) 的定義 ---
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)

        # --- 演化操作子的定義 ---
        self.toolbox.register("evaluate", self._evaluate_fitness) # 評估函數
        self.toolbox.register("mate", tools.cxTwoPoint)          # 交叉 (交配)
        self.toolbox.register("mutate", self._mutate_individual, indpb=0.2) # 突變
        self.toolbox.register("select", tools.selTournament, tournsize=3) # 選擇

    def _evaluate_fitness(self, individual):
        # 這只是一個佔位符。真正的適應度是在主迴圈中從回測結果賦值的。
        # 我們返回一個元組，因為 DEAP 的適應度可以是多目標的。
        return 0.0,

    def _mutate_individual(self, individual, indpb):
        """自定義突變函數，確保 fast_window 永遠小於 slow_window。"""
        # 突變 fast_window
        if random.random() < indpb:
            individual[0] = self.toolbox.attr_fast()

        # 突變 slow_window
        if random.random() < indpb:
            individual[1] = self.toolbox.attr_slow()

        # 【核心約束】如果突變後 fast >= slow，則進行修正
        if individual[0] >= individual[1]:
            # 簡單的修正策略：將 fast 設為 slow 的一半
            individual[0] = individual[1] // 2
            if individual[0] == 0: # 避免為 0
                individual[0] = 1

        return individual,

    def create_population(self, n=10):
        """創建一個指定大小的初始族群。"""
        return self.toolbox.population(n=n)

    def select_offspring(self, population):
        """從當前族群中選擇後代。"""
        return self.toolbox.select(population, len(population))

    def mate_and_mutate(self, offspring):
        """對後代進行交叉和突變。"""
        # 複製後代以避免修改原始列表
        offspring = list(map(self.toolbox.clone, offspring))

        # 交叉
        for child1, child2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < 0.5:
                self.toolbox.mate(child1, child2)
                del child1.fitness.values
                del child2.fitness.values

        # 突變
        for mutant in offspring:
            if random.random() < 0.2:
                self.toolbox.mutate(mutant)
                del mutant.fitness.values

        return offspring
