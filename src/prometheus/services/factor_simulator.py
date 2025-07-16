# -*- coding: utf-8 -*-
import joblib
import pandas as pd
from sklearn.linear_model import LinearRegression
from pathlib import Path

class FactorSimulator:
    """
    因子代理模擬器，負責模型的訓練、保存與預測。
    """

    def __init__(self, model_dir: str = "data/models"):
        """
        初始化 FactorSimulator。

        :param model_dir: 存放模型的目錄。
        """
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model = None

    def train(self, target_series: pd.Series, predictors_df: pd.DataFrame):
        """
        訓練模型並保存。

        :param target_series: 目標因子 (例如 T10Y2Y 的歷史數據)。
        :param predictors_df: 預測因子 (來自 factors.duckdb)。
        """
        target_name = target_series.name
        model_path = self.model_dir / f"{target_name}_simulator.joblib"

        # 處理數據對齊
        aligned_df = predictors_df.join(target_series, how='inner')

        # 處理缺失值
        aligned_df = aligned_df.dropna()

        X = aligned_df[predictors_df.columns]
        y = aligned_df[target_name]

        self.model = LinearRegression()
        self.model.fit(X, y)

        joblib.dump(self.model, model_path)
        print(f"模型已成功訓練並保存至：{model_path}")

    def predict(self, predictors_df: pd.DataFrame, target_name: str) -> pd.Series:
        """
        載入已保存的模型並進行預測。

        :param predictors_df: 當前的預測因子數據。
        :param target_name: 目標因子的名稱。
        :return: 模擬出的目標因子值。
        """
        model_path = self.model_dir / f"{target_name}_simulator.joblib"
        if not model_path.exists():
            raise FileNotFoundError(f"找不到模型檔案：{model_path}")

        model = joblib.load(model_path)

        # 確保預測數據的欄位順序與訓練時一致
        predictors_df = predictors_df.reindex(columns=model.feature_names_in_, fill_value=0)

        return pd.Series(model.predict(predictors_df), index=predictors_df.index)
