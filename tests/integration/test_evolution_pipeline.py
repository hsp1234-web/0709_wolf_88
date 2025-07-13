# 檔案: tests/integration/test_evolution_pipeline.py
import pytest
import random
from core.logger import LogManager
from core.services.evolution_chamber import EvolutionChamber

@pytest.fixture(scope="function")
def test_log_manager():
    """提供一個用於測試的 LogManager 實例。"""
    return LogManager(session_name="lightweight_evolution_test")

def mock_evaluate_fitness(individual):
    """
    一個模擬的、同步的適應度評估函數。
    它不執行任何 I/O 或多執行緒操作，能瞬時返回結果。
    """
    fast, slow = individual[0], individual[1]
    # 確保慢線 > 快線，否則適應度為 0
    if slow <= fast:
        return 0,  # DEAP 要求適應度是一個元組
    # 模擬一個簡單的適應度分數
    return (slow - fast),

def test_evolution_chamber_logic(test_log_manager):
    """
    驗證 EvolutionChamber 核心演算法邏輯的單元測試。
    """
    # 1. 初始化演化室 (注意：不傳入 queue，因為我們用不到它)
    #    為了防止 __init__ 報錯，我們傳入一個 None
    chamber = EvolutionChamber(queue=None, log_manager=test_log_manager)

    # 2. === 核心戰術：替換評估函數 ===
    #    用我們輕量級的模擬函數，覆蓋掉原本需要執行回測的真實函數。
    chamber.toolbox.register("evaluate", mock_evaluate_fitness)

    # 3. 移除會與真實管線交互的、我們不再需要的函數
    #    這確保了測試的完全隔離。
    chamber._evaluate_and_assign_fitness = lambda individuals: None

    test_log_manager.log("INFO", "開始執行輕量化演化邏輯測試...")

    # 4. 執行一個極小規模的演化
    #    我們使用 DEAP 的標準演算法，因為現在評估函數是同步的，不會有問題。
    from deap import algorithms

    population = chamber.toolbox.population(n=10)

    # 執行演算法
    result_pop, logbook = algorithms.eaSimple(
        population,
        chamber.toolbox,
        cxpb=0.5,
        mutpb=0.2,
        ngen=4,
        verbose=False # 關閉 DEAP 的內建日誌
    )

    # 5. 驗證結果
    from deap import tools
    best_individual = tools.selBest(result_pop, k=1)[0]

    test_log_manager.log("SUCCESS", f"輕量化測試完成。最佳個體: {best_individual}, 適應度: {best_individual.fitness.values[0]}")

    assert best_individual is not None, "演化未能產生任何最佳個體！"
    assert best_individual.fitness.valid, "最終選出的最佳個體沒有有效的適應度分數！"
    assert best_individual.fitness.values[0] > 0, "最佳個體的適應度不應為 0！"
