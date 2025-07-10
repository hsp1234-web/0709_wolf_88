# -*- coding: utf-8 -*-
"""
【蒼穹之心計畫】中央指揮部 (CLI)

此檔案是整個應用程式生態系的統一入口點。
所有獨立的應用程式功能都將作為子命令整合到此處。
"""
import click

@click.group()
def cli():
    """
    蒼穹之心計畫 中央指揮部 (CLI)
    """
    pass

# 從應用程式導入核心邏輯
execute_backtest = None # 初始化為 None
try:
    from apps.backtesting_engine.engine import execute_backtest
except ImportError as e:
    # 處理可能的導入錯誤，例如路徑問題或依賴問題
    # 在CLI啟動時給出提示，避免運行時才發現
    click.echo(f"警告：無法導入回測引擎模組 ({e})。`backtest` 命令可能無法使用。", err=True)
    # execute_backtest 將保持為 None

@cli.command()
def backtest():
    """
    執行回測引擎的核心邏輯。
    """
    if execute_backtest is None:
        click.echo("錯誤：回測引擎功能由於導入失敗而無法使用。請檢查先前的警告訊息。", err=True)
        return

    try:
        result = execute_backtest()
        click.echo(f"回測結果: {result}")
    except ModuleNotFoundError as e:
        if e.name == "vectorbt":
            click.echo("錯誤：回測引擎缺少必要的 `vectorbt` 依賴。請安裝後重試。", err=True)
        else:
            click.echo(f"錯誤：執行回測時發生模組未找到錯誤：{e}", err=True)
    except Exception as e:
        click.echo(f"錯誤：執行回測時發生未預期錯誤：{e}", err=True)

# --- 整合 Daily Market Analyzer ---
try:
    from apps.daily_market_analyzer.cli_interface import run_daily_analysis
except ImportError as e:
    click.echo(f"警告：無法導入每日市場分析器模組 ({e})。`analyze-market` 命令可能無法使用。", err=True)
    run_daily_analysis = None # 確保變數存在，即使導入失敗

@cli.command("analyze-market")
@click.option("--tickers", type=str, help="要分析的標的列表，以逗號分隔 (例如: AAPL,MSFT)。")
@click.option("--start-date", type=str, help="數據分析/獲取的起始日期 (格式: YYYY-MM-DD)。")
@click.option("--end-date", type=str, help="數據分析/獲取的結束日期 (格式: YYYY-MM-DD)。")
@click.option("--data-only", is_flag=True, help="僅執行數據獲取和存儲流程。")
@click.option("--report-only", is_flag=True, help="僅執行報告生成流程 (需要已存在的數據)。")
@click.option("--report-start-date", type=str, help="報告生成的起始日期 (格式: YYYY-MM-DD)，配合 --report-only 使用。")
@click.option("--report-end-date", type=str, help="報告生成的結束日期 (格式: YYYY-MM-DD)，配合 --report-only 使用。")
@click.option("--db-path", type=click.Path(), default="data_workspace/daily_market_analyzer.duckdb", help="主分析資料庫的完整路徑。")
@click.option("--table-name", default="market_ohlcv_data", help="資料庫中儲存 OHLCV 數據的表格名稱。")
@click.option("--no-data-cooldown-days", type=int, default=7, help="「無數據區塊」記錄的有效冷卻天數。")
@click.option("--force-refresh", is_flag=True, help="強制刷新數據，忽略快取。")
@click.option("--enable-local-first", is_flag=True, help="啟用本地優先工作流程，將資料庫複製到本地處理。")
@click.option("--gdrive-root", type=click.Path(), default="/content/drive/MyDrive/", help="Google Drive 的根路徑 (配合 local-first)。")
@click.option("--project-path-local", type=click.Path(), default="/content/panoramic_market_analyzer/", help="專案在本地 Colab 儲存的根路徑 (配合 local-first)。")
@click.option("--max-workers", type=int, default=16, help="YFinance 並行數據抓取的最大工作進程數。")
def analyze_market_command(
    tickers: str | None,
    start_date: str | None,
    end_date: str | None,
    data_only: bool,
    report_only: bool,
    report_start_date: str | None,
    report_end_date: str | None,
    db_path: str,
    table_name: str,
    no_data_cooldown_days: int,
    force_refresh: bool,
    enable_local_first: bool,
    gdrive_root: str,
    project_path_local: str,
    max_workers: int,
):
    """
    執行每日市場分析、數據獲取和報告生成。
    """
    if run_daily_analysis is None:
        click.echo("錯誤：每日市場分析器功能由於導入失敗而無法使用。請檢查先前的警告訊息。", err=True)
        return

    try:
        # 將 Click 參數傳遞給後端函式
        # 注意：Click 的 Path 類型會自動處理路徑的有效性，但仍是字串
        # 日期字串的驗證和轉換應在 run_daily_analysis 內部或通過 Click 的 DateTime 類型處理
        # (目前 run_daily_analysis 期望的是字串，Click 參數也定義為 str)
        result = run_daily_analysis(
            tickers=tickers,
            start_date_str=start_date,
            end_date_str=end_date,
            data_only=data_only,
            report_only=report_only,
            report_start_date_str=report_start_date,
            report_end_date_str=report_end_date,
            db_path=db_path,
            table_name=table_name,
            no_data_cooldown_days=no_data_cooldown_days,
            force_refresh=force_refresh,
            enable_local_first=enable_local_first,
            gdrive_root=gdrive_root,
            project_path_local=project_path_local,
            max_workers=max_workers
        )
        # run_daily_analysis 應該會自己 click.echo 輸出，或者返回一個結果供這裡打印
        # click.echo(f"每日市場分析結果: {result}") # 假設 run_daily_analysis 返回有意義的狀態
    except click.Abort:
        # 如果 run_daily_analysis 內部調用 click.Abort()，這裡不需要做任何事，Click 會處理退出
        pass
    except Exception as e:
        click.echo(f"錯誤：執行每日市場分析時發生未預期錯誤：{e}", err=True)
        # 考慮是否要更詳細地記錄錯誤堆疊，例如：
        # import traceback
        # click.echo(traceback.format_exc(), err=True)

if __name__ == '__main__':
    cli()
