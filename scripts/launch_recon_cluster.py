# -*- coding: utf-8 -*-
"""
【作戰計畫 129】鳳凰協議
集群啟動器 (Launcher)
一個極簡的、只負責下達命令的啟動器，用於並行啟動所有獨立的工人進程。
"""
import subprocess
import os
import sys
from rich.console import Console

console = Console()

def main():
    """主執行函數"""
    # 1. 偵察 CPU 核心數
    try:
        # os.sched_getaffinity(0) 在某些環境 (如 Windows 或非 Linux 的 Mac) 中不可用
        # os.cpu_count() 是更通用的選擇
        num_workers = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else os.cpu_count()
        if num_workers is None:
            console.print("[yellow]無法自動偵測 CPU 核心數，預設為 4。[/yellow]")
            num_workers = 4
    except Exception:
        console.print("[yellow]偵測 CPU 親和性失敗，回退到 os.cpu_count()。[/yellow]")
        num_workers = os.cpu_count() or 4

    console.print(f"[bold blue]偵測到 {num_workers} 個可用的 CPU 核心，將啟動等量的工人進程。[/bold blue]")

    processes = []

    # 確保 poetry run 在正確的環境中執行
    # sys.executable 指向當前 Python 解釋器，這通常位於 .venv/bin/python
    python_executable = sys.executable
    run_py_path = "run.py" # 假設 run.py 在專案根目錄

    for i in range(num_workers):
        # 2. 準備一個獨立的 CLI 命令
        # 使用 sys.executable (指向 venv 中的 python) 來確保我們運行的是正確的環境
        # 而不是依賴 'poetry run'，這樣更明確、更可移植
        command = [
            python_executable,
            run_py_path,
            "run-worker",
            "--worker-id",
            str(i)
        ]

        console.print(f"  [grey50]正在準備啟動工人 {i}: {' '.join(command)}[/grey50]")

        # 3. 使用 subprocess.Popen 並行地啟動所有獨立的工人進程
        # 我們不捕獲輸出，因為每個工人都會將日誌寫入自己的檔案
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(process)

    console.print(f"\n[bold green]✅ 所有 {num_workers} 個工人已成功啟動。現在等待它們完成任務...[/bold green]")
    console.print("[italic]您可以通過監控 'data/logs/' 和 'data/db/' 目錄來觀察進度。[/italic]")

    # 4. 等待所有子進程執行完畢
    for i, process in enumerate(processes):
        process.wait()
        if process.returncode != 0:
            console.print(f"[bold red]警告: 工人 {i} 以錯誤碼 {process.returncode} 退出。[/bold red]")
            console.print(f"[red]請檢查日誌檔案 'data/logs/recon_worker_{i}.log' 以獲取詳細資訊。[/red]")

    console.print("\n[bold green]🎉 所有工人進程均已執行完畢。集群攻擊結束。[/bold green]")

if __name__ == "__main__":
    main()
