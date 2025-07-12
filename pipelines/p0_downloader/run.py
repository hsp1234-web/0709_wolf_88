import argparse
import os
import random
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests

# --- 全域配置 (可移至設定檔) ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
]
BASE_URL = "https://www.taifex.com.tw"


def execute_download(session, task_info, output_dir):
    """執行單一檔案下載任務，包含重試與錯誤處理。"""
    file_path = os.path.join(output_dir, task_info["file_name"])
    if os.path.exists(file_path):
        return "exists", f"檔案已存在: {task_info['file_name']}"

    time.sleep(random.uniform(task_info["min_delay"], task_info["max_delay"]))

    for attempt in range(3):  # 重試3次
        try:
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Referer": task_info.get("referer", BASE_URL),
            }
            response = (
                session.post(
                    task_info["url"],
                    data=task_info.get("payload", {}),
                    headers=headers,
                    timeout=120,
                )
                if task_info.get("payload")
                else session.get(task_info["url"], headers=headers, timeout=120)
            )

            if (
                response.status_code == 200
                and len(response.content) > 100
                and "查無資料" not in response.text
            ):
                os.makedirs(output_dir, exist_ok=True)
                with open(file_path, "wb") as f:
                    f.write(response.content)
                return "success", f"成功下載: {task_info['file_name']}"
            elif response.status_code == 404:
                return "not_found", f"404 Not Found: {task_info['file_name']}"
            else:
                return (
                    "error",
                    f"伺服器錯誤 {response.status_code}: {task_info['file_name']}",
                )

        except requests.exceptions.RequestException as e:
            if attempt == 2:
                return "error", f"網路請求失敗: {e}"
            time.sleep(5 * (attempt + 1))

    return "error", f"達到最大重試次數: {task_info['file_name']}"


def main():
    parser = argparse.ArgumentParser(description="TAIFEX 自動化數據採集器 v1.0")
    parser.add_argument("--start-date", required=True, help="下載開始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="下載結束日期 (YYYY-MM-DD)")
    parser.add_argument("--output-dir", default="data/downloads", help="檔案儲存目錄")
    parser.add_argument(
        "--max-workers", type=int, default=16, help="最大同時下載任務數"
    )
    args = parser.parse_args()

    print("--- 啟動數據採集任務 ---")
    print(f"時間範圍: {args.start_date} 到 {args.end_date}")
    print(f"輸出目錄: {args.output_dir}")

    tasks = []
    start_dt = datetime.strptime(args.start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end_date, "%Y-%m-%d")
    date_range = [
        start_dt + timedelta(days=x) for x in range((end_dt - start_dt).days + 1)
    ]

    for current_date in date_range:
        date_str = current_date.strftime("%Y_%m_%d")
        # 範例：僅下載期貨逐筆資料
        tasks.append(
            {
                "url": f"{BASE_URL}/file/taifex/Dailydownload/DailydownloadCSV/Daily_{date_str}.zip",
                "file_name": f"Daily_{date_str}.zip",
                "min_delay": 0.2,
                "max_delay": 1.0,
            }
        )

    results_counter = Counter()
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        with requests.Session() as session:
            future_to_task = {
                executor.submit(execute_download, session, task, args.output_dir): task
                for task in tasks
            }
            for future in as_completed(future_to_task):
                try:
                    status, message = future.result()
                    results_counter[status] += 1
                    print(f"[{status.upper()}] {message}")
                except Exception as exc:
                    print(f"[CRITICAL] 任務執行異常: {exc}")

    print("\n--- 採集任務總結 ---")
    for status, count in results_counter.items():
        print(f"  {status}: {count} 個")


if __name__ == "__main__":
    main()
