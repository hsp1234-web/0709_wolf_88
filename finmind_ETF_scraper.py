# -*- coding: utf-8 -*-
"""
模擬的 FinMind ETF 爬蟲模組
"""
import requests
import sys

def fetch_etf_data(parameter_date: str):
    """
    模擬從 FinMind API 獲取指定日期的 ETF 數據。
    在實際應用中，這裡會包含完整的 API 請求和數據處理邏輯。
    """
    # 模擬 API 端點，實際情況下應為完整的 FinMind API URL
    # 例如：api_url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanExchangeTradedFund&data_id=0050&start_date={parameter_date}&end_date={parameter_date}"
    # 為了測試，我們使用一個無效的 URL 來確保 requests.get 被 mock
    api_url = "http://localhost/fake_finmind_api"

    print(f"指揮官，數據獲取模組開始嘗試連接 FinMind API 以獲取 {parameter_date} 的數據...")

    try:
        # 在實際的爬蟲中，requests.get 通常會被使用
        # 我們將在測試中 mock requests.get 或 requests.Session.get
        # 這裡我們假設直接使用 requests.get
        response = requests.get(api_url, timeout=10) # 模擬設置超時
        response.raise_for_status() # 如果狀態碼是 4xx 或 5xx，則拋出 HTTPError

        # 假設成功獲取數據後的處理
        print(f"指揮官，已成功從 FinMind API 獲取 {parameter_date} 的數據。")
        return {"data": "模擬的ETF數據"}

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print("指揮官，數據獲取模組在連接 FinMind API 時遇到權限問題 (403 Forbidden)。請檢查 API 金鑰或權限設定。", file=sys.stdout)
            # 在實際應用中，這裡可能還會有日誌記錄、重試邏輯或向監控系統發送警報等操作。
            # 為了符合測試要求，我們不讓程式崩潰
            return None # 或 raise SystemExit("API 權限問題")
        else:
            print(f"指揮官，數據獲取模組在連接 FinMind API 時遇到未預期的 HTTP 錯誤：{e}", file=sys.stdout)
            return None # 或 raise SystemExit(f"API HTTP 錯誤: {e}")

    except requests.exceptions.Timeout:
        print("指揮官，數據獲取模組在連接 FinMind API 時因超時而失敗。網路連線可能不穩定或 API 服務繁忙。", file=sys.stdout)
        # 實際應用中可能需要重試或通知
        return None # 或 raise SystemExit("API 連線超時")

    except requests.exceptions.RequestException as e:
        # 捕獲其他所有 requests 可能的異常，例如 DNS 解析失敗、連線被拒等
        print(f"指揮官，數據獲取模組在連接 FinMind API 時遇到網路連線問題：{e}", file=sys.stdout)
        return None # 或 raise SystemExit(f"API 連線問題: {e}")

if __name__ == '__main__':
    # 模擬呼叫
    print("--- 模擬正常情況 ---")
    fetch_etf_data("2023-01-01")
    print("\n--- 模擬手動觸發異常 (下方應有 requests 庫的錯誤訊息) ---")
    # 為了演示 try-except，這裡可以嘗試連接一個不存在的服務，但測試時會 mock requests.get
    try:
        requests.get("http://nonexistent-finmind-api.example.com", timeout=1)
    except requests.exceptions.RequestException as e:
        print(f"手動模擬請求失敗: {e}")
