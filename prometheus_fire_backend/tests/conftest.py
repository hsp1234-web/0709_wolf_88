import pytest
import asyncio
from httpx import AsyncClient
from typing import AsyncGenerator
import sys
import os

# 將專案根目錄添加到 sys.path 以確保模組可以被正確找到
# __file__ 是 conftest.py 的路徑: /app/prometheus_fire_backend/tests/conftest.py
# project_root 應該是 /app
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"Added to sys.path: {project_root}") # 打印以便調試

# 現在可以安全地匯入 FastAPI 應用實例
from prometheus_fire_backend.console_api.main import app as fastapi_app
import pytest_asyncio # 匯入 pytest_asyncio

@pytest.fixture(scope="session")
def event_loop():
    """為 pytest-asyncio 提供事件循環 (session scope)。"""
    # Python 3.8+ 預設在 Windows 上使用 ProactorEventLoop，可能與 httpx 不太兼容。
    # 如果遇到問題，可以考慮強制使用 SelectorEventLoop。
    # policy = asyncio.get_event_loop_policy()
    # loop = policy.new_event_loop()
    # yield loop
    # loop.close()
    # 對於大多數情況，下面的標準實現即可：
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

from asgi_lifespan import LifespanManager # <--- 匯入 LifespanManager

@pytest_asyncio.fixture(scope="session")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """
    提供一個異步的 HTTP 客戶端，用於測試 FastAPI 應用。
    使用 LifespanManager 確保 FastAPI 的 lifespan 事件被正確觸發。
    """
    from httpx import ASGITransport

    # LifespanManager 會處理應用的 startup 和 shutdown 事件
    async with LifespanManager(fastapi_app):
        # print("LifespanManager: FastAPI app startup completed.")
        async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://127.0.0.1:8000") as client:
            # print("AsyncClient for FastAPI app initialized with ASGITransport.")
            yield client
            # print("AsyncClient for FastAPI app cleaned up.")
    # print("LifespanManager: FastAPI app shutdown completed.")

# 如果需要，可以在這裡添加其他 session 或 module scope 的 fixtures，
# 例如用於清理 data_lake 的 fixture。
# 注意：pytest-asyncio 會自動處理異步測試函數的事件循環。
# `event_loop` fixture 的目的是確保有一個與 pytest 兼容的事件循環策略，
# 特別是當測試運行在不同的作業系統或 Python 版本時。
# 對於簡單的異步測試，`@pytest.mark.asyncio` 通常就足夠了。
# `async_client` fixture 的目的是提供一個配置好的 `httpx.AsyncClient` 實例。
# `scope="session"` 表示這個 client 會在整個測試 session 中共享，
# 這意味著 FastAPI 應用只會 "啟動" 一次。
# 這對於整合測試是高效的，因為不需要為每個測試都啟動和關閉應用。
# 如果每個測試都需要一個乾淨的應用狀態（不常見於這種 E2E 測試），
# 可以將 scope 改為 "function"。
