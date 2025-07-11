# -*- coding: utf-8 -*-
from __future__ import annotations  # 添加未來註解

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List  # Added Dict

import yaml

"""
核心設定模組
"""
LOG_LEVEL = "INFO"
SUBPROCESS_TIMEOUT = 300

try:
    PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
except NameError:
    PROJECT_ROOT = Path(os.getcwd())

CONFIG_YAML_NAME = "config.yaml"
SOURCE_PRIORITY_JSON_NAME = "source_priority.json"

CONFIG_YAML_PATH = PROJECT_ROOT / CONFIG_YAML_NAME
SOURCE_PRIORITY_JSON_PATH = PROJECT_ROOT / SOURCE_PRIORITY_JSON_NAME

TARGETS: List[str] = []


def load_app_config() -> Dict[str, Any]:
    """
    在系統啟動時讀取所有必要的設定檔，並返回一個統一的設定物件。
    """
    config_data: Dict[str, Any] = {}
    priority_data: Dict[str, Any] = {}

    try:
        with open(CONFIG_YAML_PATH, "r", encoding="utf-8") as f_yaml:
            loaded_yaml = yaml.safe_load(f_yaml)
            if loaded_yaml is None:
                print(
                    f"指揮官注意：核心配置檔案 '{CONFIG_YAML_NAME}' 為空或格式無效，將使用預設空配置。",
                    file=sys.stdout,
                )
                config_data = {}
            else:
                config_data = loaded_yaml
    except FileNotFoundError:
        print(
            f"指揮官，系統啟動時發現核心配置檔案 '{CONFIG_YAML_NAME}' 缺失 (預期路徑: {CONFIG_YAML_PATH})。系統無法初始化，任務已終止。",
            file=sys.stdout,
        )
        sys.exit(1)
    except yaml.YAMLError as e:
        print(
            f"指揮官，核心配置檔案 '{CONFIG_YAML_NAME}' (路徑: {CONFIG_YAML_PATH}) 格式錯誤：{e}。系統無法初始化，任務已終止。",
            file=sys.stdout,
        )
        sys.exit(1)

    try:
        with open(SOURCE_PRIORITY_JSON_PATH, "r", encoding="utf-8") as f_json:
            loaded_json = json.load(f_json)
            if loaded_json is None:
                print(
                    f"指揮官注意：數據源優先級檔案 '{SOURCE_PRIORITY_JSON_NAME}' 為空或格式無效，將使用預設空配置。",
                    file=sys.stdout,
                )
                priority_data = {}
            else:
                priority_data = loaded_json
    except FileNotFoundError:
        print(
            f"指揮官，系統啟動時發現數據源優先級檔案 '{SOURCE_PRIORITY_JSON_NAME}' 缺失 (預期路徑: {SOURCE_PRIORITY_JSON_PATH})。無法執行數據融合，任務已終止。",
            file=sys.stdout,
        )
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(
            f"指揮官，數據源優先級檔案 '{SOURCE_PRIORITY_JSON_NAME}' (路徑: {SOURCE_PRIORITY_JSON_PATH}) 格式錯誤：{e}。無法執行數據融合，任務已終止。",
            file=sys.stdout,
        )
        sys.exit(1)

    return {
        "general_config": config_data,
        "source_priority": priority_data,
        "status": "Successfully loaded all configurations.",
    }


if __name__ == "__main__":
    print("--- 模擬: 嘗試載入應用程式設定 ---")
    print(f"預期 config.yaml 路徑: {CONFIG_YAML_PATH}")
    print(f"預期 source_priority.json 路徑: {SOURCE_PRIORITY_JSON_PATH}")
    temp_files_created: List[Path] = []
    if not os.path.exists(CONFIG_YAML_PATH):
        with open(CONFIG_YAML_PATH, "w", encoding="utf-8") as f:
            yaml.dump({"sample_config": "value from temp file"}, f)
        print(f"提示: 創建了臨時 {CONFIG_YAML_NAME} 以供直接執行測試。")
        temp_files_created.append(CONFIG_YAML_PATH)
    if not os.path.exists(SOURCE_PRIORITY_JSON_PATH):
        with open(SOURCE_PRIORITY_JSON_PATH, "w", encoding="utf-8") as f:
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
                print(f"提示: 移除了臨時 {os.path.basename(str(temp_file_path))}。")
        print("--- 模擬: 執行完畢 ---")
