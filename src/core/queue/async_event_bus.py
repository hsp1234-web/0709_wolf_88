# 檔案: src/core/queue/async_event_bus.py
import asyncio
from typing import Dict, Any, Optional

class AsyncEventBus:
    """
    非同步事件總線 v1.0
    基於 asyncio.Queue，為系統提供高效、非阻塞的內部通訊。
    """
    def __init__(self, name: str = "default"):
        self.task_queue = asyncio.Queue()
        self.result_queue = asyncio.Queue()
        print(f"✔ 非同步事件總線 '{name}' 已初始化。")

    async def put(self, task: Dict[str, Any]):
        await self.task_queue.put(task)

    async def get(self) -> Optional[Dict[str, Any]]:
        return await self.task_queue.get()

    async def put_result(self, result: Dict[str, Any]):
        await self.result_queue.put(result)

    async def get_result(self) -> Optional[Dict[str, Any]]:
        return await self.result_queue.get()

    def task_done(self):
        self.task_queue.task_done()

    async def join(self):
        await self.task_queue.join()
