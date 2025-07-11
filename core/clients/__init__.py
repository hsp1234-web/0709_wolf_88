# core/clients/__init__.py

from .base import BaseAPIClient
from .fmp import FMPClient
from .finmind import FinMindClient  # <-- 更新為 FinMindClient
from .fred import FredClient # <-- 已修正為 FredClient
from .nyfed import NYFedClient
from .yfinance import YFinanceClient

__all__ = [
    "BaseAPIClient",
    "FMPClient",
    "FinMindClient",  # <-- 更新為 FinMindClient
    "FredClient", # <-- 已修正為 FredClient
    "NYFedClient",
    "YFinanceClient",
]
