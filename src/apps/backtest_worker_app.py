from src.core.context import AppContext
from src.core.services.backtesting_service import BacktestingService

def run_worker(ctx: AppContext):
    service = BacktestingService(queue=ctx.queue, log_manager=ctx.log_manager)
    service.run()
