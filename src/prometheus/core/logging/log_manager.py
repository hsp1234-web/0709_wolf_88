import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os

class LogManager:
    """
    一個單例的日誌管理器。
    它能為整個應用程式配置日誌，將日誌輸出到控制台和指定的可輪替檔案中。
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(LogManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, log_dir: str = "data/logs", log_file: str = "prometheus.log", log_level=logging.INFO):
        """
        初始化日誌管理器。

        :param log_dir: 日誌檔案存放的目錄。
        :param log_file: 日誌檔案的名稱。
        :param log_level: 日誌級別。
        """
        if self._initialized:
            return

        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        self.log_file_path = log_path / log_file
        self.log_level = log_level
        self.formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        self._initialized = True

    @classmethod
    def get_instance(cls):
        """
        獲取 LogManager 的單例實例。
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

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
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(self.formatter)
        logger.addHandler(stream_handler)

        return logger
