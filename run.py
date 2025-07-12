# run.py (v2.0 - 整合 LogManager)

import typer
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
    from pipelines.p4_daily_macro_etl.run_etl import run as run_daily_macro_etl
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


@app.command()
def build_daily_data(
    ctx: typer.Context,
    force_download: bool = typer.Option(
        False,
        "--force-download",
        "-f",
        help="強制從網路重新下載所有數據，忽略本地快取。",
    ),
):
    """執行 P4 每日宏觀數據 ETL 管線。"""
    execute_task(
        ctx.obj,
        "每日宏觀數據ETL",
        run_daily_macro_etl,
        force_download=force_download,
    )


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
