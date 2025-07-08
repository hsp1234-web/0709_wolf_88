import pandas as pd
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

def generate_signals(
    price_df: pd.DataFrame, # 實際上，此策略主要依賴 factor_df，price_df 可能用於對齊索引或未來擴展
    factor_df: pd.DataFrame,
    fast_sma_col: str = 'SMA_10_Close',
    slow_sma_col: str = 'SMA_20_Close'
) -> Tuple[pd.Series, pd.Series]:
    """
    生成基於雙移動平均線交叉的交易訊號。

    Args:
        price_df (pd.DataFrame): 價格數據 DataFrame，索引為日期時間。
                                 主要用於確保訊號與價格數據的索引對齊。
        factor_df (pd.DataFrame): 因子數據 DataFrame，索引為日期時間。
                                  應包含由 fast_sma_col 和 slow_sma_col 指定的因子列。
        fast_sma_col (str): 因子 DataFrame 中代表快速移動平均線的欄位名。
        slow_sma_col (str): 因子 DataFrame 中代表慢速移動平均線的欄位名。

    Returns:
        Tuple[pd.Series, pd.Series]:
            - entry_signals (pd.Series): 布林型買入訊號序列。
            - exit_signals (pd.Series): 布林型賣出訊號序列。
    """
    logger.info(f"開始為 SMA 穿越策略生成訊號。快速SMA欄: '{fast_sma_col}', 慢速SMA欄: '{slow_sma_col}'.")

    if factor_df.empty:
        logger.warning("因子數據為空，無法生成訊號。返回空訊號。")
        empty_signals = pd.Series(False, index=price_df.index if not price_df.empty else pd.Index([]))
        return empty_signals, empty_signals

    if fast_sma_col not in factor_df.columns:
        logger.error(f"因子數據中缺少快速SMA欄位 '{fast_sma_col}'。無法生成訊號。")
        empty_signals = pd.Series(False, index=price_df.index)
        return empty_signals, empty_signals
    if slow_sma_col not in factor_df.columns:
        logger.error(f"因子數據中缺少慢速SMA欄位 '{slow_sma_col}'。無法生成訊號。")
        empty_signals = pd.Series(False, index=price_df.index)
        return empty_signals, empty_signals

    # 確保因子數據與價格數據索引對齊 (如果 price_df 非空)
    # 策略訊號應基於因子數據的索引，但最終用於與價格數據對齊的 Portfolio
    # vectorbt 的 Portfolio.from_signals 會自動處理對齊
    common_index = factor_df.index
    if not price_df.empty:
        common_index = factor_df.index.intersection(price_df.index)
        if common_index.empty and (not factor_df.empty and not price_df.empty):
            logger.warning("因子數據和價格數據的索引沒有共同部分。訊號將基於因子數據的索引。")
            # 如果沒有共同索引，則訊號的有效性取決於後續 Portfolio 如何處理
            # 為了安全，如果 price_df 存在但無共同索引，可能應返回空訊號或發出更強警告
            # 但此處假設因子數據的索引是我們關心的交易時點
            common_index = factor_df.index
        elif common_index.empty and (factor_df.empty or price_df.empty):
             logger.warning("因子數據或價格數據為空，無法確定共同索引。")
             common_index = factor_df.index # 退回至因子數據索引


    fast_sma = factor_df[fast_sma_col].loc[common_index]
    slow_sma = factor_df[slow_sma_col].loc[common_index]

    # 買入訊號：快速SMA從下方上穿慢速SMA
    # 當期 fast_sma > slow_sma 且 前期 fast_sma <= slow_sma
    entry_condition = (fast_sma > slow_sma) & (fast_sma.shift(1) <= slow_sma.shift(1))
    entry_signals = pd.Series(entry_condition, index=common_index, name="entry")
    entry_signals = entry_signals.fillna(False) # 處理 shift(1) 產生的初始 NaN

    # 賣出訊號：快速SMA從上方下穿慢速SMA
    # 當期 fast_sma < slow_sma 且 前期 fast_sma >= slow_sma
    exit_condition = (fast_sma < slow_sma) & (fast_sma.shift(1) >= slow_sma.shift(1))
    exit_signals = pd.Series(exit_condition, index=common_index, name="exit")
    exit_signals = exit_signals.fillna(False)

    # 確保訊號是布林型
    entry_signals = entry_signals.astype(bool)
    exit_signals = exit_signals.astype(bool)

    logger.info(f"SMA 穿越策略訊號生成完畢。買入訊號數量: {entry_signals.sum()}, 賣出訊號數量: {exit_signals.sum()}")

    # 如果 price_df 存在，確保返回的訊號索引與 price_df 對齊，
    # vectorbt 會自動處理，但這裡可以明確 reindex
    if not price_df.empty:
        entry_signals = entry_signals.reindex(price_df.index, fill_value=False)
        exit_signals = exit_signals.reindex(price_df.index, fill_value=False)

    return entry_signals, exit_signals

if __name__ == '__main__':
    # --- 簡易測試 ---
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')

    num_points = 50
    dates = pd.date_range(start='2023-01-01', periods=num_points, freq='B')

    price_data = pd.DataFrame(index=dates) # 策略主要不依賴 price_df 的內容，僅索引

    # 模擬因子數據
    sma10 = pd.Series([10, 12, 11, 13, 15, 14, 13, 12, 14, 16] * (num_points // 10), index=dates)
    sma20 = pd.Series([11, 11, 12, 12, 14, 15, 14, 13, 13, 15] * (num_points // 10), index=dates)

    factor_data = pd.DataFrame({
        'SMA_10_Close': sma10,
        'SMA_20_Close': sma20
    }, index=dates)

    print("模擬因子數據 (前15行):")
    print(factor_data.head(15))

    entries, exits = generate_signals(price_data, factor_data)

    print("\n買入訊號 (前15行):")
    print(entries.head(15))
    print(f"總買入訊號數: {entries.sum()}")

    print("\n賣出訊號 (前15行):")
    print(exits.head(15))
    print(f"總賣出訊號數: {exits.sum()}")

    # 手動驗證幾個點
    # 例: 索引3 (2023-01-06): SMA10=13, SMA20=12. 前期: SMA10=11, SMA20=12.
    # SMA10 > SMA20 (13>12) AND Prev_SMA10 <= Prev_SMA20 (11<=12) => Entry True
    assert entries.iloc[3] == True

    # 例: 索引6 (2023-01-11): SMA10=13, SMA20=14. 前期: SMA10=14, SMA20=15.
    # SMA10 < SMA20 (13<14) AND Prev_SMA10 >= Prev_SMA20 (14>=15) is False for prev.
    # Let's recheck the exit logic.
    # Example: index 6: fast(13) < slow(14) AND prev_fast(14) >= prev_slow(15) -> False.
    # Example: index 7: fast(12) < slow(13) AND prev_fast(13) >= prev_slow(14) -> False.
    # Let's find an exit example:
    # Need: fast < slow AND prev_fast >= prev_slow
    # At index 5: fast=14, slow=15. prev_fast=15, prev_slow=14.
    # (14 < 15) is True. (15 >= 14) is True. So exit should be True at index 5.
    if num_points >= 6:
         assert exits.iloc[5] == True, f"Exit at index 5 failed. Fast: {factor_data['SMA_10_Close'].iloc[4:6].values}, Slow: {factor_data['SMA_20_Close'].iloc[4:6].values}"


    # 測試空因子數據
    print("\n測試空因子數據:")
    empty_factor_df = pd.DataFrame(index=dates)
    empty_entries, empty_exits = generate_signals(price_data, empty_factor_df)
    assert empty_entries.sum() == 0
    assert empty_exits.sum() == 0
    print("空因子數據測試通過。")

    # 測試缺少因子欄位
    print("\n測試缺少因子欄位:")
    incomplete_factor_df = factor_data.drop(columns=['SMA_10_Close'])
    inc_entries, inc_exits = generate_signals(price_data, incomplete_factor_df)
    assert inc_entries.sum() == 0
    assert inc_exits.sum() == 0
    print("缺少因子欄位測試通過。")

    print("\nSMA Cross Strategy 訊號生成函數簡易測試完畢。")
