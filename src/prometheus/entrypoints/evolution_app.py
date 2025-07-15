import json
import random
import uuid
from pathlib import Path

from deap import creator, tools

from prometheus.core.queue.sqlite_queue import SQLiteQueue
from prometheus.services.checkpoint_manager import CheckpointManager
from prometheus.services.evolution_chamber import EvolutionChamber

# --- 演化設定 ---
POPULATION_SIZE = 10
MAX_GENERATIONS = 5  # 增加代數以便觀察檢查點
CHECKPOINT_FREQ = 2  # 每 2 代儲存一次檢查點

# --- 檔案路徑 ---
HALL_OF_FAME_PATH = Path("data/hall_of_fame.json")
CHECKPOINT_PATH = Path("data/checkpoints/evolution_state.pkl")


def evolution_loop(
    task_queue: SQLiteQueue,
    results_queue: SQLiteQueue,
    resume: bool = False,
    clean: bool = False,
):
    """
    智慧演化引擎 v3：具備斷點續行與智慧播種能力。
    """
    print("[Evolution-Engine] 策略演化引擎 v3 已啟動...")
    chamber = EvolutionChamber()
    checkpoint_manager = CheckpointManager(CHECKPOINT_PATH)

    start_gen = 0
    population = None
    hall_of_fame = tools.HallOfFame(1)

    if clean:
        print("[Evolution-Engine] --clean 模式：將進行一次全新的演化。")
        checkpoint_manager.clear_checkpoint()

    # 1. 【斷點續行】嘗試從檢查點恢復
    if resume:
        state = checkpoint_manager.load_checkpoint()
        if state:
            population = state["population"]
            start_gen = state["generation"] + 1
            hall_of_fame = state["hall_of_fame"]
            random.setstate(state["random_state"])
            print(f"[Evolution-Engine] 從第 {start_gen} 代恢復演化。")

    # 2. 【智慧播種】如果不是恢復，則創建初始族群
    if population is None:
        print("[Evolution-Engine] 正在創建初始族群...")
        population = chamber.create_population(n=POPULATION_SIZE)

        # 嘗試從名人堂讀取最佳基因進行播種
        if HALL_OF_FAME_PATH.exists():
            try:
                with open(HALL_OF_FAME_PATH, "r") as f:
                    best_known_strategy = json.load(f)
                params = best_known_strategy["params"]
                # 注意：這裡的基因體結構必須與 EvolutionChamber 中的定義完全匹配
                elite_seed = creator.Individual(
                    [params.get("fast"), params.get("slow")]
                )
                # 將 20% 的族群替換為精英種子 (或其變異體)
                num_elites = int(POPULATION_SIZE * 0.2)
                for i in range(num_elites):
                    population[i] = chamber.toolbox.clone(elite_seed)
                print(
                    f"[Evolution-Engine] 智慧播種成功：已從名人堂注入 {num_elites} 個精英種子。"
                )
            except Exception as e:
                print(f"!!!!!! [Evolution-Engine] 讀取名人堂進行播種失敗: {e} !!!!!!")

    # --- 演化主迴圈 ---
    for gen in range(start_gen, MAX_GENERATIONS):
        print(f"\n{'='*10} 正在處理第 {gen} 代 {'='*10}")

        # 評估階段：將族群中的每個個體轉換為回測任務
        pending_tasks = {}
        for i, individual in enumerate(population):
            task_id = str(uuid.uuid4())
            fast_window, slow_window = individual

            genome_task = {
                "id": task_id,
                "params": {"fast": fast_window, "slow": slow_window},
            }
            task_queue.put((task_id, genome_task))
            pending_tasks[task_id] = individual
            print(f"[Evolution-Engine] 已發送任務: {genome_task}")

        # 回收結果並更新適應度
        print("[Evolution-Engine] 等待所有回測結果...")
        evaluated_count = 0
        while evaluated_count < len(pending_tasks):
            result = results_queue.get(block=True, timeout=20)
            if result:
                if isinstance(result, tuple) and len(result) == 2:
                    _, result_payload = result
                else:
                    result_payload = result

                if not result_payload:
                    continue

                genome_id = result_payload.get("genome_id")
                if genome_id in pending_tasks:
                    individual = pending_tasks.pop(genome_id)  # 從待辦中移除
                    report = result_payload.get("report", {})
                    fitness = report.get("sharpe_ratio", -1.0)

                    if (
                        fitness is None
                        or fitness == float("inf")
                        or fitness == float("-inf")
                        or not isinstance(fitness, (int, float))
                    ):
                        fitness = -1.0

                    individual.fitness.values = (fitness,)
                    evaluated_count += 1
                    print(
                        f"[Evolution-Engine] 收到結果: {genome_id}, 適應度: {fitness:.2f} ({evaluated_count}/{POPULATION_SIZE})"
                    )
            else:
                print("[Evolution-Engine] 警告：等待結果超時，可能部分任務已丟失。")
                # 將剩餘未完成的任務標記為失敗
                for task_id in pending_tasks:
                    pending_tasks[task_id].fitness.values = (-1.0,)
                    evaluated_count += 1
                break  # 跳出等待迴圈

        # 更新名人堂
        hall_of_fame.update(population)

        # 記錄本代最佳個體
        if len(hall_of_fame) > 0:
            best_ind = hall_of_fame[0]
            print(f"--- 第 {gen} 代最佳策略 ---")
            print(f"  參數: fast={best_ind[0]}, slow={best_ind[1]}")
            print(f"  夏普比率: {best_ind.fitness.values[0]:.2f}")

        # 3. 【定期儲存】在每一代結束後，儲存檢查點
        if (gen + 1) % CHECKPOINT_FREQ == 0:
            current_state = {
                "population": population,
                "generation": gen,
                "hall_of_fame": hall_of_fame,
                "random_state": random.getstate(),
            }
            checkpoint_manager.save_checkpoint(current_state)

        # 產生下一代
        if gen < MAX_GENERATIONS - 1:
            print("[Evolution-Engine] 正在產生下一代族群...")
            offspring = chamber.select_offspring(population)
            new_population = chamber.mate_and_mutate(offspring)
            # Elitism: 確保名人堂成員進入下一代
            if len(hall_of_fame) > 0:
                new_population[0] = hall_of_fame[0]
            population = new_population

    # --- 演化結束 ---
    print(f"\n{'='*10} 演化完成 {'='*10}")
    if len(hall_of_fame) > 0:
        best_overall = hall_of_fame[0]
        print("--- 歷史最佳策略 (名人堂) ---")
        print(f"  參數: fast={best_overall[0]}, slow={best_overall[1]}")
        print(f"  夏普比率: {best_overall.fitness.values[0]:.2f}")

        # 儲存名人堂到檔案
        try:
            HALL_OF_FAME_PATH.parent.mkdir(exist_ok=True, parents=True)
            with open(HALL_OF_FAME_PATH, "w") as f:
                # 【核心改變】將適應度儲存為字典格式，以符合驗證 App 的預期
                fitness_data = {"sharpe_ratio": best_overall.fitness.values[0]}
                json.dump(
                    {
                        "params": {"fast": best_overall[0], "slow": best_overall[1]},
                        "fitness": fitness_data,
                    },
                    f,
                    indent=4,
                )
            print(f"[Evolution-Engine] 名人堂已儲存至: {HALL_OF_FAME_PATH}")
        except Exception as e:
            print(f"!!!!!! [Evolution-Engine] 儲存名人堂失敗: {e} !!!!!!")

    print("[Evolution-Engine] 演化引擎已停止。")
