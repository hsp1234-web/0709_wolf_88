import sys
from pathlib import Path

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from prometheus.core.config import ConfigManager
from prometheus.core.clients.fred import FredClient
from rich.console import Console

console = Console()

async def main():
    """主執行函數"""
    config = ConfigManager()
    fred_api_key = config.get("api_keys.fred")

    if not fred_api_key:
        console.print("[bold red]錯誤：找不到 FRED API 金鑰 (api_keys.fred)。請在設定中配置。[/bold red]")
        return

    console.print(f"✅ FRED API 金鑰已找到。")

    try:
        client = FredClient(api_key=fred_api_key)
        df = await client.get_series("T10Y2Y")

        if df is not None and not df.empty:
            console.print("\n[bold green]成功獲取 T10Y2Y 數據：[/bold green]")
            console.print(df.head())
        else:
            console.print("[bold red]錯誤：無法獲取 T10Y2Y 數據，但未引發例外。[/bold red]")

    except Exception as e:
        console.print(f"[bold red]獲取 FRED 數據時發生錯誤：{e}[/bold red]")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
