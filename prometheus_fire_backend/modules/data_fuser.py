# prometheus_fire_backend/modules/data_fuser.py

import logging
import json # 載入 JSON 檔案
from typing import Any, Dict, List, Optional # Optional 用於 __init__ 參數
from pathlib import Path # Path 用於處理檔案路徑
from core.config import PROJECT_ROOT # 引入 PROJECT_ROOT 以定位設定檔

# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # 全局 basicConfig 可能不是最佳選擇
logger = logging.getLogger(__name__) # 使用模組級 logger

class DataFuser:
    """
    資料融合器 (Data Fuser)。
    負責根據預設的規則和優先級，將來自不同來源的數據進行清洗、轉換和融合，
    最終生成「黃金記錄」(Golden Record)。
    """
    DEFAULT_PRIORITY_CONFIG_PATH = PROJECT_ROOT / "prometheus_fire_backend" / "config" / "source_priority.json"

    def __init__(self, priority_config_path: Optional[Path] = None):
        """
        初始化資料融合器。

        Args:
            priority_config_path (Optional[Path]): source_priority.json 檔案的路徑。
                                                   如果為 None，則使用預設路徑。
        """
        self.priority_config_path = priority_config_path if priority_config_path is not None else self.DEFAULT_PRIORITY_CONFIG_PATH
        self.priority_config: Dict[str, Any] = {}
        self._load_priority_config()

        logger.info("資料融合器 (DataFuser) 初始化完畢。")
        if self.priority_config:
            logger.info(f"已載入融合優先級設定從: {self.priority_config_path}")
            # logger.debug(f"融合規則: {self.priority_config}") # 詳細規則可在 debug 層級顯示
        else:
            logger.warning(f"未能載入融合優先級設定，或設定檔為空/無效。路徑: {self.priority_config_path}")

    def _load_priority_config(self):
        """從指定的路徑載入融合優先級設定檔 (source_priority.json)。"""
        try:
            if self.priority_config_path.exists() and self.priority_config_path.is_file():
                with open(self.priority_config_path, 'r', encoding='utf-8') as f:
                    self.priority_config = json.load(f)
                logger.info(f"成功從 {self.priority_config_path} 載入融合優先級設定。")
            else:
                logger.error(f"融合優先級設定檔不存在或不是一個檔案: {self.priority_config_path}")
                self.priority_config = {} # 保持為空字典，表示無有效規則
        except json.JSONDecodeError as e:
            logger.error(f"解析融合優先級設定檔 {self.priority_config_path} 時發生 JSON 錯誤: {e}", exc_info=True)
            self.priority_config = {}
        except Exception as e:
            logger.error(f"載入融合優先級設定檔 {self.priority_config_path} 時發生未知錯誤: {e}", exc_info=True)
            self.priority_config = {}

    # fuse_data 方法的簽名和實作將在後續步驟中根據計畫完全重寫。
import pandas as pd # 引入 pandas

class DataFuser:
    # ... (之前的 __init__ 和 _load_priority_config 方法保持不變)
    DEFAULT_PRIORITY_CONFIG_PATH = PROJECT_ROOT / "prometheus_fire_backend" / "config" / "source_priority.json"

    def __init__(self, priority_config_path: Optional[Path] = None):
        """
        初始化資料融合器。

        Args:
            priority_config_path (Optional[Path]): source_priority.json 檔案的路徑。
                                                   如果為 None，則使用預設路徑。
        """
        self.priority_config_path = priority_config_path if priority_config_path is not None else self.DEFAULT_PRIORITY_CONFIG_PATH
        self.priority_config: Dict[str, Any] = {}
        self._load_priority_config()

        logger.info("資料融合器 (DataFuser) 初始化完畢。")
        if self.priority_config:
            logger.info(f"已載入融合優先級設定從: {self.priority_config_path}")
        else:
            logger.warning(f"未能載入融合優先級設定，或設定檔為空/無效。路徑: {self.priority_config_path}")

    def _load_priority_config(self):
        """從指定的路徑載入融合優先級設定檔 (source_priority.json)。"""
        try:
            if self.priority_config_path.exists() and self.priority_config_path.is_file():
                with open(self.priority_config_path, 'r', encoding='utf-8') as f:
                    self.priority_config = json.load(f)
                logger.info(f"成功從 {self.priority_config_path} 載入融合優先級設定。")
            else:
                logger.error(f"融合優先級設定檔不存在或不是一個檔案: {self.priority_config_path}")
                self.priority_config = {}
        except json.JSONDecodeError as e:
            logger.error(f"解析融合優先級設定檔 {self.priority_config_path} 時發生 JSON 錯誤: {e}", exc_info=True)
            self.priority_config = {}
        except Exception as e:
            logger.error(f"載入融合優先級設定檔 {self.priority_config_path} 時發生未知錯誤: {e}", exc_info=True)
            self.priority_config = {}

    def fuse_data(self, ticker_symbol: str, date_str: str, data_type_to_fuse: str = "daily_ohlcv") -> Optional[Path]:
        """
        對指定股票和日期的數據進行融合，生成黃金記錄。

        Args:
            ticker_symbol (str): 股票代號，例如 "0050.TW"。
            date_str (str): 日期字串，格式 "YYYY-MM-DD"。
            data_type_to_fuse (str): 要融合的數據類型，例如 "daily_ohlcv"。
                                     此參數用於從 priority_config 中獲取對應的規則。

        Returns:
            Optional[Path]: 成功儲存的黃金記錄 Parquet 檔案路徑，如果失敗則返回 None。
        """
        logger.info(f"開始融合任務: Ticker: {ticker_symbol}, Date: {date_str}, DataType: {data_type_to_fuse}")

        if not self.priority_config or data_type_to_fuse not in self.priority_config:
            logger.error(f"缺少 '{data_type_to_fuse}' 的融合規則或優先級設定未載入。無法進行融合。")
            return None

        fusion_rules = self.priority_config[data_type_to_fuse] # 例如 daily_ohlcv 的規則

        raw_data_lake_base = PROJECT_ROOT / "data_lake" / "raw"
        golden_record_warehouse_base = PROJECT_ROOT / "data_warehouse" / "golden_records" / data_type_to_fuse

        # 1. 掃描並讀取相關 Parquet 檔案
        source_dataframes: Dict[str, pd.DataFrame] = {} # Key: source_name (e.g., "yfinance"), Value: DataFrame

        # 假設來源目錄與 priority_config 中定義的來源名稱一致 (例如 "taifex", "yfinance")
        # 並且 Parquet 檔案結構為: {source_name}/{data_type_to_fuse}/{ticker_symbol}/{date_str}.parquet
        # 或 {source_name}/{ticker_symbol}/{date_str}.parquet (如果 data_type_to_fuse 暗示了檔案類型)
        # 根據 YFinanceClient 和未來 TaifexClient 的 OHLCV 儲存路徑調整：
        # yfinance: data_lake/raw/yfinance/ohlcv/{ticker_symbol}/{date_str}.parquet -> ohlcv is data_type_to_fuse
        # taifex (假設): data_lake/raw/taifex/ohlcv/{ticker_symbol}/{date_str}.parquet

        potential_sources = set()
        for field_rules in fusion_rules.values(): # fusion_rules is Dict[str, List[str]]
            potential_sources.update(field_rules) # field_rules is List[str] of source names

        logger.debug(f"潛在數據來源 (基於規則 '{data_type_to_fuse}'): {potential_sources}")

        for source_name in potential_sources:
            # 假設原始數據的 data_type 與融合目標的 data_type_to_fuse 名稱一致
            # 例如，如果要融合 daily_ohlcv，則 yfinance 的原始數據在 yfinance/daily_ohlcv/...
            # 但 YFinanceClient 儲存時是 yfinance/ohlcv/... 此處需要統一或配置化
            # 為了簡化，我們假設融合的 data_type_to_fuse (如 daily_ohlcv) 就是原始數據的子目錄名
            # 如果 YFinanceClient 存的是 'ohlcv'，而規則用 'daily_ohlcv'，需要映射或調整
            # 暫時假設規則中的 data_type_to_fuse (如 "daily_ohlcv") 與檔案路徑中的目錄名一致。
            # 或者，我們可以讓 source_priority.json 更詳細地描述每個來源的路徑模式。
            # 目前的 TaifexClient 沒有 OHLCV，YFinanceClient 的是 'ohlcv'。
            # 我們將假設融合規則 "daily_ohlcv" 意指在各來源下找名為 "daily_ohlcv" 或 "ohlcv" 的子目錄。
            # 為了與 YFinanceClient 一致，我們將在掃描時檢查 'ohlcv' 子目錄。
            # TODO: 使此處的路徑查找更具彈性或可配置。

            source_specific_data_type_dir = "ohlcv" # 假設目前只處理OHLCV，且來源都用此目錄名
            parquet_path = raw_data_lake_base / source_name / source_specific_data_type_dir / ticker_symbol / f"{date_str}.parquet"

            if parquet_path.exists() and parquet_path.is_file():
                try:
                    df = pd.read_parquet(parquet_path)
                    if not df.empty:
                        # 確保索引是 DatetimeIndex，以便進行可能的對齊或時間點查找
                        if not isinstance(df.index, pd.DatetimeIndex):
                            try:
                                df.index = pd.to_datetime(df.index)
                            except Exception as e_idx:
                                logger.warning(f"轉換 {source_name} 數據 ({parquet_path}) 索引為 DatetimeIndex 失敗: {e_idx}。將嘗試不轉換索引直接使用。")

                        source_dataframes[source_name] = df
                        logger.info(f"成功從 {parquet_path} 為來源 '{source_name}' 載入數據。Shape: {df.shape}")
                    else:
                        logger.info(f"來源 '{source_name}' 的數據檔案 {parquet_path} 為空。")
                except Exception as e:
                    logger.error(f"從 {parquet_path} 為來源 '{source_name}' 載入數據失敗: {e}", exc_info=True)
            else:
                logger.info(f"來源 '{source_name}' 的數據檔案 {parquet_path} 未找到。")

        if not source_dataframes:
            logger.warning(f"未找到任何有效的原始數據檔案 for Ticker: {ticker_symbol}, Date: {date_str}, DataType: {data_type_to_fuse}。無法進行融合。")
            return None

        # 2. 逐欄位裁決與合併
        # 假設所有 DataFrame 都只有一行（對應特定日期）或需要從索引中選取特定日期行
        # yfinance.history(start=date, end=date+1day) 通常返回單行（如果該日有數據）
        # 我們需要確保能處理多行 DataFrame（例如，如果意外讀取了多日數據）並選取正確日期

        golden_data_row = {} # 用於構建黃金記錄的單行數據

        target_datetime = pd.to_datetime(date_str) # 將目標日期字串轉為 datetime 物件，方便比較

        for field, source_priority_list in fusion_rules.items(): # field: "Open", source_priority_list: ["taifex", "yfinance"]
            found_value_for_field = False
            for source_name in source_priority_list:
                if source_name in source_dataframes:
                    source_df = source_dataframes[source_name]
                    # 檢查 DataFrame 是否包含該欄位
                    if field in source_df.columns:
                        # 從 DataFrame 中提取目標日期的值
                        # 假設 DataFrame 的索引是 DatetimeIndex
                        # 如果 DataFrame 只有一行，直接取；如果有多行，按日期篩選
                        value_to_use = None
                        if target_datetime in source_df.index:
                            value_at_date = source_df.loc[target_datetime, field]
                            # 處理可能的 Series (如果有多個相同索引) 或單個值
                            if isinstance(value_at_date, pd.Series):
                                if not value_at_date.empty:
                                    value_to_use = value_at_date.iloc[0] # 取第一個匹配項
                            else:
                                value_to_use = value_at_date
                        elif not source_df.empty: # 如果目標日期不在索引中，但df不為空 (可能只有一行且索引不同名)
                             # 這種情況比較tricky，如果df只有一行，我們可以假設這一行就是目標日期的數據
                             # 但這依賴於上游客戶端返回數據的約定
                             if len(source_df) == 1:
                                logger.warning(f"目標日期 {date_str} 不在來源 '{source_name}' 的索引中，但該 DataFrame 只有一行。將嘗試使用此行的 '{field}' 值。索引: {source_df.index[0]}")
                                value_to_use = source_df.iloc[0][field]
                             else:
                                logger.warning(f"目標日期 {date_str} 不在來源 '{source_name}' 的索引中 (多行數據)。無法為 '{field}' 提取確定值。")


                        if pd.notna(value_to_use): # 檢查值是否非空 (NaN, None, NaT)
                            golden_data_row[field] = value_to_use
                            logger.debug(f"欄位 '{field}': 從來源 '{source_name}' 選取值: {value_to_use}")
                            found_value_for_field = True
                            break # 已為此欄位找到值，跳到下一個欄位
                        else:
                            logger.debug(f"欄位 '{field}': 來源 '{source_name}' 的值為空/NA。")
                    else:
                        logger.debug(f"欄位 '{field}': 在來源 '{source_name}' 的數據中未找到。")
                else:
                    logger.debug(f"欄位 '{field}': 規則中指定的來源 '{source_name}' 沒有已載入的數據。")

            if not found_value_for_field:
                golden_data_row[field] = None # 或 pd.NA，確保欄位存在於黃金記錄中，即使值為空
                logger.info(f"欄位 '{field}': 未能在任何指定來源中找到有效值。設定為 None。")

        if not golden_data_row or all(pd.isna(v) for v in golden_data_row.values()):
            logger.warning(f"融合後未產生任何有效數據 for Ticker: {ticker_symbol}, Date: {date_str}。不生成黃金記錄。")
            return None

        # 將單行數據轉換為 DataFrame，索引設為目標日期
        golden_df = pd.DataFrame([golden_data_row], index=[target_datetime])
        golden_df.index.name = 'Date' # 或 'Datetime'，與 yfinance 保持一致

        # 3. 儲存黃金紀錄
        try:
            output_dir = golden_record_warehouse_base / ticker_symbol
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{date_str}.parquet"

            golden_df.to_parquet(output_path, index=True)
            logger.info(f"成功將融合後的黃金記錄儲存到: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"儲存融合後的黃金記錄到 {output_path} 失敗: {e}", exc_info=True)
            return None

if __name__ == '__main__':
    # 簡易測試 (未來應移至 pytest)
    # 需要先手動在 data_lake/raw/ 下創建模擬的 Parquet 檔案
    # 例如:
    # data_lake/raw/yfinance/ohlcv/0050.TW/2023-10-26.parquet
    # data_lake/raw/taifex/ohlcv/0050.TW/2023-10-26.parquet (假設 taifex 也提供)

    logger.info("--- 測試 DataFuser (完整 fuse_data 邏輯) ---")

    # 準備: 創建模擬的 DataFuser (它會自動載入 config/source_priority.json)
    fuser = DataFuser()
    if not fuser.priority_config:
        print("錯誤: DataFuser 未能載入優先級設定，無法繼續測試 fuse_data。")
        exit()

    # 準備: 創建模擬的 Parquet 檔案 (如果不存在)
    mock_ticker = "MOCK.SY"
    mock_date = "2024-01-15"
    mock_datetime = pd.to_datetime(mock_date)

    # 清理舊的模擬檔案和黃金記錄 (如果存在)
    mock_yfinance_dir = PROJECT_ROOT / "data_lake" / "raw" / "yfinance" / "ohlcv" / mock_ticker
    mock_yfinance_file = mock_yfinance_dir / f"{mock_date}.parquet"
    if mock_yfinance_file.exists(): mock_yfinance_file.unlink()

    mock_taifex_dir = PROJECT_ROOT / "data_lake" / "raw" / "taifex" / "ohlcv" / mock_ticker
    mock_taifex_file = mock_taifex_dir / f"{mock_date}.parquet"
    if mock_taifex_file.exists(): mock_taifex_file.unlink()

    mock_golden_dir = PROJECT_ROOT / "data_warehouse" / "golden_records" / "daily_ohlcv" / mock_ticker
    mock_golden_file = mock_golden_dir / f"{mock_date}.parquet"
    if mock_golden_file.exists(): mock_golden_file.unlink()


    # 模擬 yfinance 數據
    yfinance_data = {
        'Open': [100.0], 'High': [105.0], 'Low': [99.0],
        'Close': [102.0], 'Volume': [1000000], 'Adj Close': [102.0]
    }
    df_yfinance = pd.DataFrame(yfinance_data, index=[mock_datetime])
    df_yfinance.index.name = "Date"
    mock_yfinance_dir.mkdir(parents=True, exist_ok=True)
    df_yfinance.to_parquet(mock_yfinance_file)
    print(f"已創建模擬 yfinance 數據: {mock_yfinance_file}")

    # 模擬 taifex 數據 (假設它有 Open, High, Low, Close，但 Volume 較差或沒有)
    taifex_data = {
        'Open': [100.5], 'High': [105.5], 'Low': [98.5],
        'Close': [101.0], 'Volume': [500] # Taifex Volume 優先級較低
    }
    df_taifex = pd.DataFrame(taifex_data, index=[mock_datetime])
    df_taifex.index.name = "Date" # 假設索引名也統一
    mock_taifex_dir.mkdir(parents=True, exist_ok=True)
    df_taifex.to_parquet(mock_taifex_file)
    print(f"已創建模擬 taifex 數據: {mock_taifex_file}")

    # 執行融合
    print(f"\n開始融合 {mock_ticker} on {mock_date}...")
    golden_path = fuser.fuse_data(ticker_symbol=mock_ticker, date_str=mock_date)

    if golden_path and golden_path.exists():
        print(f"融合成功！黃金記錄已生成於: {golden_path}")
        df_golden = pd.read_parquet(golden_path)
        print("黃金記錄內容:")
        print(df_golden)

        # 根據 source_priority.json 的規則，預期結果：
        # Open, High, Low, Close 來自 taifex (優先)
        # Volume 來自 yfinance (優先)
        # Adj Close (如果規則中未定義，則不會出現在黃金記錄中，除非我們有 'all_other_columns' 規則)
        # 假設目前的規則只包含 Open, High, Low, Close, Volume
        expected_open = df_taifex['Open'].iloc[0]
        expected_high = df_taifex['High'].iloc[0]
        expected_low = df_taifex['Low'].iloc[0]
        expected_close = df_taifex['Close'].iloc[0]
        expected_volume = df_yfinance['Volume'].iloc[0] # yfinance volume 優先

        assert df_golden['Open'].iloc[0] == expected_open, f"Open 欄位不符預期! Got {df_golden['Open'].iloc[0]}, Expected {expected_open}"
        assert df_golden['High'].iloc[0] == expected_high, f"High 欄位不符預期! Got {df_golden['High'].iloc[0]}, Expected {expected_high}"
        assert df_golden['Low'].iloc[0] == expected_low, f"Low 欄位不符預期! Got {df_golden['Low'].iloc[0]}, Expected {expected_low}"
        assert df_golden['Close'].iloc[0] == expected_close, f"Close 欄位不符預期! Got {df_golden['Close'].iloc[0]}, Expected {expected_close}"
        assert df_golden['Volume'].iloc[0] == expected_volume, f"Volume 欄位不符預期! Got {df_golden['Volume'].iloc[0]}, Expected {expected_volume}"

        # 檢查黃金記錄是否只包含在 fusion_rules 中定義的欄位
        expected_columns = list(fuser.priority_config.get("daily_ohlcv", {}).keys())
        assert all(col in expected_columns for col in df_golden.columns), f"黃金記錄包含未在規則中定義的欄位: {df_golden.columns.tolist()} vs {expected_columns}"
        assert all(col in df_golden.columns for col in expected_columns if golden_data_row.get(col) is not None ), "黃金記錄缺少規則中應有數據的欄位"


        print("\n斷言通過：黃金記錄內容符合預期！")
    else:
        print("融合失敗或未生成黃金記錄。")

    # 清理模擬檔案
    if mock_yfinance_file.exists(): mock_yfinance_file.unlink()
    if mock_yfinance_dir.exists() and not list(mock_yfinance_dir.iterdir()): mock_yfinance_dir.rmdir()

    if mock_taifex_file.exists(): mock_taifex_file.unlink()
    if mock_taifex_dir.exists() and not list(mock_taifex_dir.iterdir()): mock_taifex_dir.rmdir()

    if mock_golden_file.exists(): mock_golden_file.unlink()
    if mock_golden_dir.exists() and not list(mock_golden_dir.iterdir()): mock_golden_dir.rmdir()
    print("模擬檔案已清理。")

    logger.info("--- DataFuser fuse_data 測試完畢 ---")
    logger.info("--- 測試 DataFuser (載入設定) ---")

    # 測試預設路徑
    fuser_default = DataFuser()
    if fuser_default.priority_config:
        print(f"使用預設路徑成功載入設定。'daily_ohlcv' 規則鍵: {list(fuser_default.priority_config.get('daily_ohlcv', {}).keys())}")
    else:
        print(f"使用預設路徑未能載入設定或設定為空。請確認 {DataFuser.DEFAULT_PRIORITY_CONFIG_PATH} 是否存在且有效。")

    # 測試提供有效路徑 (假設 source_priority.json 已在計畫步驟1中創建)
    # 此處的路徑應與 DEFAULT_PRIORITY_CONFIG_PATH 相同，用於演示
    valid_path_for_test = PROJECT_ROOT / "prometheus_fire_backend" / "config" / "source_priority.json"
    if not valid_path_for_test.exists():
         print(f"警告: 測試用的 source_priority.json ({valid_path_for_test}) 不存在，無法進行此部分測試。")
    else:
        fuser_valid_path = DataFuser(priority_config_path=valid_path_for_test)
        if fuser_valid_path.priority_config:
            print(f"使用指定有效路徑 ({valid_path_for_test}) 成功載入設定。'daily_ohlcv' 規則鍵: {list(fuser_valid_path.priority_config.get('daily_ohlcv', {}).keys())}")
            assert "Open" in fuser_valid_path.priority_config.get('daily_ohlcv', {}) # 簡單斷言，檢查 'Open' 規則是否存在
        else:
            print(f"錯誤: 使用指定有效路徑 ({valid_path_for_test}) 未能載入設定。")


    # 測試提供無效/不存在的路徑
    invalid_path = PROJECT_ROOT / "config" / "non_existent_priority_config.json"
    fuser_invalid_path = DataFuser(priority_config_path=invalid_path)
    if not fuser_invalid_path.priority_config: # 預期 priority_config 為空字典
        print(f"使用無效路徑 ({invalid_path}) 未能載入設定，符合預期 (priority_config is empty: {not bool(fuser_invalid_path.priority_config)})。")
    else:
        print(f"錯誤：使用無效路徑 ({invalid_path}) 卻載入了設定: {fuser_invalid_path.priority_config}")

    # 測試一個內容無效的 JSON 檔案 (需要手動創建一個這樣的檔案來進行此測試)
    # 例如，創建一個名為 'invalid_source_priority.json' 的檔案，內容為 '{ "bad_json": "missing_quote }'
    # invalid_json_path = PROJECT_ROOT / "prometheus_fire_backend" / "config" / "invalid_source_priority.json"
    # if invalid_json_path.exists():
    #     fuser_invalid_json = DataFuser(priority_config_path=invalid_json_path)
    #     if not fuser_invalid_json.priority_config:
    #         print(f"使用無效 JSON 檔案 ({invalid_json_path}) 未能載入設定，符合預期。")
    #     else:
    #         print(f"錯誤：使用無效 JSON 檔案 ({invalid_json_path}) 卻載入了設定: {fuser_invalid_json.priority_config}")
    # else:
    #     print(f"跳過無效 JSON 檔案測試，因檔案 {invalid_json_path} 不存在。")


    # 舊的 fuse_data 樁測試可以移除或更新，因為 fuse_data 的簽名和功能將完全改變
    # print("\n--- 測試舊版 fuse_data 樁 ---")
    # fuser_for_stub_test = DataFuser() # 使用預設設定檔路徑
    # mock_raw_data_stub = {
    #     "source_A": {"name": "Company A", "value": 100},
    #     "source_B": {"description": "Desc B", "value": 150}
    # }
    # golden_record_stub = fuser_for_stub_test.fuse_data("test_mission_stub_001", mock_raw_data_stub)
    # print(f"舊樁 fuse_data 的結果: {golden_record_stub}")
    # assert "舊版 fuse_data 樁被調用" in golden_record_stub["fusion_log"][0]

    logger.info("--- DataFuser __init__ 測試完畢 ---")
