# -*- coding: utf-8 -*-
"""
本模組定義了策略回測所需的核心數據契約。
"""
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class Strategy:
    """
    定義一個抽象的交易策略。

    Attributes:
        factors (List[str]): 此策略所使用的因子名稱列表。
        weights (Dict[str, float]): 各個因子的權重。
        target_asset (str): 交易的目標資產代碼，例如 'SPY'。
    """
    factors: List[str]
    weights: Dict[str, float]
    target_asset: str = 'SPY'

@dataclass
class PerformanceReport:
    """
    定義回測後的績效報告。

    Attributes:
        sharpe_ratio (float): 夏普比率。
        annualized_return (float): 年化報酬率。
        max_drawdown (float): 最大回撤。
        total_trades (int): 總交易次數。
    """
    sharpe_ratio: float = 0.0
    annualized_return: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0
