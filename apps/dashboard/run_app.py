# -*- coding: utf-8 -*-
"""
互動式市場儀表板應用程式
"""

import logging
import webbrowser
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.db.db_manager import DBManager

logger = logging.getLogger(__name__)


def main():
    """
    儀表板應用的主進入點。
    """
    logger.info("--- [Dashboard App] 啟動 ---")

    # 1. 讀取數據
    table_name = "hourly_market_data"
    try:
        with DBManager() as db:
            df = db.connection.table(table_name).to_df()
        logger.info(f"成功從 '{table_name}' 讀取 {len(df)} 行數據。")
    except Exception as e:
        logger.error(f"無法從數據庫讀取數據，請先執行數據管線。錯誤: {e}", exc_info=True)
        return

    df['timestamp'] = pd.to_datetime(df.index)

    # 2. 建立圖表
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        specs=[[{"type": "candlestick"}], [{"type": "bar"}], [{"type": "scatter"}]],
    )

    # 圖表一：K線圖與選擇權位
    fig.add_trace(
        go.Candlestick(
            x=df['timestamp'],
            open=df['spy_open'],
            high=df['spy_high'],
            low=df['spy_low'],
            close=df['spy_close'],
            name="SPY 價格",
        ),
        row=1,
        col=1,
    )
    fig.add_hline(y=df['spy_call_wall'].iloc[-1], line_dash="dash", line_color="red",
                  annotation_text="Call Wall", annotation_position="bottom right", row=1, col=1)
    fig.add_hline(y=df['spy_put_wall'].iloc[-1], line_dash="dash", line_color="green",
                  annotation_text="Put Wall", annotation_position="top right", row=1, col=1)

    # 圖表二：GEX
    df['spy_gex_total'] = df['spy_gex_total'].fillna(0)
    colors = ['green' if val >= 0 else 'red' for val in df['spy_gex_total']]
    fig.add_trace(
        go.Bar(x=df['timestamp'], y=df['spy_gex_total'], name="GEX", marker_color=colors),
        row=2,
        col=1,
    )

    # 圖表三：RSI
    fig.add_trace(
        go.Scatter(x=df['timestamp'], y=df['spy_rsi_14_1h'], name="RSI", mode="lines"),
        row=3,
        col=1,
    )
    fig.add_hline(y=70, line_dash="dash", line_color="orange", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="orange", row=3, col=1)

    # 3. 更新版面佈局
    fig.update_layout(
        title_text="互動式市場儀表板",
        xaxis_rangeslider_visible=False,
        height=800,
    )
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    fig.update_xaxes(showticklabels=False, row=2, col=1)

    # 4. 匯出 HTML
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "market_dashboard.html"

    fig.write_html(output_path)
    logger.info(f"儀表板已成功匯出至: {output_path}")

    # 5. 自動開啟
    try:
        webbrowser.open(output_path.resolve().as_uri())
        logger.info("已在預設瀏覽器中開啟儀表板。")
    except Exception as e:
        logger.warning(f"無法自動開啟瀏覽器，請手動開啟檔案。錯誤: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
