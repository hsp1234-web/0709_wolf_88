import pandas as pd
import numpy as np

class BondFactorEngine:
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        計算債券和利率特定因子。
        """
        result_df = df.copy()

        # 確保必要的欄位存在
        required_columns = ['yield_curve_slope', 'credit_spread', 'real_yield']
        if not all(col in result_df.columns for col in required_columns):
            missing_cols = [col for col in required_columns if col not in result_df.columns]
            raise ValueError(f"缺少必要的欄位來計算債券因子: {missing_cols}")

        # 殖利率曲線斜率 (直接使用)
        result_df['factor_yield_curve_slope'] = result_df['yield_curve_slope']

        # 高收益債信用利差 Z-score
        if 'credit_spread' in result_df.columns:
            # 將 credit_spread 轉換為數字類型，並將錯誤轉換為 NaN
            credit_spread_numeric = pd.to_numeric(result_df['credit_spread'], errors='coerce')

            # 計算 252 天滾動 Z-score
            rolling_mean = credit_spread_numeric.rolling(window=252).mean()
            rolling_std = credit_spread_numeric.rolling(window=252).std()
            result_df['factor_credit_spread_zscore'] = (credit_spread_numeric - rolling_mean) / rolling_std

        # 實質利率 (直接使用)
        result_df['factor_real_yield'] = result_df['real_yield']

        return result_df
