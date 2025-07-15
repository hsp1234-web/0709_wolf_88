# core/pipelines/steps/aggregators.py
from __future__ import annotations

import datetime  # Required for type hinting and potentially for internal logic
import logging

import pandas as pd

from ..base_step import BaseETLStep

# We will not import TimeAggregator from apps.time_aggregator.core.aggregator
# Instead, its core logic will be embedded into the TimeAggregatorStep.


class TimeAggregatorStep(BaseETLStep):
    """
    一個 ETL 步驟，用於將 Tick 數據聚合為指定時間間隔的 OHLCV 數據。
    """

    def __init__(
        self, aggregation_level: str = "1Min", db_writer_step: BaseETLStep | None = None
    ):
        """
        初始化 TimeAggregatorStep。

        Args:
            aggregation_level (str): 聚合的時間級別，例如 "1Min", "5Min"。
                                     目前主要實現 "1Min"。
            db_writer_step (BaseETLStep | None): 可選的下一步驟，用於將聚合數據寫入數據庫。
                                                 此參數是為了未來擴展，目前 execute 方法直接返回 DataFrame。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        # Correcting Pandas frequency string: 'T' or 'min' for minutes.
        # Pandas documentation suggests 'min' is preferred over 'T' for minutes.
        if "Min" in aggregation_level:
            self.aggregation_level_pd = aggregation_level.replace("Min", "min")
        elif "H" in aggregation_level:  # For hours
            self.aggregation_level_pd = aggregation_level.replace(
                "H", "h"
            )  # Pandas uses lowercase 'h'
        else:  # Add more rules or a default if needed
            self.aggregation_level_pd = (
                aggregation_level  # Use as is if no specific replacement rule
            )

        self.db_writer_step = (
            db_writer_step  # Not used in current execute, but for future design
        )
        self.logger.info(
            f"TimeAggregatorStep initialized for aggregation level: {aggregation_level} (Pandas rule: {self.aggregation_level_pd})"
        )

    def execute(self, data: pd.DataFrame | None = None) -> pd.DataFrame | None:
        """
        執行時間序列聚合。

        Args:
            data: 上一個步驟傳入的 Tick 數據 DataFrame。
                  預期包含 'timestamp', 'price', 'volume', 'instrument' 欄位。
                  'timestamp' 欄位必須是 datetime-like。

        Returns:
            一個包含聚合後 OHLCV 數據的 Pandas DataFrame。
            欄位為 ['timestamp', 'instrument', 'open', 'high', 'low', 'close', 'volume']。
            如果輸入數據為 None 或為空，則返回 None 或空 DataFrame。
        """
        if data is None or data.empty:
            self.logger.warning(
                "Input data is None or empty. TimeAggregatorStep cannot proceed."
            )
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "instrument",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]
            )

        self.logger.info(f"Executing TimeAggregatorStep with {len(data)} tick records.")

        expected_columns = ["timestamp", "price", "volume", "instrument"]
        if not all(col in data.columns for col in expected_columns):
            missing_cols = [col for col in expected_columns if col not in data.columns]
            self.logger.error(
                f"Input DataFrame is missing required columns: {missing_cols}"
            )
            raise ValueError(
                f"Input DataFrame for TimeAggregatorStep is missing columns: {missing_cols}"
            )

        if not pd.api.types.is_datetime64_any_dtype(data["timestamp"]):
            self.logger.info(
                "Attempting to convert 'timestamp' column to datetime objects."
            )
            try:
                data["timestamp"] = pd.to_datetime(data["timestamp"])
                self.logger.info(
                    "Successfully converted 'timestamp' column to datetime objects."
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to convert 'timestamp' column to datetime: {e}",
                    exc_info=True,
                )
                raise TypeError(
                    "Input DataFrame 'timestamp' column must be datetime-like or convertible to datetime."
                )

        ticks_df = data.copy()

        if (
            not isinstance(ticks_df.index, pd.DatetimeIndex)
            or ticks_df.index.name != "timestamp"
        ):
            if "timestamp" in ticks_df.columns:
                ticks_df = ticks_df.set_index("timestamp")
            else:
                self.logger.error(
                    "Critical: 'timestamp' column not found for setting index after initial checks."
                )
                raise ValueError(
                    "Cannot set 'timestamp' as index as it's not available."
                )

        ohlcv_list = []
        if "instrument" not in ticks_df.columns:
            self.logger.error("Critical: 'instrument' column not found for grouping.")
            raise ValueError("'instrument' column is required for aggregation.")

        for instrument, group_df in ticks_df.groupby("instrument"):
            self.logger.debug(
                f"Aggregating for instrument: {instrument}, {len(group_df)} ticks, rule: {self.aggregation_level_pd}"
            )

            agg_rules = {"price": ["first", "max", "min", "last"], "volume": "sum"}

            try:
                # Ensure the index is sorted for resampling to work correctly and avoid UserWarning
                group_df_sorted = group_df.sort_index()
                resampled_group = group_df_sorted.resample(
                    self.aggregation_level_pd
                ).agg(agg_rules)
            except Exception as e:
                self.logger.error(
                    f"Error during resampling for instrument {instrument} with rule '{self.aggregation_level_pd}': {e}",
                    exc_info=True,
                )
                continue

            if resampled_group.empty:
                self.logger.debug(
                    f"No data after resampling for instrument {instrument} at {self.aggregation_level_pd} interval."
                )
                continue

            resampled_group.columns = [
                "_".join(col).strip() for col in resampled_group.columns.values
            ]

            resampled_group.rename(
                columns={
                    "price_first": "open",
                    "price_max": "high",
                    "price_min": "low",
                    "price_last": "close",
                    "volume_sum": "volume",
                },
                inplace=True,
            )

            resampled_group["instrument"] = instrument
            ohlcv_list.append(resampled_group)

        if not ohlcv_list:
            self.logger.warning(
                "Aggregation resulted in an empty list. No OHLCV data produced."
            )
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "instrument",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]
            )

        final_ohlcv_df = pd.concat(ohlcv_list)
        final_ohlcv_df.reset_index(inplace=True)

        output_columns = [
            "timestamp",
            "instrument",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
        # Ensure all expected columns are present, fill with NaN if any are missing (e.g. if agg_rules somehow failed for a column)
        for col in output_columns:
            if col not in final_ohlcv_df.columns:
                final_ohlcv_df[col] = (
                    pd.NA
                )  # Or appropriate default like 0 for volume, NaN for prices

        final_ohlcv_df = final_ohlcv_df[output_columns]
        final_ohlcv_df.dropna(
            subset=["open", "high", "low", "close"], how="all", inplace=True
        )
        # Convert volume to integer type if it's float after aggregation (e.g. if NaNs were present then filled)
        if "volume" in final_ohlcv_df.columns:
            final_ohlcv_df["volume"] = (
                final_ohlcv_df["volume"].fillna(0).astype("int64")
            )

        self.logger.info(
            f"TimeAggregatorStep successfully aggregated {len(data)} ticks into {len(final_ohlcv_df)} OHLCV records."
        )

        return final_ohlcv_df


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    sample_ticks_data = [
        {
            "timestamp": datetime.datetime(2023, 1, 1, 9, 0, 5),
            "price": 100.0,
            "volume": 10,
            "instrument": "INSTR_A",
        },
        {
            "timestamp": datetime.datetime(2023, 1, 1, 9, 0, 15),
            "price": 101.0,
            "volume": 5,
            "instrument": "INSTR_A",
        },
        {
            "timestamp": datetime.datetime(2023, 1, 1, 9, 0, 30),
            "price": 99.0,
            "volume": 8,
            "instrument": "INSTR_A",
        },
        {
            "timestamp": datetime.datetime(2023, 1, 1, 9, 0, 50),
            "price": 100.5,
            "volume": 12,
            "instrument": "INSTR_A",
        },
        {
            "timestamp": datetime.datetime(2023, 1, 1, 9, 1, 10),
            "price": 102.0,
            "volume": 7,
            "instrument": "INSTR_A",
        },
        {
            "timestamp": datetime.datetime(2023, 1, 1, 9, 0, 10),
            "price": 2000.0,
            "volume": 20,
            "instrument": "INSTR_B",
        },
        {
            "timestamp": datetime.datetime(2023, 1, 1, 9, 0, 40),
            "price": 1995.0,
            "volume": 15,
            "instrument": "INSTR_B",
        },
    ]
    input_df = pd.DataFrame(sample_ticks_data)
    # 'timestamp' column is already datetime objects from creation

    print("--- Input DataFrame (Sample Ticks) ---")
    print(input_df)
    print(f"\nInput types:\n{input_df.dtypes}")

    aggregator_step = TimeAggregatorStep(aggregation_level="1Min")
    aggregated_data = aggregator_step.execute(input_df)

    if aggregated_data is not None:
        print("\n--- Aggregated Data (OHLCV) ---")
        print(aggregated_data)
        print(f"\nAggregated types:\n{aggregated_data.dtypes}")

        if not aggregated_data.empty:
            assert "timestamp" in aggregated_data.columns
            assert pd.api.types.is_datetime64_any_dtype(aggregated_data["timestamp"])
            assert "instrument" in aggregated_data.columns
            assert "open" in aggregated_data.columns
            assert "volume" in aggregated_data.columns
            assert pd.api.types.is_integer_dtype(aggregated_data["volume"])

            instr_a_first_min = aggregated_data[
                (aggregated_data["instrument"] == "INSTR_A")
                & (aggregated_data["timestamp"] == pd.Timestamp("2023-01-01 09:00:00"))
            ]
            if not instr_a_first_min.empty:
                print("\nINSTR_A 09:00:00 OHLCV:")
                print(instr_a_first_min)
                assert instr_a_first_min.iloc[0]["open"] == 100.0
                assert instr_a_first_min.iloc[0]["high"] == 101.0
                assert instr_a_first_min.iloc[0]["low"] == 99.0
                assert instr_a_first_min.iloc[0]["close"] == 100.5
                assert instr_a_first_min.iloc[0]["volume"] == 35  # 10+5+8+12
                print("INSTR_A 09:00:00 assertions passed.")
            else:
                print("Warning: INSTR_A 09:00:00 data not found in aggregated output.")
    else:
        print("Aggregator step did not return data.")
