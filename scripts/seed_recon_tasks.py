import sys
from pathlib import Path

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from prometheus.core.db.sqlite_queue import SQLiteQueue
from rich.console import Console

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
PROBE_CONFIG = {
    "1d": {"period": "max", "label": "最大歷史"},
    "1h": {"days": 729, "label": "過去 729 天"},
    "5m": {"days": 59, "label": "過去 59 天"},
    "1m": {"days": 6, "label": "過去 6 天"}
}

def main():
    """主執行函數"""
    queue = SQLiteQueue(db_path="output/recon_queue.sqlite", queue_name="recon_tasks")

    task_count = 0
    for category, details in ASSET_UNIVERSE.items():
        for ticker in details['tickers']:
            for interval, config in PROBE_CONFIG.items():
                task = {
                    "category": category,
                    "ticker": ticker,
                    "interval": interval,
                    "config": config
                }
                queue.put(task)
                task_count += 1

    console.print(f"[bold green]總共播種了 {task_count} 個偵察任務。[/bold green]")

if __name__ == "__main__":
    main()
