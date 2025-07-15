"""
結果投影者 (Results Projector) 應用程式。

此應用程式作為一個獨立的事件消費者運行。
它的唯一職責是：訂閱事件流，監聽 BacktestCompleted 事件，
並將這些事件的內容「投影」到一個為快速查詢而優化的「讀模型」中。
"""
import asyncio
import json
from src.core.context import AppContext

class ResultsProjector:
    """
    一個專職的事件消費者，負責建立「回測結果」這個讀模型。
    """
    def __init__(self, context: AppContext):
        self.context = context
        self.last_processed_id = 0
        self._running = True

    async def run(self):
        """啟動投影者，持續從事件流中讀取並處理事件。"""
        print("結果投影者已啟動，正在等待事件...")
        while self._running:
            events = await self.context.event_stream.subscribe(self.last_processed_id)
            if not events:
                await asyncio.sleep(1)
                continue

            for event_id, event_type, data_str in events:
                if event_type == "SystemShutdown":
                    print("投影者：收到關機信號，準備退出。")
                    self.stop()
                    break

                if event_type == "BacktestCompleted":
                    data = json.loads(data_str)
                    # 調用 ResultsSaver 將事件數據寫入讀模型
                    await self.context.results_saver.save_result(
                        genome_id=data['genome_id'],
                        generation=data['generation'],
                        sharpe_ratio=data['sharpe_ratio'],
                        genome=data['genome']
                    )
                    print(f"投影者：已儲存 {data['genome_id']} 的結果。")

                # 更新已處理的事件 ID，確保不重複處理
                self.last_processed_id = event_id

            if not self._running:
                break

    def stop(self):
        """停止投影者的運行循環。"""
        self._running = False

async def main(context: AppContext):
    """應用程式主入口點。"""
    projector = ResultsProjector(context)
    try:
        await projector.run()
    except asyncio.CancelledError:
        projector.stop()
        print("結果投影者任務被取消並已妥善處理。")
