# core/clients/nyfed.py
# 此模組包含從紐約聯儲 (NY Fed) 下載和解析一級交易商持有量數據的客戶端邏輯。

import traceback
from io import BytesIO
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from .base import BaseAPIClient
from prometheus.core.logging.log_manager import LogManager

logger = LogManager.get_instance().get_logger("NYFedClient")

# NY Fed API URLs 和解析設定 (保持不變)
NYFED_DATA_CONFIGS: List[Dict[str, Any]] = [
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBN2024/timeseries/PDPOSGSC-L2_PDPOSGSC-G2L3_PDPOSGSC-G3L6_PDPOSGSC-G6L7_PDPOSGSC-G7L11_PDPOSGSC-G11L21_PDPOSGSC-G21.xlsx",
        "type": "SBN",
        "sheet_name": 0,
        "header_row": 0,
        "date_column_names": ["AS OF DATE"],
        "value_column_name": "VALUE (MILLIONS)",
        "notes": "SBN2024 - PDPOSGSC series",
    },
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBN2022/timeseries/PDPOSGSC-L2_PDPOSGSC-G2L3_PDPOSGSC-G3L6_PDPOSGSC-G6L7_PDPOSGSC-G7L11_PDPOSGSC-G11L21_PDPOSGSC-G21.xlsx",
        "type": "SBN",
        "sheet_name": 0,
        "header_row": 0,
        "date_column_names": ["AS OF DATE"],
        "value_column_name": "VALUE (MILLIONS)",
        "notes": "SBN2022 - PDPOSGSC series",
    },
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBN2015/timeseries/PDPOSGSC-L2_PDPOSGSC-G2L3_PDPOSGSC-G3L6_PDPOSGSC-G6L7_PDPOSGSC-G7L11_PDPOSGSC-G11.xlsx",
        "type": "SBN",
        "sheet_name": 0,
        "header_row": 0,
        "date_column_names": ["AS OF DATE"],
        "value_column_name": "VALUE (MILLIONS)",
        "notes": "SBN2015 - PDPOSGSC series (G11 結尾)",
    },
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBN2013/timeseries/PDPOSGSC-L2_PDPOSGSC-G2L3_PDPOSGSC-G3L6_PDPOSGSC-G6L7_PDPOSGSC-G7L11_PDPOSGSC-G11.xlsx",
        "type": "SBN",
        "sheet_name": 0,
        "header_row": 0,
        "date_column_names": ["AS OF DATE"],
        "value_column_name": "VALUE (MILLIONS)",
        "notes": "SBN2013 - PDPOSGSC series",
    },
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBP2013/timeseries/PDPUSGCS3LNOP_PDPUSGCS36NOP_PDPUSGCS611NOP_PDPUSGCSM11NOP.xlsx",
        "type": "SBP",
        "sheet_name": 0,
        "header_row": 0,
        "date_column_names": ["AS OF DATE"],
        "value_column_name": "VALUE (MILLIONS)",
        "cols_to_sum_if_sbp": [
            "PDPUSGCS3LNOP",
            "PDPUSGCS36NOP",
            "PDPUSGCS611NOP",
            "PDPUSGCSM11NOP",
        ],
        "notes": "SBP2013 - 加總指定欄位",
    },
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBP2001/timeseries/PDPUSGCS5LNOP_PDPUSGCS5MNOP.xlsx",
        "type": "SBP",
        "sheet_name": 0,
        "header_row": 0,
        "date_column_names": ["AS OF DATE"],
        "value_column_name": "VALUE (MILLIONS)",
        "cols_to_sum_if_sbp": ["PDPUSGCS5LNOP", "PDPUSGCS5MNOP"],
        "notes": "SBP2001 - 加總指定欄位",
    },
]


class NYFedClient(BaseAPIClient):  # 類名從 NYFedAPIClient 改為 NYFedClient
    """
    用於從紐約聯儲 (NY Fed) API 下載和解析一級交易商持有量數據的客戶端。
    此客戶端不使用傳統的 API Key 或 JSON API，而是下載 Excel 檔案。
    """

    def __init__(self, data_configs: Optional[List[Dict[str, Any]]] = None):
        """
        初始化 NYFedClient。

        Args:
            data_configs (Optional[List[Dict[str, Any]]]):
                用於指定下載來源和解析方式的配置列表。
                如果未提供，則使用模組中定義的預設 NYFED_DATA_CONFIGS。
        """
        # NYFed 不使用 API Key 和標準的 base_url 模式，但仍調用父類構造函數
        super().__init__(api_key=None, base_url=None)
        self.data_configs = data_configs or NYFED_DATA_CONFIGS
        logger.info(f"NYFedClient 初始化完成，將使用 {len(self.data_configs)} 個數據源配置。")

    def _download_excel_to_dataframe(
        self, config: Dict[str, Any]
    ) -> Optional[pd.DataFrame]:
        """
        從指定的 API URL 下載 Excel 檔案並讀取特定 sheet 到 DataFrame。
        """
        url = config["url"]
        sheet_name = config.get("sheet_name", 0)
        header_row = config.get("header_row", 0)

        logger.debug(f"正在從 {url} 下載 Excel 數據 (Sheet: {sheet_name}, Header: {header_row})...")
        try:
            response: requests.Response = self._session.get(url, timeout=60)
            response.raise_for_status()

            excel_file = BytesIO(response.content)
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=header_row, engine="openpyxl")

            df.columns = [str(col).strip().upper().replace("\n", " ").replace("\r", " ").replace("  ", " ") for col in df.columns]

            logger.debug(f"成功從 {url} 下載並讀取了 {len(df)} 行數據。")
            return df
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"下載 Excel 檔案 {url} 時發生 HTTP 錯誤: {http_err}", exc_info=True)
            return None
        except requests.exceptions.RequestException as req_err:
            logger.error(f"下載 Excel 檔案 {url} 時發生網路錯誤: {req_err}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"處理來自 {url} 的 Excel 檔案時發生錯誤: {e}", exc_info=True)
            return None

    def _parse_dealer_positions(
        self, df_raw: pd.DataFrame, config: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        根據設定解析從單個 Excel 檔案讀取的一級交易商持有量數據。
        """
        date_col_name = config["date_column_names"][0]
        if date_col_name not in df_raw.columns:
            logger.error(f"在來源 {config['url']} 的數據中找不到預期日期欄位 '{date_col_name}'。可用欄位: {df_raw.columns.tolist()}")
            return pd.DataFrame(columns=["Date", "Total_Positions"])

        df = df_raw.copy()
        df.rename(columns={date_col_name: "Date"}, inplace=True)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        value_col_name = config.get("value_column_name", "VALUE (MILLIONS)")
        required_core_cols = [value_col_name]
        if config["type"] == "SBP":
            required_core_cols.append("TIME SERIES")

        missing_core_cols = [col for col in required_core_cols if col not in df.columns]
        if missing_core_cols:
            logger.error(f"類型 {config['type']} 的數據 ({config['url']}) 缺少核心欄位: {missing_core_cols}。可用欄位: {df.columns.tolist()}")
            return pd.DataFrame(columns=["Date", "Total_Positions"])

        df[value_col_name] = pd.to_numeric(df[value_col_name], errors="coerce")

        if config["type"] == "SBP":
            cols_to_sum = config.get("cols_to_sum_if_sbp")
            if not cols_to_sum:
                logger.error(f"SBP 類型數據 ({config['url']}) 未在配置中提供 'cols_to_sum_if_sbp' 列表。")
                return pd.DataFrame(columns=["Date", "Total_Positions"])
            target_series_codes = [code.upper() for code in cols_to_sum]
            df_filtered = df[df["TIME SERIES"].isin(target_series_codes)]
            if df_filtered.empty:
                logger.warning(f"SBP 類型數據 ({config['url']}) 在篩選目標 TIME SERIES {target_series_codes} 後為空。")
                return pd.DataFrame(columns=["Date", "Total_Positions"])
            summed_df = df_filtered.groupby("Date")[value_col_name].sum().reset_index()
            summed_df.rename(columns={value_col_name: "Total_Positions"}, inplace=True)
            df_processed = summed_df
        elif config["type"] == "SBN":
            summed_df = df.groupby("Date")[value_col_name].sum().reset_index()
            summed_df.rename(columns={value_col_name: "Total_Positions"}, inplace=True)
            df_processed = summed_df
        else:
            logger.error(f"未知的數據類型 '{config['type']}' for url {config['url']}")
            return pd.DataFrame(columns=["Date", "Total_Positions"])

        df_processed.dropna(subset=["Date", "Total_Positions"], inplace=True)
        if df_processed.empty:
            logger.warning(f"處理後 DataFrame ({config['url']}) 為空。")
            return pd.DataFrame(columns=["Date", "Total_Positions"])

        df_processed["Total_Positions"] = df_processed["Total_Positions"] * 1_000_000
        if df_processed["Date"].dt.tz is not None:
            df_processed["Date"] = df_processed["Date"].dt.tz_localize(None)
        return df_processed[["Date", "Total_Positions"]].sort_values(by="Date").reset_index(drop=True)

    def fetch_data(self, symbol: str = "", **kwargs) -> pd.DataFrame:
        """
        從 NY Fed API 獲取所有設定的一級交易商持有量數據，並進行合併和處理。
        """
        force_refresh = kwargs.get("force_refresh", False)

        if symbol:
            logger.debug(f"接收到 symbol='{symbol}'，但此參數當前被忽略。")

        all_data_frames: List[pd.DataFrame] = []
        logger.info(f"開始獲取所有一級交易商數據 (強制刷新={force_refresh})...")

        with self._get_request_context(force_refresh=force_refresh):
            for config in self.data_configs:
                logger.debug(f"處理配置: {config.get('notes', config['url'])}")
                df_raw = self._download_excel_to_dataframe(config)
                if df_raw is not None and not df_raw.empty:
                    df_parsed = self._parse_dealer_positions(df_raw, config)
                    if not df_parsed.empty:
                        all_data_frames.append(df_parsed)
                        logger.debug(f"成功解析來自 {config['url']} 的 {len(df_parsed)} 筆有效數據。")
                    else:
                        logger.warning(f"解析來自 {config['url']} 的數據後無有效記錄。")
                else:
                    logger.warning(f"下載或讀取來自 {config['url']} 的數據失敗或原始數據為空。")

        if not all_data_frames:
            logger.error("未能從任何 NY Fed 來源成功獲取和解析一級交易商數據。")
            return pd.DataFrame(columns=["Date", "Total_Positions"])

        combined_df = pd.concat(all_data_frames, ignore_index=True)
        combined_df.sort_values(by="Date", inplace=True)
        combined_df.drop_duplicates(subset=["Date"], keep="first", inplace=True)
        combined_df.reset_index(drop=True, inplace=True)

        logger.info(f"成功合併所有 NY Fed 一級交易商數據，最終共 {len(combined_df)} 筆唯一日期記錄。")
        return combined_df


# 範例使用 (主要用於開發時測試)
if __name__ == "__main__":
    print("--- NYFedClient 快取整合後測試 (直接執行 core/clients/nyfed.py) ---")
    client = NYFedClient()
    try:
        print("\n--- 執行第一次 (應會下載所有檔案) ---")
        data_first_run = client.fetch_data()
        if not data_first_run.empty:
            print(f"第一次執行成功，獲取 {len(data_first_run)} 筆數據。")
            # 檢查是否有快取相關的日誌 (在 _download_excel_to_dataframe 或 BaseAPIClient 中)
            # 注意：由於 NYFedClient 下載多個檔案，此處的 from_cache 可能不明顯
            # 真正的快取效果體現在第二次運行時，請求不應實際發出

        print("\n--- 執行第二次 (應從快取讀取所有檔案) ---")
        data_second_run = client.fetch_data()
        if not data_second_run.empty:
            print(f"第二次執行成功，獲取 {len(data_second_run)} 筆數據。")
            # 這裡需要依賴 BaseAPIClient 中 get_cached_session 的日誌
            # 或 _download_excel_to_dataframe 中 response.from_cache (如果適用)
            # 來確認是否從快取讀取。

        print("\n--- 執行第三次 (強制刷新，應重新下載所有檔案) ---")
        data_third_run = client.fetch_data(force_refresh=True)
        if not data_third_run.empty:
            print(f"第三次執行 (強制刷新) 成功，獲取 {len(data_third_run)} 筆數據。")

        # 基本的健全性檢查
        if not (
            data_first_run.equals(data_second_run)
            and data_first_run.equals(data_third_run)
        ):
            print("\n警告：不同執行之間的數據不一致，請檢查！")
            print(f"第一次 vs 第二次是否相等: {data_first_run.equals(data_second_run)}")
            print(f"第一次 vs 第三次是否相等: {data_first_run.equals(data_third_run)}")
        else:
            print("\n數據一致性檢查通過。")

        if not data_first_run.empty:
            print(
                f"\n最終合併的一級交易商持有量數據範例 (共 {len(data_first_run)} 筆):"
            )
            print("最早的 5 筆數據:")
            print(data_first_run.head())
            print("\n最新的 5 筆數據:")
            print(data_first_run.tail())
        else:
            print("錯誤：未能獲取任何一級交易商持有量數據。")

    except Exception as e:
        print(f"執行 NYFedClient 測試期間發生未預期錯誤: {e}")
        traceback.print_exc()
    finally:
        client.close_session()  # 確保關閉 session

    print("\n--- NYFedClient 快取整合後測試結束 ---")
