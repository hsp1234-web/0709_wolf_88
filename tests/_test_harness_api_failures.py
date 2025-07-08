# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import tempfile
from pathlib import Path
import asyncio
import aiohttp # 需要導入以模擬其內部的錯誤類型
import os # 需要 os 來輔助路徑校正
import logging # 用於捕獲日誌輸出

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    project_root = Path(os.getcwd())
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    print(f"警告：__file__ 未定義於 _test_harness_api_failures.py，專案路徑校正可能不準確。", file=sys.stderr)
# --- 標準化「路徑自我校正」樣板碼 END ---

# 直接導入目標函數和自定義異常
from apps.taifex_data_pipeline.run import main as taifex_main, TaifexDownloadError
from apps.taifex_data_pipeline.run import EXIT_CODE_DOWNLOAD_ERROR, EXIT_CODE_NO_DATA_AVAILABLE

class TestApiFailures(unittest.TestCase):
    temp_output_dir: Path

    def setUp(self):
        test_method_name = self.id().split('.')[-1]
        self.temp_output_dir = Path(tempfile.mkdtemp(prefix=f"taifex_api_fail_{test_method_name}_"))
        # print(f"\n[SETUP] 測試 {test_method_name} 的臨時目錄已創建: {self.temp_output_dir}")

    def tearDown(self):
        import shutil
        # print(f"[TEARDOWN] 準備清理測試 {self.id().split('.')[-1]} 的臨時目錄: {self.temp_output_dir}")
        if self.temp_output_dir.exists():
            try:
                shutil.rmtree(self.temp_output_dir)
                # print(f"[TEARDOWN] 臨時目錄已成功刪除: {self.temp_output_dir}")
            except Exception as e:
                print(f"[TEARDOWN_ERROR] 清理臨時目錄 {self.temp_output_dir} 失敗: {e}", file=sys.stderr)
        # else:
            # print(f"[TEARDOWN] 臨時目錄不存在，無需清理: {self.temp_output_dir}")

    # 移除了 _run_script_and_assert_failure，因為我們不再使用 subprocess

    @patch('apps.taifex_data_pipeline.run.setup_logger') # Mock setup_logger
    @patch('apps.taifex_data_pipeline.run.download_taifex_data')
    @patch('sys.exit')
    def test_download_handles_client_connector_error(self, mock_sys_exit: MagicMock, mock_download_taifex_data: MagicMock, mock_setup_logger: MagicMock):
        """測試：當 download_taifex_data 拋出源自 ClientConnectorError 的 TaifexDownloadError 時，main 函數是否會用返回碼 1 呼叫 sys.exit。"""
        # 1. 設定 Mock Logger
        mock_logger = MagicMock(spec=logging.Logger)
        mock_setup_logger.return_value = mock_logger

        # 2. 模擬：讓 download_taifex_data 拋出預期的錯誤
        #    ClientConnectorError 通常包含一個 connection_key 和一個 os_error
        #    我們需要確保 TaifexDownloadError 的原因鏈與原始錯誤一致
        original_os_error = OSError("Simulated OS error for connector")
        # 為了避免深入 aiohttp 內部 mock ConnectionKey 的複雜性，
        # 我們創建一個真實的 ClientConnectorError 實例（如果可能），
        # 或者 mock 其 __str__ 方法以避免 AttributeError。
        # 這裡我們選擇 mock __str__。
        # 首先，創建一個簡單的 mock connection_key，因為 ClientConnectorError 需要它
        mock_conn_key_for_error = MagicMock()
        original_connector_error = aiohttp.ClientConnectorError(
            mock_conn_key_for_error,
            original_os_error
        )
        # 然後 patch 這個實例的 __str__ 方法
        original_connector_error.__str__ = MagicMock(return_value="Simulated ClientConnectorError string")

        mock_download_taifex_data.side_effect = TaifexDownloadError(f"Network connection error: {original_connector_error}")

        # 3. 執行：直接調用 main 函數，傳遞模擬的命令列參數
        target_date = "2024-01-15"
        test_args = ['run.py', '--date', target_date, '--output-dir', str(self.temp_output_dir), '--log-level', 'ERROR']
        with patch('sys.argv', test_args):
            asyncio.run(taifex_main()) # <--- 修改：使用 asyncio.run()

        # 4. 驗收：斷言 sys.exit 是否被以參數 EXIT_CODE_DOWNLOAD_ERROR (即 1) 呼叫
        mock_sys_exit.assert_called_once_with(EXIT_CODE_DOWNLOAD_ERROR)

        # 5. 驗收 (可選但推薦): 檢查日誌輸出是否包含預期的錯誤訊息
        #    這需要 mock logger 被正確呼叫。
        #    run.py 中的 main 函數會在捕獲 TaifexDownloadError 時記錄 "捕獲到 TAIFEX 下載錯誤: {e}"
        #    而 download_taifex_data 內部會記錄更詳細的錯誤，例如 "[ERROR] Network connection error for {date_str_yyyy_mm_dd}: {e}. URL: {download_url}"
        #    由於我們 mock 了 download_taifex_data，它內部的日誌不會發生。
        #    我們應該檢查 main 函數捕獲異常後的日誌。
        logged_error = False
        for call_args in mock_logger.error.call_args_list:
            if f"捕獲到 TAIFEX 下載錯誤: Network connection error: {original_connector_error}" in call_args[0][0]:
                logged_error = True
                break
        self.assertTrue(logged_error, f"預期的錯誤日誌未被記錄。日誌呼叫: {mock_logger.error.call_args_list}")

        # 6. 驗收：輸出目錄應為空
        items_in_output_dir = list(self.temp_output_dir.iterdir())
        self.assertEqual(len(items_in_output_dir), 0,
                         f"輸出目錄 {self.temp_output_dir} 在失敗情境下應為空，但包含: {[item.name for item in items_in_output_dir]}")

    @patch('apps.taifex_data_pipeline.run.setup_logger')
    @patch('apps.taifex_data_pipeline.run.download_taifex_data')
    @patch('sys.exit')
    def test_download_handles_server_error_503(self, mock_sys_exit: MagicMock, mock_download_taifex_data: MagicMock, mock_setup_logger: MagicMock):
        """測試：當 download_taifex_data 拋出源自 HTTP 503 的 TaifexDownloadError 時，main 函數是否會用返回碼 1 呼叫 sys.exit。"""
        mock_logger = MagicMock(spec=logging.Logger)
        mock_setup_logger.return_value = mock_logger

        error_message = "Failed to download data. HTTP Status: 503"
        mock_download_taifex_data.side_effect = TaifexDownloadError(error_message)

        target_date = "2024-01-16"
        test_args = ['run.py', '--date', target_date, '--output-dir', str(self.temp_output_dir), '--log-level', 'ERROR']
        with patch('sys.argv', test_args):
            asyncio.run(taifex_main()) # <--- 修改：使用 asyncio.run()

        mock_sys_exit.assert_called_once_with(EXIT_CODE_DOWNLOAD_ERROR)

        logged_error = False
        for call_args in mock_logger.error.call_args_list:
            if f"捕獲到 TAIFEX 下載錯誤: {error_message}" in call_args[0][0]:
                logged_error = True
                break
        self.assertTrue(logged_error, f"預期的錯誤日誌未被記錄。日誌呼叫: {mock_logger.error.call_args_list}")

        items_in_output_dir = list(self.temp_output_dir.iterdir())
        self.assertEqual(len(items_in_output_dir), 0,
                         f"輸出目錄 {self.temp_output_dir} 在失敗情境下應為空，但包含: {[item.name for item in items_in_output_dir]}")

    @patch('apps.taifex_data_pipeline.run.setup_logger')
    @patch('apps.taifex_data_pipeline.run.download_taifex_data')
    @patch('sys.exit')
    def test_download_handles_timeout_error(self, mock_sys_exit: MagicMock, mock_download_taifex_data: MagicMock, mock_setup_logger: MagicMock):
        """測試：當 download_taifex_data 拋出源自 TimeoutError 的 TaifexDownloadError 時，main 函數是否會用返回碼 1 呼叫 sys.exit。"""
        mock_logger = MagicMock(spec=logging.Logger)
        mock_setup_logger.return_value = mock_logger

        original_timeout_error = asyncio.TimeoutError("Simulated timeout")
        mock_download_taifex_data.side_effect = TaifexDownloadError(f"Timeout during download: {original_timeout_error}")

        target_date = "2024-01-17"
        test_args = ['run.py', '--date', target_date, '--output-dir', str(self.temp_output_dir), '--log-level', 'ERROR']
        with patch('sys.argv', test_args):
            asyncio.run(taifex_main()) # <--- 修改：使用 asyncio.run()

        mock_sys_exit.assert_called_once_with(EXIT_CODE_DOWNLOAD_ERROR)

        logged_error = False
        for call_args in mock_logger.error.call_args_list:
            if f"捕獲到 TAIFEX 下載錯誤: Timeout during download: {original_timeout_error}" in call_args[0][0]:
                logged_error = True
                break
        self.assertTrue(logged_error, f"預期的錯誤日誌未被記錄。日誌呼叫: {mock_logger.error.call_args_list}")

        items_in_output_dir = list(self.temp_output_dir.iterdir())
        self.assertEqual(len(items_in_output_dir), 0,
                         f"輸出目錄 {self.temp_output_dir} 在失敗情境下應為空，但包含: {[item.name for item in items_in_output_dir]}")

    @patch('apps.taifex_data_pipeline.run.setup_logger')
    @patch('apps.taifex_data_pipeline.run.download_taifex_data')
    @patch('sys.exit')
    def test_download_preserves_no_data_behavior_on_404(self, mock_sys_exit: MagicMock, mock_download_taifex_data: MagicMock, mock_setup_logger: MagicMock):
        """測試：當 download_taifex_data 返回 None (模擬404或無資料日) 時，main 函數是否會用返回碼 EXIT_CODE_NO_DATA_AVAILABLE (0) 呼叫 sys.exit。"""
        mock_logger = MagicMock(spec=logging.Logger)
        mock_setup_logger.return_value = mock_logger

        # 模擬 download_taifex_data 在 404 或無數據日的情境下返回 None
        mock_download_taifex_data.return_value = None

        target_date = "2024-01-18" # 假設這是一個無資料日
        test_args = ['run.py', '--date', target_date, '--output-dir', str(self.temp_output_dir), '--log-level', 'INFO']
        with patch('sys.argv', test_args):
            asyncio.run(taifex_main()) # <--- 修改：使用 asyncio.run()

        # 驗證 sys.exit 是否被以參數 EXIT_CODE_NO_DATA_AVAILABLE (即 0) 呼叫
        mock_sys_exit.assert_called_once_with(EXIT_CODE_NO_DATA_AVAILABLE)

        # 驗證是否有 "當日無可用資料" 的 INFO 日誌
        # run.py 的 main 函數會在 exit_code == EXIT_CODE_NO_DATA_AVAILABLE 時記錄
        # "--- TAIFEX 智慧情報下載器任務完成，當日無可用資料 (日期: YYYY-MM-DD) ---"
        logged_no_data_info = False
        expected_log_message_fragment = f"TAIFEX 智慧情報下載器任務完成，當日無可用資料 (日期: {target_date})"
        for call_args in mock_logger.info.call_args_list:
            if expected_log_message_fragment in call_args[0][0]:
                logged_no_data_info = True
                break
        self.assertTrue(logged_no_data_info, f"預期的 '無可用資料' INFO 日誌未被記錄。INFO 日誌呼叫: {mock_logger.info.call_args_list}")

        # 驗證輸出目錄是否為空
        items_in_output_dir = list(self.temp_output_dir.iterdir())
        self.assertEqual(len(items_in_output_dir), 0,
                         f"輸出目錄 {self.temp_output_dir} 在404情況下應為空，但包含: {[item.name for item in items_in_output_dir]}")

if __name__ == '__main__':
    unittest.main()
