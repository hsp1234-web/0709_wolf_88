# apps/factor_engine/engine.py
from typing import Any, Callable, Dict

import pandas as pd

from apps.factor_engine.sma_crossover_factor import calculate_sma_crossover


class FactorEngine:
    """
    因子引擎，負責註冊、管理及計算各種交易因子。
    """

    def __init__(self):
        """
        初始化因子引擎，並註冊所有可用的因子計算函數。
        """
        self._factors: Dict[str, Callable[..., pd.DataFrame]] = {}
        self._register_default_factors()

    def _register_factor(self, name: str, func: Callable[..., pd.DataFrame]):
        """
        註冊一個新的因子計算函數。

        :param name: 因子名稱，用於在設定中引用。
        :param func: 實現因子計算的函數。
        """
        if name in self._factors:
            # 在真實的應用中，這裡可能需要更完善的日誌或警告系統
            print(f"警告：因子 '{name}' 已被覆蓋。")
        self._factors[name] = func

    def _register_default_factors(self):
        """
        註冊所有內建的預設因子。
        """
        self._register_factor("sma_crossover", calculate_sma_crossover)
        # 未來若有新因子，可在此處繼續添加
        # self._register_factor("rsi", calculate_rsi_factor)
        # self._register_factor("macd", calculate_macd_factor)

    def compute(
        self, data: pd.DataFrame, factor_config: Dict[str, Any]
    ) -> pd.DataFrame | None:
        """
        根據提供的設定，計算指定的因子。

        :param data: 原始數據，通常是價格數據的 DataFrame。
                     (注意：在此版本的設計中，因子函數自行獲取數據，
                      此參數是為了未來擴充，使其能處理傳入的數據)
        :param factor_config: 一個字典，定義了要計算的因子及其參數。
                              例如：
                              {
                                  "name": "sma_crossover",
                                  "params": {
                                      "ticker": "spy",
                                      "start_date": "2023-01-01",
                                      "end_date": "2023-12-31",
                                      "short_window": 10,
                                      "long_window": 30
                                  }
                              }
        :return: 一個包含因子計算結果的 DataFrame，如果找不到因子則返回 None。
        """
        factor_name = factor_config.get("name")
        if not factor_name:
            print("錯誤：因子設定中未指定 'name'。")
            return None

        factor_func = self._factors.get(factor_name)
        if not factor_func:
            print(f"錯誤：找不到名為 '{factor_name}' 的因子。")
            return None

        params = factor_config.get("params", {})

        # 這裡我們假設因子函數會自行處理數據獲取
        # 在更進階的版本中，可以將 `data` DataFrame 傳入
        print(f"--- 因子引擎：開始計算 '{factor_name}' 因子 ---")
        try:
            # **params 會將字典解包成關鍵字參數傳遞
            return factor_func(**params)
        except Exception as e:
            print(f"計算因子 '{factor_name}' 時發生錯誤：{e}")
            return None

    def list_factors(self) -> list[str]:
        """
        返回所有已註冊的因子名稱列表。
        """
        return list(self._factors.keys())
