# --- v2 - 時序校準版程式碼 ---

import asyncio
import pandas as pd
from datetime import datetime, timedelta
import sys
from pathlib import Path

# 將 src 目錄加入 Python 路徑，以符合專案的模組結構
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from prometheus.core.context import AppContext
from prometheus.core.engines.robust_acquisition_engine import RobustDataAcquisitionEngine
from rich.console import Console

console = Console()

# --- 核心戰術參數：固定基準日期 ---
BASE_DATE = datetime(2025, 7, 16)

# --- 完整資產宇宙定義 (來自 v2.2 總綱) ---
ASSET_UNIVERSE = {
    "指數 & 指數期貨": {
        "desc": "核心市場指數與相關衍生品",
        "tickers": ["ES=F", "^VIX", "^TWII", "^SPX", "DX-Y.NYB", "SPY", "NQ=F"]
    },
    "債券 & 利率": {
        "desc": "政府公債、利率與相關 ETF",
        "tickers": ["ZN=F", "TLT", "^TNX", "^IRX", "^FVX", "^TYX"]
    },
    "商品 & 商品期貨": {
        "desc": "主要原物料與相關 ETF",
        "tickers": ["GC=F", "CL=F", "SI=F", "USO", "HG=F", "PL=F"]
    },
    "股票": {
        "desc": "代表性個股 (美股、台股、港股)",
        "tickers": ["AAPL", "TSM", "2330.TW", "0981.HK"]
    },
    "加密貨幣": {
        "desc": "主流加密貨幣",
        "tickers": ["BTC-USD", "ETH-USD"]
    },
    "總體經濟 (FRED)": {
        "desc": "來自 FRED 的宏觀經濟數據",
        "tickers": ["T10Y2Y", "BAMLH0A0HYM2", "DFII10", "T10YIE", "SKEW", "VIXCLS", "^MOVE"]
    }
}

# --- 探測配置 (基於 yfinance 限制) ---
PROBE_CONFIG = {
    "1d": {"period": "max", "label": "最大歷史"},
    "1h": {"days": 729, "label": "過去 729 天"},
    "5m": {"days": 59, "label": "過去 59 天"},
    "1m": {"days": 6, "label": "過去 6 天"}
}

async def probe_ticker(engine, ticker, interval, config):
    """探測單一資產的數據可用性"""
    start_date, end_date, period = None, None, None
    end_date_str = BASE_DATE.strftime('%Y-%m-%d')

    if "period" in config:
        period = config["period"]
        start_date_str = "N/A"
    else:
        # yfinance's period argument takes precedence over start_date and end_date
        # so we calculate the period based on the number of days
        days = config["days"]
        period = f"{days}d"
        start_date = BASE_DATE - timedelta(days=days)
        start_date_str = start_date.strftime('%Y-%m-%d')


    try:
        # RobustDataAcquisitionEngine's fetch_single_ticker takes interval and period
        ticker_instance, df = await engine.fetch_single_ticker(
            ticker=ticker,
            interval=interval,
            period=period
        )
        if df is not None and not df.empty:
            return {
                "status": "✅ 成功",
                "count": len(df),
                "start_date": df['date'].min().strftime('%Y-%m-%d'),
                "end_date": df['date'].max().strftime('%Y-%m-%d'),
            }
    except Exception as e:
        console.log(f"探測 {ticker} ({interval}) 時發生錯誤: {e}", style="bold red")

    return {"status": "❌ 失敗", "count": 0, "start_date": "N/A", "end_date": "N/A"}

async def main():
    """主執行函數"""
    report_content = [f"# 【普羅米修斯之火】全域數據可用性報告 (基準日: {BASE_DATE.strftime('%Y-%m-%d')})\n\n"]
    report_content.append("本報告旨在系統性地探測我們因子宇宙中所有數據點的真實可用性與歷史深度。\n\n")

    all_tickers = [ticker for details in ASSET_UNIVERSE.values() for ticker in details['tickers']]

    async with AppContext() as context:
        engine = RobustDataAcquisitionEngine(tickers=all_tickers)

        for category, details in ASSET_UNIVERSE.items():
            console.print(f"正在處理類別: [bold cyan]{category}[/bold cyan]")
            report_content.append(f"## {category}\n\n")
            report_content.append(f"{details['desc']}\n\n")
            report_content.append("| 資產代號 | 時間顆粒度 | 請求週期 | 狀態 | 數據筆數 | 最早日期 | 最晚日期 |\n")
            report_content.append("|:---|:---|:---|:---|:---|:---|:---|\n")

            for ticker in details['tickers']:
                for interval, config in PROBE_CONFIG.items():
                    console.print(f"  -> 正在探測 [yellow]{ticker}[/yellow] @ [magenta]{interval}[/magenta]...")
                    result = await probe_ticker(engine, ticker, interval, config)
                    report_content.append(
                        f"| `{ticker}` | `{interval}` | {config['label']} | {result['status']} | {result['count']} | {result['start_date']} | {result['end_date']} |\n"
                    )
            report_content.append("\n")

    report_filename = "DATA_AVAILABILITY_REPORT.md"
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write("".join(report_content))

    console.print(f"\n[bold green]報告已生成完畢：{report_filename}[/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
