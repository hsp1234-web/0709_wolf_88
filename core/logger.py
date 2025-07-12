# core/logger.py
import logging
import sys


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    獲取一個標準化配置的 Logger 實例。
    """
    logger = logging.getLogger(name)

    # 防止重複添加 handler
    if logger.hasHandlers():
        return logger

    logger.setLevel(level)

    # 創建 handler 並設置格式
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    return logger
