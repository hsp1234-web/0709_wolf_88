# -*- coding: utf-8 -*-
"""
演化室：使用遺傳演算法來發現高效的交易策略。
"""
import random
from typing import List, Tuple

from deap import base, creator, tools

from prometheus.services.backtesting_service import BacktestingService
from prometheus.models.strategy_models import Strategy

class EvolutionChamber:
    """
    一個「演化室」，將因子庫轉化為基因池，並使用遺傳演算法進行策略演化。
    """
    def __init__(self, backtesting_service: BacktestingService, available_factors: List[str]):
        """
        初始化演化室。

        Args:
            backtesting_service (BacktestingService): 用於評估策略適應度的回測服務。
            available_factors (List[str]): 可供演化選擇的所有因子名稱列表。
        """
        self.backtester = backtesting_service
        self.available_factors = available_factors
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
        selected_factors = [self.available_factors[i] for i in individual]

        # 2. 建立策略物件 (此處使用等權重作為範例)
        strategy_to_test = Strategy(
            factors=selected_factors,
            weights={factor: 1.0 / len(selected_factors) for factor in selected_factors}
        )

        # 3. 執行回測以獲得績效
        report = self.backtester.run(strategy_to_test)

        # 4. 返回適應度分數 (以元組形式)
        return (report.sharpe_ratio,)

    def _setup_toolbox(self):
        """
        設定 DEAP 的 toolbox，定義基因、個體、族群的生成規則。
        """
        # 定義「基因」：一個代表因子索引的整數
        self.toolbox.register("factor_indices", random.sample, range(len(self.available_factors)), self.num_factors_to_select)

        # 定義「個體」：由一組不重複的因子索引構成
        self.toolbox.register("individual", tools.initIterate, creator.Individual, self.toolbox.factor_indices)

        # 定義「族群」：由多個「個體」組成的列表
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)

        # 新增：註冊評估函數
        self.toolbox.register("evaluate", self._evaluate_strategy)

    def run_evolution(self):
        """
        執行完整的演化流程（將在後續藍圖中實現）。
        """
        # TODO: 實現演化主迴圈
        # 1. 初始化族群
        # 2. 迭代執行評估、選擇、交叉、突變
        # 3. 返回最優個體
        print("INFO: 演化室主迴圈待實現。")
        pass
