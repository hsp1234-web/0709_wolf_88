# 檔案: tests/integration/test_final_acceptance.py
import pytest
import asyncio
from src.core.context import AppContext
from src.apps import evolution_app, backtest_worker_app

@pytest.mark.asyncio
async def test_full_async_evolution_flow():
    """
    最終驗收測試 v4.0 (鳳凰版)
    驗證完整的非同步事件驅動流程。
    """
    # 使用異步上下文管理器來確保資源的正確初始化和關閉
    async with AppContext(session_name="phoenix_test", mode='test') as context:
        print("\n--- 最終驗收測試 (鳳凰版) 開始 ---")

        # 1. 創建並啟動背景工作者 (Worker) 任務
        worker_task = asyncio.create_task(backtest_worker_app.main(context))
        print("背景回測工作者任務已創建。")

        # 2. 在主線程中運行演化流程
        await evolution_app.main(context)
        print("演化流程已執行完畢。")

        # 3. 發送 "毒丸" 信號來終止 Worker
        await context.queue.put(None)

        # 等待 Worker 任務處理完 "毒丸" 並終止
        await asyncio.sleep(0.1) # 給予事件循環一點時間來處理
        await worker_task
        print("Worker 任務已確認終止。")

        # 4. 最終驗證
        results_count = await context.results_saver.count_results()
        print(f"在資料庫中找到 {results_count} 筆回測結果。")

        # 初始族群(10) + 後續世代... 預期應有結果
        assert results_count > 10, f"預期應有多於10個回測結果，但只找到 {results_count} 個。"

        print("--- 最終驗收測試 (鳳凰版) 圓滿成功 ---")
