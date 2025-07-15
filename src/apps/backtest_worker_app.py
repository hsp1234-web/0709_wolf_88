import asyncio
import json
from src.core.context import AppContext
from src.core.events.event_types import BacktestCompleted
from src.core.services.backtesting_service import BacktestingService

class BacktestWorker:
    def __init__(self, context: AppContext):
        self.context = context
        self.backtester = BacktestingService(context)
        self.last_processed_id = 0
        self._running = True

    async def run(self):
        """主運行循環，持續從事件流中讀取並處理事件。"""
        print("回測工作者已啟動，正在監聽 'GenomeGenerated' 事件...")
        while self._running:
            events = await self.context.event_stream.subscribe(self.last_processed_id)
            if not events:
                await asyncio.sleep(1)  # 如果沒有新事件，稍作等待
                continue

            print(f"偵測到 {len(events)} 個新事件。")
            for event_id, event_type, data_str in events:
                if event_type == "GenomeGenerated":
                    try:
                        data = json.loads(data_str)
                        # 執行回測...
                        sharpe_ratio = await self.backtester.run_backtest(data['genome'])

                        # 產生一個完成事件
                        completed_event = BacktestCompleted(
                            genome_id=data['genome_id'],
                            sharpe_ratio=sharpe_ratio,
                            generation=data['generation'],
                            genome=data['genome']
                        )
                        # 將完成事件寫回流中
                        await self.context.event_stream.append(completed_event)
                        print(f"已處理 genome_id: {data['genome_id']}，夏普比率: {sharpe_ratio:.2f}")

                    except json.JSONDecodeError:
                        print(f"錯誤：無法解析事件 ID {event_id} 的資料。")
                    except Exception as e:
                        print(f"處理事件 ID {event_id} 時發生未知錯誤: {e}")

                # 無論事件類型如何，都更新已處理的 ID
                self.last_processed_id = event_id
        print("回測工作者已停止。")

    def stop(self):
        """停止工作循環。"""
        self._running = False
        print("正在停止回測工作者...")

async def main(context: AppContext):
    """應用程式主入口點"""
    worker = BacktestWorker(context)
    try:
        await worker.run()
    except asyncio.CancelledError:
        worker.stop()
        print("工作者任務被取消並已妥善處理。")
