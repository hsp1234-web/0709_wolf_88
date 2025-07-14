from collections import deque
from typing import Any, Dict, Optional

from src.core.queue.base import BaseQueue

class InMemoryQueue(BaseQueue):
    """An in-memory queue for testing purposes."""

    def __init__(self, name: str):
        self.name = name
        self._queue = deque()
        self._results: Dict[str, Any] = {}

    def put(self, task: Dict[str, Any]):
        self._queue.append(task)

    def get(self, block: bool = True, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        if not self._queue:
            return None
        return self._queue.popleft()

    def put_result(self, result: Dict[str, Any]):
        backtest_id = result.get("backtest_id")
        if backtest_id:
            self._results[backtest_id] = result

    def get_result(self, backtest_id: str) -> Optional[Dict[str, Any]]:
        return self._results.get(backtest_id)

    def clear(self):
        self._queue.clear()
        self._results.clear()

    def qsize(self):
        return len(self._queue)

    def task_done(self):
        pass
