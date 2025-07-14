import pytest
import uuid
from src.core.context import AppContext

@pytest.fixture(scope="function")
def app_context() -> AppContext:
    """ 測試上下文工廠 v2.1 (統一關閉協議版) """
    session_name = f"test_session_{uuid.uuid4().hex[:8]}"
    context = AppContext(session_name=session_name, mode='test')

    context.queue.clear()
    context.results_saver.clear_results()

    try:
        yield context
    finally:
        # === 核心修正：確保 context.close() 被可靠地調用 ===
        print(f"\n測試會話 {session_name} 正在清理...")
        context.close()
