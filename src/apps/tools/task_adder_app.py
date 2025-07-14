import json
from src.core.context import AppContext

def add_tasks(ctx: AppContext):
    """向佇列中添加一組預定義的測試任務"""
    tasks = [
        {"type": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9}},
        {"type": "SMA_Crossover", "params": {"fast": 20, "slow": 50}},
        {"type": "RSI", "params": {"period": 14, "buy_level": 30, "sell_level": 70}},
    ]

    ctx.log_manager.log("INFO", f"正在向佇列添加 {len(tasks)} 個任務...")
    for task in tasks:
        ctx.queue.put(task)
    ctx.log_manager.log("SUCCESS", "所有任務已成功添加。")
