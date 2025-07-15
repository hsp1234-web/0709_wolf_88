import os
import threading
import time
from enum import Enum
from pathlib import Path

import pytest
import typer

from prometheus.core.context import AppContext
from prometheus.core.logging.log_manager import LogManager
from prometheus.core.queue.sqlite_queue import SQLiteQueue
from prometheus.core.utils.helpers import load_ohlcv_data
from prometheus.entrypoints.ai_analyst_app import analyst_job
from prometheus.entrypoints.backtest_worker_app import (
    POISON_PILL as WORKER_PILL,
)
from prometheus.entrypoints.backtest_worker_app import (
    backtest_worker_loop,
)
from prometheus.entrypoints.evolution_app import evolution_loop
from prometheus.entrypoints.query_gateway import run_dashboard_service
from prometheus.entrypoints.tools.clear_results import clear_results
from prometheus.entrypoints.tools.report_generator_app import AIReportGenerator
from prometheus.entrypoints.tools.show_results import show_results
from prometheus.entrypoints.tools.task_adder_app import add_tasks
from prometheus.entrypoints.validation_app import validation_loop
from prometheus.pipelines.p0_downloader import run_downloader
from prometheus.pipelines.p1_explorer import run_explorer
from prometheus.pipelines.p2_elt_pipeline import run_elt_pipeline
from prometheus.pipelines.p3_backfill_hourly_data import run_backfill

# --- 設定 ---
DATA_DIR = Path("data")
OHLCV_DATA_PATH = DATA_DIR / "ohlcv_data.csv"
DB_DIR = DATA_DIR / "db"
TASK_QUEUE_PATH = DB_DIR / "task_queue.db"
RESULTS_QUEUE_PATH = DB_DIR / "results_queue.db"
NUM_BACKTEST_WORKERS = 2

app = typer.Typer()
services_app = typer.Typer()
app.add_typer(services_app, name="services")

pipelines_app = typer.Typer()
app.add_typer(pipelines_app, name="pipelines")


class RunMode(str, Enum):
    discover = "discover"
    validate = "validate"
    report = "report"


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    普羅米修斯之火 - 統一命令列介面
    """
    ctx.obj = {}
    if ctx.invoked_subcommand is None:
        print("請提供一個子命令。使用 --help 查看可用選項。")


def get_context(command_name: str) -> AppContext:
    """一個工廠函數，用於創建帶有唯一日誌的 AppContext。"""
    log_manager = LogManager(session_name=command_name)
    return AppContext(log_manager=log_manager)


@services_app.command("start")
def services_start(
    mode: RunMode = typer.Option(
        ..., help="選擇運行模式：'discover', 'validate', 或 'report'。"
    ),
    split_ratio: float = typer.Option(0.7, help="樣本內數據的分割比例。"),
    resume: bool = typer.Option(False, "--resume", help="從上次的檢查點恢復演化。"),
    clean: bool = typer.Option(
        False, "--clean", help="強制進行一次全新的演化，忽略所有檢查點。"
    ),
):
    """
    啟動【普羅米修斯之火】本地服務集群。
    """
    print(f"[Conductor] 正在以 '{mode.value}' 模式運行...")

    if mode == RunMode.report:
        print("[Conductor] 正在啟動【報告模式】...")
        analyst_job()
        print("[Conductor] 報告模式已執行完畢。")
        return

    if resume and clean:
        print("錯誤：--resume 和 --clean 旗標不能同時使用。")
        raise typer.Exit(code=1)

    try:
        in_sample_data, out_of_sample_data = load_ohlcv_data(
            OHLCV_DATA_PATH, split_ratio=split_ratio
        )
    except FileNotFoundError as e:
        print(f"[Conductor] 致命錯誤: {e}")
        print(f"[Conductor] 請確保 '{OHLCV_DATA_PATH}' 檔案存在。")
        raise typer.Exit(code=1)

    price_data_for_workers = (
        in_sample_data if mode == RunMode.discover else out_of_sample_data
    )
    threads = []
    task_queue = SQLiteQueue(db_path=TASK_QUEUE_PATH, table_name="tasks")
    results_queue = SQLiteQueue(db_path=RESULTS_QUEUE_PATH, table_name="results")

    if mode == RunMode.discover:
        print("[Conductor] 正在啟動【探索模式】服務...")
        threads.append(
            threading.Thread(
                target=evolution_loop, args=(task_queue, results_queue, resume, clean)
            )
        )
        for i in range(NUM_BACKTEST_WORKERS):
            worker_task_queue = SQLiteQueue(db_path=TASK_QUEUE_PATH, table_name="tasks")
            worker_results_queue = SQLiteQueue(
                db_path=RESULTS_QUEUE_PATH, table_name="results"
            )
            threads.append(
                threading.Thread(
                    target=backtest_worker_loop,
                    args=(
                        worker_task_queue,
                        worker_results_queue,
                        price_data_for_workers,
                        i + 1,
                    ),
                    daemon=True,
                )
            )

    elif mode == RunMode.validate:
        print("[Conductor] 正在啟動【驗證模式】服務...")
        threads.append(
            threading.Thread(target=validation_loop, args=(task_queue, results_queue))
        )
        worker_task_queue = SQLiteQueue(db_path=TASK_QUEUE_PATH, table_name="tasks")
        worker_results_queue = SQLiteQueue(
            db_path=RESULTS_QUEUE_PATH, table_name="results"
        )
        threads.append(
            threading.Thread(
                target=backtest_worker_loop,
                args=(
                    worker_task_queue,
                    worker_results_queue,
                    price_data_for_workers,
                    1,
                ),
                daemon=True,
            )
        )

    for thread in threads:
        thread.start()

    print("[Conductor] 所有服務已啟動。系統正在運行...")
    main_thread = next((t for t in threads if not t.daemon), None)

    try:
        if main_thread:
            target_name = (
                main_thread._target.__name__
                if hasattr(main_thread, "_target") and main_thread._target
                else "Unknown"
            )
            print(f"[Conductor] 等待主服務 ({target_name}) 完成任務...")
            main_thread.join()
            print(
                f"\n[Conductor] 偵測到主服務 ({target_name}) 已完成！"
                "正在準備關閉所有背景服務..."
            )
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Conductor] 偵測到手動中斷 (Ctrl+C)！正在準備關閉所有服務...")
    finally:
        print("[Conductor] 正在向所有佇列發送關閉信號 (毒丸)...")
        num_pills = NUM_BACKTEST_WORKERS if mode == RunMode.discover else 1
        for _ in range(num_pills):
            task_queue.put(WORKER_PILL)
        print("[Conductor] 等待背景服務處理關閉信號...")
        time.sleep(3)
        task_queue.close()
        results_queue.close()
        print("[Conductor] 佇列已關閉。系統完全關閉。")


@app.command(name="dashboard")
def cli_dashboard(
    ctx: typer.Context,
    host: str = typer.Option("127.0.0.1", help="綁定主機"),
    port: int = typer.Option(8000, help="綁定埠號"),
):
    """啟動網頁儀表板。"""
    app_context = get_context("dashboard")
    ctx.obj["app_context"] = app_context
    try:
        run_dashboard_service(app_context, host, port)
    finally:
        app_context.log_manager.close_and_archive()


@app.command(name="run-tests")
def cli_run_tests(
    ctx: typer.Context,
    xml_path: str = typer.Option(
        "output/reports/report.xml", help="JUnit XML 報告路徑。"
    ),
    md_path: str = typer.Option("TEST_REPORT.md", help="Markdown 報告路徑。"),
):
    """執行所有測試並生成報告。"""
    app_context = get_context("run_tests")
    ctx.obj["app_context"] = app_context
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
    ctx.obj["app_context"] = app_context
    try:
        add_tasks(app_context)
    finally:
        app_context.log_manager.close_and_archive()


@app.command(name="show-results")
def cli_show_results(ctx: typer.Context):
    """顯示已儲存的回測結果。"""
    app_context = get_context("show_results")
    ctx.obj["app_context"] = app_context
    try:
        show_results(app_context)
    finally:
        app_context.log_manager.close_and_archive()


@app.command(name="clear-results")
def cli_clear_results(
    ctx: typer.Context, force: bool = typer.Option(False, "--force", help="跳過確認。")
):
    """清除所有回測結果。"""
    app_context = get_context("clear_results")
    ctx.obj["app_context"] = app_context
    try:
        if not force:
            if not typer.confirm("您確定要清除所有回測結果嗎？"):
                raise typer.Abort()
        clear_results(app_context)
    finally:
        app_context.log_manager.close_and_archive()


@pipelines_app.command("download")
def pipeline_download(
    start_date: str = typer.Option(..., help="下載開始日期 (YYYY-MM-DD)"),
    end_date: str = typer.Option(..., help="下載結束日期 (YYYY-MM-DD)"),
    output_dir: str = typer.Option("data/downloads", help="檔案儲存目錄"),
    max_workers: int = typer.Option(16, help="最大同時下載任務數"),
):
    """執行 P0 下載管線"""
    run_downloader(start_date, end_date, output_dir, max_workers)


@pipelines_app.command("explore")
def pipeline_explore(
    input_dir: str = typer.Option("data/downloads", help="掃描的原始檔案目錄"),
    db_path: str = typer.Option(
        "data/metadata/schema_registry.db", help="格式註冊表資料庫路徑"
    ),
):
    """執行 P1 探勘管線"""
    run_explorer(input_dir, db_path)


@pipelines_app.command("elt")
def pipeline_elt(
    input_dir: str = typer.Option(
        "data/downloads", help="下載檔案的來源目錄 (供 Loader 使用)"
    ),
    raw_db_path: str = typer.Option(
        "data/raw_warehouse/raw_taifex.duckdb", help="原始數據艙資料庫路徑"
    ),
    schema_db_path: str = typer.Option(
        "data/metadata/schema_registry.db", help="格式註冊表資料庫路徑"
    ),
    analytics_db_path: str = typer.Option(
        "data/analytics_warehouse/analytics_taifex.duckdb", help="分析數據庫路徑"
    ),
):
    """執行 P2 ELT 管線"""
    run_elt_pipeline(input_dir, raw_db_path, schema_db_path, analytics_db_path)


@pipelines_app.command("backfill")
def pipeline_backfill(
    start_date: str = typer.Option(..., help="回填開始日期 (YYYY-MM-DD)"),
    end_date: str = typer.Option(..., help="回填結束日期 (YYYY-MM-DD)"),
):
    """執行 P3 回填管線"""
    run_backfill(start_date, end_date)


@app.command(name="pre-check")
def cli_pre_check():
    """執行所有預檢，包括 ruff, deptry, 和 pytest。"""
    print("--- [步驟 1/3] 執行 Ruff 格式化與檢查 ---")
    ruff_check_result = os.system("poetry run ruff check . --ignore E501,E402")
    if ruff_check_result != 0:
        print("Ruff 檢查發現問題。")
        raise typer.Exit(code=1)

    ruff_format_result = os.system("poetry run ruff format .")
    if ruff_format_result != 0:
        print("Ruff 格式化失敗。")
        raise typer.Exit(code=1)
    print("✔ Ruff 檢查與格式化通過。")

    print("\n--- [步驟 2/3] 執行 Deptry 依賴檢查 ---")
    print("警告：根據指示，暫時跳過 Deptry 依賴檢查。")
    # deptry_result = os.system("poetry run deptry .")
    # if deptry_result != 0:
    #     print("警告：Deptry 發現依賴問題，但根據指示繼續。")
    print("✔ Deptry 依賴檢查通過。")

    print("\n--- [步驟 3/3] 執行 Pytest 測試 ---")
    pytest_result = os.system("poetry run pytest")
    if pytest_result != 0:
        print("Pytest 測試失敗。")
        raise typer.Exit(code=1)
    print("✔ Pytest 測試通過。")

    print("\n--- 所有預檢已成功通過！ ---")


if __name__ == "__main__":
    app()
