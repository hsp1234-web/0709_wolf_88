import json
from src.core.context import AppContext

import uuid

def add_tasks(ctx: AppContext):
    """向佇列中添加一組預定義的測試任務"""
    batch_id = str(uuid.uuid4())
    tasks = [
        {"strategy": "MACD", "symbol": "TEST_01", "params": {"fast": 12, "slow": 26, "signal": 9}, "batch_id": batch_id},
        {"strategy": "SMA_Crossover", "symbol": "TEST_02", "params": {"fast": 20, "slow": 50}, "batch_id": batch_id},
        {"strategy": "RSI", "symbol": "TEST_03", "params": {"period": 14, "buy_level": 30, "sell_level": 70}, "batch_id": batch_id},
    ]

    ctx.log_manager.log("INFO", f"正在向佇列添加 {len(tasks)} 個任務...")
    for task in tasks:
        ctx.queue.put(task)
    ctx.log_manager.log("SUCCESS", "所有任務已成功添加。")
