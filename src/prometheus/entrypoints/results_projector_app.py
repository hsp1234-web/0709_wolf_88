import time

from prometheus.core.queue.sqlite_queue import SQLiteQueue

# 【核心】定義一個所有工作者都認可的、明確的關閉信號
POISON_PILL = "STOP_WORKING"


def projector_loop(results_queue: SQLiteQueue):
    """
    一個遵守鋼鐵契約的結果投影器：永不放棄，直到收到毒丸。
    """
    print("[Projector] 結果投影器已啟動，正在等待結果...")

    while True:
        try:
            # 【核心改變】get() 現在會一直阻塞，直到拿到結果或毒丸
            result = results_queue.get(block=True)

            # 【核心改變】檢查是否收到了下班指令
            if result == POISON_PILL:
                print("[Projector] 收到關閉信號，正在優雅退出...")
                break  # 退出 while 迴圈

            # 簡單地打印結果，在真實應用中這裡會寫入數據庫
            print(f"[Projector] 收到結果: {result}")

        except Exception as e:
            # 即使單一結果出錯，也絕不退出，繼續等待下一個
            print(f"!!!!!! [Projector] 處理結果時發生錯誤: {e} !!!!!!")
            time.sleep(5)

    print("[Projector] 已成功關閉。")
