# --- 快速反應版程式碼 ---

import asyncio
from datetime import datetime, timedelta
import sys
from pathlib import Path

# 將 src 目錄加入 Python 路徑，以符合專案的模組結構
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from prometheus.core.context import AppContext
from prometheus.core.engines.robust_acquisition_engine import RobustDataAcquisitionEngine
from rich.console import Console
from rich.table import Table

console = Console()

# --- 核心戰術參數 ---
BASE_DATE = datetime(2025, 7, 16)

# --- 精英偵察小隊 (代表性抽樣) ---
RECON_SQUAD = {
    "核心指數": "SPY",
    "台灣科技股": "2330.TW",
    "核心商品": "GC=F",
    "核心債券": "TLT",
    "宏觀數據 (FRED)": "T10Y2Y",
    "加密貨幣": "BTC-USD",
    "已知問題數據": "SI=F", # 用於驗證容錯
}

# --- 快速探測配置 (只測日線與小時線) ---
PROBE_CONFIG = {
    "1d": {"period": "1y", "label": "過去 1 年"},
    "1h": {"days": 60, "label": "過去 60 天"}
}

async def probe_ticker(engine, ticker, interval, config):
    """探測單一資產的數據可用性"""
    period = config.get("period")
    if not period and "days" in config:
        period = f"{config['days']}d"

    try:
        # RobustDataAcquisitionEngine's fetch_single_ticker takes interval and period
        ticker_instance, df = await engine.fetch_single_ticker(
            ticker=ticker,
            interval=interval,
            period=period
        )
        if df is not None and not df.empty:
            return { "status": "✅ 成功", "count": len(df) }
    except Exception:
        pass # 靜默處理錯誤，只關心結果

    return { "status": "❌ 失敗", "count": 0 }

async def main():
    """主執行函數"""
    console.print(f"[bold cyan]===【快速反應偵察啟動 (基準日: {BASE_DATE.strftime('%Y-%m-%d')})】===[/bold cyan]")
    table = Table(title="偵察結果")
    table.add_column("任務目標", style="cyan")
    table.add_column("資產代號", style="yellow")
    table.add_column("日線 (1d)", justify="center")
    table.add_column("小時線 (1h)", justify="center")

    all_tickers = list(RECON_SQUAD.values())

    async with AppContext() as context:
        engine = RobustDataAcquisitionEngine(tickers=all_tickers)

        for name, ticker in RECON_SQUAD.items():
            daily_result = await probe_ticker(engine, ticker, "1d", PROBE_CONFIG["1d"])
            hourly_result = await probe_ticker(engine, ticker, "1h", PROBE_CONFIG["1h"])
            table.add_row(
                name,
                ticker,
                f"{daily_result['status']} ({daily_result['count']})",
                f"{hourly_result['status']} ({hourly_result['count']})"
            )
        console.print(table)
        console.print("[bold green]偵察任務完成。[/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
