# -*- coding: utf-8 -*-
"""
整合測試腳本：核心設定檔缺失模擬

此腳本用於驗證系統的初始化模組 (`core.config.load_app_config`)
在無法找到關鍵設定檔時，能否按預期終止並報告。
"""
import unittest
from unittest.mock import patch, mock_open, MagicMock
import io
import sys
import os
import json # 用於創建模擬的 JSON 內容
import yaml # 用於創建模擬的 YAML 內容

# 假設 core 模組在 tests 的同級目錄的 core 資料夾下
# 調整 sys.path 以便測試腳本能找到 core.config
try:
    from core.config import load_app_config, CONFIG_YAML_NAME, SOURCE_PRIORITY_JSON_NAME, PROJECT_ROOT
except ImportError:
    current_dir = os.path.dirname(os.path.abspath(__file__)) # tests/
    project_base_dir = os.path.dirname(current_dir) # <project_root>
    core_dir_path = os.path.join(project_base_dir, "core")
    if project_base_dir not in sys.path:
        sys.path.insert(0, project_base_dir)
    if core_dir_path not in sys.path: # 確保 core 目錄也在搜索路徑中 (如果 core 不是一個包，這可能不需要)
        sys.path.insert(0, core_dir_path)
    from core.config import load_app_config, CONFIG_YAML_NAME, SOURCE_PRIORITY_JSON_NAME, PROJECT_ROOT


class TestConfigMissing(unittest.TestCase):
    """
    測試核心設定檔缺失的情境。
    """

    def setUp(self):
        """
        每個測試方法執行前呼叫。
        設置 stdout 捕獲。
        """
        self.held_stdout = sys.stdout
        sys.stdout = io.StringIO()

    def tearDown(self):
        """
        每個測試方法執行後呼叫。
        恢復 stdout。
        """
        sys.stdout.close()
        sys.stdout = self.held_stdout
        # 如果在測試中修改了 os.environ 或其他全域狀態，應在此處恢復

    def mock_file_open(self, read_data_map, filepath, *args, **kwargs):
        """
        自訂的 side_effect 函數給 builtins.open。
        根據 filepath 決定是拋出 FileNotFoundError 還是返回一個模擬檔案物件。
        read_data_map: 一個字典，key 是檔案路徑，value 是檔案內容。
        """
        # 標準化路徑以進行比較 (例如，去除 ./, 處理 ..)
        normalized_filepath = os.path.normpath(filepath)

        # 從 read_data_map 中查找標準化後的路徑
        # 首先檢查 basename，然後檢查完整路徑，以增加靈活性
        file_basename = os.path.basename(normalized_filepath)

        if file_basename in read_data_map:
            content = read_data_map[file_basename]
            if content == FileNotFoundError:
                # print(f"DEBUG_MOCK: Raising FileNotFoundError for {file_basename} (path: {filepath})")
                raise FileNotFoundError(f"模擬的檔案未找到錯誤 for {file_basename}")

            # print(f"DEBUG_MOCK: Mocking open for {file_basename} (path: {filepath}) with content.")
            # mock_open 不能直接處理 bytes，但 read_data 可以是字串
            # PyYAML 和 json.load 通常期望字串
            mock_file = mock_open(read_data=content)
            return mock_file.return_value # 返回 mock_open 實例的 return_value (即模擬的檔案控制代碼)
        else:
            # 如果檔案不在 map 中，則可能是未預期的檔案開啟，可以選擇報錯或調用真實的 open
            # print(f"DEBUG_MOCK: Path {filepath} (normalized: {normalized_filepath}, basename: {file_basename}) not in read_data_map. Raising actual FileNotFoundError.")
            # 為避免干擾其他可能的 open 調用，這裡最好引發一個真正的 FileNotFoundError
            # 或者如果確定 load_app_config 只打開這兩個文件，可以更嚴格
            raise FileNotFoundError(f"真實的檔案未找到錯誤 for unmocked path: {filepath}")


    @patch('builtins.open')
    def test_config_yaml_missing(self, mock_open_func):
        """
        情境一：測試 config.yaml 缺失。
        `load_app_config` 應捕獲 FileNotFoundError，打印錯誤訊息，並以 SystemExit(1) 終止。
        """
        # 設定 mock_open 的 side_effect
        # 當嘗試打開 CONFIG_YAML_NAME 時，拋出 FileNotFoundError
        # SOURCE_PRIORITY_JSON_NAME 應該不會被嘗試打開，因為在 config.yaml 失敗後就會退出

        # 檔案路徑是相對於 PROJECT_ROOT，但 open 通常接收絕對路徑或相對於 CWD 的路徑
        # core.config.py 中使用的是 os.path.join(PROJECT_ROOT, CONFIG_YAML_NAME)
        # 我們需要確保 mock_open_func 攔截的是這個確切的路徑

        # 我們將讓 side_effect 決定行為
        # 注意：CONFIG_YAML_NAME 和 SOURCE_PRIORITY_JSON_NAME 只是檔案名稱
        # 在 core.config.py 中，它們與 PROJECT_ROOT 結合
        # 因此，我們的 mock_file_open 也應該基於檔案名稱來決定行為

        read_data_config = {
            CONFIG_YAML_NAME: FileNotFoundError,
            # SOURCE_PRIORITY_JSON_NAME 不應被讀取
        }
        mock_open_func.side_effect = lambda filepath, *args, **kwargs: self.mock_file_open(read_data_config, filepath, *args, **kwargs)

        with self.assertRaises(SystemExit) as cm:
            load_app_config()

        self.assertEqual(cm.exception.code, 1, "SystemExit 的退出碼應為 1")

        output = sys.stdout.getvalue()
        expected_message = f"指揮官，系統啟動時發現核心配置檔案 '{CONFIG_YAML_NAME}' 缺失 (預期路徑: {os.path.join(PROJECT_ROOT, CONFIG_YAML_NAME)})。系統無法初始化，任務已終止。"
        self.assertIn(expected_message, output, "未找到 config.yaml 缺失的預期錯誤報告")

    @patch('builtins.open')
    def test_source_priority_json_missing(self, mock_open_func):
        """
        情境二：測試 source_priority.json 缺失。
        `load_app_config` 應成功讀取 config.yaml (模擬)，然後在讀取 source_priority.json 時失敗，
        打印錯誤訊息，並以 SystemExit(1) 終止。
        """
        # 模擬 config.yaml 成功讀取的情況
        # 創建一個模擬的 YAML 內容
        mock_yaml_content = yaml.dump({"setting1": "value1", "setting2": True})

        # 模擬 source_priority.json 缺失
        read_data_config = {
            CONFIG_YAML_NAME: mock_yaml_content,
            SOURCE_PRIORITY_JSON_NAME: FileNotFoundError
        }
        mock_open_func.side_effect = lambda filepath, *args, **kwargs: self.mock_file_open(read_data_config, filepath, *args, **kwargs)

        with self.assertRaises(SystemExit) as cm:
            load_app_config()

        self.assertEqual(cm.exception.code, 1, "SystemExit 的退出碼應為 1")

        output = sys.stdout.getvalue()
        expected_message = f"指揮官，系統啟動時發現數據源優先級檔案 '{SOURCE_PRIORITY_JSON_NAME}' 缺失 (預期路徑: {os.path.join(PROJECT_ROOT, SOURCE_PRIORITY_JSON_NAME)})。無法執行數據融合，任務已終止。"
        self.assertIn(expected_message, output, "未找到 source_priority.json 缺失的預期錯誤報告")

        # 額外驗證：確保 config.yaml 被模擬成功讀取，沒有打印 config.yaml 的錯誤
        unexpected_config_yaml_error = f"指揮官，系統啟動時發現核心配置檔案 '{CONFIG_YAML_NAME}' 缺失"
        self.assertNotIn(unexpected_config_yaml_error, output, "不應出現 config.yaml 缺失的報告")


    @patch('builtins.open')
    def test_config_yaml_format_error(self, mock_open_func):
        """
        額外測試：config.yaml 存在但格式錯誤。
        """
        invalid_yaml_content = "key: value: another_value" # 無效的 YAML

        read_data_config = {
            CONFIG_YAML_NAME: invalid_yaml_content,
            # SOURCE_PRIORITY_JSON_NAME 不應被讀取
        }
        mock_open_func.side_effect = lambda filepath, *args, **kwargs: self.mock_file_open(read_data_config, filepath, *args, **kwargs)

        with self.assertRaises(SystemExit) as cm:
            load_app_config()

        self.assertEqual(cm.exception.code, 1)
        output = sys.stdout.getvalue()
        expected_message_part = f"指揮官，核心配置檔案 '{CONFIG_YAML_NAME}' (路徑: {os.path.join(PROJECT_ROOT, CONFIG_YAML_NAME)}) 格式錯誤"
        self.assertIn(expected_message_part, output, "未找到 config.yaml 格式錯誤的預期報告")

    @patch('builtins.open')
    def test_source_priority_json_format_error(self, mock_open_func):
        """
        額外測試：source_priority.json 存在但格式錯誤。
        """
        mock_yaml_content = yaml.dump({"valid_yaml": True})
        invalid_json_content = "{'key': 'value_missing_quote}" # 無效的 JSON

        read_data_config = {
            CONFIG_YAML_NAME: mock_yaml_content,
            SOURCE_PRIORITY_JSON_NAME: invalid_json_content
        }
        mock_open_func.side_effect = lambda filepath, *args, **kwargs: self.mock_file_open(read_data_config, filepath, *args, **kwargs)

        with self.assertRaises(SystemExit) as cm:
            load_app_config()

        self.assertEqual(cm.exception.code, 1)
        output = sys.stdout.getvalue()
        expected_message_part = f"指揮官，數據源優先級檔案 '{SOURCE_PRIORITY_JSON_NAME}' (路徑: {os.path.join(PROJECT_ROOT, SOURCE_PRIORITY_JSON_NAME)}) 格式錯誤"
        self.assertIn(expected_message_part, output, "未找到 source_priority.json 格式錯誤的預期報告")


if __name__ == '__main__':
    unittest.main()
