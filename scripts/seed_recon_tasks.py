import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from inject_env import inject_poetry_env
inject_poetry_env()

from prometheus.core.queue.sqlite_queue import SQLiteQueue
from rich.console import Console
import os

console = Console()

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
# ReconWorker 將直接使用 period 或 days
PROBE_CONFIG = {
    "1d": {"period": "10y", "label": "過去10年日線"},
    "1h": {"period": "730d", "label": "過去730天小時線"}, # yfinance a little over 2 years
    "5m": {"period": "60d", "label": "過去60天5分鐘線"}, # yfinance max
    "1m": {"period": "7d", "label": "過去7天1分鐘線"} # yfinance max
}


def main():
    """主執行函數"""
    db_path = "recon_tasks.sqlite"
    # 清理舊的佇列檔案
    if os.path.exists(db_path):
        os.remove(db_path)
        console.print(f"[yellow]已刪除舊的任務佇列檔案: {db_path}[/yellow]")

    queue = SQLiteQueue(db_path=db_path, table_name="recon_tasks")

    task_count = 0
    for category, details in ASSET_UNIVERSE.items():
        for ticker in details['tickers']:
            # 對於每個 ticker，我們只探測最重要的 '1d' 資料
            # 這是為了簡化和加速【鳳凰協議】的首次運行
            # 後續可以輕鬆擴展到所有 PROBE_CONFIG
            interval = "1d"
            config = PROBE_CONFIG[interval]

            task = {
                "ticker": ticker,
                "interval": interval,
                "period": config.get("period"), # 直接傳遞 period
                "label": f"{category} - {config['label']}"
            }
            queue.put(task)
            task_count += 1

    console.print(f"[bold green]✅ 總共播種了 {task_count} 個基礎偵察任務。[/bold green]")
    queue.close()

if __name__ == "__main__":
    main()
