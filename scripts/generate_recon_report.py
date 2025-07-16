import duckdb
import pandas as pd
from rich.console import Console

console = Console()

def main():
    """主執行函數"""
    conn = duckdb.connect("output/recon_results.duckdb")
    df = conn.execute("SELECT * FROM recon_results ORDER BY category, ticker, interval").fetchdf()
    conn.close()

    report_content = [f"# 【普羅米修斯之火】全域數據可用性報告 (持久化偵察版)\n\n"]
    report_content.append("本報告旨在系統性地探測我們因子宇宙中所有數據點的真實可用性與歷史深度。\n\n")

    current_category = None
    for index, row in df.iterrows():
        if row['category'] != current_category:
            if current_category is not None:
                report_content.append("\n")
            current_category = row['category']
            report_content.append(f"## {current_category}\n\n")
            # Assuming the description is not stored in the db, we can't add it here.
            report_content.append("| 資產代號 | 時間顆粒度 | 請求週期 | 狀態 | 數據筆數 | 最早日期 | 最晚日期 |\n")
            report_content.append("|:---|:---|:---|:---|:---|:---|:---|\n")

        report_content.append(
            f"| `{row['ticker']}` | `{row['interval']}` | {row['label']} | {row['status']} | {row['count']} | {row['start_date']} | {row['end_date']} |\n"
        )
    report_content.append("\n")

    report_filename = "DATA_AVAILABILITY_REPORT.md"
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write("".join(report_content))

    console.print(f"\n[bold green]報告已生成完畢：{report_filename}[/bold green]")

if __name__ == "__main__":
    main()
