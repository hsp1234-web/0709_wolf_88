import pytest
from unittest.mock import MagicMock, patch
from src.core.context import AppContext
from src.core.services.evolution_chamber import EvolutionChamber

@pytest.mark.asyncio
async def test_evolution_logic_in_loop(app_context: AppContext):
    """
    驗證演化核心邏輯的「完全內循環」測試。
    此測試不依賴任何背景執行緒或真實的佇列等待。
    """
    log_manager = app_context.log_manager
    # 由於我們是內循環測試，我們需要一個 Mock Queue
    app_context.queue = MagicMock()

    # 這裡我們需要傳入 db_connection
    chamber = EvolutionChamber(
        queue=app_context.queue,
        log_manager=log_manager,
        db_connection=app_context.duckdb_connection
    )

    # 模擬 _evaluate_and_assign_fitness 方法，避免真實的回測
    with patch.object(chamber, '_evaluate_and_assign_fitness', autospec=True) as mock_evaluate:
        def side_effect(individuals):
            for ind in individuals:
                # 簡單地將 fitness 設為兩個基因的總和
                ind.fitness.values = (sum(ind),)
        mock_evaluate.side_effect = side_effect

        # 執行一個非常短的演化週期
        chamber.run_evolution_cycle(population_size=5, generations=1)

        # 驗證 evaluate 方法是否被呼叫
        assert mock_evaluate.call_count > 0, "評估方法從未被呼叫！"

        # 驗證是否有任務被放入佇列 (雖然是 Mock)
        # 在這個內循環測試中，我們不直接測試 queue.put
        # 相反，我們專注於演化邏輯本身
        # 如果需要測試 queue.put，需要更精細的 mock
        pass
