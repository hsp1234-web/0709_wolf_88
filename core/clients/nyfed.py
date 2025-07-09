# core/clients/nyfed.py
# 此模組包含從紐約聯儲 (NY Fed) 下載和解析一級交易商持有量數據的客戶端邏輯。

import requests
import pandas as pd
from io import BytesIO
from datetime import datetime
import traceback
from typing import List, Dict, Any, Optional

# NY Fed API URLs 和解析設定
# 每個字典包含: url, type ('SBN'/'SBP'), sheet_name, header_row, date_column_names, value_column_pattern/cols_to_sum
NYFED_DATA_CONFIGS: List[Dict[str, Any]] = [
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBN2024/timeseries/PDPOSGSC-L2_PDPOSGSC-G2L3_PDPOSGSC-G3L6_PDPOSGSC-G6L7_PDPOSGSC-G7L11_PDPOSGSC-G11L21_PDPOSGSC-G21.xlsx",
        "type": "SBN", "sheet_name": 0, "header_row": 0, "date_column_names": ["AS OF DATE"],
        "value_column_name": "VALUE (MILLIONS)", "notes": "SBN2024 - PDPOSGSC series"
    },
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBN2022/timeseries/PDPOSGSC-L2_PDPOSGSC-G2L3_PDPOSGSC-G3L6_PDPOSGSC-G6L7_PDPOSGSC-G7L11_PDPOSGSC-G11L21_PDPOSGSC-G21.xlsx",
        "type": "SBN", "sheet_name": 0, "header_row": 0, "date_column_names": ["AS OF DATE"],
        "value_column_name": "VALUE (MILLIONS)", "notes": "SBN2022 - PDPOSGSC series"
    },
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBN2015/timeseries/PDPOSGSC-L2_PDPOSGSC-G2L3_PDPOSGSC-G3L6_PDPOSGSC-G6L7_PDPOSGSC-G7L11_PDPOSGSC-G11.xlsx",
        "type": "SBN", "sheet_name": 0, "header_row": 0, "date_column_names": ["AS OF DATE"],
        "value_column_name": "VALUE (MILLIONS)", "notes": "SBN2015 - PDPOSGSC series (G11 結尾)"
    },
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBN2013/timeseries/PDPOSGSC-L2_PDPOSGSC-G2L3_PDPOSGSC-G3L6_PDPOSGSC-G6L7_PDPOSGSC-G7L11_PDPOSGSC-G11.xlsx",
        "type": "SBN", "sheet_name": 0, "header_row": 0, "date_column_names": ["AS OF DATE"],
        "value_column_name": "VALUE (MILLIONS)", "notes": "SBN2013 - PDPOSGSC series"
    },
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBP2013/timeseries/PDPUSGCS3LNOP_PDPUSGCS36NOP_PDPUSGCS611NOP_PDPUSGCSM11NOP.xlsx",
        "type": "SBP", "sheet_name": 0, "header_row": 0, "date_column_names": ["AS OF DATE"],
        "value_column_name": "VALUE (MILLIONS)",
        "cols_to_sum_if_sbp": ['PDPUSGCS3LNOP', 'PDPUSGCS36NOP', 'PDPUSGCS611NOP', 'PDPUSGCSM11NOP'],
        "notes": "SBP2013 - 加總指定欄位"
    },
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBP2001/timeseries/PDPUSGCS5LNOP_PDPUSGCS5MNOP.xlsx",
        "type": "SBP", "sheet_name": 0, "header_row": 0, "date_column_names": ["AS OF DATE"],
        "value_column_name": "VALUE (MILLIONS)",
        "cols_to_sum_if_sbp": ['PDPUSGCS5LNOP', 'PDPUSGCS5MNOP'],
        "notes": "SBP2001 - 加總指定欄位"
    }
]

class NYFedAPIClient:
    """
    用於從紐約聯儲 (NY Fed) API 下載和解析一級交易商持有量數據的客戶端。
    """

    def __init__(self, data_configs: Optional[List[Dict[str, Any]]] = None):
        """
        初始化 NYFedAPIClient。

        Args:
            data_configs (Optional[List[Dict[str, Any]]]):
                用於指定下載來源和解析方式的配置列表。
                如果未提供，則使用模組中定義的預設 NYFED_DATA_CONFIGS。
        """
        self.data_configs = data_configs or NYFED_DATA_CONFIGS
        print(f"資訊：NYFedAPIClient 初始化完成，將使用 {len(self.data_configs)} 個數據源配置。")

    def _download_excel_to_dataframe(self, config: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        從指定的 API URL 下載 Excel 檔案並讀取特定 sheet 到 DataFrame。
        此為內部輔助方法。

        Args:
            config (Dict[str, Any]): 單個數據源的配置字典。

        Returns:
            Optional[pd.DataFrame]: 包含 Excel 數據的 DataFrame，若下載或讀取失敗則為 None。
        """
        url = config["url"]
        sheet_name = config.get("sheet_name", 0)
        header_row = config.get("header_row", 0)

        print(f"資訊：正在從 {url} 下載 Excel 數據 (Sheet: {sheet_name}, Header: {header_row})...")
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            excel_file = BytesIO(response.content)
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=header_row, engine='openpyxl')

            # 清理欄位名稱
            df.columns = [str(col).strip().upper().replace('\N{LINE FEED}', ' ').replace('\n', ' ').replace('\r', ' ').replace('  ', ' ') for col in df.columns]

            print(f"資訊：成功從 {url} 下載並讀取了 {len(df)} 行數據。")
            return df
        except requests.exceptions.RequestException as e:
            print(f"錯誤：下載 Excel 檔案 {url} 時發生網路錯誤: {e}")
        except Exception as e:
            print(f"錯誤：處理來自 {url} 的 Excel 檔案時發生錯誤: {e}")
            traceback.print_exc()
        return None

    def _parse_dealer_positions(self, df_raw: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        """
        根據設定解析從單個 Excel 檔案讀取的一級交易商持有量數據。
        此為內部輔助方法。

        Args:
            df_raw (pd.DataFrame): 從 Excel 讀取的原始 DataFrame。
            config (Dict[str, Any]): 對應的數據源配置字典。

        Returns:
            pd.DataFrame: 包含 'Date' 和 'Total_Positions' 兩欄的 DataFrame。
                          如果解析失敗或無有效數據，則返回空的 DataFrame。
        """
        # 查找日期欄位 (預期已在 config["date_column_names"][0] 中指定為 "AS OF DATE")
        date_col_name = config["date_column_names"][0]
        if date_col_name not in df_raw.columns:
            print(f"錯誤：在來源 {config['url']} 的數據中找不到預期日期欄位 '{date_col_name}'。可用欄位: {df_raw.columns.tolist()}")
            return pd.DataFrame(columns=['Date', 'Total_Positions'])

        df = df_raw.copy() # 操作副本
        df.rename(columns={date_col_name: 'Date'}, inplace=True)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

        value_col_name = config.get("value_column_name", "VALUE (MILLIONS)") # 預設值

        # 檢查核心數值欄位是否存在
        required_core_cols = [value_col_name]
        if config["type"] == "SBP": # SBP 類型還需要 TIME SERIES 欄位來篩選
            required_core_cols.append("TIME SERIES")

        missing_core_cols = [col for col in required_core_cols if col not in df.columns]
        if missing_core_cols:
            print(f"錯誤：類型 {config['type']} 的數據 ({config['url']}) 缺少核心欄位: {missing_core_cols}。可用欄位: {df.columns.tolist()}")
            return pd.DataFrame(columns=['Date', 'Total_Positions'])

        df[value_col_name] = pd.to_numeric(df[value_col_name], errors='coerce')

        if config["type"] == "SBP":
            cols_to_sum = config.get("cols_to_sum_if_sbp")
            if not cols_to_sum:
                print(f"錯誤：SBP 類型數據 ({config['url']}) 未在配置中提供 'cols_to_sum_if_sbp' 列表。")
                return pd.DataFrame(columns=['Date', 'Total_Positions'])

            target_series_codes = [code.upper() for code in cols_to_sum]
            df_filtered = df[df["TIME SERIES"].isin(target_series_codes)]

            if df_filtered.empty:
                print(f"警告：SBP 類型數據 ({config['url']}) 在篩選目標 TIME SERIES {target_series_codes} 後為空。")
                return pd.DataFrame(columns=['Date', 'Total_Positions'])

            summed_df = df_filtered.groupby('Date')[value_col_name].sum().reset_index()
            summed_df.rename(columns={value_col_name: 'Total_Positions'}, inplace=True)
            df_processed = summed_df
            print(f"資訊：為 SBP ({config['url']}) 篩選並加總了 TIME SERIES {target_series_codes} 的 '{value_col_name}'。")

        elif config["type"] == "SBN":
            # SBN 類型：按日期分組，加總所有 time series 的 value
            summed_df = df.groupby('Date')[value_col_name].sum().reset_index()
            summed_df.rename(columns={value_col_name: 'Total_Positions'}, inplace=True)
            df_processed = summed_df
            print(f"資訊：為 SBN ({config['url']}) 按日期加總了 '{value_col_name}'。")
        else:
            print(f"錯誤：未知的數據類型 '{config['type']}' for url {config['url']}")
            return pd.DataFrame(columns=['Date', 'Total_Positions'])

        # 數據清洗和格式化
        df_processed.dropna(subset=['Date', 'Total_Positions'], inplace=True)
        if df_processed.empty:
             print(f"警告：處理後 DataFrame ({config['url']}) 為空 (可能因日期轉換失敗或 Total_Positions 為 NaN)。")
             return pd.DataFrame(columns=['Date', 'Total_Positions'])


        df_processed['Total_Positions'] = df_processed['Total_Positions'] * 1_000_000 # 單位從百萬轉換
        if df_processed['Date'].dt.tz is not None:
            df_processed['Date'] = df_processed['Date'].dt.tz_localize(None)

        return df_processed[['Date', 'Total_Positions']].sort_values(by='Date').reset_index(drop=True)

    def fetch_all_primary_dealer_positions(self) -> pd.DataFrame:
        """
        從 NY Fed API 獲取所有設定的一級交易商持有量數據，並進行合併和處理。

        Returns:
            pd.DataFrame: 包含 'Date' 和 'Total_Positions' (單位：實際數值) 的時間序列數據。
                          如果未能從任何來源獲取數據，則返回空的 DataFrame。
        """
        all_data_frames: List[pd.DataFrame] = []
        print("資訊：開始獲取所有一級交易商數據...")

        for config in self.data_configs:
            print(f"\n資訊：處理配置: {config.get('notes', config['url'])}")
            df_raw = self._download_excel_to_dataframe(config)
            if df_raw is not None and not df_raw.empty:
                df_parsed = self._parse_dealer_positions(df_raw, config)
                if not df_parsed.empty:
                    all_data_frames.append(df_parsed)
                    print(f"資訊：成功解析來自 {config['url']} 的 {len(df_parsed)} 筆有效數據。")
                else:
                    print(f"警告：解析來自 {config['url']} 的數據後無有效記錄。")
            else:
                print(f"警告：下載或讀取來自 {config['url']} 的數據失敗或原始數據為空。")

        if not all_data_frames:
            print("錯誤：未能從任何 NY Fed 來源成功獲取和解析一級交易商數據。")
            return pd.DataFrame(columns=['Date', 'Total_Positions'])

        # 合併所有來源的數據
        combined_df = pd.concat(all_data_frames, ignore_index=True)

        # 處理可能的日期重疊：按日期分組，如果有多個來源提供同一日期的數據，
        # 這裡選擇保留第一個出現的 (基於 NYFED_DATA_CONFIGS 的順序，通常較新的年份在前)。
        # 或者，可以考慮加總，但 NYFED 的數據源設計通常是不同年份的文件包含不重疊的歷史時期。
        # 如果確實有重疊，drop_duplicates(keep='first') 是合理的。
        # 更穩健的做法是，如果日期有重疊，應該檢查數據是否一致，或根據數據源的權威性選擇。
        # 目前的 NYFED_DATA_CONFIGS 似乎是按年份劃分，理論上日期重疊較少，除非配置本身有問題。
        # 我們先按日期排序，再去重，保留第一個。
        combined_df.sort_values(by='Date', inplace=True)
        combined_df.drop_duplicates(subset=['Date'], keep='first', inplace=True)

        combined_df.reset_index(drop=True, inplace=True)

        print(f"\n資訊：成功合併所有 NY Fed 一級交易商數據，最終共 {len(combined_df)} 筆唯一日期記錄。")
        return combined_df

# 範例使用 (主要用於開發時測試)
if __name__ == '__main__':
    print("--- NYFed API Client 測試 (直接執行 core/clients/nyfed.py) ---")
    try:
        client = NYFedAPIClient() # 使用預設配置

        dealer_positions_data = client.fetch_all_primary_dealer_positions()

        if not dealer_positions_data.empty:
            print(f"\n最終合併的一級交易商持有量數據範例 (共 {len(dealer_positions_data)} 筆):")
            print("最早的 5 筆數據:")
            print(dealer_positions_data.head())
            print("\n最新的 5 筆數據:")
            print(dealer_positions_data.tail())

            # 檢查是否有 NaN 值
            if dealer_positions_data['Total_Positions'].isnull().any():
                print("\n警告：Total_Positions 欄位中存在 NaN 值。")
                print(dealer_positions_data[dealer_positions_data['Total_Positions'].isnull()])

            # 簡單繪圖 (如果環境允許)
            try:
                import matplotlib.pyplot as plt
                plt.figure(figsize=(10, 5))
                plt.plot(dealer_positions_data['Date'], dealer_positions_data['Total_Positions'])
                plt.title('NY Fed 一級交易商總持有量')
                plt.xlabel('日期')
                plt.ylabel('總持有量 (實際數值)')
                plt.grid(True)
                # plt.show() # 在非互動環境下可能不顯示，或需要保存到檔案
                print("\n(可選) 數據已準備好，可進行繪圖。")
            except ImportError:
                print("\n(可選) 未安裝 matplotlib，無法進行繪圖預覽。")
        else:
            print("錯誤：未能獲取任何一級交易商持有量數據。")

    except Exception as e:
        print(f"執行 NYFedAPIClient 測試期間發生未預期錯誤: {e}")
        traceback.print_exc()

    print("--- NYFed API Client 測試結束 ---")
