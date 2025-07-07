# apps/nyfed_client/client.py
# 這個模組包含從紐約聯儲 (NY Fed) 下載和解析一級交易商持有量數據的客戶端邏輯。
# 版本更新：參考 "一級交易pro.py Cell 1" 中的 URL 和加總邏輯。

import requests
import pandas as pd
import duckdb
from io import BytesIO
from datetime import datetime
import traceback

# 資料庫檔案路徑 (與 yfinance_client 共用)
MARKET_DATA_DB = "market_data.duckdb"
TABLE_NAME = "primary_dealer_positions"

# --- NY Fed API URLs 和解析設定 (來自 "一級交易pro.py Cell 1") ---
# 每個字典包含:
#   url: 直接的 API URL
#   type: 'SBN' 或 'SBP' (決定解析邏輯)
#   sheet_name: Excel 中的工作表名稱 (可能需要實際查看確認，先用通用預期)
#   header_row: 標頭行號 (0-indexed)
#   date_column_names: 可能的日期欄位名稱列表 (會依次嘗試)
#   value_column_pattern: (主要用於 SBN) 尋找總持有量欄位的模式
#   cols_to_sum: (主要用於 SBP) 需要加總的欄位列表
#   notes: 備註

NYFED_DATA_CONFIG = [
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBN2024/timeseries/PDPOSGSC-L2_PDPOSGSC-G2L3_PDPOSGSC-G3L6_PDPOSGSC-G6L7_PDPOSGSC-G7L11_PDPOSGSC-G11L21_PDPOSGSC-G21.xlsx",
        "type": "SBN",
        "sheet_name": 0,
        "header_row": 0,
        "date_column_names": ["AS OF DATE"], # 更新日期欄位名
        "value_column_pattern": "VALUE (MILLIONS)", # SBN API 返回的數值欄位名
        "cols_to_sum": None, # SBN 通常不需要手動加總，除非 value_column_pattern 找不到
        "notes": "SBN2024 - PDPOSGSC series"
    },
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBN2022/timeseries/PDPOSGSC-L2_PDPOSGSC-G2L3_PDPOSGSC-G3L6_PDPOSGSC-G6L7_PDPOSGSC-G7L11_PDPOSGSC-G11L21_PDPOSGSC-G21.xlsx",
        "type": "SBN",
        "sheet_name": 0,
        "header_row": 0,
        "date_column_names": ["AS OF DATE"], # 更新日期欄位名
        "value_column_pattern": "VALUE (MILLIONS)",
        "cols_to_sum": None,
        "notes": "SBN2022 - PDPOSGSC series"
    },
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBN2015/timeseries/PDPOSGSC-L2_PDPOSGSC-G2L3_PDPOSGSC-G3L6_PDPOSGSC-G6L7_PDPOSGSC-G7L11_PDPOSGSC-G11.xlsx",
        "type": "SBN",
        "sheet_name": 0,
        "header_row": 0,
        "date_column_names": ["AS OF DATE"], # 更新日期欄位名
        "value_column_pattern": "VALUE (MILLIONS)",
        "cols_to_sum": None,
        "notes": "SBN2015 - PDPOSGSC series (G11 結尾)"
    },
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBN2013/timeseries/PDPOSGSC-L2_PDPOSGSC-G2L3_PDPOSGSC-G3L6_PDPOSGSC-G6L7_PDPOSGSC-G7L11_PDPOSGSC-G11.xlsx",
        "type": "SBN",
        "sheet_name": 0,
        "header_row": 0,
        "date_column_names": ["AS OF DATE"], # 更新日期欄位名
        "value_column_pattern": "VALUE (MILLIONS)",
        "cols_to_sum": None,
        "notes": "SBN2013 - PDPOSGSC series"
    },
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBP2013/timeseries/PDPUSGCS3LNOP_PDPUSGCS36NOP_PDPUSGCS611NOP_PDPUSGCSM11NOP.xlsx",
        "type": "SBP",
        "sheet_name": 0,
        "header_row": 0,
        "date_column_names": ["AS OF DATE"], # 更新日期欄位名
        "value_column_pattern": None,
        "cols_to_sum": ['PDPUSGCS3LNOP', 'PDPUSGCS36NOP', 'PDPUSGCS611NOP', 'PDPUSGCSM11NOP'],
        "notes": "SBP2013 - 加總指定欄位"
    },
    {
        "url": "https://markets.newyorkfed.org/api/pd/get/SBP2001/timeseries/PDPUSGCS5LNOP_PDPUSGCS5MNOP.xlsx",
        "type": "SBP",
        "sheet_name": 0,
        "header_row": 0,
        "date_column_names": ["AS OF DATE"], # 更新日期欄位名
        "value_column_pattern": None,
        "cols_to_sum": ['PDPUSGCS5LNOP', 'PDPUSGCS5MNOP'],
        "notes": "SBP2001 - 加總指定欄位"
    }
]

def download_excel_to_dataframe(config: dict) -> pd.DataFrame | None:
    """
    從指定的 API URL 下載 Excel 檔案並讀取特定 sheet 到 DataFrame。
    """
    url = config["url"]
    sheet_name = config.get("sheet_name", 0) # 預設第一個 sheet
    header_row = config.get("header_row", 0) # 預設第一行是標頭

    print(f"正在從 {url} 下載 Excel 數據 (Sheet: {sheet_name}, Header Row: {header_row})...")
    try:
        response = requests.get(url, timeout=60) # 增加超時到60秒
        response.raise_for_status()

        excel_file = BytesIO(response.content)
        # API 直接返回 .xlsx，應使用 openpyxl
        df = pd.read_excel(excel_file, sheet_name=sheet_name, header=header_row, engine='openpyxl')

        # 清理欄位名稱：去除前後空格，轉換為大寫，替換換行符和多餘空格
        df.columns = [str(col).strip().upper().replace('\N{LINE FEED}', ' ').replace('\n', ' ').replace('\r', ' ').replace('  ', ' ') for col in df.columns]

        print(f"成功從 {url} (Sheet: {sheet_name}) 下載並讀取數據。")
        return df
    except requests.exceptions.RequestException as e:
        print(f"下載 Excel 檔案 {url} 時發生網路錯誤: {e}")
    except Exception as e: # 包括 BadZipFile, ValueError 等 pd.read_excel 可能的錯誤
        print(f"處理來自 {url} 的 Excel 檔案時發生錯誤: {e}")
        traceback.print_exc()
    return None

def find_column_by_names(df_columns: list[str], target_names: list[str]) -> str | None:
    """在 DataFrame 的欄位列表中按順序查找目標欄位名 (忽略大小寫和空格)。"""
    for target_name in target_names:
        target_upper = target_name.strip().upper()
        for col in df_columns:
            if col == target_upper: # 欄位名已在下載時處理過
                return col
    return None

def find_column_by_pattern(df_columns: list[str], pattern: str) -> str | None:
    """在 DataFrame 的欄位列表中查找包含特定模式的欄位名 (忽略大小寫)。"""
    pattern_upper = pattern.strip().upper()
    for col in df_columns:
        if pattern_upper in col:
            return col
    return None

def parse_dealer_positions(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    根據設定解析一級交易商持有量數據。
    返回一個包含 'Date' 和 'Total_Positions' 兩欄的 DataFrame。
    """
    # 查找日期欄位 (現在是 'AS OF DATE')
    date_col_name = config["date_column_names"][0] # 已經更新為 ["AS OF DATE"]
    if date_col_name not in df.columns:
        print(f"錯誤：在來源 {config['url']} 的數據中找不到日期欄位 '{date_col_name}'。可用欄位: {df.columns.tolist()}")
        return pd.DataFrame()

    print(f"使用日期欄位: '{date_col_name}' from {config['url']}")

    # 重命名日期欄位為 'Date'
    df.rename(columns={date_col_name: 'Date'}, inplace=True)
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

    if config["type"] == "SBP":
        # SBP API 返回的 Excel 結構現在與 SBN 相同: 'AS OF DATE', 'TIME SERIES', 'VALUE (MILLIONS)'
        # 但我們只對 'cols_to_sum' 中指定的 TIME SERIES 感興趣。
        required_sbp_cols = ["TIME SERIES", "VALUE (MILLIONS)"] # Date 欄位已處理
        missing_sbp_cols = [col for col in required_sbp_cols if col not in df.columns]
        if missing_sbp_cols:
            print(f"錯誤: SBP 類型數據 ({config['url']}) 缺少核心欄位: {missing_sbp_cols}。可用欄位: {df.columns.tolist()}")
            return pd.DataFrame()

        if not config.get("cols_to_sum"):
            print(f"錯誤: SBP 類型數據 ({config['url']}) 未在配置中提供 'cols_to_sum' 列表。")
            return pd.DataFrame()

        # 將配置中的 series code 轉為大寫以匹配 DataFrame 中的 'TIME SERIES' (已大寫)
        target_series_codes = [code.upper() for code in config["cols_to_sum"]]

        # 篩選出 'TIME SERIES' 在 target_series_codes 中的行
        df_filtered_sbp = df[df["TIME SERIES"].isin(target_series_codes)].copy() # 使用 .copy() 避免 SettingWithCopyWarning

        if df_filtered_sbp.empty:
            print(f"警告: SBP 類型數據 ({config['url']}) 在篩選目標 TIME SERIES {target_series_codes} 後為空。檢查 'cols_to_sum' 配置是否正確，以及 Excel 中是否存在這些 Series Code。")
            # 即使為空，也返回一個空的 DataFrame，而不是錯誤，因為這可能是預期行為（如果某些歷史文件不包含特定 series）
            # 但在 fetch_all_primary_dealer_data 中會被過濾掉
            return pd.DataFrame(columns=['Date', 'Total_Positions'])


        df_filtered_sbp["VALUE (MILLIONS)"] = pd.to_numeric(df_filtered_sbp["VALUE (MILLIONS)"], errors='coerce')

        sbp_summed = df_filtered_sbp.groupby('Date')["VALUE (MILLIONS)"].sum().reset_index()
        sbp_summed.rename(columns={"VALUE (MILLIONS)": 'Total_Positions'}, inplace=True)

        df = sbp_summed
        print(f"為 SBP ({config['url']}) 篩選並加總了 TIME SERIES {target_series_codes} 的 'VALUE (MILLIONS)'。")

    elif config["type"] == "SBN":
        # SBN API 返回的 Excel 結構是: 'AS OF DATE', 'TIME SERIES', 'VALUE (MILLIONS)'
        # 我們需要按 'AS OF DATE' 分組，並加總 'VALUE (MILLIONS)'
        required_sbn_cols = ["TIME SERIES", "VALUE (MILLIONS)"] # Date 欄位已處理
        missing_sbn_cols = [col for col in required_sbn_cols if col not in df.columns]
        if missing_sbn_cols:
            print(f"錯誤: SBN 類型數據 ({config['url']}) 缺少核心欄位: {missing_sbn_cols}。可用欄位: {df.columns.tolist()}")
            return pd.DataFrame()

        df["VALUE (MILLIONS)"] = pd.to_numeric(df["VALUE (MILLIONS)"], errors='coerce')

        # 按日期分組，加總所有 time series 的 value
        # 由於 SBN URL 已經指定了所有券種，所以該 Excel 中的所有 series 都應該被加總
        sbn_summed = df.groupby('Date')["VALUE (MILLIONS)"].sum().reset_index()
        sbn_summed.rename(columns={"VALUE (MILLIONS)": 'Total_Positions'}, inplace=True)

        # 將 sbn_summed 合併回 df (或直接使用 sbn_summed)
        # 為了保持結構一致，我們將結果賦給一個新的 df
        df = sbn_summed
        print(f"為 SBN ({config['url']}) 按日期加總了 'VALUE (MILLIONS)'。")

    else:
        print(f"錯誤: 未知的數據類型 '{config['type']}' for url {config['url']}")
        return pd.DataFrame()

    # 篩選並處理最終結果
    # 'Date' 欄位已轉換
    df.dropna(subset=['Date', 'Total_Positions'], inplace=True)

    df['Total_Positions'] = df['Total_Positions'] * 1_000_000 # 單位轉換

    if 'Date' in df.columns and df['Date'].dt.tz is not None: # 確保 Date 欄存在
        df['Date'] = df['Date'].dt.tz_localize(None)

    # 確保最終 DataFrame 只有需要的欄位並排序
    if 'Date' not in df.columns or 'Total_Positions' not in df.columns:
        print(f"警告: 解析後 DataFrame ({config['url']}) 缺少 'Date' 或 'Total_Positions' 欄位。")
        return pd.DataFrame()

    return df[['Date', 'Total_Positions']].sort_values(by='Date').reset_index(drop=True)


def fetch_all_primary_dealer_data() -> pd.DataFrame:
    all_data = []
    for config in NYFED_DATA_CONFIG:
        df_raw = download_excel_to_dataframe(config)
        if df_raw is not None and not df_raw.empty:
            df_parsed = parse_dealer_positions(df_raw, config)
            if not df_parsed.empty:
                all_data.append(df_parsed)
                print(f"成功解析來自 {config['url']} 的 {len(df_parsed)} 筆數據。")
            else:
                print(f"警告：解析來自 {config['url']} 的數據後為空。")
        else:
            print(f"警告：下載或讀取來自 {config['url']} 的數據失敗或為空。")

    if not all_data:
        print("錯誤：未能從任何來源成功獲取和解析一級交易商數據。")
        return pd.DataFrame()

    combined_df = pd.concat(all_data, ignore_index=True)
    combined_df.drop_duplicates(subset=['Date'], keep='first', inplace=True) # 可能有重疊日期，保留第一個
    combined_df.sort_values(by='Date', inplace=True)
    combined_df.reset_index(drop=True, inplace=True)

    print(f"成功合併所有一級交易商數據，共 {len(combined_df)} 筆。")
    return combined_df

def store_data_to_duckdb(df: pd.DataFrame, table_name: str = TABLE_NAME, db_file: str = MARKET_DATA_DB):
    if df.empty:
        print(f"沒有數據可儲存至資料表 {table_name}。")
        return
    try:
        with duckdb.connect(db_file) as con:
            con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")
            print(f"數據已成功儲存至 DuckDB 資料庫 '{db_file}' 的資料表 '{table_name}'。")
            count_result = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            if count_result:
                print(f"資料表 '{table_name}' 目前包含 {count_result[0]} 筆數據。")
    except Exception as e:
        print(f"儲存數據至 DuckDB 時發生錯誤：{e}")
        traceback.print_exc()

if __name__ == '__main__':
    print("--- 開始 nyfed_client 測試 (使用 API URLs) ---")

    dealer_data = fetch_all_primary_dealer_data()

    if not dealer_data.empty:
        print(f"\n最終合併的數據範例 (共 {len(dealer_data)} 筆):")
        print("最早的數據 (前5筆):")
        print(dealer_data.head())
        print("\n最新的數據 (後5筆):")
        print(dealer_data.tail())
        print("\n數據資訊:")
        dealer_data.info()

        store_data_to_duckdb(dealer_data)
    else:
        print("未抓取到任何一級交易商數據。")

    print("\n--- DuckDB 數據驗證 ---")
    try:
        with duckdb.connect(MARKET_DATA_DB) as con:
            print(f"從 DuckDB 讀取 '{MARKET_DATA_DB}' 的 '{TABLE_NAME}' 資料表進行驗證...")
            tables_df = con.execute("SHOW TABLES").df()
            if TABLE_NAME not in tables_df['name'].values:
                print(f"錯誤: '{TABLE_NAME}' 資料表未在資料庫中找到。")
            else:
                retrieved_data = con.table(TABLE_NAME).df()
                print(f"成功從 '{TABLE_NAME}' 讀取 {len(retrieved_data)} 筆數據。")
                if not retrieved_data.empty:
                    print(retrieved_data.head())
                    retrieved_data.info()
    except Exception as e:
        print(f"從 DuckDB 驗證讀取時發生錯誤: {e}")
        traceback.print_exc()

    print("--- nyfed_client 測試結束 ---")
