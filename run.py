# run.py (v2.0 - 整合 LogManager)

import typer
import uvicorn # 導入 uvicorn
import sys
from pathlib import Path

# --- 標準路徑自我校正樣板 ---
try:
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from core.logger import LogManager
    from apps.backtesting_engine.run import main as run_sma_backtest
    from apps.run_stress_index import main as run_stress_index
    from apps.run_fmp_test import main as run_fmp_test
    # 導入新的應用函數
    from apps.backtest_worker_app import run_worker
    from apps.tools.task_adder_app import add_tasks
    from apps.tools.show_results import show_results # 導入新函數
    from apps.query_gateway import app as dashboard_app # 導入 dashboard app
    from apps.tools.clear_results import clear_results
except ImportError as e:
    print(f"錯誤：導入應用模組失敗。錯誤訊息：{e}", file=sys.stderr)
    sys.exit(1)
# --- 樣板結束 ---

app = typer.Typer(
    name="prometheus-fire",
    help="【普羅米修斯之火】金融數據與分析框架 - 統一作戰指揮中心",
    add_completion=False
)

# 在 Typer App 的回呼中初始化 LogManager
@app.callback()
def main(ctx: typer.Context):
    """
    初始化共享資源，如 LogManager。
    """
    output_dir = project_root / "output"
    log_db_path = output_dir / "logs" / "session.sqlite"
    archive_dir = output_dir / "logs" / "archive"

    # 將 LogManager 實例儲存在 context 中，供所有指令共享
    ctx.obj = LogManager(db_path=log_db_path, archive_dir=archive_dir)

def execute_task(log_manager: LogManager, task_name: str, task_func, **kwargs):
    """統一的任務執行與日誌記錄模板"""
    log_manager.log("BATTLE", f"--- [啟動任務：{task_name}] ---")
    try:
        # 將 log_manager 傳遞給任務函數
        task_func(log_manager=log_manager, **kwargs)
        log_manager.log("SUCCESS", f"--- [任務完成：{task_name}] ---")
    except Exception as e:
        log_manager.log("ERROR", f"執行 {task_name} 時發生錯誤: {e}")
        raise typer.Exit(code=1)

@app.command()
def sma_backtest(ctx: typer.Context):
    """執行 SMA (簡單移動平均線) 策略回測。"""
    execute_task(ctx.obj, "SMA 策略回測", run_sma_backtest)

@app.command()
def stress_index(ctx: typer.Context):
    """執行壓力指數計算。"""
    execute_task(ctx.obj, "壓力指數計算", run_stress_index)

@app.command()
def fmp_fetch(ctx: typer.Context):
    """執行 FMPClient 端到端實戰驗證。"""
    execute_task(ctx.obj, "FMP 數據獲取驗證", run_fmp_test)

# 新增回測工作者命令
@app.command(name="backtest-worker")
def cli_run_backtest_worker(ctx: typer.Context):
    """啟動一個回測服務工作者，持續監聽並執行任務。"""
    log_manager: LogManager = ctx.obj
    log_manager.log("INFO", "CLI: 正在啟動回測服務工作者...")
    run_worker(log_manager)

# 新增測試任務命令
@app.command(name="add-test-tasks")
def cli_add_test_tasks(ctx: typer.Context):
    """向佇列中添加一批用於測試的回測任務。"""
    log_manager: LogManager = ctx.obj
    log_manager.log("INFO", "CLI: 正在新增測試任務...")
    add_tasks(log_manager)

# 新增檢視結果命令
@app.command(name="show-results")
def cli_show_results(ctx: typer.Context):
    """查詢並顯示所有已儲存的回測結果。"""
    log_manager: LogManager = ctx.obj
    show_results(log_manager)

# 新增儀表板命令
@app.command(name="dashboard")
def cli_dashboard(
    ctx: typer.Context,
    host: str = typer.Option("127.0.0.1", help="綁定主機"),
    port: int = typer.Option(8000, help="綁定埠號")
):
    """啟動網頁儀表板以可視化回測結果。"""
    log_manager: LogManager = ctx.obj
    log_manager.log("INFO", f"正在於 http://{host}:{port} 啟動儀表板...")
    uvicorn.run(dashboard_app, host=host, port=port)

# 新增清理結果命令
@app.command(name="clear-results")
def cli_clear_results(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", help="跳過確認，直接執行清除。")
):
    """清除資料庫中所有已儲存的回測結果。"""
    log_manager: LogManager = ctx.obj

    if not force:
        # 進行安全確認
        confirm = typer.confirm("您確定要清除所有回測結果嗎？此操作無法復原。")
        if not confirm:
            log_manager.log("INFO", "操作已取消。")
            raise typer.Abort()

    clear_results(log_manager)

if __name__ == "__main__":
    try:
        # 這是 app(...) 的一個技巧，以便能存取到 context
        # https://github.com/tiangolo/typer/issues/152#issuecomment-993332854
        result = app(standalone_mode=False)
        if result != 0: # 如果命令執行失敗，直接退出
            sys.exit(result)

        # 只有當命令成功執行後，才執行歸檔
        # typer.get_current_context() 只能在指令函數內部使用
        # 所以我們從 result 中獲取 context.obj
        # 修正: 更簡單的方式是直接在 try/finally 中處理
        # (Typer 的這個部分設計得有些複雜，我們用最穩健的方式)

    except typer.Exit:
        # 處理由 execute_task 拋出的退出異常
        # 此時還未歸檔，所以需要手動處理
        ctx = typer.get_current_context()
        if ctx.obj:
            ctx.obj.archive_to_file()
        sys.exit(1)
    except Exception as e:
        print(f"災難性頂層錯誤: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # 確保無論成功或失敗，都會嘗試歸檔
        # Typer 的 context 管理使其難以在指令外安全地獲取
        # 我們採用一個更簡單的策略：在 finally 中重新初始化一個實例來歸檔
        output_dir = project_root / "output"
        log_db_path = output_dir / "logs" / "session.sqlite"
        archive_dir = output_dir / "logs" / "archive"
        final_archiver = LogManager(db_path=log_db_path, archive_dir=archive_dir)
        final_archiver.archive_to_file()
