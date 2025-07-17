import pandas as pd
import numpy as np

class IndexFactorEngine:
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        計算指數特定因子。
        """
        result_df = df.copy()

        # 確保必要的欄位存在
        required_columns = ['vix', 'move', 'close']
        if not all(col in result_df.columns for col in required_columns):
            missing_cols = [col for col in required_columns if col not in result_df.columns]
            raise ValueError(f"缺少必要的欄位來計算指數因子: {missing_cols}")

        # 股債波動率比率 (VIX / MOVE)
        # 避免除以零
        if 'vix' in result_df.columns and 'move' in result_df.columns:
            result_df['factor_vix_move_ratio'] = result_df['vix'] / result_df['move'].replace(0, np.nan)

        # 波動率風險溢價 (VIX - 已實現波動率)
        # 計算 20 日已實現波動率
        result_df['realized_vol_20d'] = result_df['close'].pct_change().rolling(window=20).std() * np.sqrt(252)
        if 'vix' in result_df.columns:
            result_df['factor_vrp'] = result_df['vix'] - result_df['realized_vol_20d']

        return result_df
