import pytest
import asyncio
from src.core.context import AppContext
from src.apps import evolution_app, backtest_worker_app

# 模擬的 evolution_app，因為它現在變得很簡單
class MockEvolutionApp:
    def __init__(self, context):
        from src.core.services.evolution_chamber import EvolutionChamber
        self.evolver = EvolutionChamber(context)

    async def main(self):
        # 在測試中，我們只演化一小部分
        await self.evolver.evolve(generations=1, population_size=10)

@pytest.mark.asyncio
async def test_event_sourcing_flow():
    """
    驗證基於事件溯源的完整流程：
    1. EvolutionChamber 發布 GenomeGenerated 事件。
    2. BacktestWorker 監聽事件，執行回測，並發布 BacktestCompleted 事件。
    3. 驗證所有事件都已正確記錄在資料庫中。
    4. (可選) 驗證讀取模型（如 results table）是否被正確更新。
    """
    db_path = ":memory:"  # 在記憶體中執行測試以提高速度和隔離性
    async with AppContext(db_path=db_path) as context:

        # 創建並短暫運行 worker 任務
        # backtest_worker_app.main 現在是一個無限循環，所以我們在背景運行它
        worker_task = asyncio.create_task(backtest_worker_app.main(context))

        # 運行演化器以產生事件
        # 由於 evolution_app 的邏輯被簡化，我們直接調用一個模擬版本
        mock_evo_app = MockEvolutionApp(context)
        await mock_evo_app.main()

        # 給 worker 一點時間來處理所有已生成的事件
        # 在真實的系統中，這裡需要一個更優雅的同步機制
        # 例如，檢查 BacktestCompleted 事件的數量是否與 GenomeGenerated 相符
        await asyncio.sleep(2)

        # 優雅地取消 worker 任務
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass  # 任務被取消是正常的

        # --- 驗證階段 ---
        # 1. 驗證事件流本身
        cursor = await context.conn.execute("SELECT event_type, COUNT(*) FROM events GROUP BY event_type")
        counts = dict(await cursor.fetchall())

        # 根據 MockEvolutionApp 的設置，我們預期 10 個基因體
        assert counts.get("GenomeGenerated") == 10, "應產生 10 個 GenomeGenerated 事件"
        assert counts.get("BacktestCompleted") == 10, "應有 10 個 BacktestCompleted 事件作為回應"

        # 2. 驗證最終的讀模型（如果有的話，這裡我們沒有單獨的結果表，但可以檢查）
        # 在這個設計中，BacktestCompleted 事件本身就是結果，
        # 但如果有一個單獨的 results 表，我們會在這裡驗證它。
        # 例如:
        # count = await context.results_saver.count_results()
        # assert count == 10
        print("\n測試成功：事件流和處理流程符合預期。")
