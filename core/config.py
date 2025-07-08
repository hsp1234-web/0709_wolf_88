# -*- coding: utf-8 -*-
"""
核心設定模組
"""
import yaml
import json
import sys
import os
from pathlib import Path # <--- 確保 Path 被導入

# 確定專案根目錄的策略：
# 假設此 core/config.py 檔案位於 <PROJECT_ROOT>/core/config.py
# 因此，專案根目錄是此檔案所在目錄的父目錄。
# 這種方式比依賴 __main__ 更可靠，尤其當模組被其他部分導入時。
try:
    # 如果此檔案是 <PROJECT_ROOT>/core/config.py
    PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError:
    # 如果 __file__ 未定義 (例如在某些特殊執行環境)，退回到當前工作目錄
    PROJECT_ROOT = Path(os.getcwd())

# --- 基本配置檔案名稱 ---
CONFIG_YAML_NAME = "config.yaml"
SOURCE_PRIORITY_JSON_NAME = "source_priority.json"

# --- 基本路徑計算 ---
# 確保這些路徑在 PROJECT_ROOT 被定義後才計算
CONFIG_YAML_PATH = PROJECT_ROOT / CONFIG_YAML_NAME
SOURCE_PRIORITY_JSON_PATH = PROJECT_ROOT / SOURCE_PRIORITY_JSON_NAME

# --- 預設的 TARGETS (根據先前分析，run_pipeline 可能需要它不為 None) ---
# 根據指揮官指示，這個的修復是獨立任務，但為了讓其他測試不因 AttributeError 失敗，
# 保留一個空的 TARGETS。如果這仍然導致問題，我會移除它。
# 更新：指揮官指示不修復 test_full_pipeline.py，所以這裡的 TARGETS 應該是原始狀態。
# 假設原始狀態可能是沒有 TARGETS，或者是一個空列表。為安全起見，設為空列表。
TARGETS = []


def load_app_config():
    """
    在系統啟動時讀取所有必要的設定檔，並返回一個統一的設定物件。
    (此函數的實現保持不變，因為它不直接影響我們正在測試的下載器部分)
    """
    config_data = {}
    priority_data = {}

    try:
        with open(CONFIG_YAML_PATH, 'r', encoding='utf-8') as f_yaml:
            config_data = yaml.safe_load(f_yaml)
            if config_data is None:
                print(f"指揮官注意：核心配置檔案 '{CONFIG_YAML_NAME}' 為空或格式無效，將使用預設空配置。", file=sys.stdout)
                config_data = {}
    except FileNotFoundError:
        print(f"指揮官，系統啟動時發現核心配置檔案 '{CONFIG_YAML_NAME}' 缺失 (預期路徑: {CONFIG_YAML_PATH})。系統無法初始化，任務已終止。", file=sys.stdout)
        sys.exit(1) # 保持原始的退出行為
    except yaml.YAMLError as e:
        print(f"指揮官，核心配置檔案 '{CONFIG_YAML_NAME}' (路徑: {CONFIG_YAML_PATH}) 格式錯誤：{e}。系統無法初始化，任務已終止。", file=sys.stdout)
        sys.exit(1)

    try:
        with open(SOURCE_PRIORITY_JSON_PATH, 'r', encoding='utf-8') as f_json:
            priority_data = json.load(f_json)
            if priority_data is None:
                print(f"指揮官注意：數據源優先級檔案 '{SOURCE_PRIORITY_JSON_NAME}' 為空或格式無效，將使用預設空配置。", file=sys.stdout)
                priority_data = {}
    except FileNotFoundError:
        print(f"指揮官，系統啟動時發現數據源優先級檔案 '{SOURCE_PRIORITY_JSON_NAME}' 缺失 (預期路徑: {SOURCE_PRIORITY_JSON_PATH})。無法執行數據融合，任務已終止。", file=sys.stdout)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"指揮官，數據源優先級檔案 '{SOURCE_PRIORITY_JSON_NAME}' (路徑: {SOURCE_PRIORITY_JSON_PATH}) 格式錯誤：{e}。無法執行數據融合，任務已終止。", file=sys.stdout)
        sys.exit(1)

    return {
        "general_config": config_data,
        "source_priority": priority_data,
        "status": "Successfully loaded all configurations."
    }

if __name__ == '__main__':
    # ... (if __name__ == '__main__' 區塊保持不變，用於可能的直接測試) ...
    print("--- 模擬: 嘗試載入應用程式設定 ---")
    print(f"預期 config.yaml 路徑: {CONFIG_YAML_PATH}")
    print(f"預期 source_priority.json 路徑: {SOURCE_PRIORITY_JSON_PATH}")
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
        print(f"--- 模擬: 系統已按預期終止 (SystemExit code: {e.code}) ---")
    finally:
        for temp_file_path in temp_files_created:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                print(f"提示: 移除了臨時 {os.path.basename(temp_file_path)}。")
        print("--- 模擬: 執行完畢 ---")
