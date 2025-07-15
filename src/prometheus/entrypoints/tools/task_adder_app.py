import random
import uuid

from prometheus.core.context import AppContext


def add_tasks(ctx: AppContext, num_tasks: int = 10):
    """
    向任務佇列中添加指定數量的隨機回測任務。
    """
    ctx.log_manager.log("INFO", f"正在生成 {num_tasks} 個回測任務...")
    batch_id = str(uuid.uuid4())
    for i in range(num_tasks):
        # 任務現在是一個字典
        task = {
            "task_id": str(uuid.uuid4()),
            "type": "backtest",
            "strategy": "SMA_Crossover",
            "symbol": random.choice(["BTC/USDT", "ETH/USDT", "XRP/USDT"]),
            "params": {"fast": random.randint(5, 15), "slow": random.randint(20, 40)},
            "batch_id": batch_id,
        }
        ctx.queue.put(task)
        ctx.log_manager.log(
            "DEBUG", f"已將任務 {i+1}/{num_tasks} ({task['strategy']}) 添加到佇列。"
        )
    ctx.log_manager.log("SUCCESS", f"成功將 {num_tasks} 個任務添加到佇列。")
