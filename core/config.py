# core/config.py
import yaml
from pathlib import Path
from typing import Any, Dict, Optional # Added Optional for type hinting

# 為了確保 core.logger 能被正確初始化 (它可能依賴 core.config 來設定日誌級別)
# 我們需要小心處理循環導入。
# 一個簡單的方法是讓 core.config 不直接依賴 core.logger 進行自身的日誌記錄，
# 或者延遲 core.logger 的導入。
# 在此，我們假設 core.config 自身的初始化過程不需要複雜的日誌記錄。

class Config:
    _instance: Optional['Config'] = None # Type hint for _instance
    _config_data: Dict[str, Any] = {}

    def __new__(cls) -> 'Config': # Return type hint
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            # 在實例首次創建時載入配置
            cls._instance._load_config() # Use a "private" method for loading
        return cls._instance

    def _load_config(self) -> None: # Underscore to indicate internal use
        """載入位於專案根目錄的 config.yml"""
        # __file__ 是當前 config.py 的路徑
        # Path(__file__).parent 是 core/
        # Path(__file__).parent.parent 是專案根目錄
        config_path = Path(__file__).parent.parent / "config.yml"

        if not config_path.exists():
            # 考慮到這是一個核心模組，拋出錯誤比默默失敗更好
            # 實際應用中，這裡也可以嘗試從環境變數或其他來源載入預設配置
            raise FileNotFoundError(f"核心設定檔 config.yml 未在預期路徑找到: {config_path}")

        try:
            with open(config_path, 'r', encoding='utf-8') as f: # 指定 utf-8 編碼
                loaded_yaml = yaml.safe_load(f)
            if loaded_yaml is None: # 如果 YAML 檔案為空或只包含註解
                self._config_data = {}
                # 可以考慮在此處記錄一個警告，如果 logger 可用的話
                # print("警告: 設定檔 config.yml 為空或只包含註解。") # 暫時用 print
            else:
                self._config_data = loaded_yaml
        except yaml.YAMLError as e:
            # YAML 解析錯誤
            # print(f"錯誤: 解析設定檔 config.yml 失敗: {e}") # 暫時用 print
            raise ValueError(f"解析設定檔 config.yml 失敗: {e}") from e
        except Exception as e:
            # 其他檔案讀取等錯誤
            # print(f"錯誤: 載入設定檔 config.yml 時發生未知錯誤: {e}") # 暫時用 print
            raise RuntimeError(f"載入設定檔 config.yml 時發生未知錯誤: {e}") from e


    def get(self, key: str, default: Any = None) -> Any:
        """
        用點狀路徑獲取設定值，例如 'global.log_level' 或 'news_client.api_key'
        """
        keys = key.split('.')
        value = self._config_data

        # 確保 _config_data 已被初始化 (雖然 __new__ 中會調用 _load_config)
        if not value and key: # 如果配置為空但嘗試獲取 key
             # print(f"警告: 設定資料為空，但嘗試獲取鍵 '{key}'。返回預設值。") # 暫時用 print
             return default

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                # print(f"警告: 在設定中未找到鍵 '{k}' (完整路徑: '{key}')。返回預設值。") # 暫時用 print
                return default
        return value

    def get_section(self, section_key: str) -> Optional[Dict[str, Any]]:
        """
        獲取設定檔中的整個區段 (section)。
        例如 get_section('news_client') 會返回 news_client 下的所有設定。
        """
        section_data = self._config_data.get(section_key)
        if isinstance(section_data, dict):
            return section_data
        # print(f"警告: 在設定中未找到名為 '{section_key}' 的區段，或其不是一個字典。") # 暫時用 print
        return None # 或者返回一個空字典 {}，取決於期望的行為

# 建立一個全域可用的單例
# 首次導入 core.config 時，Config 類別的 __new__ 會被調用，
# _load_config() 會執行，config.yml 的內容會被載入。
try:
    config = Config()
except Exception as e:
    # 如果在 Config 初始化過程中發生任何錯誤 (例如 FileNotFoundError, ValueError, RuntimeError)
    # 我們需要一種方式來處理這種情況，因為 config 可能在很多地方被導入。
    # 一個選項是讓錯誤傳播出去，這會導致應用程式啟動失敗，通常是期望的行為，
    # 因為核心配置失敗意味著應用無法正常運行。
    # 另一個選項是設置一個 "無效" 的 config 物件，但這會使錯誤更難追蹤。
    # 目前，我們讓錯誤直接拋出。
    print(f"嚴重錯誤: 核心配置模組 (core.config) 初始化失敗: {e}")
    # 為了讓其他模組在導入時不立即崩潰，可以提供一個備用的 "空" Config，
    # 但這會掩蓋問題。更好的做法是確保 config.yml 始終存在且格式正確。
    # 或者，應用程式的入口點應該捕獲這個異常。
    # 為了讓系統在測試或某些情況下仍能導入，這裡可以創建一個空的 Config 實例
    # 但在實際運行中，這應該導致啟動失敗。
    # config = object() # 創建一個假的 config，這樣導入不會失敗，但使用會出錯。
    # 更安全的做法是讓錯誤傳播。
    raise # 重新拋出異常，使問題更明顯
