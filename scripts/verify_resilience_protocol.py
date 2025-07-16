# 檔案: scripts/verify_resilience_protocol.py
# --- 韌性驗證協議腳本 ---

import asyncio
import os
from unittest.mock import patch, AsyncMock

import pandas as pd
from rich.console import Console
from rich.table import Table

# --- 環境設定 ---
# 在導入我們自己的模組之前，設定 FINMIND_API_TOKEN
# 這樣即使 FinMindClient 初始化失敗，測試腳本也能顯示警告但繼續執行
os.environ["FINMIND_API_TOKEN"] = "test_token" # 測試時使用假 token

from prometheus.core.engines.omni_data_engine import OmniDataEngine
from prometheus.core.clients.yfinance import YFinanceClient

# --- 測試情境定義 ---
TEST_SCENARIOS = [
    {
        "name": "情境 1: 標準路徑",
        "symbol": "SPY",
        "interval": "1d",
        "mock_yfinance_failure": False,
        "expected_source": "yfinance",
        "expected_interval": "1d",
    },
    {
        "name": "情境 2: 數據源降級 (台股)",
        "symbol": "2330.TW",
        "interval": "1d",
        "mock_yfinance_failure": True,
        "expected_source": "finmind",
        "expected_interval": "1d",
    },
    {
        "name": "情境 3: 顆粒度降級",
        "symbol": "TLT",
        "interval": "5m",
        "mock_yfinance_failure": True, # 模擬分鐘線失敗
        "expected_source": "yfinance",
        "expected_interval": "1d",
    },
    {
        "name": "情境 4: 完全失敗",
        "symbol": "NONEXISTENT_TICKER_XYZ",
        "interval": "1d",
        "mock_yfinance_failure": True,
        "expected_source": "none",
        "expected_interval": "none",
    },
]

async def run_single_test(scenario: dict) -> str:
    """
    執行單一測試情境。
    - 模擬 yfinance 客戶端的失敗行為。
    - 呼叫 OmniDataEngine。
    - 比較實際結果與預期結果。
    """
    console = Console()
    console.print(f"[bold cyan]執行中: {scenario['name']}[/bold cyan]")

    engine = OmniDataEngine()

    # 為了模擬 FinMind 成功，我們需要確保它有一個可用的客戶端
    # 如果 FinMindClient 因為沒有 token 而初始化失敗，我們這裡模擬一個成功的假 client
    if scenario["expected_source"] == "finmind" and engine.finmind_client is None:
         # This is a simplified mock. A real scenario might need a more detailed mock object.
        engine.finmind_client = AsyncMock()
        engine.finmind_client.fetch_data.return_value = pd.DataFrame({"close": [100]})


    # 使用 patch 來模擬 yfinance 的失敗
    # 我們 patch 'fetch_data' 方法，讓它異步地返回一個空的 DataFrame
    patch_target = "src.prometheus.core.clients.yfinance.YFinanceClient.fetch_data"

    # 根據情境決定 fetch_data 的行為
    if scenario["mock_yfinance_failure"]:
        # 模擬 yfinance 第一次呼叫 (可能是分鐘線) 失敗
        # 模擬 yfinance 第二次呼叫 (可能是日線) 也失敗 (針對情境2, 4) 或成功 (針對情境3)
        if scenario['name'] == '情境 3: 顆粒度降級':
             side_effect = [
                pd.DataFrame(), # 第一次呼叫 (5m) 失敗
                pd.DataFrame({"Close": [1.0, 2.0]}) # 第二次呼叫 (1d) 成功
             ]
        else:
            side_effect = [pd.DataFrame(), pd.DataFrame()] # 總是失敗
    else:
        # 模擬 yfinance 成功
        side_effect = [pd.DataFrame({"Close": [1.0, 2.0]})]


    with patch(patch_target, new_callable=AsyncMock, side_effect=side_effect) as mock_fetch:
        # 特別處理 FinMind 的模擬
        if scenario["expected_source"] == "finmind":
             # We need to mock the finmind client's fetch_data to return a valid dataframe
             patch_finmind_target = "src.prometheus.core.clients.finmind.FinMindClient.fetch_data"
             with patch(patch_finmind_target, return_value=pd.DataFrame({"close": [100]})) as mock_finmind_fetch:
                data, source, interval = await engine.get_data(
                    symbol=scenario["symbol"], interval=scenario["interval"], period="1d"
                )
        else:
             data, source, interval = await engine.get_data(
                symbol=scenario["symbol"], interval=scenario["interval"], period="1d"
            )


    # 驗證結果
    is_source_match = source == scenario["expected_source"]
    is_interval_match = interval == scenario["expected_interval"]

    if is_source_match and is_interval_match:
        result = f"✅ [bold green]驗證通過[/bold green]"
        console.print(f"  [green]↳ 結果符合預期 (來源: {source}, 顆粒度: {interval})[/green]")
    else:
        result = f"❌ [bold red]邏輯不符[/bold red]"
        console.print(f"  [red]↳ 預期來源: {scenario['expected_source']}, 實際來源: {source}[/red]")
        console.print(f"  [red]↳ 預期顆粒度: {scenario['expected_interval']}, 實際顆粒度: {interval}[/red]")

    return result


async def main():
    """主執行流程，運行所有測試並打印報告。"""
    console = Console()
    table = Table(title="【韌性驗證協議】執行報告")
    table.add_column("測試情境", justify="left", style="cyan", no_wrap=True)
    table.add_column("預期來源", justify="center", style="magenta")
    table.add_column("預期顆粒度", justify="center", style="magenta")
    table.add_column("驗證結果", justify="center")

    for scenario in TEST_SCENARIOS:
        result = await run_single_test(scenario)
        table.add_row(
            scenario["name"],
            scenario["expected_source"],
            scenario["expected_interval"],
            result,
        )
        table.add_section()

    console.print(table)


if __name__ == "__main__":
    asyncio.run(main())
