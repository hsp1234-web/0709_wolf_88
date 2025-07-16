# -*- coding: utf-8 -*-
"""
【作戰計畫 129】鳳凰協議
最終報告生成器 (Report Generator)
讀取最終匯總資料庫，並生成權威性 Markdown 報告。
"""
import duckdb
import pandas as pd
from pathlib import Path
from rich.console import Console
from datetime import datetime

console = Console()

def main():
    """主執行函數"""
    final_db_path = Path("data/db/recon_final.duckdb")
    report_path = Path("DATA_AVAILABILITY_REPORT.md")

    if not final_db_path.exists():
        console.print(f"[bold red]錯誤：找不到最終結果資料庫 {final_db_path}。請先執行戰果收集器。[/bold red]")
        return

    console.print(f"[blue]正在從 {final_db_path} 讀取最終偵察數據...[/blue]")

    try:
        conn = duckdb.connect(str(final_db_path), read_only=True)
        df = conn.execute("SELECT * FROM recon_results ORDER BY label, ticker").fetchdf()
        conn.close()
    except Exception as e:
        console.print(f"[bold red]讀取資料庫時發生錯誤: {e}[/bold red]")
        return

    if df.empty:
        console.print("[yellow]資料庫中沒有找到任何數據，無法生成報告。[/yellow]")
        return

    console.print(f"[green]成功讀取 {len(df)} 條偵察記錄。開始生成報告...[/green]")

    # --- 開始構建 Markdown 報告 ---
    report_content = []
    report_content.append("# **【鳳凰協議】數據可用性普查報告**")
    report_content.append(f"> :timer_clock: **報告生成時間：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # --- 1. 總覽儀表板 ---
    total_tickers = df["ticker"].nunique()
    ok_count = len(df[df["status"] == "OK"])
    no_data_count = len(df[df["status"] == "NO_DATA"])
    success_rate = (ok_count / len(df)) * 100 if len(df) > 0 else 0

    report_content.append("## :bar_chart: 一、戰況總覽")
    summary_table = [
        "| 指標 (Metric) | 數值 (Value) |",
        "|:---|:---:|",
        f"| :dart: **總偵察任務** | {len(df)} |",
        f"| :satellite: **獨立資產標的** | {total_tickers} |",
        f"| :white_check_mark: **數據可用 (OK)** | {ok_count} |",
        f"| :x: **數據缺失 (NO_DATA)** | {no_data_count} |",
        f"| :chart_with_upwards_trend: **數據覆蓋率** | **{success_rate:.2f}%** |"
    ]
    report_content.append("\n".join(summary_table))

    # --- 2. 按分類匯總 ---
    report_content.append("\n## :books: 二、按資產類別匯總")

    # 使用 pivot_table 來創建一個更清晰的視圖
    pivot_df = pd.pivot_table(df, values='ticker', index='label', columns='status', aggfunc='count', fill_value=0)
    if 'OK' not in pivot_df.columns:
        pivot_df['OK'] = 0
    if 'NO_DATA' not in pivot_df.columns:
        pivot_df['NO_DATA'] = 0

    pivot_df['總計'] = pivot_df['OK'] + pivot_df['NO_DATA']
    pivot_df['覆蓋率 (%)'] = (pivot_df['OK'] / pivot_df['總計'] * 100).fillna(0).round(2)

    # 轉換為 Markdown
    pivot_df.reset_index(inplace=True)
    pivot_df.rename(columns={'label': '資產類別', 'OK': '✅ 可用', 'NO_DATA': '❌ 缺失'}, inplace=True)

    report_content.append(pivot_df[['資產類別', '✅ 可用', '❌ 缺失', '總計', '覆蓋率 (%)']].to_markdown(index=False))

    # --- 3. 數據缺失詳情 ---
    report_content.append("\n## :mag: 三、數據缺失詳情")
    no_data_df = df[df["status"] == "NO_DATA"]
    if no_data_df.empty:
        report_content.append("\n> :tada: **好消息！所有偵察任務都找到了數據。**\n")
    else:
        report_content.append(no_data_df[['label', 'ticker', 'interval']].to_markdown(index=False))

    # --- 4. 數據可用性完整報告 ---
    report_content.append("\n## :clipboard: 四、完整偵察結果")
    # 格式化日期，處理 NaT
    df['start_date'] = pd.to_datetime(df['start_date']).dt.strftime('%Y-%m-%d').fillna('N/A')
    df['end_date'] = pd.to_datetime(df['end_date']).dt.strftime('%Y-%m-%d').fillna('N/A')
    # 格式化狀態圖標
    df['status'] = df['status'].apply(lambda s: '✅ OK' if s == 'OK' else '❌ NO_DATA')

    report_content.append(df[['label', 'ticker', 'interval', 'status', 'count', 'start_date', 'end_date']].to_markdown(index=False))

    # --- 寫入檔案 ---
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_content))
        console.print(f"\n[bold green]✅ 最終報告已成功生成至: [cyan]{report_path}[/cyan]")
    except Exception as e:
        console.print(f"[bold red]寫入報告檔案時發生錯誤: {e}[/bold red]")

if __name__ == "__main__":
    main()
