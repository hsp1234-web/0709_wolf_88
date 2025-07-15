import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os

class LogManager:
    """
    一個集中式的日誌管理器，採用單例模式，以確保整個應用程式使用統一的日誌設定。
    它能同時將日誌輸出到控制台和可輪替的檔案中。
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LogManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, log_dir: str = "data/logs", log_file: str = "prometheus.log", log_level=logging.INFO):
        # 由於是單例，防止重複初始化
        if hasattr(self, '_initialized') and self._initialized:
            return

        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        self.log_file_path = log_path / log_file
        self.log_level = log_level
        self.formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        self._configure_root_logger()
        self._initialized = True

    def _configure_root_logger(self):
        """
        配置根日誌記錄器，所有由此管理器創建的 logger 都會繼承此設定。
        """
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)

        # 清除所有現有的 handlers，以避免重複記錄
        if root_logger.hasHandlers():
            root_logger.handlers.clear()

        # 檔案 handler (帶輪替功能)
        file_handler = RotatingFileHandler(
            self.log_file_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(self.formatter)
        root_logger.addHandler(file_handler)

        # 控制台 handler
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(self.formatter)
        root_logger.addHandler(stream_handler)

    def get_logger(self, name: str) -> logging.Logger:
        """
        獲取一個以指定名稱命名的日誌記錄器。
        它會繼承根記錄器的設定 (handlers, level)。
        """
        return logging.getLogger(name)

    @staticmethod
    def get_instance(log_dir: str = "data/logs", log_file: str = "prometheus.log", log_level=logging.INFO):
        """
        獲取 LogManager 的單例實例。
        """
        if LogManager._instance is None:
            LogManager._instance = LogManager(log_dir=log_dir, log_file=log_file, log_level=log_level)
        return LogManager._instance
