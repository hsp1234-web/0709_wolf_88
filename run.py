import typer
import pytest
import os

from src.core.logger import LogManager
from src.core.context import AppContext

# 導入應用函數
from src.apps.evolution_app import run_evolution
from src.apps.backtest_worker_app import run_worker
from src.apps.tools.task_adder_app import add_tasks
from src.apps.tools.show_results import show_results
from src.apps.tools.clear_results import clear_results
from src.apps.tools.report_generator_app import AIReportGenerator
from src.apps.query_gateway import run_dashboard_service

app = typer.Typer()

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    普羅米修斯之火 - 統一命令列介面
    """
    # === 核心變更：不在這裡初始化 LogManager ===
    # 我們將在每個子命令中，根據命令名稱來初始化
    ctx.obj = {} # 初始化一個空字典來傳遞物件
    if ctx.invoked_subcommand is None:
        print("請提供一個子命令。使用 --help 查看可用選項。")

def get_context(command_name: str) -> AppContext:
    """一個工廠函數，用於創建帶有唯一日誌的 AppContext。"""
    log_manager = LogManager(session_name=command_name)
    return AppContext(log_manager=log_manager)

# --- 重構所有子命令 ---
@app.command(name="evolve")
def cli_evolve(ctx: typer.Context):
    """執行一次策略演化週期。"""
    # === 核心變更：為此命令創建專屬上下文 ===
    app_context = get_context("evolve")
    ctx.obj['app_context'] = app_context
    try:
        run_evolution(app_context)
    finally:
        app_context.log_manager.close_and_archive()

@app.command(name="backtest-worker")
def cli_run_backtest_worker(ctx: typer.Context):
    """啟動一個回測服務工作者。"""
    # === 核心變更：為此命令創建專屬上下文 ===
    app_context = get_context("worker")
    ctx.obj['app_context'] = app_context
    try:
        run_worker(app_context)
    finally:
        # 在工作者被中斷時 (如 Ctrl+C)，也能歸檔日誌
        app_context.log_manager.close_and_archive()

@app.command(name="dashboard")
def cli_dashboard(
    ctx: typer.Context,
    host: str = typer.Option("127.0.0.1", help="綁定主機"),
    port: int = typer.Option(8000, help="綁定埠號")
):
    """啟動網頁儀表板。"""
    app_context = get_context("dashboard")
    ctx.obj['app_context'] = app_context
    try:
        run_dashboard_service(app_context, host, port)
    finally:
        app_context.log_manager.close_and_archive()


@app.command(name="run-tests")
def cli_run_tests(
    ctx: typer.Context,
    xml_path: str = typer.Option("output/reports/report.xml", help="JUnit XML 報告路徑。"),
    md_path: str = typer.Option("TEST_REPORT.md", help="Markdown 報告路徑。")
):
    """執行所有測試並生成報告。"""
    app_context = get_context("run_tests")
    ctx.obj['app_context'] = app_context
    try:
        os.makedirs(os.path.dirname(xml_path), exist_ok=True)
        pytest.main(["-v", f"--junitxml={xml_path}"])
        reporter = AIReportGenerator(app_context.log_manager)
        reporter.generate_from_xml(xml_path, md_path)
    finally:
        app_context.log_manager.close_and_archive()


@app.command(name="add-test-tasks")
def cli_add_test_tasks(ctx: typer.Context):
    """向佇列中添加測試任務。"""
    app_context = get_context("add_test_tasks")
    ctx.obj['app_context'] = app_context
    try:
        add_tasks(app_context)
    finally:
        app_context.log_manager.close_and_archive()


@app.command(name="show-results")
def cli_show_results(ctx: typer.Context):
    """顯示已儲存的回測結果。"""
    app_context = get_context("show_results")
    ctx.obj['app_context'] = app_context
    try:
        show_results(app_context)
    finally:
        app_context.log_manager.close_and_archive()


@app.command(name="clear-results")
def cli_clear_results(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", help="跳過確認。")
):
    """清除所有回測結果。"""
    app_context = get_context("clear_results")
    ctx.obj['app_context'] = app_context
    try:
        if not force:
            if not typer.confirm("您確定要清除所有回測結果嗎？"):
                raise typer.Abort()
        clear_results(app_context)
    finally:
        app_context.log_manager.close_and_archive()


if __name__ == "__main__":
    app()
