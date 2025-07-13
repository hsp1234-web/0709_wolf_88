# core/pipelines/steps/financial_steps.py
from core.pipelines.base_step import BaseETLStep  # 修正導入


class BuildGoldLayerStep(BaseETLStep):  # 修正繼承
    """
    將多個來源的數據融合成「黃金層」數據的管線步驟。
    """

    def execute(self, data=None):  # 修正方法名稱
        print("\n--- [Step] Executing BuildGoldLayerStep ---")
        # 在此執行黃金層數據的複雜ETL邏輯
        # ...
        print("--- [Success] Gold layer data built. ---")
        # 為了測試，返回一個成功的標誌
        return {"status": "gold_layer_ok"}


from core.analysis.stress_index import StressIndexCalculator


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
            print(f"--- [Error] An error occurred during stress index calculation: {e} ---")
            return {"status": "error", "reason": str(e)}
        finally:
            if calculator:
                calculator.close_all_sessions()
