import pytest
from src.core.context import AppContext
from src.apps import evolution_app, backtest_worker_app, results_projector_app
import asyncio

@pytest.mark.asyncio
async def test_full_cqrs_event_sourcing_flow():
    """
    驗證一個完整的、包含三個並發服務的事件溯源流程。
    1. 演化室 (生產者) -> 產生 GenomeGenerated 事件
    2. 回測工作者 (處理者) -> 消費 GenomeGenerated，產生 BacktestCompleted 事件
    3. 結果投影者 (消費者) -> 消費 BacktestCompleted，將結果寫入讀模型
    """
    db_path = ":memory:"  # 在記憶體資料庫中執行測試以提高速度
    async with AppContext(db_path=db_path) as context:
        # --- 啟動三個核心服務作為背景任務 ---
        worker_task = asyncio.create_task(backtest_worker_app.main(context))
        projector_task = asyncio.create_task(results_projector_app.main(context))

        # --- 運行主流程 (演化器)，觸發整個事件鏈 ---
        await evolution_app.main(context)

        # --- 給予消費者足夠的時間來處理所有事件 ---
        # 在真實應用中，我們會使用更優雅的關閉信號機制。
        # 在測試中，短暫等待足以驗證流程。
        await asyncio.sleep(2)

        # --- 優雅地關閉背景任務 ---
        worker_task.cancel()
        projector_task.cancel()
        try:
            await worker_task
            await projector_task
        except asyncio.CancelledError:
            pass  # 任務被取消是預期行為

        # --- 最終驗證 ---
        # 1. 驗證事件流的完整性
        cursor = await context.conn.execute("SELECT event_type, COUNT(*) FROM events GROUP BY event_type")
        event_counts = dict(await cursor.fetchall())

        # 假設演化了 10 個基因體
        assert event_counts.get("GenomeGenerated") == 10
        assert event_counts.get("BacktestCompleted") == 10

        # 2. 驗證「讀模型」是否被投影者正確建立
        results_count = await context.results_saver.count_results()
        assert results_count == 10
        print(f"\n驗證成功：事件流中產生了 {event_counts.get('BacktestCompleted')} 個完成事件，"
              f"投影者成功將 {results_count} 筆結果寫入讀模型。")
