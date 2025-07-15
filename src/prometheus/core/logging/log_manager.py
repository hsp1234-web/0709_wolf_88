import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


class LogManager:
    """一個集中式的日誌管理器，確保全應用程式使用統一的日誌設定。"""

    def __init__(
        self,
        log_dir: str = "logs",
        log_file: str = "prometheus.log",
        log_level=logging.INFO,
    ):
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        self.log_file_path = log_path / log_file
        self.log_level = log_level
        self._loggers = {}

    def get_logger(self, name: str) -> logging.Logger:
        if name in self._loggers:
            return self._loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(self.log_level)

        # 防止在測試或多重初始化中重複添加 handlers
        if not logger.handlers:
            # 檔案 handler
            handler = RotatingFileHandler(
                self.log_file_path,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

            # 主控台 handler
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)

        self._loggers[name] = logger
        return logger
