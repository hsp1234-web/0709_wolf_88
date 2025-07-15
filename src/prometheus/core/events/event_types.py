"""
定義系統中所有領域事件的標準資料結構。
使用 dataclasses 確保事件的不可變性與結構清晰。
"""

import dataclasses
from typing import Any, Dict


@dataclasses.dataclass(frozen=True)
class BaseEvent:
    """事件基類"""

    pass


@dataclasses.dataclass(frozen=True)
class GenomeGenerated(BaseEvent):
    """當一個新的策略基因體被創造出來時觸發"""

    genome_id: str
    genome: Dict[str, Any]
    generation: int


@dataclasses.dataclass(frozen=True)
class BacktestCompleted(BaseEvent):
    """當一個基因體的回測完成時觸發"""

    genome_id: str
    sharpe_ratio: float
    generation: int
    genome: Dict[str, Any]


@dataclasses.dataclass(frozen=True)
class SystemShutdown(BaseEvent):
    """一個特殊的信號事件，通知所有消費者優雅地關閉。"""

    reason: str
