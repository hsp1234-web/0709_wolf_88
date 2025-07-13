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
    from pipelines.p5_hourly_price_etl.run_etl import run as run_hourly_price_etl
    from core.db.db_manager import DBManager
    import pandas as pd
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
    start_date: str = typer.Option(
        None,
        "--start-date",
        help="數據提取的開始日期 (YYYY-MM-DD)。",
    ),
    end_date: str = typer.Option(
        None,
        "--end-date",
        help="數據提取的結束日期 (YYYY-MM-DD)。",
    ),
):
    """執行 P4 每日宏觀數據 ETL 管線。"""
    execute_task(
        ctx.obj,
        "每日宏觀數據ETL",
        run_daily_macro_etl,
        force_download=force_download,
        start_date=start_date,
        end_date=end_date,
    )


@app.command()
def build_hourly_data(
    ctx: typer.Context,
    mode: str = typer.Option(
        "update",
        "--mode",
        "-m",
        help="執行模式，可選值為 'backfill' 或 'update'。",
        case_sensitive=False,
    ),
):
    """執行 P5 小時級價格數據 ETL 管線。"""
    execute_task(
        ctx.obj,
        f"小時級價格數據ETL ({mode}模式)",
        run_hourly_price_etl,
        mode=mode,
    )


@app.command()
def calculate_hourly_indicators(ctx: typer.Context):
    """從數據庫讀取小時數據，計算技術指標，然後將結果寫回數據庫。"""
    log_manager = ctx.obj
    task_name = "小時級數據技術指標計算"
    log_manager.log("BATTLE", f"--- [啟動任務：{task_name}] ---")

    table_name = "hourly_market_data"

    try:
        # 1. 讀取數據
        with DBManager() as db_manager:
            log_manager.log("INFO", f"正在從 '{table_name}' 讀取數據...")
            try:
                price_df = db_manager.connection.table(table_name).to_df()
            except duckdb.CatalogException:
                log_manager.log("ERROR", f"數據表 '{table_name}' 不存在。請先執行 'build-hourly-data --mode backfill'。")
                raise typer.Exit(code=1)

        if price_df.empty:
            log_manager.log("WARNING", f"數據表 '{table_name}' 為空，沒有數據可供計算。")
            raise typer.Exit()

        log_manager.log("INFO", f"成功讀取 {len(price_df)} 行數據。")

        # 2. 計算指標
        log_manager.log("INFO", "正在調用轉換模組計算技術指標...")
        from pipelines.p5_hourly_price_etl.transform import calculate_technical_indicators
        data_with_indicators = calculate_technical_indicators(price_df)
        log_manager.log("INFO", "技術指標計算完成。")

        # 3. 寫回數據庫
        log_manager.log("INFO", "正在調用加載模組將數據寫回數據庫...")
        from pipelines.p5_hourly_price_etl.load import overwrite_data_with_indicators
        overwrite_data_with_indicators(data_with_indicators)
        log_manager.log("INFO", "數據已成功寫回。")

        log_manager.log("SUCCESS", f"--- [任務完成：{task_name}] ---")

    except Exception as e:
        log_manager.log("ERROR", f"執行 {task_name} 時發生錯誤: {e}")
        raise typer.Exit(code=1)


@app.command()
def verify_daily_data(ctx: typer.Context):
    """驗證每日宏觀數據是否已成功載入數據庫。"""
    log_manager = ctx.obj
    task_name = "每日宏觀數據驗證"
    log_manager.log("BATTLE", f"--- [啟動任務：{task_name}] ---")

    table_name = "daily_macro_market_data"

    try:
        with DBManager() as db_manager:
            log_manager.log("INFO", f"正在連接到數據庫: {db_manager.db_path}")

            # 檢查表格是否存在
            tables_df = db_manager.connection.execute("SHOW TABLES").fetchdf()
            if table_name not in tables_df['name'].values:
                log_manager.log("ERROR", f"數據表 '{table_name}' 不存在於數據庫中。")
                print(f"❌ 驗證失敗：數據表 '{table_name}' 不存在。")
                raise typer.Exit(code=1)

            log_manager.log("INFO", f"正在查詢數據表: {table_name}")
            data_df = db_manager.connection.table(table_name).to_df()

        if data_df.empty:
            log_manager.log("WARNING", f"數據表 '{table_name}' 為空。")
            print(f"⚠️ 驗證警告：數據表 '{table_name}' 為空。")
            raise typer.Exit()

        total_rows = len(data_df)
        min_date = pd.to_datetime(data_df['Date']).min().strftime('%Y-%m-%d')
        max_date = pd.to_datetime(data_df['Date']).max().strftime('%Y-%m-%d')

        # 打印驗證報告
        print("\n--- 📊 每日宏觀數據驗證報告 ---")
        print(f"✅ 數據表 '{table_name}' 存在且可查詢。")
        print(f"🔢 總行數: {total_rows}")
        print(f"📅 數據時間範圍: 從 {min_date} 到 {max_date}")
        print("\n--- 預覽前 5 行數據 ---")
        print(data_df.head(5).to_string())
        print("---------------------------------")

        log_manager.log("SUCCESS", f"--- [任務完成：{task_name}] ---")

    except Exception as e:
        log_manager.log("ERROR", f"執行 {task_name} 時發生錯誤: {e}")
        print(f"❌ 驗證失敗：執行過程中發生錯誤: {e}")
        raise typer.Exit(code=1)


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
