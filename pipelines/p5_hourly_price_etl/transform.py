# -*- coding: utf-8 -*-
"""
數據管線第二階段：小時級價格數據轉換器 (Transformer)
"""
import logging
from typing import Dict

import pandas as pd

logger = logging.getLogger(__name__)


def run_transformation(raw_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    將從 yfinance 提取的原始小時線數據，轉換為一個扁平化的、
    以時間為索引的單一 DataFrame。

    Args:
        raw_data (Dict[str, pd.DataFrame]): 來自 extract.run_extraction() 的原始數據字典。
                                             鍵為資產代號，值為其對應的 OHLCV DataFrame。

    Returns:
        pd.DataFrame: 一個以小時級時間戳為索引的、扁平化的單一 DataFrame。
                      欄位名稱格式為 'spy_open', 'qqq_high' 等。
    """
    logger.info(f"--- [Transformer] 啟動，準備處理 {len(raw_data)} 檔資產數據 ---")

    if not raw_data:
        logger.warning("沒有傳入任何原始數據，轉換流程終止。")
        return pd.DataFrame()

    all_transformed_dfs = []

    for ticker, df in raw_data.items():
        if not isinstance(df, pd.DataFrame) or df.empty:
            logger.warning(f"資產 {ticker} 的數據不是有效的 DataFrame 或為空，已跳過。")
            continue

        # 複製以避免 SettingWithCopyWarning
        transformed_df = df.copy()

        # 將索引轉換為 UTC 時間以實現標準化
        if not isinstance(transformed_df.index, pd.DatetimeIndex):
             logger.warning(f"資產 {ticker} 的索引不是 DatetimeIndex，已跳過。")
             continue

        # yfinance 返回的時區可能是本地化的，也可能沒有時區。
        # 我們將其統一為 UTC。
        if transformed_df.index.tz is None:
            transformed_df.index = transformed_df.index.tz_localize('UTC')
        else:
            transformed_df.index = transformed_df.index.tz_convert('UTC')

        # 將欄位名稱轉換為小寫，以便統一處理
        transformed_df.columns = [col.lower() for col in transformed_df.columns]

        # 清理資產代號中的特殊字符，使其適用於欄位名稱
        # 例如: 'BRK-B' -> 'brk_b', 'GC=F' -> 'gc_f'
        safe_ticker = ticker.lower().replace("-", "_").replace("=f", "_f").replace('^', '')

        # 創建新的欄位名稱
        column_mapping = {
            "open": f"{safe_ticker}_open",
            "high": f"{safe_ticker}_high",
            "low": f"{safe_ticker}_low",
            "close": f"{safe_ticker}_close",
            "volume": f"{safe_ticker}_volume",
        }

        # 只保留我們需要的欄位並重命名
        required_cols = list(column_mapping.keys())
        transformed_df = transformed_df[required_cols]
        transformed_df = transformed_df.rename(columns=column_mapping)

        all_transformed_dfs.append(transformed_df)

    if not all_transformed_dfs:
        logger.warning("沒有任何數據成功轉換，返回空的 DataFrame。")
        return pd.DataFrame()

    # 使用 outer join 合併所有的 DataFrame，以時間戳為基準
    logger.info(f"正在合併 {len(all_transformed_dfs)} 個已轉換的 DataFrame...")
    final_df = pd.concat(all_transformed_dfs, axis=1, join="outer")

    # 按時間索引排序
    final_df.sort_index(inplace=True)

    # 由於不同資產的交易時間不同，合併後會產生很多 NaN。
    # 例如，美股交易時段，期貨市場可能也在交易，但反之則不然。
    # 在這裡我們暫不填充，讓加載或分析階段根據需要決定填充策略。
    # 但可以移除完全是 NaN 的行，這些通常是數據錯誤或假日。
    final_df.dropna(how='all', inplace=True)

    # 將索引（時間戳）重設為一個正常的欄位
    final_df.reset_index(inplace=True)

    logger.info(f"--- [Transformer] 完成，最終 DataFrame 維度: {final_df.shape} ---")

    return final_df


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # 創建一個模擬的 raw_data 字典
    mock_raw_data = {
        "SPY": pd.DataFrame({
            "Open": [300, 301], "High": [302, 302], "Low": [299, 300],
            "Close": [301, 301.5], "Volume": [10000, 12000]
        }, index=pd.to_datetime(["2023-01-02 09:30:00", "2023-01-02 10:30:00"])),
        "GC=F": pd.DataFrame({
            "Open": [1800, 1801], "High": [1802, 1802], "Low": [1799, 1800],
            "Close": [1801, 1801.5], "Volume": [5000, 5200]
        }, index=pd.to_datetime(["2023-01-02 09:30:00", "2023-01-02 11:30:00"])), # 注意時間戳不同
         "BRK-B": pd.DataFrame({ # 測試特殊字符
            "Open": [410, 411], "High": [412, 412], "Low": [409, 410],
            "Close": [411, 411.5], "Volume": [8000, 8200]
        }, index=pd.to_datetime(["2023-01-02 09:30:00", "2023-01-02 10:30:00"])),
    }

    print("--- [測試] 執行數據轉換模組 ---")
    transformed_df = run_transformation(mock_raw_data)

    print("\n轉換後的 DataFrame:")
    print(transformed_df)

    print("\nDataFrame Info:")
    transformed_df.info()

    # 驗證欄位名稱
    expected_columns = [
        'spy_open', 'spy_high', 'spy_low', 'spy_close', 'spy_volume',
        'gc_f_open', 'gc_f_high', 'gc_f_low', 'gc_f_close', 'gc_f_volume',
        'brk_b_open', 'brk_b_high', 'brk_b_low', 'brk_b_close', 'brk_b_volume'
    ]
    assert all(col in transformed_df.columns for col in expected_columns)
    print("\n✅ 欄位名稱驗證成功！")

    # 驗證索引
    assert isinstance(transformed_df.index, pd.DatetimeIndex)
    assert transformed_df.index.tz is not None
    print("✅ 索引類型和時區驗證成功！")

    print("\n--- [測試] 數據轉換模組執行完畢 ---")
