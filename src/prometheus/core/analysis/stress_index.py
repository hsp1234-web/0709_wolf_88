import logging
from datetime import datetime, timedelta

import numpy as np
from prometheus.core.logging.log_manager import LogManager
import pandas as pd
import plotly.graph_objects as go

from prometheus.core.clients.fred import FredClient
from prometheus.core.clients.nyfed import NYFedClient

logger = LogManager.get_instance().get_logger("StressIndexCalculator")


class StressIndexCalculator:
    def __init__(self, rolling_window=252):
        logger.info("正在初始化壓力指數計算引擎...")
        self.fred_client = FredClient()
        self.nyfed_client = NYFedClient()
        self.rolling_window = rolling_window
        self.logger = logging.getLogger(self.__class__.__name__)

    def _fetch_all_data(self, force_refresh=False):
        data_frames = {}
        nyfed_df = self.nyfed_client.fetch_data(force_refresh=force_refresh)
        if not nyfed_df.empty and "Date" in nyfed_df.columns and "Total_Positions" in nyfed_df.columns:
            data_frames["NYFed_Positions"] = nyfed_df[["Date", "Total_Positions"]].set_index("Date")
        fred_symbols = {"VIX": "VIXCLS", "Yield_Spread": "T10Y2Y", "Reserves": "WTREGEN", "SOFR": "SOFR"}
        for name, symbol in fred_symbols.items():
            df_item = self.fred_client.fetch_data(symbol, force_refresh=force_refresh)
            if not df_item.empty:
                data_frames[name] = df_item
        return data_frames

    def _align_and_preprocess(self, data_frames):
        if not data_frames:
            return pd.DataFrame()
        combined_df = pd.concat(data_frames.values(), axis=1, join="outer")
        combined_df = combined_df.ffill().dropna()
        return combined_df

    def _normalize_to_zscore(self, df):
        zscore_df = pd.DataFrame(index=df.index)
        for col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce")
            if series.isnull().all():
                continue
            rolling_mean = series.rolling(window=self.rolling_window, min_periods=1).mean()
            rolling_std = series.rolling(window=self.rolling_window, min_periods=1).std()
            rolling_std.loc[rolling_std.abs() < 1e-6] = 1.0
            zscore_values = (series - rolling_mean) / rolling_std
            zscore_df[f"{col}_zscore"] = zscore_values
        return zscore_df.dropna()

    def _invert_and_weight(self, zscore_df):
        if "VIX_zscore" in zscore_df.columns:
            zscore_df["VIX_zscore"] = -zscore_df["VIX_zscore"]
        if "Yield_Spread_zscore" in zscore_df.columns:
            zscore_df["Yield_Spread_zscore"] = -zscore_df["Yield_Spread_zscore"]
        return zscore_df

    def calculate_stress_index(self, force_refresh=False):
        data_frames = self._fetch_all_data(force_refresh=force_refresh)
        aligned_df = self._align_and_preprocess(data_frames)
        if aligned_df.empty:
            return pd.Series(dtype="float64")
        zscore_df = self._normalize_to_zscore(aligned_df)
        weighted_df = self._invert_and_weight(zscore_df)
        stress_index = weighted_df.mean(axis=1)
        return stress_index.dropna()

    def plot_stress_index(self, stress_index, zscore_components):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=stress_index.index, y=stress_index, mode='lines', name='Stress Index', line=dict(color='red', width=2)))
        for col in zscore_components.columns:
            fig.add_trace(go.Scatter(x=zscore_components.index, y=zscore_components[col], mode='lines', name=col, visible='legendonly'))
        fig.update_layout(title="Financial Stress Index and Components", xaxis_title="Date", yaxis_title="Z-Score / Index Value")
        fig.show()

if __name__ == "__main__":
    calculator = StressIndexCalculator()
    stress_index = calculator.calculate_stress_index()
    if not stress_index.empty:
        print("Stress Index calculated successfully:")
        print(stress_index.tail())
        data_frames = calculator._fetch_all_data()
        aligned_df = calculator._align_and_preprocess(data_frames)
        zscore_df = calculator._normalize_to_zscore(aligned_df)
        calculator.plot_stress_index(stress_index, zscore_df)
    else:
        print("Failed to calculate Stress Index.")
