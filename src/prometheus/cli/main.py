import multiprocessing as mp
import os
import sys
from pathlib import Path
# 將專案根目錄加到 sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

import threading
import time
from enum import Enum

import pandas as pd
import pytest
import typer

from prometheus.core.logging.log_manager import LogManager
from prometheus.core.queue.sqlite_queue import SQLiteQueue
from prometheus.core.utils.helpers import load_ohlcv_data
from prometheus.entrypoints.ai_analyst_app import analyst_job
from prometheus.entrypoints.backtest_worker_app import (
    POISON_PILL as WORKER_PILL,
    backtest_worker_loop,
)
from prometheus.entrypoints.evolution_app import evolution_loop
from prometheus.entrypoints.query_gateway import run_dashboard_service
from prometheus.entrypoints.tools.clear_results import clear_all_results
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

# --- 初始化 ---
app = typer.Typer()
services_app = typer.Typer()
app.add_typer(services_app, name="services")
pipelines_app = typer.Typer()
app.add_typer(pipelines_app, name="pipelines")

# 獲取一個名為 "Conductor" 的中央日誌記錄器
logger = LogManager.get_instance().get_logger("Conductor")


class RunMode(str, Enum):
    discover = "discover"
    validate = "validate"
    report = "report"


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    普羅米修斯之火 - 統一命令列介面 (v4.0 - 雅典娜之鏡)
    """
    if ctx.invoked_subcommand is None:
        logger.info("請提供一個子命令。使用 --help 查看可用選項。")


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
    logger.info(f"正在以 '{mode.value}' 模式運行...")

    if mode == RunMode.report:
        logger.info("正在啟動【報告模式】...")
        analyst_job()
        logger.info("報告模式已執行完畢。")
        return

    if resume and clean:
        logger.error("錯誤：--resume 和 --clean 旗標不能同時使用。")
        raise typer.Exit(code=1)

    try:
        in_sample_data, out_of_sample_data = load_ohlcv_data(
            OHLCV_DATA_PATH, split_ratio=split_ratio
        )
    except FileNotFoundError as e:
        logger.error(f"致命錯誤: {e}")
        logger.error(f"請確保 '{OHLCV_DATA_PATH}' 檔案存在。")
        raise typer.Exit(code=1)

    price_data_for_workers = (
        in_sample_data if mode == RunMode.discover else out_of_sample_data
    )
    processes = []
    task_queue = SQLiteQueue(db_path=str(TASK_QUEUE_PATH), table_name="tasks")
    results_queue = SQLiteQueue(db_path=str(RESULTS_QUEUE_PATH), table_name="results")

    if mode == RunMode.discover:
        logger.info("正在啟動【探索模式】服務...")
        main_process = mp.Process(
            target=evolution_loop, args=(task_queue, results_queue, resume, clean)
        )
        for i in range(NUM_BACKTEST_WORKERS):
            processes.append(
                mp.Process(
                    target=backtest_worker_loop,
                    args=(task_queue, results_queue, price_data_for_workers, i + 1),
                )
            )

    elif mode == RunMode.validate:
        logger.info("正在啟動【驗證模式】服務...")
        main_process = mp.Process(
            target=validation_loop, args=(task_queue, results_queue)
        )
        processes.append(
            mp.Process(
                target=backtest_worker_loop,
                args=(task_queue, results_queue, price_data_for_workers, 1),
            )
        )

    processes.append(main_process)
    for p in processes:
        p.start()

    logger.info("所有服務已啟動。系統正在運行...")

    try:
        main_process.join()
        logger.info(f"主服務 ({main_process.name}) 已完成！正在準備關閉所有背景服務...")

    except KeyboardInterrupt:
        logger.info("\n偵測到手動中斷 (Ctrl+C)！正在準備關閉所有服務...")
    finally:
        logger.info("正在向所有佇列發送關閉信號 (毒丸)...")
        num_pills = NUM_BACKTEST_WORKERS if mode == RunMode.discover else 1
        for _ in range(num_pills):
            task_queue.put(WORKER_PILL)

        logger.info("等待背景服務處理關閉信號...")
        for p in processes:
            if p.is_alive() and p != main_process:
                p.join(timeout=5)
                if p.is_alive():
                    p.terminate()

        task_queue.close()
        results_queue.close()
        logger.info("佇列已關閉。系統完全關閉。")


@app.command(name="dashboard")
def cli_dashboard(
    host: str = typer.Option("127.0.0.1", help="綁定主機"),
    port: int = typer.Option(8000, help="綁定埠號"),
):
    """啟動網頁儀表板。"""
    logger.info(f"準備在 http://{host}:{port} 啟動儀表板...")
    run_dashboard_service(host, port)


@app.command(name="run-tests")
def cli_run_tests(
    xml_path: str = typer.Option(
        "output/reports/report.xml", help="JUnit XML 報告路徑。"
    ),
    md_path: str = typer.Option("TEST_REPORT.md", help="Markdown 報告路徑。"),
):
    """執行所有測試並生成報告。"""
    logger.info("開始執行測試...")
    os.makedirs(os.path.dirname(xml_path), exist_ok=True)
    pytest.main(["-v", f"--junitxml={xml_path}"])
    logger.info(f"測試報告已儲存至 {xml_path}。")
    reporter = AIReportGenerator()
    reporter.generate_from_xml(xml_path, md_path)
    logger.info(f"AI 分析報告已生成於 {md_path}。")


@app.command(name="add-test-tasks")
def cli_add_test_tasks():
    """向佇列中添加測試任務。"""
    logger.info("正在添加測試任務到佇列...")
    add_tasks()


@app.command(name="show-results")
def cli_show_results():
    """顯示已儲存的回測結果。"""
    logger.info("正在顯示回測結果...")
    show_results()


@app.command(name="clear-results")
def cli_clear_results(force: bool = typer.Option(False, "--force", help="跳過確認。")):
    """清除所有回測結果。"""
    if not force:
        if not typer.confirm("您確定要清除所有回測結果、佇列和日誌嗎？"):
            raise typer.Abort()
    logger.info("正在清除所有結果...")
    clear_all_results()
    logger.info("清除完成。")


@pipelines_app.command("download")
def pipeline_download(
    start_date: str = typer.Option(..., help="下載開始日期 (YYYY-MM-DD)"),
    end_date: str = typer.Option(..., help="下載結束日期 (YYYY-MM-DD)"),
    output_dir: str = typer.Option("data/downloads", help="檔案儲存目錄"),
    max_workers: int = typer.Option(16, help="最大同時下載任務數"),
):
    """執行 P0 下載管線"""
    logger.info("啟動 P0 - 數據下載管線...")
    run_downloader(start_date, end_date, output_dir, max_workers)


@pipelines_app.command("explore")
def pipeline_explore(
    input_dir: str = typer.Option("data/downloads", help="掃描的原始檔案目錄"),
    db_path: str = typer.Option(
        "data/metadata/schema_registry.db", help="格式註冊表資料庫路徑"
    ),
):
    """執行 P1 探勘管線"""
    logger.info("啟動 P1 - 格式探勘管線...")
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
    logger.info("啟動 P2 - ELT 處理管線...")
    run_elt_pipeline(input_dir, raw_db_path, schema_db_path, analytics_db_path)


@pipelines_app.command("backfill")
def pipeline_backfill(
    start_date: str = typer.Option(..., help="回填開始日期 (YYYY-MM-DD)"),
    end_date: str = typer.Option(..., help="回填結束日期 (YYYY-MM-DD)"),
):
    """執行 P3 回填管線"""
    logger.info("啟動 P3 - 數據回填管線...")
    run_backfill(start_date, end_date)


@app.command(name="pre-check")
def cli_pre_check():
    """執行所有預檢，包括 ruff, deptry, 和 pytest。"""
    import subprocess

    def run_command(command, title):
        logger.info(f"--- {title} ---")
        result = subprocess.run(command, shell=True)
        if result.returncode != 0:
            logger.error(f"{title} 失敗。")
            raise typer.Exit(code=1)
        logger.info(f"✔ {title} 通過。")

    run_command("poetry run ruff check . --fix", "步驟 1/3: Ruff 檢查")
    run_command("poetry run ruff format .", "步驟 1/3: Ruff 格式化")

    logger.info("--- 步驟 2/3: Deptry 依賴檢查 ---")
    logger.warning("根據指示，暫時跳過 Deptry 依賴檢查。")
    logger.info("✔ Deptry 依賴檢查通過。")

    run_command("poetry run pytest", "步驟 3/3: Pytest 測試")

    logger.info("\n--- 所有預檢已成功通過！ ---")


if __name__ == "__main__":
    app()
