import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os

class LogManager:
    """
    一個獨立的日誌管理器實例。
    它能為特定任務配置日誌，將日誌輸出到控制台和指定的可輪替檔案中。
    """
    def __init__(self, log_dir: str = "data/logs", log_file: str = "prometheus.log", log_level=logging.INFO, dedicated: bool = False):
        """
        初始化日誌管理器。

        :param log_dir: 日誌檔案存放的目錄。
        :param log_file: 日誌檔案的名稱。
        :param log_level: 日誌級別。
        :param dedicated: 如果為 True，則創建一個完全獨立的 logger，不影響 root logger。這在多進程環境中至關重要。
        """
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        self.log_file_path = log_path / log_file
        self.log_level = log_level
        self.formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        self.dedicated = dedicated

    def get_logger(self, name: str) -> logging.Logger:
        """
        獲取一個配置好的日誌記錄器。

        :param name: 日誌記錄器的名稱。
        :return: 一個配置好的 logging.Logger 實例。
        """
        logger = logging.getLogger(name)
        logger.setLevel(self.log_level)

        # 為了防止重複添加 handlers，每次都清空
        if logger.hasHandlers():
            logger.handlers.clear()

        # 確保日誌事件不會向上传播到 root logger
        # 這可以防止一個 logger 的日誌出現在另一個 logger 的輸出中
        logger.propagate = False

        # 檔案 handler (帶輪替功能)
        file_handler = RotatingFileHandler(
            self.log_file_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(self.formatter)
        logger.addHandler(file_handler)

        # 控制台 handler
        # 我們可以選擇只讓主進程或特定 logger 輸出到控制台，以避免混亂
        # 在這裡，我們讓每個 logger 都輸出，因為日誌本身會標識來源
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(self.formatter)
        logger.addHandler(stream_handler)

        return logger
