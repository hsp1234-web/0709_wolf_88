import json
import random
import uuid
from pathlib import Path

from deap import creator, tools

from prometheus.core.queue.sqlite_queue import SQLiteQueue
from prometheus.services.checkpoint_manager import CheckpointManager
from prometheus.services.evolution_chamber import EvolutionChamber
from prometheus.core.logging.log_manager import LogManager

# --- 演化設定 ---
POPULATION_SIZE = 10
MAX_GENERATIONS = 5
CHECKPOINT_FREQ = 2

# --- 檔案路徑 ---
HALL_OF_FAME_PATH = Path("data/hall_of_fame.json")
CHECKPOINT_PATH = Path("data/checkpoints/evolution_state.pkl")

# 初始化日誌記錄器
logger = LogManager.get_instance().get_logger("Evolution-Engine")


def evolution_loop(
    task_queue: SQLiteQueue,
    results_queue: SQLiteQueue,
    resume: bool = False,
    clean: bool = False,
):
    """
    智慧演化引擎 v4：整合了結構化日誌與萬象引擎。
    """
    logger.info("策略演化引擎已啟動...")
    chamber = EvolutionChamber()
    checkpoint_manager = CheckpointManager(CHECKPOINT_PATH)

    start_gen = 0
    population = None
    hall_of_fame = tools.HallOfFame(1)

    if clean:
        logger.info("--clean 模式：將進行一次全新的演化。")
        checkpoint_manager.clear_checkpoint()

    if resume:
        state = checkpoint_manager.load_checkpoint()
        if state:
            population = state["population"]
            start_gen = state["generation"] + 1
            hall_of_fame = state["hall_of_fame"]
            random.setstate(state["random_state"])
            logger.info(f"從第 {start_gen} 代恢復演化。")

    if population is None:
        logger.info("正在創建初始族群...")
        population = chamber.create_population(n=POPULATION_SIZE)

    # --- 演化主迴圈 ---
    for gen in range(start_gen, MAX_GENERATIONS):
        logger.info(f"正在處理第 {gen} 代...")

        pending_tasks = {}
        for i, individual in enumerate(population):
            task_id = str(uuid.uuid4())
            genome_task = {"id": task_id, "params": individual}
            task_queue.put((task_id, genome_task))
            pending_tasks[task_id] = individual
            logger.debug(f"已發送任務: {genome_task}")

        logger.info("等待所有回測結果...")
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
                    individual = pending_tasks.pop(genome_id)
                    report = result_payload.get("report", {})
                    fitness = report.get("sharpe_ratio", -1.0) if report.get("is_valid") else -1.0
                    individual.fitness.values = (fitness,)
                    evaluated_count += 1
                    logger.debug(f"收到結果: {genome_id}, 適應度: {fitness:.2f} ({evaluated_count}/{len(population)})")
            else:
                logger.warning("等待結果超時，可能部分任務已丟失。")
                for task_id in pending_tasks:
                    pending_tasks[task_id].fitness.values = (-1.0,)
                    evaluated_count += 1
                break

        hall_of_fame.update(population)

        if len(hall_of_fame) > 0:
            best_ind = hall_of_fame[0]
            logger.info(f"第 {gen} 代最佳策略: 夏普比率 = {best_ind.fitness.values[0]:.2f}, 基因 = {best_ind}")

        if (gen + 1) % CHECKPOINT_FREQ == 0:
            current_state = {
                "population": population, "generation": gen,
                "hall_of_fame": hall_of_fame, "random_state": random.getstate(),
            }
            checkpoint_manager.save_checkpoint(current_state)

        if gen < MAX_GENERATIONS - 1:
            logger.info("正在產生下一代族群...")
            offspring = chamber.select_offspring(population)
            new_population = chamber.apply_mating_and_mutation(offspring)
            if len(hall_of_fame) > 0:
                new_population[0] = hall_of_fame[0]
            population = new_population

    logger.info("演化完成")
    if len(hall_of_fame) > 0:
        best_overall = hall_of_fame[0]
        logger.info(f"歷史最佳策略 (名人堂): 夏普比率 = {best_overall.fitness.values[0]:.2f}, 基因 = {best_overall}")

        try:
            HALL_OF_FAME_PATH.parent.mkdir(exist_ok=True, parents=True)
            with open(HALL_OF_FAME_PATH, "w") as f:
                fitness_data = {"sharpe_ratio": best_overall.fitness.values[0]}
                # 將 deap 個體轉換為可序列化的列表
                genome_list = list(best_overall)
                json.dump([{"params": genome_list, "fitness": fitness_data}], f, indent=4)
            logger.info(f"名人堂已儲存至: {HALL_OF_FAME_PATH}")
        except Exception as e:
            logger.error(f"儲存名人堂失敗: {e}", exc_info=True)

    logger.info("演化引擎已停止。")
