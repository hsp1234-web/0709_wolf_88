# 檔案: src/prometheus/entrypoints/ai_analyst_app.py
import json
from pathlib import Path
import pandas as pd
import vectorbt as vbt

# --- 檔案路徑 ---
DATA_DIR = Path("data")
REPORTS_DIR = DATA_DIR / "reports"
HALL_OF_FAME_PATH = DATA_DIR / "hall_of_fame.json"
OHLCV_DATA_PATH = DATA_DIR / "ohlcv_data.csv"
EQUITY_CURVE_PATH = REPORTS_DIR / "equity_curve.png"
ANALYSIS_REPORT_PATH = REPORTS_DIR / "analysis_report.md"

# --- 模擬 Gemini 客戶端 ---
class MockGeminiClient:
    def generate_report(self, prompt: str) -> str:
        print("\n[AI-Analyst] 正在調用模擬的 Gemini API...")
        # 在真實場景中，這裡會是 API 呼叫
        # 為了演示，我們返回一個基於提示的簡單模板化回應
        return """
**AI 洞察**

*   **行為模式分析**: 根據回測數據，此策略似乎在市場呈現溫和上漲趨勢時表現最佳。它利用短期動量進場，並在相對強弱指標（RSI）顯示超買時退出，這是一種典型的「趨勢跟隨」與「均值回歸」的混合策略。

*   **潛在風險**: 該策略在橫盤震盪市場中可能會因為頻繁的進出場而產生較多交易成本，從而侵蝕利潤。此外，在市場出現劇烈反轉時，基於RSI的出場信號可能滯後，導致較大的回撤。

*   **建議**: 建議在實際部署前，對策略的參數進行更細緻的優化，特別是針對不同的市場波動率進行調整。同時，可以考慮加入止損訂單來限制最大虧損。
"""

def get_best_strategy():
    """從名人堂讀取最佳策略。"""
    if not HALL_OF_FAME_PATH.exists():
        print(f"[AI-Analyst] 錯誤: 名人堂檔案不存在於 {HALL_OF_FAME_PATH}")
        return None
    with open(HALL_OF_FAME_PATH, "r") as f:
        return json.load(f)

def run_backtest(strategy_genome, price_data):
    """使用 vectorbt 執行回測。"""
    # 這裡我們需要一個策略函數來解釋基因體
    # 為了簡化，我們假設基因體直接對應到某個指標的參數
    # 例如：基因體的前兩個值是快慢均線的窗口
    fast_ma_window = int(strategy_genome[0] * 10) + 5  # 示例：窗口範圍 5-15
    slow_ma_window = int(strategy_genome[1] * 30) + 20 # 示例：窗口範圍 20-50

    fast_ma = vbt.MA.run(price_data, fast_ma_window)
    slow_ma = vbt.MA.run(price_data, slow_ma_window)

    entries = fast_ma.ma_crossed_above(slow_ma)
    exits = fast_ma.ma_crossed_below(slow_ma)

    portfolio = vbt.Portfolio.from_signals(price_data, entries, exits, init_cash=100000)
    return portfolio

def generate_markdown_report(stats, equity_curve_path):
    """生成 Markdown 格式的分析報告。"""

    # 從 stats Series 中提取指標
    total_return = stats['Total Return [%]']
    max_drawdown = stats['Max Drawdown [%]']
    sharpe_ratio = stats['Sharpe Ratio']
    calmar_ratio = stats['Calmar Ratio']

    # 模擬 Gemini 客戶端生成 AI 洞察
    client = MockGeminiClient()
    # 為了簡化，我們傳遞一個固定的 prompt
    ai_insights = client.generate_report("請分析此策略")

    report_content = f"""
# AI 首席分析師報告

## 策略概述

本報告旨在分析從演化計算中脫穎而出的最佳交易策略。我們將透過回測來評估其歷史表現，並提供由 AI 生成的洞察。

## 核心績效指標

| 指標           | 數值                  |
| -------------- | --------------------- |
| 總回報 (%)     | {total_return:.2f}    |
| 最大回撤 (%)   | {max_drawdown:.2f}    |
| 夏普比率       | {sharpe_ratio:.2f}    |
| 卡瑪比率       | {calmar_ratio:.2f}    |

## 權益曲線

![權益曲線]({equity_curve_path.name})

{ai_insights}
"""
    return report_content.strip()


def ai_analyst_job():
    """AI 分析師的主工作流程。"""
    print("[AI-Analyst] AI 首席分析師已啟動。")

    # 1. 確保報告目錄存在
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 2. 讀取最佳策略和價格數據
    strategy_data = get_best_strategy()
    if not strategy_data:
        return

    if not OHLCV_DATA_PATH.exists():
        print(f"[AI-Analyst] 錯誤: 價格數據檔案不存在於 {OHLCV_DATA_PATH}")
        return

    price_data = pd.read_csv(OHLCV_DATA_PATH, index_col='Date', parse_dates=True)['Close']

    # 3. 執行回測
    print("[AI-Analyst] 正在對最佳策略進行回測...")
    portfolio = run_backtest(strategy_data["genome"], price_data)
    stats = portfolio.stats()

    # 4. 生成並儲存權益曲線圖
    print(f"[AI-Analyst] 正在生成權益曲線圖並儲存至 {EQUITY_CURVE_PATH}...")
    fig = portfolio.plot()
    fig.write_image(EQUITY_CURVE_PATH)

    # 5. 生成並儲存 Markdown 報告
    print(f"[AI-Analyst] 正在生成 Markdown 分析報告...")
    report_content = generate_markdown_report(stats, EQUITY_CURVE_PATH)

    try:
        with open(ANALYSIS_REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(report_content)
        print("\n" + "="*20 + " 任務完成 " + "="*20)
        print(f"🎉 分析報告已成功生成！請查看: {ANALYSIS_REPORT_PATH}")
        print(f"📈 權益曲線圖已儲存！請查看: {EQUITY_CURVE_PATH}")
        print("="*52)
    except Exception as e:
        print(f"!!!!!! [AI-Analyst] 儲存報告失敗: {e} !!!!!!")

if __name__ == "__main__":
    ai_analyst_job()
