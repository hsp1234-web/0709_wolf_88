# 檔案: core/services/evolution_chamber.py
import random
from deap import base, creator, tools, algorithms
from core.logger import LogManager

class EvolutionChamber:
    """
    演化室：使用遺傳演算法來探索和優化策略參數。
    """
    def __init__(self, log_manager: LogManager):
        self.log = log_manager

        # --- 基因定義 ---
        # 1. 定義適應度：我們的目標是找到最大值，所以權重是 1.0
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        # 2. 定義「個體」(即策略)：一個帶有適應度的列表
        creator.create("Individual", list, fitness=creator.FitnessMax)

        # --- 工具箱設定 ---
        self.toolbox = base.Toolbox()

        # 3. 定義基因的產生方式：一個 1 到 50 之間的整數
        self.toolbox.register("attr_int", random.randint, 1, 50)

        # 4. 定義個體的產生方式：由 2 個基因 (快、慢週期) 組成
        self.toolbox.register("individual", tools.initRepeat, creator.Individual, self.toolbox.attr_int, n=2)

        # 5. 定義「族群」的產生方式：由多個個體組成的列表
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)

        # 6. 註冊遺傳演算法的核心操作
        self.toolbox.register("evaluate", self._evaluate_fitness) # 適應度評估
        self.toolbox.register("mate", tools.cxTwoPoint)          # 交叉 (交配)
        self.toolbox.register("mutate", tools.mutUniformInt, low=1, up=50, indpb=0.2) # 突變
        self.toolbox.register("select", tools.selTournament, tournsize=3) # 選擇

    def _evaluate_fitness(self, individual):
        """
        適應度評估函數 (目前為模擬)。
        目標：評估一個策略 (個體) 的優劣。
        真實場景下，這裡會觸發回測並返回評估指標。
        """
        fast, slow = individual[0], individual[1]
        # 確保慢線 > 快線
        if slow <= fast:
            return 0, # 返回一個元組
        # 模擬一個簡單的適應度分數
        return (slow - fast) * 1.5,

    def run_evolution_cycle(self, population_size=10, generations=3):
        """
        執行一次完整的演化週期。
        """
        self.log.log("INFO", "演化室啟動：正在初始化族群...")
        population = self.toolbox.population(n=population_size)

        self.log.log("INFO", f"開始演化，族群規模: {population_size}，世代數: {generations}")

        # 執行 DEAP 提供的標準遺傳演算法
        algorithms.eaSimple(
            population,
            self.toolbox,
            cxpb=0.5,    # 交叉機率
            mutpb=0.2,   # 突變機率
            ngen=generations, # 世代數
            verbose=False    # 關閉 DEAP 的內建日誌
        )

        # 找出最終族群中的最佳個體
        best_individual = tools.selBest(population, k=1)[0]
        self.log.log("SUCCESS", f"演化完成！找到的最佳策略參數為: {best_individual}")
        self.log.log("DATA", f"  - 最佳適應度分數: {best_individual.fitness.values[0]:.2f}")
        return best_individual
