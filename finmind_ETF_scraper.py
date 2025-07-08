# -*- coding: utf-8 -*-
"""
模擬的 FinMind ETF 爬蟲模組
"""
import requests
import sys

def fetch_etf_data(parameter_date: str):
    """
    模擬從 FinMind API 獲取指定日期的 ETF 數據。
    在實際應用中，這裡會包含完整的 API 請求和數據處理邏輯。
    """
    # 模擬 API 端點，實際情況下應為完整的 FinMind API URL
    # 例如：api_url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanExchangeTradedFund&data_id=0050&start_date={parameter_date}&end_date={parameter_date}"
    # 為了測試，我們使用一個無效的 URL 來確保 requests.get 被 mock
    api_url = "http://localhost/fake_finmind_api"

    print(f"指揮官，數據獲取模組開始嘗試連接 FinMind API 以獲取 {parameter_date} 的數據...")

    try:
        # 在實際的爬蟲中，requests.get 通常會被使用
        # 我們將在測試中 mock requests.get 或 requests.Session.get
        # 這裡我們假設直接使用 requests.get
        response = requests.get(api_url, timeout=10) # 模擬設置超時
        response.raise_for_status() # 如果狀態碼是 4xx 或 5xx，則拋出 HTTPError

        # 假設成功獲取數據後的處理
        print(f"指揮官，已成功從 FinMind API 獲取 {parameter_date} 的數據。")
        return {"data": "模擬的ETF數據"}

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print("指揮官，數據獲取模組在連接 FinMind API 時遇到權限問題 (403 Forbidden)。請檢查 API 金鑰或權限設定。", file=sys.stdout)
            # 在實際應用中，這裡可能還會有日誌記錄、重試邏輯或向監控系統發送警報等操作。
            # 為了符合測試要求，我們不讓程式崩潰
            return None # 或 raise SystemExit("API 權限問題")
        else:
            print(f"指揮官，數據獲取模組在連接 FinMind API 時遇到未預期的 HTTP 錯誤：{e}", file=sys.stdout)
            return None # 或 raise SystemExit(f"API HTTP 錯誤: {e}")

    except requests.exceptions.Timeout:
        print("指揮官，數據獲取模組在連接 FinMind API 時因超時而失敗。網路連線可能不穩定或 API 服務繁忙。", file=sys.stdout)
        # 實際應用中可能需要重試或通知
        return None # 或 raise SystemExit("API 連線超時")

    except requests.exceptions.RequestException as e:
        # 捕獲其他所有 requests 可能的異常，例如 DNS 解析失敗、連線被拒等
        print(f"指揮官，數據獲取模組在連接 FinMind API 時遇到網路連線問題：{e}", file=sys.stdout)
        return None # 或 raise SystemExit(f"API 連線問題: {e}")

def process_raw_data(df: 'pd.DataFrame') -> 'pd.DataFrame':
    """
    處理從 API 獲取的原始 DataFrame，進行數據清洗與轉換。

    參數:
        df (pd.DataFrame): 包含原始市場數據的 DataFrame。
                           預期欄位: ['date', 'stock_id', 'open_price', 'high_price', 'low_price', 'close_price', 'trade_volume']

    返回:
        pd.DataFrame: 清洗和轉換後的 DataFrame，移除了包含無效數據的行。
    """
    import pandas as pd
    import numpy as np

    if not isinstance(df, pd.DataFrame):
        print("指揮官，輸入的數據不是有效的 DataFrame 格式，處理中止。", file=sys.stdout)
        return pd.DataFrame() # 返回空的 DataFrame

    original_row_count = len(df)
    cleaned_df = df.copy()
    rows_to_drop = pd.Series([False] * len(cleaned_df), index=cleaned_df.index)

    # 欄位和預期類型
    numeric_cols_to_check = {
        'open_price': float,
        'high_price': float,
        'low_price': float,
        'close_price': float,
        'trade_volume': int, # 雖然 trade_volume 是整數，但 pd.to_numeric 預設轉為 float，後面再處理
    }

    for col, expected_type in numeric_cols_to_check.items():
        if col not in cleaned_df.columns:
            print(f"指揮官，輸入數據缺少必要欄位 '{col}'，相關數據行可能無法正確處理。", file=sys.stdout)
            # 根據策略，如果缺少關鍵欄位，可以選擇跳過所有行或進行特定處理
            # 此處我們假設如果欄位不存在，則無法進行後續檢查，但不會立即丟棄所有行，除非後續檢查失敗
            continue

        # 嘗試轉換為數值類型，無法轉換的設為 NaN
        # errors='coerce' 會將無法轉換的值變為 NaT (for datetime) 或 NaN (for numeric)
        original_values = cleaned_df[col].copy()
        cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors='coerce')

        # 檢查是否有因格式錯誤導致的 NaN (原先非 NaN 或 None 的值變成了 NaN)
        # None 值在 pd.to_numeric 時也會變成 NaN，這是可接受的格式問題
        format_errors = original_values.notna() & cleaned_df[col].isna()

        if format_errors.any():
            for index in cleaned_df[format_errors].index:
                if not rows_to_drop[index]: # 避免重複報告同一行的問題
                    print(f"指揮官，偵測到索引 {index} 的數據在 '{col}' 欄位格式不符預期 (值: '{original_values[index]}')。該行數據已被標記並將自動跳過。", file=sys.stdout)
                    rows_to_drop[index] = True

    # 特別處理 trade_volume，確保其為整數 (如果已成功轉為 float)
    if 'trade_volume' in cleaned_df.columns:
        # 對於已成功轉換為數值但非整數的 trade_volume (例如 float)，檢查是否可以安全轉為 int
        # NaN 值在 astype(int) 時會報錯，所以要先處理 NaN (已經在上面 to_numeric 時處理了)
        # 如果 trade_volume 是 float 且包含小數，則視為格式錯誤
        is_float_and_has_decimal = cleaned_df['trade_volume'].notna() & (cleaned_df['trade_volume'] != cleaned_df['trade_volume'].round())
        for index in cleaned_df[is_float_and_has_decimal].index:
            if not rows_to_drop[index]:
                 print(f"指揮官，偵測到索引 {index} 的數據在 'trade_volume' 欄位值 '{cleaned_df.loc[index, 'trade_volume']}' 非整數。該行數據已被標記並將自動跳過。", file=sys.stdout)
                 rows_to_drop[index] = True

        # 對於沒有被標記移除的行，嘗試轉換為 nullable Integer
        # cleaned_df.loc[~rows_to_drop, 'trade_volume'] = cleaned_df.loc[~rows_to_drop, 'trade_volume'].astype('Int64')
        # 由於 Int64 可能引入 <NA> 而非 NaN，且後續邏輯檢查基於數值，這裡保持 float 進行邏輯檢查，最後再轉換

    # 邏輯異常檢查 (只對沒有因格式問題被丟棄的行進行)
    # 1. close_price 為負數
    if 'close_price' in cleaned_df.columns:
        # 確保 close_price 是數值類型 (已經是 float 或 NaN)
        negative_close_price = cleaned_df['close_price'].notna() & (cleaned_df['close_price'] < 0)
        for index in cleaned_df[negative_close_price & ~rows_to_drop].index:
            if not rows_to_drop[index]: # 避免重複報告
                print(f"指揮官，偵測到索引 {index} 的數據 'close_price' 為負數 ({cleaned_df.loc[index, 'close_price']})。該行數據已被標記並將自動跳過。", file=sys.stdout)
                rows_to_drop[index] = True

    # 2. trade_volume 為 0
    if 'trade_volume' in cleaned_df.columns:
        # 確保 trade_volume 是數值類型
        zero_trade_volume = cleaned_df['trade_volume'].notna() & (cleaned_df['trade_volume'] == 0)
        for index in cleaned_df[zero_trade_volume & ~rows_to_drop].index:
            if not rows_to_drop[index]: # 避免重複報告
                print(f"指揮官，偵測到索引 {index} 的數據 'trade_volume' 為零。該行數據已被標記並將自動跳過。", file=sys.stdout)
                rows_to_drop[index] = True

    # 移除標記的行
    cleaned_df = cleaned_df[~rows_to_drop]

    # 對於通過所有檢查的行，確保 trade_volume 是整數類型
    if 'trade_volume' in cleaned_df.columns and not cleaned_df.empty:
        # 如果 trade_volume 仍然是 float (因為 to_numeric 轉成 float)，現在可以安全轉為 Int64
        # Int64 可以處理 NaN (如果有的話，雖然理論上此時不應有因錯誤導致的 NaN)
        cleaned_df['trade_volume'] = cleaned_df['trade_volume'].astype('Int64')


    dropped_row_count = rows_to_drop.sum()
    if dropped_row_count > 0:
        print(f"指揮官，原始數據共 {original_row_count} 行，在清洗過程中，共有 {dropped_row_count} 行因數據問題被自動跳過。", file=sys.stdout)
    else:
        print(f"指揮官，原始數據共 {original_row_count} 行，所有數據均符合基本質量標準。", file=sys.stdout)

    return cleaned_df

if __name__ == '__main__':
    # 模擬呼叫 fetch_etf_data
    print("--- 模擬 API 呼叫 ---")
    # fetch_etf_data("2023-01-01")
    # print("\n")

    # 模擬 process_raw_data 的使用
    print("--- 模擬數據清洗 process_raw_data ---")
    # 創建一個範例 DataFrame
    example_data = {
        'date': ['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05', '2023-01-06', '2023-01-07', '2023-01-08', '2023-01-09'],
        'stock_id': ['0050', '0050', '0050', '0050', '0050', '0050', '0050', '0050', '0050'],
        'open_price': [100.0, 101.0, 'N/A', 103.0, 104.0, 105.0, 106.0, 107.0, 108.0], # 格式錯誤
        'high_price': [102.0, 102.5, 102.0, 104.0, 105.5, 106.0, 107.5, 108.0, 109.0],
        'low_price': [99.0, 100.0, 100.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0],
        'close_price': [101.0, None, 101.0, -103.0, 105.0, 105.5, 107.0, 107.5, 108.0], # None 格式錯誤, -103.0 邏輯異常
        'trade_volume': [1000, 2000, 1500, 0, 5000, 'error_val', 2500.5, 3000, 4000] # 0 邏輯異常, 'error_val' 格式錯誤, 2500.5 格式錯誤 (非整數)
    }
    # 確保 pandas 被正確導入
    try:
        import pandas as pd
        raw_df = pd.DataFrame(example_data)
        print("原始 DataFrame:")
        print(raw_df)

        cleaned_df = process_raw_data(raw_df.copy()) # 傳遞副本以避免修改原始 raw_df

        print("\n清洗後的 DataFrame:")
        print(cleaned_df)
        print("\n清洗後 DataFrame 的資料型態:")
        print(cleaned_df.dtypes)

    except ImportError:
        print("Pandas 模組未安裝，無法執行 process_raw_data 範例。")
    except Exception as e:
        print(f"執行範例時發生錯誤: {e}")
