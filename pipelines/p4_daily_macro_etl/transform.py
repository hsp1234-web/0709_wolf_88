# -*- coding: utf-8 -*-
"""
數據管線第二階段：數據轉換器 (Transformer)
"""

import logging
from typing import Dict

import pandas as pd

logger = logging.getLogger(__name__)


def run_transformation(raw_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    核心數據轉換函式。

    將從提取器獲得的、異構的原始數據集，轉換、合併為一個
    統一、乾淨、可供分析的單一時間序列 DataFrame。

    Args:
        raw_data (Dict[str, pd.DataFrame]): 來自 extract.run_extraction() 的原始數據字典。

    Returns:
        pd.DataFrame: 一個以日期為索引的、經過清洗和整合的單一 DataFrame。
    """
    if not raw_data:
        logger.warning("沒有傳入任何原始數據，轉換流程終止，返回空的 DataFrame。")
        return pd.DataFrame()

    logger.info("數據轉換流程開始...")

    # --- 步驟一: 標準化 yfinance 數據 ---
    logger.info("[轉換步驟 1/4] 標準化 yfinance 數據...")
    yfinance_dfs = {
        key: df
        for key, df in raw_data.items()
        if key.startswith("YFINANCE_") and "Close" in df.columns
    }

    standardized_yfinance_dfs = []
    for key, df in yfinance_dfs.items():
        symbol = key.replace("YFINANCE_", "")
        # 將代號中的 '^' 和 '=F' 替換為有效的欄位名字符
        column_name = symbol.replace("^", "").replace("=F", "") + "_daily_close"

        # 提取 'Date' 和 'Close'，並將 'Date' 設為索引
        if "Date" in df.columns:
            renamed_df = df[["Date", "Close"]].set_index("Date").rename(columns={"Close": column_name})
            standardized_yfinance_dfs.append(renamed_df)

    # 合併所有標準化的 yfinance DataFrame
    if standardized_yfinance_dfs:
        yfinance_merged = pd.concat(standardized_yfinance_dfs, axis=1)
        logger.info(f"成功標準化並合併 {len(yfinance_dfs)} 個 yfinance 數據集。")
    else:
        yfinance_merged = pd.DataFrame()
        logger.info("未找到可處理的 yfinance 數據集。")


    # --- 步驟二: 合併核心數據源 ---
    logger.info("[轉換步驟 2/4] 合併核心數據源 (FRED)...")
    fred_dfs = [df for key, df in raw_data.items() if key.startswith("FRED_")]

    # 將所有 FRED DataFrame 合併到 yfinance_merged
    merged_df = yfinance_merged
    for df in fred_dfs:
        merged_df = merged_df.join(df, how="outer")

    logger.info(f"成功合併 {len(fred_dfs)} 個 FRED 數據集。")

    # --- 步驟三: 計算衍生指標 ---
    logger.info("[轉換步驟 3/4] 計算衍生指標...")

    # 計算黃金/銅價格比率
    if "GC_daily_close" in merged_df.columns and "HG_daily_close" in merged_df.columns:
        merged_df["gold_copper_ratio_daily"] = merged_df["GC_daily_close"] / merged_df["HG_daily_close"]
        logger.info("成功計算黃金/銅價格比率。")
    else:
        logger.warning("缺少黃金或銅的價格數據，無法計算黃金/銅價格比率。")

    # --- 步驟四: 數據清洗與填充 ---
    logger.info("[轉換步驟 4/4] 數據清洗與填充...")

    # 使用前向填充 (forward-fill) 處理 NaN 值
    final_df = merged_df.ffill()

    # 刪除數據轉換過程中可能產生的全為 NaN 的初始行
    final_df.dropna(how='all', inplace=True)

    logger.info(f"數據已使用前向填充策略進行清洗。最終 DataFrame 包含 {len(final_df)} 行。")

    logger.info("數據轉換流程成功結束。")

    return final_df


if __name__ == "__main__":
    # 建立一個模擬的 raw_data 字典用於本地測試
    mock_raw_data = {
        "YFINANCE_^GSPC": pd.DataFrame({
            "Date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Close": [4000, 4010, 4020]
        }),
        "YFINANCE_GC=F": pd.DataFrame({
            "Date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-04"]),
            "Close": [1800, 1805, 1810]
        }),
        "YFINANCE_HG=F": pd.DataFrame({
            "Date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Close": [3.8, 3.82, 3.85]
        }),
        "FRED_DGS10": pd.DataFrame({
            "DGS10": [3.5, 3.55, 3.6, 3.58]
        }, index=pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04"]))
    }

    print("--- [測試] 執行數據轉換模組 ---")
    transformed_df = run_transformation(mock_raw_data)

    print("\n轉換後的 DataFrame:")
    print(transformed_df)

    print("\nDataFrame Info:")
    transformed_df.info()

    print("\n--- [測試] 數據轉換模組執行完畢 ---")
