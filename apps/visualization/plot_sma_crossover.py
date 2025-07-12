# In apps/visualization/plot_sma_crossover.py
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


def generate_plot(csv_path: Path, output_html_path: Path):
    """
    讀取 SMA 交叉分析結果，並生成互動式 Plotly 圖表。

    核心邏輯:
    1. 讀取 CSV 數據。
    2. 使用 Plotly.graph_objects 建立圖表。
    3. 繪製主要線條：價格、短期 SMA、長期 SMA。
    4. 找出信號點 (交叉點)，並在圖上添加顯著的買/賣標記。
    5. 設定圖表標題、座標軸等樣式。
    6. 將圖表儲存為 HTML 檔案。
    """
    print(f"--- 開始生成視覺化圖表，讀取數據來源: {csv_path} ---")
    if not csv_path.exists():
        print(f"❌ 錯誤：找不到輸入檔案 {csv_path}。請先執行作戰計畫 025 的分析管線。")
        return

    # 步驟 1: 讀取數據
    df = pd.read_csv(csv_path, index_col="datetime", parse_dates=True)

    # 步驟 2: 建立圖表物件
    fig = go.Figure()

    # 步驟 3: 繪製主要線條
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["spy_close"],
            mode="lines",
            name="SPY 收盤價",
            line=dict(color="black", width=1),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["short_sma"],
            mode="lines",
            name="20H SMA",
            line=dict(color="blue", width=1),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["long_sma"],
            mode="lines",
            name="50H SMA",
            line=dict(color="orange", width=1),
        )
    )

    # 步驟 4: 繪製買賣信號標記
    buy_signals = df[df["signal"] == 1.0]
    sell_signals = df[df["signal"] == -1.0]

    fig.add_trace(
        go.Scatter(
            x=buy_signals.index,
            y=buy_signals["short_sma"],
            mode="markers",
            name="買進信號 (黃金交叉)",
            marker=dict(color="green", symbol="triangle-up", size=10),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=sell_signals.index,
            y=sell_signals["short_sma"],
            mode="markers",
            name="賣出信號 (死亡交叉)",
            marker=dict(color="red", symbol="triangle-down", size=10),
        )
    )

    # 步驟 5: 設定圖表樣式
    fig.update_layout(
        title="SPY 小時線 SMA 交叉信號視覺化",
        xaxis_title="日期",
        yaxis_title="價格 (USD)",
        legend_title="圖例",
        template="plotly_white",
    )

    # 步驟 6: 儲存為 HTML
    output_html_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_html_path))
    print(f"✔ 視覺化圖表已成功儲存至: {output_html_path}")


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent.parent
    # 定義輸入與輸出路徑
    input_file = project_root / "output" / "sma_crossover_result.csv"
    output_file = project_root / "output" / "sma_crossover_chart.html"
    generate_plot(input_file, output_file)
