# 檔案: src/core/services/evolution_chamber.py
import random
from deap import base, creator, tools, algorithms
from typing import Dict, Any, List, Tuple

from src.core.queue.base import BaseQueue
from src.core.logger import LogManager

# --- 自定義基因操作函數 ---

def create_rsi_genome() -> Dict[str, Any]:
    """生成一個隨機參數的 RSI 策略基因體。"""
    return {
        "strategy_name": "RSI_MeanReversion",
        "indicators": [{
            "name": "RSI",
            "params": {"window": random.randint(7, 21)}
        }],
        "entry_rules": [{
            "indicator": "RSI",
            "operator": "<",
            "value": random.randint(20, 40)
        }],
        "exit_rules": [{
            "indicator": "RSI",
            "operator": ">",
            "value": random.randint(60, 80)
        }]
    }

def mutate_genome(individual: Dict[str, Any]) -> Tuple[Dict[str, Any]]:
    """
    針對策略基因體字典的自定義突變函數。
    隨機選擇基因體中的一個數值進行變異。
    """
    # DEAP 要求突變函數返回一個元組
    mutation_type = random.choice(["rsi_window", "entry_value", "exit_value"])

    if mutation_type == "rsi_window":
        individual["indicators"][0]["params"]["window"] += random.randint(-3, 3)
        # 確保參數在合理範圍內
        individual["indicators"][0]["params"]["window"] = max(5, min(30, individual["indicators"][0]["params"]["window"]))

    elif mutation_type == "entry_value":
        individual["entry_rules"][0]["value"] += random.randint(-5, 5)
        individual["entry_rules"][0]["value"] = max(15, min(45, individual["entry_rules"][0]["value"]))

    elif mutation_type == "exit_value":
        individual["exit_rules"][0]["value"] += random.randint(-5, 5)
        individual["exit_rules"][0]["value"] = max(55, min(85, individual["exit_rules"][0]["value"]))

    return individual,


class EvolutionChamber:
    """
    策略演化室 v2.0 (基因體感知版)
    """
    def __init__(self, queue: BaseQueue, log_manager: LogManager):
        self.queue = queue
        self.log_manager = log_manager
        self.stats = self._setup_stats()

        # === 核心升級：確保 DEAP 類型只被創建一次 ===
        if not hasattr(creator, "FitnessMax"):
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        # 將 Individual 的基礎類型從 list 改為 dict
        if not hasattr(creator, "Individual"):
            creator.create("Individual", dict, fitness=creator.FitnessMax)

        self.toolbox = base.Toolbox()

        # === 核心升級：註冊基因體生成與操作工具 ===
        self.toolbox.register("individual", tools.initIterate, creator.Individual, create_rsi_genome)
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)

        # 註冊自定義的突變函數
        self.toolbox.register("mutate", mutate_genome)

        # 交叉操作暫時使用簡單的兩點交叉，未來可擴充為更複雜的基因體交叉
        self.toolbox.register("mate", tools.cxUniform, indpb=0.5)
        self.toolbox.register("select", tools.selTournament, tournsize=3)
        self.toolbox.register("evaluate", self._submit_for_evaluation)

        self.log_manager.log("INFO", "演化室 v2.0 初始化，已啟用策略基因體感知能力。")

    def _setup_stats(self):
        # ... (此方法保持不變)
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", lambda x: sum(x) / len(x) if len(x) > 0 else 0)
        stats.register("std", lambda x: (sum((i - sum(x)/len(x))**2 for i in x) / len(x))**0.5 if len(x) > 0 else 0)
        stats.register("min", min)
        stats.register("max", max)
        return stats

    def _submit_for_evaluation(self, individual: Dict[str, Any]) -> None:
        """將單個基因體提交到任務佇列進行評估。"""
        # ... (此方法保持不變，因為它傳遞的是整個 individual)
        backtest_id = f"backtest_{random.randint(1000, 9999)}_{random.randint(1000, 9999)}"
        task = {"individual": individual, "backtest_id": backtest_id}
        self.queue.put(task)
        return backtest_id

    def _evaluate_and_assign_fitness(self, individuals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # ... (此方法保持不變)
        task_ids = [self._submit_for_evaluation(ind) for ind in individuals]

        results = {}
        for _ in range(len(task_ids)):
            result = self.queue.get_result()
            if result:
                results[result['backtest_id']] = result['fitness']

        for i, ind in enumerate(individuals):
            backtest_id = task_ids[i]
            fitness = results.get(backtest_id)
            if fitness is not None:
                ind.fitness.values = (fitness,)

        return individuals

    def evolve(self):
        # ... (此方法保持不變)
        self.log_manager.log("INFO", "演化流程開始...")
        population = self.toolbox.population(n=10)

        for gen in range(2): # 簡化世代數以便測試
            self.log_manager.log("INFO", f"--- 第 {gen + 1} 世代 ---")

            offspring = algorithms.varAnd(population, self.toolbox, cxpb=0.5, mutpb=0.2)

            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]

            evaluated_inds = self._evaluate_and_assign_fitness(invalid_ind)

            population = self.toolbox.select(offspring, k=len(population))

            record = self.stats.compile(population)
            self.log_manager.log("INFO", f"本世代統計: {record}")

        self.log_manager.log("SUCCESS", "演化流程完成。")
        return population
