# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch, MagicMock
import subprocess
import sys
import tempfile
from pathlib import Path
import asyncio
import aiohttp # 需要導入以模擬其內部的錯誤類型
import os # 需要 os 來輔助路徑校正

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

TARGET_SCRIPT_MODULE = "apps.taifex_data_pipeline.run"

class TestApiFailures(unittest.TestCase):
    temp_output_dir: Path

    def setUp(self):
        # 使用基於類名和方法名的臨時目錄，方便追蹤
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


    def _run_script_and_assert_failure(self, target_date: str, expected_error_log_片段: str, expected_exit_code: int = 1, mock_session_get_config=None):
        """
        執行 run.py 腳本並斷言其失敗行為。
        mock_session_get_config: 一個字典，用於配置 mock_session_get 的行為, e.g. {'side_effect': SomeError} or {'return_value': mock_response}
        """

        # 使用 patch.object 或 patch 來模擬 aiohttp.ClientSession.get
        # 這裡我們在調用此輔助函數之前已經在測試方法中應用了 @patch

        cmd = [
            sys.executable,
            "-m", TARGET_SCRIPT_MODULE,
            "--date", target_date,
            "--output-dir", str(self.temp_output_dir),
            "--log-level", "ERROR" # 我們關心 ERROR 級別的日誌 for failure cases
        ]
        # print(f"\n[RUN_SCRIPT] 執行指令: {' '.join(cmd)}")
        process = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

        # print(f"\n[TEST STDOUT for {self.id()} with date {target_date}]:\n{process.stdout}")
        # print(f"[TEST STDERR for {self.id()} with date {target_date}]:\n{process.stderr}")

        self.assertEqual(process.returncode, expected_exit_code,
                         f"腳本應以返回碼 {expected_exit_code} 退出，實際為 {process.returncode}。\nstdout:\n{process.stdout}\nstderr:\n{process.stderr}")

        # core.utils.setup_logger 預設將日誌輸出到 stdout
        # 我們需要檢查 stdout 是否包含錯誤日誌片段
        # 注意: 錯誤日誌中可能包含 "[ERROR]" 前綴，這取決於 logger 的格式設定
        # run.py 中 download_taifex_data 函數的 logger.error 訊息格式是 "[ERROR] {message}"
        # main 函數中捕獲 TaifexDownloadError 後的 logger.error 訊息格式是 "捕獲到 TAIFEX 下載錯誤: {e}"
        # 我們應該檢查由 download_taifex_data 直接產生的錯誤訊息，因為那是 mock 的目標
        self.assertIn(expected_error_log_片段, process.stdout,
                      f"預期的錯誤日誌片段 '{expected_error_log_片段}' 未在 stdout 中找到。\nstdout:\n{process.stdout}")

        items_in_output_dir = list(self.temp_output_dir.iterdir())
        self.assertEqual(len(items_in_output_dir), 0,
                         f"輸出目錄 {self.temp_output_dir} 在失敗情境下應為空，但包含: {[item.name for item in items_in_output_dir]}")

    @patch('aiohttp.ClientSession.get')
    def test_download_handles_client_connector_error(self, mock_get: MagicMock):
        """測試 run.py 在 aiohttp.ClientConnectorError 時的行為"""
        mock_get.side_effect = aiohttp.ClientConnectorError(
            MagicMock(spec=aiohttp.connector.Connection), # connection_key (修正: ConnectionKey -> Connection)
            OSError("Simulated OS error for connector")
        )
        target_date = "2024-01-15"
        # 預期 download_taifex_data 函數內的日誌
        error_log_snippet = f"[ERROR] Network connection error for {target_date}: Simulated OS error for connector. URL: https://www.taifex.com.tw/file/taifex/Dailydownload/DailydownloadCSV/Data_{target_date.replace('-', '')}.zip"
        print(f"\n[INFO] 執行 test_download_handles_client_connector_error (目標日期: {target_date})")
        self._run_script_and_assert_failure(target_date, error_log_snippet)

    @patch('aiohttp.ClientSession.get')
    def test_download_handles_server_error_503(self, mock_get: MagicMock):
        """測試 run.py 在伺服器返回 503 錯誤時的行為"""
        mock_response = MagicMock(spec=aiohttp.ClientResponse)
        mock_response.status = 503
        mock_response.reason = "Service Unavailable"

        # 模擬 response context manager
        async def mock_response_context_manager(*args, **kwargs):
            return mock_response

        mock_get.return_value.__aenter__ = mock_response_context_manager
        mock_get.return_value.__aexit__ = MagicMock(return_value=None) # 異步的 __aexit__

        target_date = "2024-01-16"
        error_log_snippet = f"[ERROR] Failed to download data for {target_date}. HTTP Status: 503. URL: https://www.taifex.com.tw/file/taifex/Dailydownload/DailydownloadCSV/Data_{target_date.replace('-', '')}.zip"
        print(f"\n[INFO] 執行 test_download_handles_server_error_503 (目標日期: {target_date})")
        self._run_script_and_assert_failure(target_date, error_log_snippet)

    @patch('aiohttp.ClientSession.get')
    def test_download_handles_timeout_error(self, mock_get: MagicMock):
        """測試 run.py 在 asyncio.TimeoutError 時的行為"""
        mock_get.side_effect = asyncio.TimeoutError("Simulated timeout")

        target_date = "2024-01-17"
        error_log_snippet = f"[ERROR] Timeout during download for {target_date}. URL: https://www.taifex.com.tw/file/taifex/Dailydownload/DailydownloadCSV/Data_{target_date.replace('-', '')}.zip"
        print(f"\n[INFO] 執行 test_download_handles_timeout_error (目標日期: {target_date})")
        self._run_script_and_assert_failure(target_date, error_log_snippet)

    @patch('aiohttp.ClientSession.get')
    def test_download_preserves_no_data_behavior_on_404(self, mock_get: MagicMock):
        """測試 run.py 在 404 時是否保持「無數據」的行為 (返回碼0)"""
        mock_response = MagicMock(spec=aiohttp.ClientResponse)
        mock_response.status = 404

        async def mock_response_context_manager(*args, **kwargs):
            return mock_response

        mock_get.return_value.__aenter__ = mock_response_context_manager
        mock_get.return_value.__aexit__ = MagicMock(return_value=None)

        target_date = "2024-01-18"
        cmd = [
            sys.executable,
            "-m", TARGET_SCRIPT_MODULE,
            "--date", target_date,
            "--output-dir", str(self.temp_output_dir),
            "--log-level", "INFO" # 這次需要INFO來看 "No data available"
        ]
        # print(f"\n[RUN_SCRIPT] 執行指令 for 404 test: {' '.join(cmd)}")
        process = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

        # print(f"\n[TEST STDOUT for 404 test {target_date}]:\n{process.stdout}")
        # print(f"[TEST STDERR for 404 test {target_date}]:\n{process.stderr}")

        self.assertEqual(process.returncode, 0,
                         f"腳本在404時應以返回碼 0 退出，實際為 {process.returncode}。\nstdout:\n{process.stdout}\nstderr:\n{process.stderr}")
        self.assertIn(f"[INFO] No data available for {target_date}", process.stdout, # run.py prints YYYY-MM-DD
                      f"stdout 未包含預期的 'No data available' 日誌。\nstdout:\n{process.stdout}")

        items_in_output_dir = list(self.temp_output_dir.iterdir())
        self.assertEqual(len(items_in_output_dir), 0,
                         f"輸出目錄 {self.temp_output_dir} 在404情況下應為空，但包含: {[item.name for item in items_in_output_dir]}")
        print(f"\n[INFO] 執行 test_download_preserves_no_data_behavior_on_404 (目標日期: {target_date})")

if __name__ == '__main__':
    unittest.main()
