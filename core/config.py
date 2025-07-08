# -*- coding: utf-8 -*-
"""
核心設定模組
"""
import yaml
import json
import sys
import os

# 確定專案根目錄的策略：
# 假設此 core/config.py 檔案位於 <PROJECT_ROOT>/core/config.py
# 因此，專案根目錄是此檔案所在目錄的父目錄。
# 這種方式比依賴 __main__ 更可靠，尤其當模組被其他部分導入時。
try:
    # 如果此檔案是 <PROJECT_ROOT>/core/config.py
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    # 如果 __file__ 未定義 (例如在某些特殊執行環境)，退回到當前工作目錄
    # 這在測試時可能需要調整，或通過環境變數設定 PROJECT_ROOT
    PROJECT_ROOT = os.getcwd()


CONFIG_YAML_NAME = "config.yaml"
SOURCE_PRIORITY_JSON_NAME = "source_priority.json"

# 檔案的絕對路徑
CONFIG_YAML_PATH = os.path.join(PROJECT_ROOT, CONFIG_YAML_NAME)
SOURCE_PRIORITY_JSON_PATH = os.path.join(PROJECT_ROOT, SOURCE_PRIORITY_JSON_NAME)

def load_app_config():
    """
    在系統啟動時讀取所有必要的設定檔，並返回一個統一的設定物件。

    職責：
    1. 讀取位於專案根目錄的 'config.yaml'。
    2. 讀取位於專案根目錄的 'source_priority.json'。
    3. 如果任一關鍵設定檔缺失，則捕獲 FileNotFoundError，
       向 stdout 打印友善的錯誤報告，並以 SystemExit(1) 終止程式。
    4. 如果檔案格式錯誤，也打印報告並以 SystemExit(1) 終止。
    5. 如果所有設定檔成功讀取，則返回一個包含設定內容的字典。
    """
    config_data = {}
    priority_data = {}

    # 1. 讀取 config.yaml
    try:
        # print(f"DEBUG: Attempting to open {CONFIG_YAML_PATH}") # 用於測試時調試路徑
        with open(CONFIG_YAML_PATH, 'r', encoding='utf-8') as f_yaml:
            config_data = yaml.safe_load(f_yaml)
            if config_data is None: # 空的 yaml 檔案會 parse 成 None
                print(f"指揮官注意：核心配置檔案 '{CONFIG_YAML_NAME}' 為空或格式無效，將使用預設空配置。", file=sys.stdout)
                config_data = {}
        # print(f"DEBUG: Successfully loaded {CONFIG_YAML_NAME}")
    except FileNotFoundError:
        print(f"指揮官，系統啟動時發現核心配置檔案 '{CONFIG_YAML_NAME}' 缺失 (預期路徑: {CONFIG_YAML_PATH})。系統無法初始化，任務已終止。", file=sys.stdout)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"指揮官，核心配置檔案 '{CONFIG_YAML_NAME}' (路徑: {CONFIG_YAML_PATH}) 格式錯誤：{e}。系統無法初始化，任務已終止。", file=sys.stdout)
        sys.exit(1)

    # 2. 讀取 source_priority.json
    try:
        # print(f"DEBUG: Attempting to open {SOURCE_PRIORITY_JSON_PATH}")
        with open(SOURCE_PRIORITY_JSON_PATH, 'r', encoding='utf-8') as f_json:
            priority_data = json.load(f_json)
            if priority_data is None: # 空的 json 檔案可能 parse 成 None (取決於內容)
                print(f"指揮官注意：數據源優先級檔案 '{SOURCE_PRIORITY_JSON_NAME}' 為空或格式無效，將使用預設空配置。", file=sys.stdout)
                priority_data = {}
        # print(f"DEBUG: Successfully loaded {SOURCE_PRIORITY_JSON_NAME}")
    except FileNotFoundError:
        print(f"指揮官，系統啟動時發現數據源優先級檔案 '{SOURCE_PRIORITY_JSON_NAME}' 缺失 (預期路徑: {SOURCE_PRIORITY_JSON_PATH})。無法執行數據融合，任務已終止。", file=sys.stdout)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"指揮官，數據源優先級檔案 '{SOURCE_PRIORITY_JSON_NAME}' (路徑: {SOURCE_PRIORITY_JSON_PATH}) 格式錯誤：{e}。無法執行數據融合，任務已終止。", file=sys.stdout)
        sys.exit(1)

    # 合併設定
    return {
        "general_config": config_data,
        "source_priority": priority_data,
        "status": "Successfully loaded all configurations."
    }

if __name__ == '__main__':
    # 為了在本機直接執行此檔案進行基本測試，
    # 你可以在專案根目錄手動創建或移除 config.yaml 和 source_priority.json
    print("--- 模擬: 嘗試載入應用程式設定 ---")

    # 檢查並報告預期檔案路徑 (方便本地調試)
    print(f"預期 config.yaml 路徑: {CONFIG_YAML_PATH}")
    print(f"預期 source_priority.json 路徑: {SOURCE_PRIORITY_JSON_PATH}")

    # 創建臨時檔案以供測試 (如果不存在)
    temp_files_created = []
    if not os.path.exists(CONFIG_YAML_PATH):
        with open(CONFIG_YAML_PATH, 'w', encoding='utf-8') as f:
            yaml.dump({"sample_config": "value from temp file"}, f)
        print(f"提示: 創建了臨時 {CONFIG_YAML_NAME} 以供直接執行測試。")
        temp_files_created.append(CONFIG_YAML_PATH)

    if not os.path.exists(SOURCE_PRIORITY_JSON_PATH):
        with open(SOURCE_PRIORITY_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump({"default_source": "primary from temp file"}, f)
        print(f"提示: 創建了臨時 {SOURCE_PRIORITY_JSON_NAME} 以供直接執行測試。")
        temp_files_created.append(SOURCE_PRIORITY_JSON_PATH)

    try:
        app_settings = load_app_config()
        print("\n--- 模擬: 設定載入成功 ---")
        print(f"設定內容: {app_settings}")
    except SystemExit as e:
        # load_app_config 內部已經打印了錯誤訊息
        print(f"--- 模擬: 系統已按預期終止 (SystemExit code: {e.code}) ---")
    finally:
        # 清理此腳本創建的臨時檔案
        for temp_file_path in temp_files_created:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                print(f"提示: 移除了臨時 {os.path.basename(temp_file_path)}。")
        print("--- 模擬: 執行完畢 ---")
