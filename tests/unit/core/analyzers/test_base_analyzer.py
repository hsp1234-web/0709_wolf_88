# tests/unit/core/analyzers/test_base_analyzer.py
from unittest.mock import MagicMock

import pandas as pd
import pytest  # 導入 pytest 以便使用 mocker fixture

from prometheus.core.analyzers.base_analyzer import BaseAnalyzer


# 為了測試，創建一個最小化的具體實現子類
class DummyAnalyzer(BaseAnalyzer):
    def __init__(
        self, analyzer_name: str, **kwargs
    ):  # 添加 **kwargs 以便測試初始化參數傳遞
        super().__init__(analyzer_name)
        self.kwargs = kwargs
        # 在實際子類中，這裡可能會初始化 db_manager 或其他依賴

    def _load_data(self) -> pd.DataFrame:
        # 實際子類會執行數據載入邏輯
        return pd.DataFrame({"data": [1]})

    def _perform_analysis(self, data: pd.DataFrame) -> pd.DataFrame:
        # 實際子類會執行分析邏輯
        return pd.DataFrame(
            {"result": [data["data"].iloc[0] * 2 if not data.empty else 0]}
        )

    def _save_results(self, results: pd.DataFrame) -> None:
        # 實際子類會執行保存邏輯
        pass


def test_run_orchestrates_methods_correctly(mocker):  # pytest 使用 mocker fixture
    """
    測試 BaseAnalyzer.run() 是否以正確的順序和參數調用其抽象方法。
    """
    # 準備
    analyzer_name = "dummy_test_analyzer"
    init_kwargs = {"param1": "value1"}
    analyzer = DummyAnalyzer(analyzer_name=analyzer_name, **init_kwargs)

    # 模擬 DataFrame，用於測試參數傳遞
    mock_loaded_df = pd.DataFrame({"loaded_data": [10]})
    mock_analyzed_df = pd.DataFrame({"analyzed_data": [20]})

    # 模擬(Mock)所有需要被調用的方法
    # 使用 mocker.patch.object 來 mock 實例的方法
    mock_load = mocker.patch.object(analyzer, "_load_data", return_value=mock_loaded_df)
    mock_analyze = mocker.patch.object(
        analyzer, "_perform_analysis", return_value=mock_analyzed_df
    )
    mock_save = mocker.patch.object(analyzer, "_save_results")

    # 也 mock logger，以避免實際的日誌輸出干擾測試結果，並可以驗證日誌調用
    mock_logger_info = mocker.patch.object(analyzer.logger, "info")
    mock_logger_error = mocker.patch.object(analyzer.logger, "error")

    # 執行
    analyzer.run()

    # 斷言(Assert) - 驗證流程是否如預期
    mock_load.assert_called_once()
    mock_analyze.assert_called_once_with(
        mock_loaded_df
    )  # 驗證 _perform_analysis 是否以 _load_data 的返回值調用
    mock_save.assert_called_once_with(
        mock_analyzed_df
    )  # 驗證 _save_results 是否以 _perform_analysis 的返回值調用

    # 驗證日誌調用 (可選，但有助於確認流程訊息)
    assert (
        mock_logger_info.call_count >= 6
    )  # 初始化1次 + 開始流程1次 + 步驟1,2,3各1次 + 結束流程1次
    mock_logger_error.assert_not_called()  # 確保沒有錯誤日誌


def test_run_handles_exception_in_load_data(mocker):
    analyzer = DummyAnalyzer(analyzer_name="dummy_error_load")
    mocker.patch.object(
        analyzer, "_load_data", side_effect=ValueError("Error loading data")
    )
    mock_analyze = mocker.patch.object(analyzer, "_perform_analysis")
    mock_save = mocker.patch.object(analyzer, "_save_results")
    mock_logger_error = mocker.patch.object(analyzer.logger, "error")

    with pytest.raises(ValueError, match="Error loading data"):
        analyzer.run()

    mock_analyze.assert_not_called()
    mock_save.assert_not_called()
    mock_logger_error.assert_called_once()


def test_run_handles_exception_in_perform_analysis(mocker):
    analyzer = DummyAnalyzer(analyzer_name="dummy_error_analyze")
    mock_df = pd.DataFrame({"data": [1]})
    mocker.patch.object(analyzer, "_load_data", return_value=mock_df)
    mocker.patch.object(
        analyzer,
        "_perform_analysis",
        side_effect=RuntimeError("Error performing analysis"),
    )
    mock_save = mocker.patch.object(analyzer, "_save_results")
    mock_logger_error = mocker.patch.object(analyzer.logger, "error")

    with pytest.raises(RuntimeError, match="Error performing analysis"):
        analyzer.run()

    mock_save.assert_not_called()
    mock_logger_error.assert_called_once()


def test_run_handles_exception_in_save_results(mocker):
    analyzer = DummyAnalyzer(analyzer_name="dummy_error_save")
    mock_df = pd.DataFrame({"data": [1]})
    mock_analyzed_df = pd.DataFrame({"result": [2]})
    mocker.patch.object(analyzer, "_load_data", return_value=mock_df)
    mocker.patch.object(analyzer, "_perform_analysis", return_value=mock_analyzed_df)
    mocker.patch.object(
        analyzer, "_save_results", side_effect=IOError("Error saving results")
    )
    mock_logger_error = mocker.patch.object(analyzer.logger, "error")

    with pytest.raises(IOError, match="Error saving results"):
        analyzer.run()

    mock_logger_error.assert_called_once()


def test_base_analyzer_initialization_logs_name(mocker):
    """測試 BaseAnalyzer 初始化時是否記錄分析器名稱。"""
    mock_logger = MagicMock()
    mocker.patch(
        "logging.getLogger", return_value=mock_logger
    )  # Mock getLogger 以捕獲日誌實例

    analyzer_name = "my_test_analyzer"
    DummyAnalyzer(
        analyzer_name=analyzer_name
    )  # Create instance, but not assigned if not used

    # 驗證 getLogger 是否以正確的名稱被調用
    # logging.getLogger.assert_called_once_with(f"analyzer.{analyzer_name}") # 這是 mocker.patch 的用法

    # 驗證初始化日誌訊息
    mock_logger.info.assert_any_call(f"分析器 '{analyzer_name}' 已初始化。")

    # 為了讓 mocker.patch('logging.getLogger', ...) 生效，需要確保它在 BaseAnalyzer 初始化前被 patch
    # 或者，我們可以檢查 analyzer.logger 的調用
    # 在這個測試中，DummyAnalyzer 繼承了 BaseAnalyzer，所以 BaseAnalyzer 的 __init__ 會被調用
    # 我們可以直接檢查 DummyAnalyzer 實例的 logger

    # 重新設計這個測試，直接檢查實例的 logger
    analyzer_name_direct = "direct_logger_test"
    DummyAnalyzer(
        analyzer_name=analyzer_name_direct
    )  # Create instance, but not assigned if not used

    # 由於 logger 是在 BaseAnalyzer 的 __init__ 中創建的，我們需要 mock BaseAnalyzer 內部的 getLogger
    # 或者，更簡單的方式是，如果 BaseAnalyzer.__init__ 確實調用了 self.logger.info，
    # 我們可以 mock DummyAnalyzer 實例的 logger。

    # 讓我們使用一個更直接的方法來驗證 BaseAnalyzer 的 __init__ 中的日誌記錄
    # 這需要我們能夠在 BaseAnalyzer 的 __init__ 執行時捕獲其 logger 的調用

    # 上面的 mocker.patch('logging.getLogger', return_value=mock_logger) 應該可以工作
    # 如果 DummyAnalyzer 的 super().__init__(analyzer_name) 被調用，
    # 那麼 BaseAnalyzer 的 __init__ 中的 logging.getLogger(f"analyzer.{analyzer_name}")
    # 就會返回 mock_logger。

    # 讓我們確保 DummyAnalyzer 的 __init__ 正確調用了 super()
    # 它確實調用了：super().__init__(analyzer_name)

    # 斷言 mock_logger.info 被以預期的方式調用
    # 由於 run() 方法也會調用 logger.info，我們只關心初始化時的調用

    # 篩選出初始化時的日誌調用
    found_init_log = False
    for call_args in mock_logger.info.call_args_list:
        if call_args[0][0] == f"分析器 '{analyzer_name}' 已初始化。":
            found_init_log = True
            break
    assert (
        found_init_log
    ), f"預期的初始化日誌 '分析器 '{analyzer_name}' 已初始化。' 未找到。"


pytest_plugins = [
    "pytester"
]  # 如果需要 pytest-mock 的高級功能或 fixture，通常不需要顯式聲明
