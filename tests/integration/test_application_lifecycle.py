import pytest
import asyncio
from unittest.mock import patch
from src.apps.run_evolution import main as run_evolution_main

@pytest.mark.timeout(90) # 為這個特別的測試設定更長的逾時時間，例如 90 秒
async def test_full_application_lifecycle_does_not_hang():
    """
    驗證完整的應用程式生命週期可以正常結束，不會發生死鎖或無限迴圈。
    我們故意不傳入 --monitor 旗標，以簡化首次診斷的複雜性。
    """
    # 我們預期這個測試會因為逾時而失敗。
    # 失敗時 pytest-timeout 提供的堆疊追蹤，就是我們需要的關鍵情報。
    print("\n[Probe] 正在啟動應用程式生命週期測試...")

    shutdown_event = asyncio.Event()

    async def mock_backtest_worker(context):
        while not shutdown_event.is_set():
            await asyncio.sleep(0.1)

    with patch('src.apps.backtest_worker_app.main', new=mock_backtest_worker):
        try:
            await run_evolution_main(monitor=False)
        finally:
            shutdown_event.set()

    print("[Probe] 應用程式生命週期測試正常結束。")
