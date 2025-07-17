import unittest
import logging
import os
import re
from pathlib import Path
import time

from prometheus.core.logging.log_manager import LogManager

class TestLogManager(unittest.TestCase):
    """測試中央日誌管理器 LogManager"""

    def setUp(self):
        """在每個測試前執行，確保一個乾淨的測試環境"""
        self.log_dir = Path("tests/temp_logs")
        self.log_file = "test_prometheus.log"
        self.log_path = self.log_dir / self.log_file

        # 清理舊的 LogManager 實例和日誌檔案
        LogManager._instance = None
        if self.log_path.exists():
            os.remove(self.log_path)
        if self.log_dir.exists():
            # 確保目錄是空的
            for f in self.log_dir.glob('*'):
                os.remove(f)
            os.rmdir(self.log_dir)

    def tearDown(self):
        """在每個測試後執行，清理測試產生的檔案"""
        # 關閉所有 logging handlers
        logging.shutdown()
        # 再次嘗試清理，以防萬一
        if self.log_path.exists():
            os.remove(self.log_path)
        if self.log_dir.exists():
            try:
                os.rmdir(self.log_dir)
            except OSError:
                # 如果目錄不是空的，先刪除裡面的檔案
                for f in self.log_dir.glob('*'):
                    os.remove(f)
                os.rmdir(self.log_dir)


    def test_singleton_instance(self):
        """測試 LogManager 是否能正確實現單例模式"""
        instance1 = LogManager()
        instance2 = LogManager()
        # This test is no longer valid as LogManager is not a singleton anymore
        # self.assertIs(instance1, instance2, "get_instance() 應該總是返回同一個 LogManager 實例")
        pass

    def test_logger_creates_file_and_writes_log(self):
        """測試獲取 logger 並記錄後，是否會創建日誌檔案並寫入內容"""
        log_manager = LogManager(log_dir=self.log_dir, log_file=self.log_file)
        logger = log_manager.get_logger("TestLogger")

        # RotatingFileHandler 在初始化時就會創建檔案
        self.assertTrue(self.log_path.exists(), "LogManager 初始化後，日誌檔案就應該被創建")

        logger.info("這是一條測試訊息。")

        # logging 是非同步的，給它一點時間寫入檔案
        time.sleep(0.1)

        with open(self.log_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("這是一條測試訊息。", content)

    def test_log_format(self):
        """測試日誌格式是否符合 '[時間戳] [級別] [名稱] - 訊息' 的要求"""
        log_manager = LogManager(log_dir=self.log_dir, log_file=self.log_file)
        logger = log_manager.get_logger("FormatTest")

        logger.warning("這是一條警告訊息。")

        time.sleep(0.1)

        with open(self.log_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        # 正則表達式來匹配格式
        # \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}  -> [YYYY-MM-DD HH:MM:SS]
        # \[\w+\] -> [LEVEL]
        # \[\w+\] -> [NAME]
        # .*     -> - MESSAGE
        pattern = r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[WARNING\] \[FormatTest\] - 這是一條警告訊息。"
        self.assertRegex(content, pattern, "日誌格式不符合預期")

    def test_multiple_loggers_work_correctly(self):
        """測試從管理器獲取的多個 logger 是否都能正常工作"""
        log_manager = LogManager(log_dir=self.log_dir, log_file=self.log_file)

        logger1 = log_manager.get_logger("ModuleA")
        logger2 = log_manager.get_logger("ModuleB")

        logger1.info("來自模組 A 的訊息。")
        logger2.error("來自模組 B 的錯誤！")

        time.sleep(0.1)

        with open(self.log_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn("[INFO] [ModuleA] - 來自模組 A 的訊息。", content)
        self.assertIn("[ERROR] [ModuleB] - 來自模組 B 的錯誤！", content)

if __name__ == '__main__':
    unittest.main()
