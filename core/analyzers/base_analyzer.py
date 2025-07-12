# core/analyzers/base_analyzer.py
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import pandas as pd


class BaseAnalyzer(ABC):
    """
    所有分析器應用的抽象基礎類 (Abstract Base Class)。

    它採用了「模板方法」設計模式，定義了一個標準化的分析工作流程骨架 (`run` 方法)，
    同時允許子類通過實現抽象方法來定義具體的步驟。

    所有繼承此類的分析器都將自動獲得標準化的日誌記錄和執行流程。
    """

    def __init__(self, analyzer_name: str):
        """
        初始化基礎分析器。

        Args:
            analyzer_name: 分析器的名稱，將用於日誌記錄。
        """
        self.analyzer_name = analyzer_name
        self.logger = logging.getLogger(f"analyzer.{self.analyzer_name}")
        self.logger.info(f"分析器 '{self.analyzer_name}' 已初始化。")

    @abstractmethod
    def _load_data(self) -> pd.DataFrame:
        """
        【子類必須實現】載入分析所需的原始數據。

        Returns:
            一個包含原始數據的 Pandas DataFrame。
        """
        pass

    @abstractmethod
    def _perform_analysis(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        【子類必須實現】執行具體的核心分析邏輯。

        Args:
            data: 從 _load_data() 方法載入的數據。

        Returns:
            一個包含分析結果的 Pandas DataFrame。
        """
        pass

    @abstractmethod
    def _save_results(self, results: pd.DataFrame) -> None:
        """
        【子類必須實現】將分析結果進行保存（例如存入數據庫、寫入 CSV 文件等）。

        Args:
            results: 從 _perform_analysis() 方法返回的結果。
        """
        pass

    def run(self) -> None:
        """
        執行完整的分析工作流程。
        這是一個模板方法，它以固定的順序調用各個步驟。
        """
        self.logger.info(f"--- 開始執行分析流程：{self.analyzer_name} ---")
        try:
            # 第一步：載入數據
            self.logger.info("步驟 1/3：正在載入數據...")
            source_data = self._load_data()
            self.logger.info(f"數據載入成功，共 {len(source_data)} 筆記錄。")

            # 第二步：執行分析
            self.logger.info("步驟 2/3：正在執行核心分析...")
            analysis_results = self._perform_analysis(source_data)
            self.logger.info("核心分析執行完畢。")

            # 第三步：保存結果
            self.logger.info("步驟 3/3：正在保存結果...")
            self._save_results(analysis_results)
            self.logger.info("結果保存成功。")

        except Exception as e:
            self.logger.error(
                f"分析流程 '{self.analyzer_name}' 發生嚴重錯誤：{e}", exc_info=True
            )
            # 可以在此處添加失敗通知等邏輯
            raise  # 重新拋出異常，讓上層調用者知道發生了問題
        finally:
            self.logger.info(f"--- 分析流程執行完畢：{self.analyzer_name} ---")
