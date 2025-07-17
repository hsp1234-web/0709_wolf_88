# -*- coding: utf-8 -*-
"""
演化室：使用遺傳演算法來發現高效的交易策略。
"""
import random
from typing import List, Tuple
import numpy as np

from deap import base, creator, tools

from prometheus.services.backtesting_service import BacktestingService
from prometheus.models.strategy_models import Strategy

class EvolutionChamber:
    """
    一個「演化室」，將因子庫轉化為基因池，並使用遺傳演算法進行策略演化。
    """
    def __init__(self, backtesting_service: BacktestingService, available_factors: List[str], target_asset: str = 'SPY'):
        """
        初始化演化室。

        Args:
            backtesting_service (BacktestingService): 用於評估策略適應度的回測服務。
            available_factors (List[str]): 可供演化選擇的所有因子名稱列表。
            target_asset (str): 演化和回測的目標資產。
        """
        self.backtester = backtesting_service
        self.available_factors = available_factors
        self.target_asset = target_asset
        self.num_factors_to_select = 5 # 暫定每個策略由5個因子構成

        # --- DEAP 核心設定 ---
        # 確保 FitnessMax 和 Individual 只被創建一次，避免在多個實例中重複創建導致錯誤
        if not hasattr(creator, "FitnessMax"):
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        if not hasattr(creator, "Individual"):
            # 每個「個體」都是一個列表，代表一個策略
            creator.create("Individual", list, fitness=creator.FitnessMax)

        self.toolbox = base.Toolbox()
        self._setup_toolbox()

    def _evaluate_strategy(self, individual: List[int]) -> Tuple[float]:
        """
        評估單一個體的適應度，此為演化核心的「適應度函數」。
        """
        # 1. 解碼基因：將因子索引轉換為因子名稱
        raw_factors = [self.available_factors[i] for i in individual]
        # 【修正】確保因子列表的唯一性，防止因交叉突變導致的重複
        selected_factors = list(dict.fromkeys(raw_factors))

        # 如果去重後因子少於1個，這是一個無效策略
        if not selected_factors:
            return (0.0,)

        # 2. 建立策略物件 (此處使用等權重作為範例)
        strategy_to_test = Strategy(
            factors=selected_factors,
            weights={factor: 1.0 / len(selected_factors) for factor in selected_factors},
            target_asset=self.target_asset # 使用演化室指定的目標資產
        )

        # 3. 執行回測以獲得績效
        report = self.backtester.run(strategy_to_test)

        # 4. 返回適應度分數 (以元組形式)
        return (report.sharpe_ratio,)

    def _setup_toolbox(self):
        """
        設定 DEAP 的 toolbox，定義基因、個體、族群的生成規則與演化算子。
        """
        # 定義「基因」：一個代表因子索引的整數
        self.toolbox.register("factor_indices", random.sample, range(len(self.available_factors)), self.num_factors_to_select)

        # 定義「個體」：由一組不重複的因子索引構成
        self.toolbox.register("individual", tools.initIterate, creator.Individual, self.toolbox.factor_indices)

        # 定義「族群」：由多個「個體」組成的列表
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)

        # --- 新增：註冊核心遺傳算子 ---
        self.toolbox.register("evaluate", self._evaluate_strategy)
        # 交叉算子：兩點交叉
        self.toolbox.register("mate", tools.cxTwoPoint)
        # 突變算子：隨機交換索引，indpb 為每個基因的突變機率
        self.toolbox.register("mutate", tools.mutShuffleIndexes, indpb=0.1)
        # 選擇算子：錦標賽選擇，tournsize 為每次競賽的個體數
        self.toolbox.register("select", tools.selTournament, tournsize=3)

    def run_evolution(self, n_pop: int = 50, n_gen: int = 10, cxpb: float = 0.5, mutpb: float = 0.2):
        """
        執行完整的演化流程。

        Args:
            n_pop (int): 族群大小。
            n_gen (int): 演化世代數。
            cxpb (float): 交叉機率。
            mutpb (float): 突變機率。

        Returns:
            tools.HallOfFame: 包含演化過程中發現的最優個體。
        """
        pop = self.toolbox.population(n=n_pop)
        hof = tools.HallOfFame(1) # 名人堂，只儲存最優的一個個體
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", np.mean)
        stats.register("std", np.std)
        stats.register("min", np.min)
        stats.register("max", np.max)

        # 1. 首次評估所有個體
        fitnesses = map(self.toolbox.evaluate, pop)
        for ind, fit in zip(pop, fitnesses):
            ind.fitness.values = fit

        print(f"--- 開始演化，共 {n_gen} 代 ---")

        for g in range(n_gen):
            # 2. 選擇下一代的個體
            offspring = self.toolbox.select(pop, len(pop))
            offspring = list(map(self.toolbox.clone, offspring))

            # 3. 執行交叉與突變
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < cxpb:
                    self.toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values

            for mutant in offspring:
                if random.random() < mutpb:
                    self.toolbox.mutate(mutant)
                    del mutant.fitness.values

            # 4. 評估被改變的個體
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = map(self.toolbox.evaluate, invalid_ind)
            for ind, fit in zip(invalid_ind, fitnesses):
                ind.fitness.values = fit

            # 5. 更新族群與名人堂
            pop[:] = offspring
            hof.update(pop)

            record = stats.compile(pop)
            print(f"> 第 {g+1} 代: 最優夏普 = {record['max']:.4f}, 平均夏普 = {record['avg']:.4f}")

        print("--- 演化結束 ---")
        return hof
