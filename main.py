import typer
from rich.console import Console
from typing import Optional
import os # 新增 os 模組導入，用於路徑處理
import sys # 新增 sys 模組導入，用於路徑處理

# --- 應用邏輯導入 ---
# 每日市場分析儀
try:
    from apps.daily_market_analyzer.logic import daily_market_analyzer_main_logic
except ModuleNotFoundError:
    # 為了在開發或直接執行 main.py 時，如果尚未安裝為套件，也能找到模組
    # 這段程式碼假設 main.py 位於專案根目錄
    PROJECT_ROOT_FOR_DMA = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
    if PROJECT_ROOT_FOR_DMA not in sys.path:
        sys.path.insert(0, PROJECT_ROOT_FOR_DMA)
    from apps.daily_market_analyzer.logic import daily_market_analyzer_main_logic

# 回測引擎 (稍後添加)
try:
    from apps.backtesting_engine.engine import run_backtest_logic, VECTORBT_AVAILABLE
except ModuleNotFoundError:
    PROJECT_ROOT_FOR_BT = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
    if PROJECT_ROOT_FOR_BT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT_FOR_BT) # 確保根目錄在 sys.path
    # 嘗試再次導入，如果 engine.py 確實不存在或 vectorbt 就是有問題，這裡還是會出錯
    # 但至少排除了 main.py 執行時的路徑問題
    from apps.backtesting_engine.engine import run_backtest_logic, VECTORBT_AVAILABLE


# --- Typer 應用實例 ---
app = typer.Typer(
    help="【普羅米修斯之火】中央指揮部 (CLI)",
    rich_markup_mode="markdown" # 啟用 rich 的 markdown 格式
)
console = Console()


# --- Helper function to set project root ---
# 這個輔助函數可以考慮放到 core.utils 中，如果多處需要
def _ensure_project_root_in_path():
    """確保專案根目錄在 sys.path 中，以便正確解析模組。"""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        # console.print(f"DEBUG: Project root [green]{project_root}[/green] added to sys.path.")

# 在所有命令執行前，可以先調用一次，確保路徑正確
# _ensure_project_root_in_path()
# 或者在每個 command 內部調用，但 Typer 的 callback 可能更適合全局設置

# --- 全局回調 (在任何命令執行前運行) ---
@app.callback()
def main_callback(ctx: typer.Context):
    """
    普羅米修斯之火 CLI。在執行具體命令前，會先執行此回調。
    """
    _ensure_project_root_in_path()
    # console.print("DEBUG: Global callback executed, project root ensured in sys.path.")


# --- Daily Market Analyzer 命令 ---
@app.command(name="daily-market-analyzer", help="執行每日市場分析與報告生成流程。")
def daily_market_analyzer_command(
    tickers: Optional[str] = typer.Option(None, "--tickers", "-t", help="要分析的標的列表，以逗號分隔 (例如: AAPL,MSFT)。"),
    start_date: Optional[str] = typer.Option(None, "--start-date", "-s", help="數據分析/獲取的起始日期 (格式: YYYY-MM-DD)。"),
    end_date: Optional[str] = typer.Option(None, "--end-date", "-e", help="數據分析/獲取的結束日期 (格式: YYYY-MM-DD)。"),
    data_only: bool = typer.Option(False, "--data-only", help="僅執行數據獲取和存儲流程。"),
    report_only: bool = typer.Option(False, "--report-only", help="僅執行報告生成流程 (需要已存在的數據)。"),
    report_start_date: Optional[str] = typer.Option(None, "--report-start-date", help="報告生成的起始日期，配合 --report-only。"),
    report_end_date: Optional[str] = typer.Option(None, "--report-end-date", help="報告生成的結束日期，配合 --report-only。"),
    db_path: str = typer.Option("data_workspace/daily_market_analyzer.duckdb", "--db-path", help="主分析資料庫的路徑。"),
    cache_db_path: Optional[str] = typer.Option(None, "--cache-db-path", help="DuckDB 快取資料庫路徑 (目前未使用)。"), # 修正：明確這是可選的
    table_name: str = typer.Option("market_ohlcv_data", "--table-name", help="OHLCV 數據的表格名稱。"),
    no_data_cooldown_days: int = typer.Option(7, "--no-data-cooldown-days", help="「無數據區塊」記錄的冷卻天數。"),
    force_refresh: bool = typer.Option(False, "--force-refresh", help="強制刷新數據，忽略快取。"),
    enable_local_first: bool = typer.Option(False, "--enable-local-first", help="啟用本地優先工作流程。"),
    gdrive_root: str = typer.Option("/content/drive/MyDrive/", "--gdrive-root", help="Google Drive 根路徑。"),
    project_path_local: str = typer.Option("/content/panoramic_market_analyzer/", "--project-path-local", help="專案本地儲存根路徑。"),
    max_workers: int = typer.Option(16, "--max-workers", help="並行數據抓取最大工作進程數。")
):
    """
    CLI 命令，用於啟動每日市場分析儀。
    """
    console.print(f"[bold green]接收到 daily-market-analyzer 命令[/bold green]")
    try:
        daily_market_analyzer_main_logic(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            data_only=data_only,
            report_only=report_only,
            report_start_date=report_start_date,
            report_end_date=report_end_date,
            db_path=db_path,
            cache_db_path=cache_db_path,
            table_name=table_name,
            no_data_cooldown_days=no_data_cooldown_days,
            force_refresh=force_refresh,
            enable_local_first=enable_local_first,
            gdrive_root=gdrive_root,
            project_path_local=project_path_local,
            max_workers=max_workers
        )
        console.print(f"[bold blue]daily-market-analyzer 命令執行完畢。[/bold blue]")
    except ValueError as ve:
        console.print(f"[bold red]參數錯誤（每日市場分析儀）：{ve}[/bold red]")
    except ModuleNotFoundError as me: # 理論上 main_callback 應該處理了路徑問題
        console.print(f"[bold red]模組導入錯誤（每日市場分析儀）：{me}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]執行 daily-market-analyzer 時發生未預期錯誤：{e}[/bold red]")
        import traceback
        console.print(f"詳細錯誤追蹤：\n{traceback.format_exc()}")


# --- Backtesting Engine 命令 ---
@app.command(name="backtest", help="執行回測引擎。")
def backtesting_engine_command(
    # 根據需要添加回測引擎的參數，例如：
    # strategy_name: str = typer.Option(..., "--strategy", "-s", help="要執行的策略名稱。"),
    # symbols: Optional[str] = typer.Option(None, "--symbols", help="要回測的標的列表，逗號分隔。"),
    # start_date_bt: Optional[str] = typer.Option(None, "--bt-start-date", help="回測起始日期。"),
    # end_date_bt: Optional[str] = typer.Option(None, "--bt-end-date", help="回測結束日期。")
):
    """
    CLI 命令，用於啟動回測引擎。
    """
    console.print(f"[bold green]接收到 backtest 命令[/bold green]")

    if not VECTORBT_AVAILABLE:
        console.print("[bold yellow]警告：[/bold yellow] 核心回測依賴 `vectorbt` 模組未在本環境中找到。")
        console.print("請確認已在 `requirements.in` (或 `requirements.lock.txt`) 中包含 `vectorbt` 並已成功安裝。")
        console.print("回測功能可能無法正常運行。")
        # 根據使用者先前的指示 (選項B：自然拋出)，這裡可以不主動退出，
        # run_backtest_logic 內部會處理並返回錯誤狀態。
        # 或者，如果希望更早失敗，可以 raise typer.Exit(code=1)
        # raise typer.Exit(code=1)

    try:
        result = run_backtest_logic()
        if result.get("status") == "success":
            console.print(f"[bold blue]回測命令執行完畢：{result.get('message')}[/bold blue]")
        else:
            console.print(f"[bold red]回測命令執行失敗：{result.get('message')}[/bold red]")
            if result.get("missing_dependency"):
                 console.print(f"原因：缺少依賴模組 - [bold cyan]{result.get('missing_dependency')}[/bold cyan]")

    except ImportError as ie: # 雖然 engine.py 內部處理了，但以防萬一
        if 'vectorbt' in str(ie).lower():
            console.print(f"[bold red]執行回測時發生導入錯誤：{ie}[/bold red]")
            console.print("這通常意味著 `vectorbt` 模組未正確安裝。請檢查您的環境。")
        else:
            console.print(f"[bold red]執行回測時發生未預期的導入錯誤：{ie}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]執行 backtest 時發生未預期錯誤：{e}[/bold red]")
        import traceback
        console.print(f"詳細錯誤追蹤：\n{traceback.format_exc()}")


if __name__ == "__main__":
    app()
