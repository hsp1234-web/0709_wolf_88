# -*- coding: utf-8 -*-
"""
【作戰計畫 129】鳳凰協議
戰果收集器 (Gatherer)
負責將所有獨立工人的偵察結果合併到一個最終的資料庫中。
"""
import duckdb
import glob
from pathlib import Path
from rich.console import Console
from rich.progress import track

console = Console()

def main():
    """主執行函數"""
    db_dir = Path("data/db")
    final_db_path = db_dir / "recon_final.duckdb"
    worker_db_pattern = str(db_dir / "recon_worker_*.duckdb")

    worker_db_files = glob.glob(worker_db_pattern)

    if not worker_db_files:
        console.print("[bold yellow]未找到任何工人的結果資料庫。[/bold yellow]")
        return

    console.print(f"[bold blue]找到 {len(worker_db_files)} 個工人的結果資料庫。準備開始合併...[/bold blue]")

    # 如果最終資料庫已存在，先刪除，確保是全新合併
    if final_db_path.exists():
        final_db_path.unlink()
        console.print(f"[yellow]已刪除舊的最終結果資料庫: {final_db_path}[/yellow]")

    # 連接到最終資料庫
    final_conn = duckdb.connect(str(final_db_path))

    # 創建目標表格
    # 這個 schema 必須與 DuckDBWriter 中創建的 recon_results 表格一致
    final_conn.execute("""
        CREATE TABLE IF NOT EXISTS recon_results (
            category VARCHAR,
            ticker VARCHAR,
            interval VARCHAR,
            label VARCHAR,
            status VARCHAR,
            count INTEGER,
            start_date VARCHAR,
            end_date VARCHAR
        )
    """)

    total_rows_imported = 0

    # 遍歷所有工人的資料庫並導入數據
    for db_file in track(worker_db_files, description="正在合併戰果..."):
        try:
            worker_conn = duckdb.connect(str(db_file), read_only=True)
            # 使用 ATTACH DATABASE，然後從附加的資料庫中查詢
            # 這是合併 DuckDB 檔案的最高效方法之一
            db_name = Path(db_file).stem
            final_conn.execute(f"ATTACH '{db_file}' AS {db_name} (READ_ONLY)")

            # 從附加的資料庫中將數據插入主資料庫
            insert_query = f"INSERT INTO recon_results SELECT * FROM {db_name}.recon_results;"
            result = final_conn.execute(insert_query)

            # DuckDBPyRelation.execute() 返回一個 DuckDBPyRelation，沒有直接的 rowcount
            # 我們可以通過查詢來驗證
            count_query = f"SELECT COUNT(*) FROM {db_name}.recon_results;"
            rows_in_worker_db = final_conn.execute(count_query).fetchone()[0]
            total_rows_imported += rows_in_worker_db

            final_conn.execute(f"DETACH {db_name}")
            worker_conn.close()

        except Exception as e:
            console.print(f"[bold red]處理檔案 {db_file} 時發生錯誤: {e}[/bold red]")

    console.print(f"[bold green]✅ 戰果合併完成！總共從 {len(worker_db_files)} 個工人資料庫導入了 {total_rows_imported} 條記錄。[/bold green]")
    console.print(f"最終結果已儲存至: [cyan]{final_db_path}[/cyan]")

    # 顯示總結
    console.print("\n[bold]--- 最終結果預覽 ---[/bold]")
    summary_df = final_conn.execute("SELECT category, status, COUNT(*) as count FROM recon_results GROUP BY category, status ORDER BY category, status").fetchdf()
    console.print(summary_df)

    final_conn.close()

if __name__ == "__main__":
    main()
