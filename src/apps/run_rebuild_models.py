"""
【時光計畫】讀模型重建工具。

此工具用於從事件流中，從零開始重建所有查詢用的讀模型。
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import typer
import asyncio
from src.core.context import AppContext
from src.apps import results_projector_app

app = typer.Typer()

@app.command()
def rebuild(force: bool = typer.Option(False, "--force", help="強制執行，將會清空現有讀模型！")):
    """從事件流中重建所有讀模型。"""
    if not force:
        print("錯誤：此操作會清空現有讀模型。請使用 --force 旗標確認。")
        raise typer.Exit(code=1)
    asyncio.run(main())

async def main():
    async with AppContext() as context:
        print("正在清空現有讀模型...")
        await context.results_saver.clear_all()
        # 重設投影者的檢查點，讓它從頭開始
        await context.event_stream.update_checkpoint("results_projector", 0)
        await context.event_stream.update_checkpoint("backtest_worker", 0)

        print("正在啟動投影者以重建讀模型...")
        # 我們可以設計一個特殊的 main 函數或模式，讓投影者在處理完所有歷史事件後自動退出
        await results_projector_app.main(context, run_once=True)
        print("讀模型重建完成。")

if __name__ == "__main__":
    app()
