# apps/fmp_client/config.py
import os

class FMPConfig:
    """
    FMP 客戶端設定類別。
    """
    # 優先從環境變數讀取 API Key
    API_KEY = os.getenv("FMP_API_KEY")

    # FMP API 基礎 URL (不含版本)
    BASE_URL = "https://financialmodelingprep.com/api"

    # 預設 API 版本
    DEFAULT_API_VERSION = "v3"

    # 預設數據輸出目錄
    DEFAULT_OUTPUT_PATH_PRICES = "data/fmp_data/prices"
    DEFAULT_OUTPUT_PATH_FINANCIALS = "data/fmp_data/financials"

    # 可以在這裡加入其他的預設設定，例如：
    # DEFAULT_TIMEOUT = 30  # seconds
    # DEFAULT_RETRY_ATTEMPTS = 3

    @staticmethod
    def get_api_key() -> str:
        """
        獲取 FMP API Key。
        如果環境變數 FMP_API_KEY 未設定，則拋出 ValueError。

        Returns:
            str: FMP API Key.

        Raises:
            ValueError: 如果 API Key 未設定。
        """
        key = FMPConfig.API_KEY
        if not key:
            raise ValueError(
                "FMP API key 未設定。"
                "請設定 FMP_API_KEY 環境變數，"
                "或在初始化 Client/執行 run.py 時手動傳入 key。"
            )
        return key

# 使用範例 (通常由 client.py 或 run.py 間接使用)
if __name__ == '__main__':
    try:
        key = FMPConfig.get_api_key()
        print(f"成功獲取 FMP API Key (前三碼): {key[:3]}...")
    except ValueError as e:
        print(f"錯誤: {e}")
        print("請確保已設定 FMP_API_KEY 環境變數。")

    print(f"FMP API 基礎 URL: {FMPConfig.BASE_URL}")
    print(f"預設 API 版本: {FMPConfig.DEFAULT_API_VERSION}")
    print(f"預設價格數據輸出路徑: {FMPConfig.DEFAULT_OUTPUT_PATH_PRICES}")
    print(f"預設財報數據輸出路徑: {FMPConfig.DEFAULT_OUTPUT_PATH_FINANCIALS}")

"""
此 `config.py` 檔案目的：
1.  集中管理 FMP 客戶端相關的設定，例如 API Key, API 基礎 URL, 和預設輸出路徑。
2.  提供一個標準的方式來獲取這些設定值。
3.  使設定與客戶端的核心邏輯分離，方便未來修改設定。

`client.py` 和 `run.py` 目前是直接使用 `os.getenv` 或透過參數傳遞 API Key。
它們可以被修改來使用此 `config.py` 以獲得更集中的管理 (例如，如果 API Key 未在參數中提供，則嘗試從 `FMPConfig.get_api_key()` 獲取)。
現階段，此 `config.py` 檔案作為一個已建立的結構，供未來可能的重構或擴展設定時使用，
同時 `run.py` 和 `client.py` 仍保持其現有的 API Key 處理優先順序 (參數 > 環境變數)。
"""
