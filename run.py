# run.py
# 【普羅米修斯之火】專案統一命令列進入點 (基於 Typer)

import typer
import sys
from pathlib import Path

# --- 標準路徑自我校正樣板 ---
# 確保無論從何處執行，都能正確找到 core 和 apps 模組
try:
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        print(f"資訊：已將專案根目錄 '{project_root}' 添加到 sys.path")

    # 延遲導入，確保路徑已設定
    from apps.backtesting_engine.run import main as run_sma_backtest
    from apps.run_stress_index import main as run_stress_index
    from apps.run_fmp_test import main as run_fmp_test
    from pipelines.p3_backfill_hourly_data.run import main as run_backfill
except ImportError as e:
    print(f"錯誤：導入應用模組失敗，請確認 apps 和 pipelines 資料夾下的腳本結構是否正確。錯誤訊息：{e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"錯誤：初始化時發生未知錯誤。{e}", file=sys.stderr)
    sys.exit(1)
# --- 樣板結束 ---

# 初始化 Typer 應用
app = typer.Typer(
    name="prometheus-fire",
    help="【普羅米修斯之火】金融數據與分析框架 - 統一作戰指揮中心",
    add_completion=False
)

@app.command()
def sma_backtest():
    """
    執行 SMA (簡單移動平均線) 策略回測與視覺化生成。
    """
    print("--- [啟動任務：SMA 策略回測] ---")
    try:
        run_sma_backtest()
        # 假設視覺化是獨立的，也可以整合進來
        # from apps.visualization.plot_sma_crossover import main as run_sma_viz
        # run_sma_viz()
        print("--- [任務完成：SMA 策略回測] ---")
    except Exception as e:
        print(f"錯誤：執行 SMA 策略回測時發生錯誤: {e}", file=sys.stderr)
        raise typer.Exit(code=1)

@app.command()
def stress_index():
    """
    執行壓力指數計算，需要 config.yml 中配置 FRED API 金鑰。
    """
    print("--- [啟動任務：壓力指數計算] ---")
    try:
        run_stress_index()
        print("--- [任務完成：壓力指數計算] ---")
    except Exception as e:
        print(f"錯誤：執行壓力指數計算時發生錯誤: {e}", file=sys.stderr)
        raise typer.Exit(code=1)

@app.command()
def fmp_fetch():
    """
    執行 FMPClient 端到端實戰驗證，需要 config.yml 中配置 FMP API 金鑰。
    """
    print("--- [啟動任務：FMP 數據獲取驗證] ---")
    try:
        run_fmp_test()
        print("--- [任務完成：FMP 數據獲取驗證] ---")
    except Exception as e:
        print(f"錯誤：執行 FMP 數據獲取驗證時發生錯誤: {e}", file=sys.stderr)
        raise typer.Exit(code=1)

@app.command()
def backfill():
    """
    執行數據回填管線，將 SPY 的小時級數據填充到 DuckDB。
    """
    print("--- [啟動任務：數據回填] ---")
    try:
        run_backfill()
        print("--- [任務完成：數據回填] ---")
    except Exception as e:
        print(f"錯誤：執行數據回填時發生錯誤: {e}", file=sys.stderr)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
