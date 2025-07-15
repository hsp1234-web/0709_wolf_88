import time
import uuid
import asyncio
from src.core.queue.sqlite_queue import SQLiteQueue
from src.core.services.evolution_chamber import EvolutionChamber
from deap import tools

# --- 沙箱模式設定 ---
POPULATION_SIZE = 10
MAX_GENERATIONS = 3

def evolution_loop(task_queue: SQLiteQueue, results_queue: SQLiteQueue):
    """
    智慧演化引擎的主迴圈。
    """
    print("[Evolution-Engine] 策略演化引擎已啟動...")
    chamber = EvolutionChamber()

    # 1. 產生初始族群 (第 0 代)
    population = chamber.create_population(n=POPULATION_SIZE)
    hall_of_fame = None # 用於記錄整個演化過程中的最佳個體

    # --- 演化主迴圈 ---
    for gen in range(MAX_GENERATIONS):
        print(f"\n{'='*10} 正在處理第 {gen} 代 {'='*10}")

        # 2. 評估階段：將族群中的每個個體轉換為回測任務
        pending_tasks = {}
        for i, individual in enumerate(population):
            task_id = str(uuid.uuid4())
            fast_window, slow_window = individual

            genome_task = {
                "id": task_id,
                "params": {"fast": fast_window, "slow": slow_window}
            }
            task_queue.put((task_id, genome_task))
            pending_tasks[task_id] = individual
            print(f"[Evolution-Engine] 已發送任務: {genome_task}")

        # 3. 回收結果並更新適應度
        print("[Evolution-Engine] 等待所有回測結果...")
        evaluated_count = 0
        while evaluated_count < len(pending_tasks):
            result = results_queue.get(block=True, timeout=10) # 增加超時
            if result:
                # 確保我們處理的是元組 (item_id, payload)
                if isinstance(result, tuple) and len(result) == 2:
                    _, result_payload = result
                else:
                    # 假設如果不是元組，就是 payload 本身
                    result_payload = result

                if not result_payload: continue

                genome_id = result_payload.get("genome_id")

                if genome_id in pending_tasks:
                    individual = pending_tasks[genome_id]
                    report = result_payload.get("report", {})
                    fitness = report.get("sharpe_ratio", -1.0) # 使用夏普比率作為適應度

                    # 處理無效的適應度值
                    if fitness is None or fitness == float('inf') or fitness == float('-inf'):
                        fitness = -1.0

                    # 為個體賦予適應度分數
                    individual.fitness.values = (fitness,)

                    evaluated_count += 1
                    print(f"[Evolution-Engine] 收到結果: {genome_id}, 適應度: {fitness:.2f} ({evaluated_count}/{len(pending_tasks)})")
            else:
                # 如果超時後仍未收到結果，可能是有工作者已死亡
                print("[Evolution-Engine] 警告：等待結果超時，可能部分任務已丟失。")
                evaluated_count += 1 # 避免無限等待

        # 4. 記錄本代最佳個體
        best_ind = tools.selBest(population, 1)[0]
        print(f"--- 第 {gen} 代最佳策略 ---")
        print(f"  參數: fast={best_ind[0]}, slow={best_ind[1]}")
        print(f"  夏普比率: {best_ind.fitness.values[0]:.2f}")

        # 更新名人堂
        if hall_of_fame is None or best_ind.fitness.values[0] > hall_of_fame.fitness.values[0]:
            hall_of_fame = best_ind

        # 5. 產生下一代
        print("[Evolution-Engine] 正在產生下一代族群...")
        offspring = chamber.select_offspring(population)
        new_population = chamber.mate_and_mutate(offspring)

        # Elitism: 將名人堂成員替換掉新族群中的一個隨機成員
        if hall_of_fame:
            new_population[0] = hall_of_fame

        population = new_population

    # --- 演化結束 ---
    print(f"\n{'='*10} 演化完成 {'='*10}")
    print("--- 歷史最佳策略 ---")
    if hall_of_fame:
        print(f"  參數: fast={hall_of_fame[0]}, slow={hall_of_fame[1]}")
        print(f"  夏普比率: {hall_of_fame.fitness.values[0]:.2f}")
    print("[Evolution-Engine] 演化引擎已停止。")

    # 讓主執行緒知道可以關閉了 (透過讓迴圈結束)
