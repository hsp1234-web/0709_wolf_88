import typer
from prometheus.entrypoints.ai_analyst_app import ai_analyst_job
from prometheus.entrypoints.query_gateway import run_dashboard_service
from prometheus.core.logging.log_manager import LogManager

app = typer.Typer()
logger = LogManager.get_instance().get_logger("Conductor")

@app.command(name="analyze")
def cli_analyze():
    """
    啟動 AI 分析師報告生成器。
    """
    logger.info("正在啟動 AI 分析師...")
    ai_analyst_job()
    logger.info("AI 分析師工作完成。")


@app.command(name="dashboard")
def cli_dashboard(
    host: str = typer.Option("127.0.0.1", help="綁定主機"),
    port: int = typer.Option(8000, help="綁定埠號"),
):
    """啟動網頁儀表板。"""
    logger.info(f"準備在 http://{host}:{port} 啟動儀表板...")
    run_dashboard_service(None, host, port)

if __name__ == "__main__":
    app()
