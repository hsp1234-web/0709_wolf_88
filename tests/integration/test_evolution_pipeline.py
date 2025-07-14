import pytest
import json
from src.core.context import AppContext
from src.core.services.evolution_chamber import EvolutionChamber
from src.apps.factor_engine.sma_crossover_factor import calculate_sma_crossover
from src.core.db.results_saver import save_result

# --- 常數定義 ---
POPULATION_SIZE = 4 # 使用較小的族群以加速測試
GENERATIONS = 2     # 使用較少的世代數

def test_evolution_logic_in_loop(app_context: AppContext):
    """
    驗證演化核心邏輯的「完全內循環」測試。
    此測試不依賴任何背景執行緒或真實的佇列等待。
    """
    log_manager = app_context.log_manager
    chamber = EvolutionChamber(queue=app_context.queue, log_manager=log_manager)

    # === 核心戰術：用一個「同步執行」的模擬函數，覆蓋掉原本的異步評估流程 ===
    def synchronous_evaluation_mock(individuals_to_eval):
        """
        這個模擬函數扮演了「演化室」和「背景工作者」的雙重角色。
        它在同一個執行緒中，完成了從派發到執行的所有工作。
        """
        log_manager.log("INFO", "[MOCK] 攔截到批次評估請求...")

        if not individuals_to_eval:
            return

        # 1. 模擬「派發」與「執行」
        #    直接在主執行緒中計算結果並儲存，而不是放入佇列等待。
        for ind in individuals_to_eval:
            fast, slow = ind[0], ind[1]
            if slow <= fast:
                ind.fitness.values = (0,)
                continue

            # 模擬工作者執行計算
            params = {"fast": fast, "slow": slow}
            result = calculate_sma_crossover(symbol="MOCK_SYMBOL", **params)
            result['params'] = json.dumps(params)

            # 模擬工作者儲存結果
            save_result(result)

        # 2. 模擬「等待」與「分配適應度」
        #    因為計算已同步完成，這裡直接從資料庫讀取結果即可。
        from deap import tools
        import duckdb

        conn = duckdb.connect("prometheus_fire.duckdb", read_only=True)
        results_df = conn.execute("SELECT params, crossover_points FROM backtest_results").fetchdf()
        conn.close()

        fitness_map = {row['params']: (row['crossover_points'],) for _, row in results_df.iterrows()}

        for ind in individuals_to_eval:
            params_str = json.dumps({"fast": ind[0], "slow": ind[1]})
            fitness = fitness_map.get(params_str, (0,))
            ind.fitness.values = fitness

        log_manager.log("SUCCESS", "[MOCK] 模擬評估完成。")

    # === 將演化室的真實評估函數替換為我們的模擬版本 ===
    chamber._evaluate_and_assign_fitness = synchronous_evaluation_mock

    log_manager.log("INFO", "開始執行完全邏輯內循環演化測試...")

    # 執行演化，現在它將在一個完全同步、可預測的環境中運行
    best_individual = chamber.run_evolution_cycle(
        population_size=POPULATION_SIZE,
        generations=GENERATIONS
    )

    # 驗證最終結果
    log_manager.log("SUCCESS", f"內循環測試完成。最佳個體: {best_individual}, 適應度: {best_individual.fitness.values[0]}")

    assert best_individual is not None, "演化未能產生任何最佳個體！"
    assert best_individual.fitness.valid, "最終選出的最佳個體沒有有效的適應度分數！"

    # 驗證資料庫中確實產生了結果
    import duckdb
    conn = duckdb.connect("prometheus_fire.duckdb", read_only=True)
    count_result = conn.execute("SELECT COUNT(*) FROM backtest_results").fetchone()
    conn.close()
    assert count_result[0] > 0, "資料庫中沒有任何回測結果！"
