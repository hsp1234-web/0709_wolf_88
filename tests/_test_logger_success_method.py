# 檔名: tests/_test_logger_success_method.py
import unittest
import os
import sys
import logging # 導入 logging 以便測試

# --- 路徑自我校正 ---
# 確保無論從哪裡執行此測試，都能找到 src 目錄
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '..'))
    src_path = os.path.join(project_root, 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    # 特別確保 utils 目錄也被加入，因為 logger 是在 utils.logger
    utils_path = os.path.join(project_root, 'src', 'utils')
    if utils_path not in sys.path:
        sys.path.insert(0, utils_path)

except Exception as e:
    print(f"路徑校正失敗: {e}", file=sys.stderr)
    sys.exit(1)
# --- 校正結束 ---

# 由於 setup_logger 和 success 方法的添加是在 src.utils.logger 模組加載時發生的
# 我們需要導入 setup_logger 來觸發這些操作
from utils.logger import setup_logger, SUCCESS_LEVEL_NUM

class TestLoggerSuccessMethod(unittest.TestCase):

    def test_success_method_exists_and_callable(self):
        """
        測試: Logger 物件是否擁有 'success' 方法並且可以被調用。
        預期: 不會拋出 AttributeError，且日誌級別正確。
        """
        print("\n🧪  測試案例：驗證 logger.success() 方法的存在性與可調用性...")

        # 獲取一個 logger 實例
        # 注意：由於 success 是動態添加到 logging.Logger 上的，
        # 我們需要先 setup_logger 來確保 utils.logger 被加載，
        # 從而使 logging.Logger.success = success 這行代碼被執行。
        # 同時，setup_logger 返回的是一個配置好的 logger 實例。

        # 使用一個臨時的日誌文件以隔離測試，並確保日誌目錄存在
        test_log_dir = os.path.join(project_root, 'logs_test') # 測試用的日誌目錄
        if not os.path.exists(test_log_dir):
            os.makedirs(test_log_dir)
        temp_log_file = os.path.join(test_log_dir, '_test_logger_success.log')

        # 確保 logger 的級別足夠低，以便 SUCCESS (25) 級別的日誌能夠被記錄
        # logging.DEBUG (10) < SUCCESS_LEVEL_NUM (25)
        logger = setup_logger(
            name='TestSuccessLogger',
            log_file_path_str=temp_log_file,
            level=logging.DEBUG # 設定為 DEBUG 以確保 SUCCESS 會被處理
        )

        try:
            # 驗證 logger 實例確實是 logging.Logger (或其子類)
            self.assertIsInstance(logger, logging.Logger, "logger 不是 logging.Logger 的實例")

            # 檢查 'success' 方法是否存在
            self.assertTrue(hasattr(logger, 'success'), "Logger 物件缺少 'success' 方法屬性。")
            self.assertTrue(callable(logger.success), "Logger 物件的 'success' 屬性不可調用。")

            # 調用 success 方法
            test_message = "這是一條成功的測試訊息。"
            logger.success(test_message)
            print(f"✅  測試訊息：logger.success('{test_message}') 已成功調用。")

            # 驗證日誌是否確實寫入（可選，但更完整）
            # 為了簡化，這裡我們主要測試方法的可調用性。
            # 實際的日誌內容驗證可以在更集中的日誌測試中進行。
            # 但我們可以檢查日誌文件是否創建。
            self.assertTrue(os.path.exists(temp_log_file), f"測試日誌檔案 '{temp_log_file}' 未被創建。")

            # 簡單讀取日誌內容，檢查是否包含 SUCCESS 和訊息
            with open(temp_log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()

            self.assertIn("SUCCESS", log_content, "日誌內容中未找到 'SUCCESS' 關鍵字。")
            self.assertIn(test_message, log_content, f"日誌內容中未找到測試訊息 '{test_message}'。")
            print(f"✅  日誌驗證：在 '{temp_log_file}' 中成功找到 SUCCESS 級別的日誌訊息。")


        except AttributeError as e:
            self.fail(f"❌ 測試失敗：Logger 物件缺少 'success' 方法或調用時出錯。錯誤: {e}")
        except Exception as e:
            self.fail(f"❌ 測試失敗：調用 logger.success() 時發生非預期錯誤: {e}")
        finally:
            # 清理測試產生的檔案和目錄
            # 為了避免影響其他測試或遺留文件，需要關閉 logger 的 handlers
            for handler in logger.handlers[:]: # 迭代副本以安全移除
                handler.close()
                logger.removeHandler(handler)

            if os.path.exists(temp_log_file):
                os.remove(temp_log_file)
            if os.path.exists(test_log_dir) and not os.listdir(test_log_dir): # 如果目錄為空則刪除
                os.rmdir(test_log_dir)
            elif os.path.exists(test_log_dir) and os.listdir(test_log_dir) == ['_test_logger_success.log-expected.png']: # specific for a potential image file
                 pass # Do not delete if it contains specific non-log files, adjust as needed

if __name__ == '__main__':
    print("\n--- 沙箱環境：中央日誌系統 `success` 方法驗收測試 ---")
    # 為了在 __main__ 中運行時也能找到 logger，確保 utils.logger 已被處理
    # 雖然 import utils.logger 已經做了，但明確一下
    if 'utils.logger' not in sys.modules:
        import utils.logger # 確保 SUCCESS 級別和方法已設定

    unittest.main(verbosity=2)
