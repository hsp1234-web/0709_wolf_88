# import pytest
# import asyncio
# import uuid
# from prometheus.core.context import AppContext

# @pytest.fixture(scope="function")
# async def app_context() -> AppContext:
#     """ 測試上下文工廠 v3.0 (非同步版) """
#     session_name = f"test_session_{uuid.uuid4().hex[:8]}"

#     # 使用非同步上下文管理器
#     async with AppContext(session_name=session_name, mode='test') as context:
#         yield context
#     # __aexit__ 會自動處理清理工作
