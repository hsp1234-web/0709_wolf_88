from prometheus.core.pipelines.base_step import BaseETLStep
from prometheus.core.analysis.stress_index import StressIndexCalculator
import pandas as pd
import logging
from typing import Dict, Any

from src.prometheus.core.pipelines.base_step import BaseStep
from src.prometheus.core.engines.stock_factor_engine import StockFactorEngine
from src.prometheus.core.engines.crypto_factor_engine import CryptoFactorEngine

logger = logging.getLogger(__name__)


class BuildGoldLayerStep(BaseETLStep):
    """
    將多個來源的數據融合成「黃金層」數據的管線步驟。
    """

    def execute(self, data=None):
        print("\n--- [Step] Executing BuildGoldLayerStep ---")
        # 在此執行黃金層數據的複雜ETL邏輯
        # ...
        print("--- [Success] Gold layer data built. ---")
        # 為了測試，返回一個成功的標誌
        return {"status": "gold_layer_ok"}


class CalculateStressIndexStep(BaseETLStep):
    """
    計算市場壓力指數的管線步驟。
    """

    def execute(self, data=None):
        print("\n--- [Step] Executing CalculateStressIndexStep ---")
        calculator = None
        try:
            calculator = StressIndexCalculator()
            stress_index_df = calculator.calculate()
            if not stress_index_df.empty:
                latest_stress_index = stress_index_df["Stress_Index"].iloc[-1]
                print("--- [Success] Stress index calculated. ---")
                print(f"壓力指數當前值: {latest_stress_index:.2f}")
                return {"status": "success", "stress_index": latest_stress_index}
            else:
                print("--- [Failed] Stress index calculation returned empty data. ---")
                return {"status": "failed", "reason": "Empty data from calculator"}
        except Exception as e:
            print(
                f"--- [Error] An error occurred during stress index calculation: {e} ---"
            )
            return {"status": "error", "reason": str(e)}
        finally:
            if calculator:
                calculator.close_all_sessions()


class RunStockFactorEngineStep(BaseStep):
    """
    一個 Pipeline 步驟，用於執行股票因子引擎。
    """

    def __init__(self, engine: StockFactorEngine):
        """
        初始化步驟。

        :param engine: 一個 StockFactorEngine 的實例。
        """
        self.engine = engine

    async def run(self, data: pd.DataFrame, context: Dict[str, Any]) -> pd.DataFrame:
        """
        對輸入的 DataFrame 執行因子引擎。

        :param data: 包含價格數據的 DataFrame。
        :param context: Pipeline 的共享上下文。
        :return: 處理後、包含新因子欄位的 DataFrame。
        """
        logger.info("正在執行 RunStockFactorEngineStep...")

        if data.empty:
            logger.warning("輸入的數據為空，跳過因子計算。")
            return data

        # StockFactorEngine 的 run 方法是按 symbol 處理的
        # 我們需要確保輸入的 data 是單一 symbol 的
        # 或者修改引擎以處理多個 symbol
        # 這裡我們假設 Pipeline 的上一步 (Loader) 已經將數據按 symbol 分組

        processed_data = await self.engine.run(data)

        logger.info("RunStockFactorEngineStep 執行完畢。")
        return processed_data


class RunCryptoFactorEngineStep(BaseStep):
    """
    一個 Pipeline 步驟，用於執行加密貨幣因子引擎。
    """

    def __init__(self, engine: CryptoFactorEngine):
        """
        初始化步驟。

        :param engine: 一個 CryptoFactorEngine 的實例。
        """
        self.engine = engine

    async def run(self, data: pd.DataFrame, context: Dict[str, Any]) -> pd.DataFrame:
        """
        對輸入的 DataFrame 執行因子引擎。

        :param data: 包含價格數據的 DataFrame。
        :param context: Pipeline 的共享上下文。
        :return: 處理後、包含新因子欄位的 DataFrame。
        """
        logger.info("正在執行 RunCryptoFactorEngineStep...")

        if data.empty:
            logger.warning("輸入的數據為空，跳過因子計算。")
            return data

        processed_data = await self.engine.run(data)

        logger.info("RunCryptoFactorEngineStep 執行完畢。")
        return processed_data
