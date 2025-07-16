# -*- coding: utf-8 -*-
from typing import Any, Dict

import yaml

from prometheus.core.logging.log_manager import LogManager

logger = LogManager.get_instance().get_logger("ConfigManager")


class ConfigManager:
    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls, config_path: str = "config.yml"):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        cls._instance._load_config(config_path)
        return cls._instance

    def _load_config(self, config_path: str):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.__class__._config.update(yaml.safe_load(f))
                logger.info(f"設定檔 '{config_path}' 載入成功。")
        except FileNotFoundError:
            logger.warning(f"找不到設定檔 '{config_path}'。將使用預設值或空值。")
        except Exception as e:
            logger.error(f"載入設定檔 '{config_path}' 時發生錯誤: {e}", exc_info=True)

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = self.__class__._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value


# 建立一個全域實例，方便在專案中各處直接導入使用
# 確保在模組加載時，ConfigManager('config.yml') 被調用一次以加載配置。
config = ConfigManager(config_path="config.yml")  # 指定路徑


def get_fred_api_key() -> str:
    """一個專用的輔助函數，用於安全地獲取 FRED API 金鑰。"""
    key = config.get("api_keys.fred")
    if not key or "YOUR_REAL" in key:
        error_msg = "FRED API 金鑰未在 config.yml 中正確設定或仍為預留位置。"
        logger.error(error_msg)
        raise ValueError(error_msg)
    return key


if __name__ == "__main__":
    print("--- 設定檔管理器測試 ---")
    # 重新載入設定以確保測試時是最新的（或創建一個新的臨時實例）
    # test_config = ConfigManager(config_path='config.yml') # 確保測試使用的是最新的

    db_path = config.get("database.path", "default.db")
    print(f"資料庫路徑: {db_path}")

    retries = config.get("data_acquisition.retries", 0)
    print(f"重試次數: {retries}")

    non_existent = config.get("non_existent.key", "預設值")
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
