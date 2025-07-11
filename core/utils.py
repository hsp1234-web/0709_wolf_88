import logging
import sys


def setup_logger(name: str, level: int = logging.INFO):
    """
    設定並返回一個日誌記錄器。

    :param name: 日誌記錄器的名稱。
    :param level: 日誌記錄的級別。
    :return: 配置好的 logging.Logger 實例。
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重複添加處理程序 (如果 logger 已有處理程序)
    if not logger.handlers:
        # 創建控制台處理程序
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)

        # 創建模仿 pipeline 主腳本的日誌格式器
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s"
        )
        ch.setFormatter(formatter)

        # 添加處理程序到 logger
        logger.addHandler(ch)

    # 為 logger.success 添加一個自定義級別
    # 這模仿了某些日誌庫 (如 loguru) 的行為，但標準 logging 需要一點技巧
    # SUCCESS_LEVEL_NUM = 25 #介於 INFO (20) 和 WARNING (30) 之間
    # logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")
    # def success(self, message, *args, **kws):
    #    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
    #        self._log(SUCCESS_LEVEL_NUM, message, args, **kws)
    # logging.Logger.success = success
    # logger.success = lambda message, *args, **kws: success(logger, message, *args, **kws)
    # 上述 success 方法的實現方式對於標準 logging 來說有點複雜且可能不是最佳實踐，
    # 為了簡化，taifex_data_pipeline 中的 logger.success 將僅作為 logger.info 的別名或直接使用 logger.info。
    # 如果需要真正的 'SUCCESS' 級別，需要在 logging 系統層面進行更深入的配置。
    # 目前，我們將確保 logger.info, logger.debug 等標準方法可用。
    # taifex_data_pipeline/run.py 中的 logger.success() 調用，如果沒有 success 級別，
    # 最好的處理方式是在該腳本中將其視為 info 級別。

    return logger


if __name__ == "__main__":
    # 測試 setup_logger
    logger1 = setup_logger("my_app_logger", level=logging.DEBUG)
    logger1.debug("這是一個調試訊息 from my_app_logger.")
    logger1.info("這是一個資訊訊息 from my_app_logger.")
    logger1.warning("這是一個警告訊息 from my_app_logger.")

    logger2 = setup_logger("another_module_logger", level=logging.INFO)
    logger2.debug("這個調試訊息不應該出現 (logger2)。")  # 不會顯示，因為級別是 INFO
    logger2.info("這是一個資訊訊息 from another_module_logger.")

    # 測試 logger.success (目前不會有特殊級別)
    # logger1.success("這是一個 '成功' 訊息 from my_app_logger.")
    # 如果 taifex_data_pipeline 真的依賴 logger.success，我們需要在該腳本中處理它
    # 例如，通過在該腳本中定義：
    # if not hasattr(logger, 'success'):
    #     logger.success = logger.info
    pass
