# apps/finmind_client/config.py
import os

class FinMindConfig:
    """
    FinMind 客戶端設定類別。
    目前主要用於管理 API Token，但未來可以擴展其他設定。
    """
    # 優先從環境變數讀取 API Token
    API_TOKEN = os.getenv("FINMIND_API_TOKEN")

    # FinMind API 基礎 URL
    BASE_URL = "https://api.finmindtrade.com/api/v4/data"

    # 預設數據輸出目錄
    DEFAULT_OUTPUT_PATH = "data/finmind_data"

    # 可以在這裡加入其他的預設設定，例如：
    # DEFAULT_TIMEOUT = 30  # seconds
    # DEFAULT_RETRY_ATTEMPTS = 3

    @staticmethod
    def get_api_token() -> str:
        """
        獲取 FinMind API Token。
        如果環境變數 FINMIND_API_TOKEN 未設定，則拋出 ValueError。

        Returns:
            str: FinMind API Token.

        Raises:
            ValueError: 如果 API Token 未設定。
        """
        token = FinMindConfig.API_TOKEN
        if not token:
            raise ValueError(
                "FinMind API token 未設定。"
                "請設定 FINMIND_API_TOKEN 環境變數，"
                "或在初始化 Client 時手動傳入 token。"
            )
        return token

# 使用範例 (通常由 client.py 或 run.py 間接使用)
if __name__ == '__main__':
    try:
        token = FinMindConfig.get_api_token()
        print(f"成功獲取 FinMind API Token (前三碼): {token[:3]}...")
    except ValueError as e:
        print(f"錯誤: {e}")
        print("請確保已設定 FINMIND_API_TOKEN 環境變數。")

    print(f"FinMind API 基礎 URL: {FinMindConfig.BASE_URL}")
    print(f"預設輸出路徑: {FinMindConfig.DEFAULT_OUTPUT_PATH}")

"""
此 `config.py` 檔案目的：
1.  集中管理 FinMind 客戶端相關的設定，例如 API Token 和 API 的基礎 URL。
2.  提供一個標準的方式來獲取這些設定值。
3.  使設定與客戶端的核心邏輯分離，方便未來修改設定而不需要大幅更動 `client.py` 或 `run.py`。

目前 `client.py` 是直接使用 `os.getenv`，可以考慮修改 `client.py` 來使用此 `config.py` 以獲得更集中的管理。
不過，由於 `client.py` 的 `__init__` 函數已經允許傳入 `api_token`，
且 `run.py` 也允許透過命令列參數傳入，目前的彈性已經足夠。
此 `config.py` 可以作為一個備選的設定來源或未來擴展使用。

為了讓 `client.py` 和 `run.py` 能夠利用這個 `config.py` (如果決定這樣做)，
它們需要導入 `FinMindConfig` 並使用例如 `FinMindConfig.get_api_token()` 或 `FinMindConfig.BASE_URL`。
現階段，我會保持 `client.py` 和 `run.py` 的現有 API Token 處理方式 (優先參數傳入，其次環境變數)，
這個 `config.py` 檔案作為一個已建立的結構，供未來可能的重構或擴展設定時使用。
"""
