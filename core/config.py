# -*- coding: utf-8 -*-
import yaml
from typing import Any, Dict

class ConfigManager:
    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls, config_path: str = 'config.yml'):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            # 當首次創建實例時，立即載入設定檔
            # 避免在 _load_config 中再次嘗試創建 cls._instance
            cls._instance._config = {} # 初始化 _config 以免 AttributeError
            cls._instance._load_config(config_path)
        return cls._instance

    def _load_config(self, config_path: str):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                # 直接更新實例的 _config 字典
                self.__class__._config.update(yaml.safe_load(f))
                print(f"資訊：設定檔 '{config_path}' 載入成功。")
        except FileNotFoundError:
            print(f"警告：找不到設定檔 '{config_path}'。將使用預設值或空值。")
            # self.__class__._config remains as it was (e.g. {} if first load failed)
        except Exception as e:
            print(f"錯誤：載入設定檔 '{config_path}' 時發生錯誤: {e}")
            # self.__class__._config remains as it was

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        # 從類別層級的 _config 獲取值
        value = self.__class__._config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError, AttributeError): # AttributeError for initial empty _config
            # print(f"DEBUG: Key '{key}' not found or value is None, returning default '{default}'")
            return default

# 建立一個全域實例，方便在專案中各處直接導入使用
# 確保在模組加載時，ConfigManager('config.yml') 被調用一次以加載配置。
config = ConfigManager(config_path='config.yml') # 指定路徑

def get_fred_api_key() -> str:
    """一個專用的輔助函數，用於安全地獲取 FRED API 金鑰。"""
    # 直接從全域 config 實例獲取
    key = config.get('api_keys.fred')
    if not key or key == "YOUR_FRED_API_KEY_HERE": # 檢查是否為預留位置
        print("錯誤：FRED API 金鑰未在 config.yml 中正確設定或仍為預留位置。")
        raise ValueError("錯誤：FRED API 金鑰未在 config.yml 中正確設定或仍為預留位置。")
    return key

if __name__ == '__main__':
    print("--- 設定檔管理器測試 ---")
    # 重新載入設定以確保測試時是最新的（或創建一個新的臨時實例）
    # test_config = ConfigManager(config_path='config.yml') # 確保測試使用的是最新的

    db_path = config.get('database.path', 'default.db')
    print(f"資料庫路徑: {db_path}")

    retries = config.get('data_acquisition.retries', 0)
    print(f"重試次數: {retries}")

    non_existent = config.get('non_existent.key', '預設值')
    print(f"不存在的鍵: {non_existent}")

    try:
        api_key = get_fred_api_key()
        # 安全起見，不在日誌中打印金鑰本身
        print(f"成功讀取 FRED API Key (長度: {len(api_key)})")
    except ValueError as e:
        print(e)

    # 測試直接從 config 實例獲取金鑰
    fred_key_direct = config.get("api_keys.fred")
    if fred_key_direct and fred_key_direct != "YOUR_FRED_API_KEY_HERE":
        print(f"直接從 config 實例獲取 FRED API Key (長度: {len(fred_key_direct)})")
    else:
        print("無法直接從 config 實例獲取有效的 FRED API Key。")

    print("--- 測試結束 ---")
