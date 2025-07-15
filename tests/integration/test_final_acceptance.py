import pytest
from src.apps.run_evolution import main as run_evolution_main
from src.core.context import AppContext
import asyncio
import tempfile
import os

@pytest.mark.asyncio
async def test_main_orchestrator():
    """
    驗收測試：直接運行主控台應用，並驗證最終結果。
    這模擬了使用者從命令列啟動應用的真實場景。
    """
    with tempfile.NamedTemporaryFile(suffix=".sqlite") as tmp:
        db_path = tmp.name

    try:
        # 由於主控台內部處理了 AppContext，我們在這裡只需要一個臨時的 context 來驗證結果
        await run_evolution_main(db_path)

        # --- 驗證 ---
        # 流程結束後，重新連接到資料庫以驗證結果
        async with AppContext(db_path=db_path) as context:
            # 1. 驗證事件流的完整性
            cursor = await context.conn.execute("SELECT event_type, COUNT(*) FROM events GROUP BY event_type")
            event_counts = dict(await cursor.fetchall())

            assert event_counts.get("GenomeGenerated") == 10
            assert event_counts.get("BacktestCompleted") == 10
            assert event_counts.get("SystemShutdown") == 1

            # 2. 驗證「讀模型」是否被投影者正確建立
            results_count = await context.results_saver.count_results()
            assert results_count == 10
            print(f"\n驗收成功：主控台成功執行，並產生了 {results_count} 筆結果。")
    finally:
        # 清理臨時數據庫文件
        if os.path.exists(db_path):
            os.remove(db_path)
