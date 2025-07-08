import logging
import json
from typing import Any, Dict, List, Optional
from pathlib import Path
import pandas as pd
import pandas_ta as ta # 導入 pandas_ta
import numpy as np # 用於生成模擬數據

from core.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

class FactorEngine:
    """
    因子引擎 (Factor Engine)。
    負責從黃金紀錄中讀取數據，並根據預設的「因子配方」計算量化因子。
    """
    DEFAULT_RECIPES_CONFIG_PATH = PROJECT_ROOT / "prometheus_fire_backend" / "config" / "factor_recipes.json"
    DEFAULT_FACTOR_STORE_BASE_PATH = PROJECT_ROOT / "data_warehouse" / "factor_store" / "daily"

    def __init__(self,
                 recipes_config_path: Optional[Path] = None,
                 factor_store_base_path: Optional[Path] = None):
        """
        初始化因子引擎。

        Args:
            recipes_config_path (Optional[Path]): 因子配方設定檔 (factor_recipes.json) 的路徑。
                                                 如果為 None，則使用預設路徑。
            factor_store_base_path (Optional[Path]): 儲存每日因子數據的基礎路徑。
                                                      如果為 None，則使用預設路徑。
        """
        self.recipes_config_path = recipes_config_path if recipes_config_path is not None else self.DEFAULT_RECIPES_CONFIG_PATH
        self.factor_store_base_path = factor_store_base_path if factor_store_base_path is not None else self.DEFAULT_FACTOR_STORE_BASE_PATH

        self.recipes: Dict[str, Any] = {}
        self._load_recipes()

        logger.info("因子引擎 (FactorEngine) 初始化完畢。")
        if self.recipes:
            logger.info(f"已從 {self.recipes_config_path} 載入 {len(self.recipes)} 個因子配方。")
        else:
            logger.warning(f"未能從 {self.recipes_config_path} 載入因子配方，或設定檔為空/無效。")

    def _load_recipes(self):
        """從指定的路徑載入因子配方設定檔 (factor_recipes.json)。"""
        try:
            if self.recipes_config_path.exists() and self.recipes_config_path.is_file():
                with open(self.recipes_config_path, 'r', encoding='utf-8') as f:
                    self.recipes = json.load(f)
                logger.info(f"成功從 {self.recipes_config_path} 載入因子配方。")
            else:
                logger.error(f"因子配方設定檔不存在或不是一個檔案: {self.recipes_config_path}")
                self.recipes = {}
        except json.JSONDecodeError as e:
            logger.error(f"解析因子配方設定檔 {self.recipes_config_path} 時發生 JSON 錯誤: {e}", exc_info=True)
            self.recipes = {}
        except Exception as e:
            logger.error(f"載入因子配方設定檔 {self.recipes_config_path} 時發生未知錯誤: {e}", exc_info=True)
            self.recipes = {}

    def calculate_factors(self, golden_ohlcv_df: pd.DataFrame) -> pd.DataFrame:
        """
        根據載入的因子配方，在給定的黃金 OHLCV DataFrame 上計算所有因子。

        Args:
            golden_ohlcv_df (pd.DataFrame): 包含黃金 OHLCV 數據的 DataFrame。
                                           索引應為日期時間，欄位包含 'Open', 'High', 'Low', 'Close', 'Volume'。

        Returns:
            pd.DataFrame: 一個新的 DataFrame，包含原始 OHLCV 數據以及所有成功計算出的因子列。
                          如果沒有配方或輸入 DataFrame 為空，則可能返回原始 DataFrame 的副本或空 DataFrame。
        """
        if not self.recipes:
            logger.warning("沒有載入任何因子配方，無法計算因子。")
            return golden_ohlcv_df.copy() if golden_ohlcv_df is not None else pd.DataFrame()

        if golden_ohlcv_df is None or golden_ohlcv_df.empty:
            logger.warning("輸入的黃金 OHLCV DataFrame 為空，無法計算因子。")
            return pd.DataFrame()

        factors_df = golden_ohlcv_df.copy()

        if not isinstance(factors_df.index, pd.DatetimeIndex):
            try:
                factors_df.index = pd.to_datetime(factors_df.index)
            except Exception as e:
                logger.error(f"無法將輸入 DataFrame 的索引轉換為 DatetimeIndex: {e}。因子計算可能會失敗。")
                return factors_df

        for factor_id, recipe in self.recipes.items():
            logger.debug(f"開始計算因子: {factor_id}，配方: {recipe}")
            try:
                calculator_func_name = recipe.get("calculator_function")
                params = recipe.get("params", {})
                source_column_name = params.get("source_column", "Close")
                output_col_name = recipe.get("output_column_name", factor_id)

                if not hasattr(factors_df.ta, calculator_func_name):
                    logger.error(f"因子 '{factor_id}': pandas_ta 中找不到指定的計算函數 '{calculator_func_name}'。")
                    continue

                calculator_method = getattr(factors_df.ta, calculator_func_name)

                ta_params = {}
                if 'length' in params: ta_params['length'] = params['length']
                if 'fast' in params: ta_params['fast'] = params['fast']
                if 'slow' in params: ta_params['slow'] = params['slow']
                if 'signal' in params: ta_params['signal'] = params['signal']

                if source_column_name not in factors_df.columns:
                    logger.error(f"因子 '{factor_id}': 配方中指定的源數據欄位 '{source_column_name}' 在輸入 DataFrame 中不存在。")
                    continue

                source_series = factors_df[source_column_name]

                # 預期 pandas_ta 方法如 sma, rsi 等以 'close' 作為其主要序列參數名
                # 其他方法可能需要 'high', 'low', 'open', 'volume'
                # 為了簡化，這裡主要處理以 'close' (通過 source_column_name 傳遞) 為主的情況
                # 對於需要多列的指標 (如 ATR)，pandas_ta 通常能從 DataFrame 自動推斷
                # 如果 calculator_method 明確需要 'high', 'low', 'close' 等，則需調整參數傳遞
                # 例如，ATR: df.ta.atr(length=params['length'], high=df['High'], low=df['Low'], close=df['Close'])
                # 目前，我們假設 'close' 參數是通用的，並傳遞 source_series 給它。
                # 這對 SMA, RSI 是有效的。

                # 檢查計算函數是否需要 'close' 參數 (大多數情況)
                # 更健壯的方式是檢查 calculator_method 的簽名，或讓 recipe 更明確指定輸入映射
                # 為了此階段的實現，我們假設 'close' 是標準接口
                calculated_series = calculator_method(close=source_series, **ta_params)

                if calculated_series is not None:
                    # pandas_ta 返回的 Series 可能有自己的名字，例如 "SMA_10"
                    # 我們要用 recipe 中定義的 output_column_name
                    factors_df[output_col_name] = calculated_series
                    logger.info(f"成功計算並添加因子 '{output_col_name}' (來自 {factor_id})。")
                else:
                    logger.warning(f"因子 '{factor_id}' 的計算結果為 None。")

            except Exception as e:
                logger.error(f"計算因子 '{factor_id}' 時發生錯誤: {e}", exc_info=True)
                factors_df[output_col_name] = pd.NA

        return factors_df

    def generate_and_store_daily_factors(self, golden_ohlcv_df: pd.DataFrame, ticker_symbol: str) -> List[Path]:
        """
        計算給定黃金 OHLCV 數據的所有因子，並將每日結果儲存到 Parquet 檔案。
        每日的 Parquet 檔案將包含當天所有已計算的因子值。
        """
        logger.info(f"開始為股票 {ticker_symbol} 生成並儲存每日因子...")
        if golden_ohlcv_df.empty:
            logger.warning("輸入的黃金 OHLCV DataFrame 為空，不執行因子生成和儲存。")
            return []

        all_factors_df = self.calculate_factors(golden_ohlcv_df)
        if all_factors_df.empty:
            logger.warning("因子計算未返回有效數據，無法儲存。")
            return []

        logger.debug(f"計算得到的完整因子 DataFrame for {ticker_symbol} (head):\n{all_factors_df.head()}")

        stored_file_paths: List[Path] = []

        factor_columns_to_store = [
            recipe.get("output_column_name", factor_id)
            for factor_id, recipe in self.recipes.items()
            if recipe.get("output_column_name", factor_id) in all_factors_df.columns # 只選擇實際計算出的列
        ]

        if not factor_columns_to_store:
            logger.warning(f"沒有有效的因子列可供儲存 for {ticker_symbol}。")
            return []

        for date_idx, row_data in all_factors_df.iterrows():
            # date_idx 應為 DatetimeIndex 中的 Timestamp 物件
            date_str = date_idx.strftime('%Y-%m-%d')

            current_day_factor_values = {}
            has_any_valid_factor_for_day = False
            for factor_col_name in factor_columns_to_store:
                if factor_col_name in row_data and pd.notna(row_data[factor_col_name]):
                    current_day_factor_values[factor_col_name] = row_data[factor_col_name]
                    has_any_valid_factor_for_day = True

            if not has_any_valid_factor_for_day:
                logger.debug(f"日期 {date_str} for {ticker_symbol} 沒有有效的因子數據可儲存，跳過。")
                continue

            # 創建單行 DataFrame，索引為當前日期
            daily_factors_to_save_df = pd.DataFrame([current_day_factor_values], index=[date_idx])
            daily_factors_to_save_df.index.name = "Date"


            output_dir = self.factor_store_base_path / ticker_symbol
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{date_str}.parquet"

            try:
                daily_factors_to_save_df.to_parquet(output_path, index=True)
                logger.info(f"成功將 {ticker_symbol} 在 {date_str} 的因子數據儲存到: {output_path}")
                stored_file_paths.append(output_path)
            except Exception as e:
                logger.error(f"儲存 {ticker_symbol} 在 {date_str} 的因子數據到 {output_path} 失敗: {e}", exc_info=True)

        logger.info(f"為股票 {ticker_symbol} 完成每日因子儲存，共儲存 {len(stored_file_paths)} 個檔案。")
        return stored_file_paths


if __name__ == '__main__':
    # 配置基本的日誌記錄器，以便在直接運行此檔案時能看到日誌輸出
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info("--- 測試 FactorEngine ---")

    engine = FactorEngine()
    if not engine.recipes:
        print("錯誤: FactorEngine 未能載入因子配方，無法繼續測試。")
        exit()

    num_days = 30
    start_date_dt = pd.to_datetime("2023-01-01")
    date_index = pd.date_range(start_date_dt, periods=num_days, freq='B')

    # 使用 numpy 生成更隨機的 OHLCV 數據
    np.random.seed(42) # 為了可重複性
    open_prices = np.random.uniform(90, 100, num_days)
    # High 必須 >= Open 且 >= Low 且 >= Close
    # Low 必須 <= Open 且 <= High 且 <= Close
    # Close 是一個隨機遊走
    close_changes = np.random.normal(0, 1, num_days).cumsum()
    close_prices = open_prices[0] + close_changes
    close_prices = np.clip(close_prices, 50, 150) # 限制價格範圍

    high_prices = np.maximum.reduce([open_prices, close_prices, np.random.uniform(close_prices, close_prices + 5, num_days)])
    low_prices = np.minimum.reduce([open_prices, close_prices, np.random.uniform(close_prices - 5, close_prices, num_days)])
    # 再次確保 H >= L
    high_prices = np.maximum(high_prices, low_prices + 0.1)


    volume_data = np.random.randint(100000, 5000000, num_days)

    mock_ohlcv_df = pd.DataFrame({
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volume_data
    }, index=date_index)
    mock_ohlcv_df.index.name = "Date"

    print("模擬的黃金 OHLCV DataFrame (前5行):")
    print(mock_ohlcv_df.head())

    print("\n測試 calculate_factors...")
    factors_result_df = engine.calculate_factors(mock_ohlcv_df.copy())

    print("\n因子計算結果 DataFrame (前15行):")
    print(factors_result_df.head(15))

    assert "SMA_10_Close" in factors_result_df.columns, "SMA_10_Close 因子未生成"
    assert "RSI_14_Close" in factors_result_df.columns, "RSI_14_Close 因子未生成"

    if len(factors_result_df) > 9:
        assert pd.notna(factors_result_df["SMA_10_Close"].iloc[9]), "SMA_10_Close 在索引9應有值"
        if len(factors_result_df) > 8:
             assert pd.isna(factors_result_df["SMA_10_Close"].iloc[8]), "SMA_10_Close 在索引8應為NaN"

    if len(factors_result_df) > 14:
        assert pd.notna(factors_result_df["RSI_14_Close"].iloc[14]), "RSI_14_Close 在索引14應有值"
        if len(factors_result_df) > 13:
            assert pd.isna(factors_result_df["RSI_14_Close"].iloc[13]), "RSI_14_Close 在索引13應為NaN"

    print("calculate_factors 基本驗證通過。")

    mock_ticker_for_storage = "MOCK_FCTR_ENG"
    print(f"\n測試 generate_and_store_daily_factors for {mock_ticker_for_storage}...")

    test_output_base_dir = FactorEngine.DEFAULT_FACTOR_STORE_BASE_PATH
    test_output_dir_ticker = test_output_base_dir / mock_ticker_for_storage
    if test_output_dir_ticker.exists():
        shutil.rmtree(test_output_dir_ticker) # 清理舊的 ticker 目錄

    stored_paths = engine.generate_and_store_daily_factors(mock_ohlcv_df.copy(), mock_ticker_for_storage)

    expected_num_files_with_factors = 0
    if len(mock_ohlcv_df) >= 10: # SMA_10 需要至少10天數據才能開始有值
        expected_num_files_with_factors = len(mock_ohlcv_df) - 9

    if not stored_paths and expected_num_files_with_factors > 0 :
        print(f"錯誤：generate_and_store_daily_factors 未返回任何儲存路徑，但預期應有 {expected_num_files_with_factors} 個檔案。")
    elif len(stored_paths) != expected_num_files_with_factors:
        print(f"警告: 儲存的因子檔案數量 ({len(stored_paths)}) 與預期 ({expected_num_files_with_factors}) 不符。可能是因子計算初期的 NaN 值導致部分日期無有效因子可存。")
    else:
         print(f"成功儲存 {len(stored_paths)} 個每日因子檔案。")

    if stored_paths:
        # 抽查最後一個儲存的檔案 (理論上應該包含所有因子)
        last_stored_file_path = stored_paths[-1]
        df_sample_factor_day = pd.read_parquet(last_stored_file_path)
        print(f"\n抽查最後一個儲存的因子檔案 ({last_stored_file_path.name}) 內容:")
        print(df_sample_factor_day)

        assert "SMA_10_Close" in df_sample_factor_day.columns
        assert "RSI_14_Close" in df_sample_factor_day.columns
        assert pd.notna(df_sample_factor_day["SMA_10_Close"].iloc[0])
        if len(mock_ohlcv_df) >= 15 : # RSI_14 需要至少15天數據
             assert pd.notna(df_sample_factor_day["RSI_14_Close"].iloc[0])

        date_of_sample_str = last_stored_file_path.stem
        original_row_for_sample = factors_result_df.loc[pd.to_datetime(date_of_sample_str)]

        assert df_sample_factor_day["SMA_10_Close"].iloc[0] == original_row_for_sample["SMA_10_Close"]
        if "RSI_14_Close" in df_sample_factor_day.columns and pd.notna(original_row_for_sample["RSI_14_Close"]):
            assert df_sample_factor_day["RSI_14_Close"].iloc[0] == original_row_for_sample["RSI_14_Close"]
        print("抽查檔案內容與原始計算一致。")

    if test_output_dir_ticker.exists():
        shutil.rmtree(test_output_dir_ticker)
    print(f"generate_and_store_daily_factors 測試完畢並清理 {mock_ticker_for_storage} 的因子檔案。")

    logger.info("--- FactorEngine 測試完畢 ---")
