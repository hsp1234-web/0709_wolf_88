# -*- coding: utf-8 -*-
"""
數據管線第二階段：小時級價格數據轉換器 (Transformer)
"""
import logging
from typing import Dict

import pandas as pd
import yfinance as yf

from core.db.db_manager import DBManager

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


def calculate_technical_indicators(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    為 hourly_market_data DataFrame 計算技術指標。

    Args:
        price_df (pd.DataFrame): 從數據庫讀取的包含純淨價格數據的 DataFrame。

    Returns:
        pd.DataFrame: 包含原始價格數據和所有新計算出的技術指標的 DataFrame。
    """
    logger.info(f"--- [Indicator Calculator] 啟動，準備為 {price_df.shape[0]} 行數據計算指標 ---")

    # 確保 'timestamp' 欄位是 datetime 類型
    price_df['timestamp'] = pd.to_datetime(price_df['timestamp'])
    price_df.set_index('timestamp', inplace=True)

    # 獲取所有資產的基礎名稱 (e.g., 'spy' from 'spy_open')
    assets = sorted(list(set([col.split('_')[0] for col in price_df.columns if '_' in col])))

    all_indicators = []

    for asset in assets:
        # 檢查是否存在該資產的完整 OHLCV 數據
        ohlcv_cols = {
            "open": f"{asset}_open",
            "high": f"{asset}_high",
            "low": f"{asset}_low",
            "close": f"{asset}_close",
            "volume": f"{asset}_volume"
        }
        if not all(col in price_df.columns for col in ohlcv_cols.values()):
            logger.warning(f"資產 {asset} 缺少完整的 OHLCV 欄位，跳過指標計算。")
            continue

        logger.info(f"正在為資產 {asset} 計算技術指標...")

        # 創建一個只包含當前資產 OHLCV 的 DataFrame
        asset_df = price_df[list(ohlcv_cols.values())].copy()
        asset_df.columns = ["open", "high", "low", "close", "volume"] # pandas-ta 需要標準欄位名

        # 計算指標
        # RSI
        asset_df.ta.rsi(length=14, append=True)
        # MACD
        asset_df.ta.macd(fast=12, slow=26, signal=9, append=True)
        # Bollinger Bands
        asset_df.ta.bbands(length=20, std=2, append=True)
        # SMA
        asset_df.ta.sma(length=50, append=True)
        asset_df.ta.sma(length=200, append=True)

        # 重命名指標欄位以符合我們的規範
        new_cols = {col: f"{asset}_{col.lower()}_1h" for col in asset_df.columns if col not in ohlcv_cols}
        asset_df.rename(columns=new_cols, inplace=True)

        # 只保留新計算出的指標欄位
        indicator_df = asset_df[list(new_cols.values())]
        all_indicators.append(indicator_df)

    # 合併所有指標到原始 DataFrame
    if all_indicators:
        indicators_merged = pd.concat(all_indicators, axis=1)
        final_df = price_df.join(indicators_merged)
        logger.info(f"--- [Indicator Calculator] 完成，新增 {len(indicators_merged.columns)} 個指標欄位 ---")
    else:
        final_df = price_df
        logger.warning("--- [Indicator Calculator] 未計算任何指標 ---")

    final_df.reset_index(inplace=True) # 將 timestamp 索引再次轉為欄位
    return final_df


def calculate_options_derived_metrics(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    為 SPY 計算選擇權衍生指標。

    Args:
        price_df (pd.DataFrame): 包含基礎價格數據的 DataFrame。

    Returns:
        pd.DataFrame: 一個僅包含新計算出的選擇權衍生指標的 DataFrame。
    """
    logger.info("--- [Options Calculator] 啟動 ---")

    # 1. 獲取 SPY 選擇權鏈
    spy = yf.Ticker("SPY")
    try:
        exp_dates = spy.options
        if not exp_dates:
            logger.warning("無法獲取 SPY 選擇權到期日，跳過計算。")
            return pd.DataFrame()

        # 獲取最近的到期日
        chain = spy.option_chain(exp_dates[0])
        calls = chain.calls
        puts = chain.puts
    except Exception as e:
        logger.error(f"獲取 SPY 選擇權鏈時發生錯誤: {e}", exc_info=True)
        return pd.DataFrame()

    # 2. 獲取無風險利率
    risk_free_rate = 0.01 # 預設值
    try:
        with DBManager() as db:
            # 檢查日線數據表是否存在
            tables_df = db.connection.execute("SHOW TABLES").fetchdf()
            if 'daily_macro_market_data' in tables_df['name'].values:
                daily_data = db.connection.table("daily_macro_market_data").to_df()
                if 'DGS3MO' in daily_data.columns and not daily_data['DGS3MO'].empty:
                    # 使用 .iloc[-1] 獲取最新的非 NaN 值
                    last_valid_rate = daily_data['DGS3MO'].dropna().iloc[-1]
                    risk_free_rate = last_valid_rate / 100
                    logger.info(f"成功獲取無風險利率: {risk_free_rate:.4f}")
                else:
                    logger.warning("日線數據表中缺少 'DGS3MO' 欄位或該欄位為空，將使用預設無風險利率。")
            else:
                logger.warning("日線數據表 'daily_macro_market_data' 不存在，將使用預設無風險利率。")
    except Exception as e:
        logger.error(f"獲取無風險利率時發生未預期錯誤: {e}", exc_info=True)
        logger.warning("將使用預設無風險利率。")

    # 3. 計算衍生指標
    # GEX
    if 'gamma' in calls.columns and 'gamma' in puts.columns:
        calls['gamma'] = calls['gamma'].fillna(0)
        puts['gamma'] = puts['gamma'].fillna(0)
        total_gex = (calls['gamma'] * calls['openInterest'] * 100).sum() - \
                    (puts['gamma'] * puts['openInterest'] * 100).sum()
    else:
        logger.warning("選擇權鏈中缺少 'gamma' 欄位，跳過 GEX 計算。")
        total_gex = None

    # Max Pain
    strikes = sorted(list(set(calls['strike']) | set(puts['strike'])))
    pain = {}
    for strike in strikes:
        call_loss = ((calls['strike'] - strike) * calls['openInterest']).clip(lower=0).sum()
        put_loss = ((strike - puts['strike']) * puts['openInterest']).clip(lower=0).sum()
        pain[strike] = call_loss + put_loss
    max_pain_strike = min(pain, key=pain.get)

    # Call/Put Walls
    call_wall = calls.loc[calls['openInterest'].idxmax()]['strike']
    put_wall = puts.loc[puts['openInterest'].idxmax()]['strike']

    # P/C Ratios
    pc_volume_ratio = puts['volume'].sum() / calls['volume'].sum()
    pc_oi_ratio = puts['openInterest'].sum() / calls['openInterest'].sum()

    # 4. 創建結果 DataFrame
    options_metrics = pd.DataFrame({
        'spy_gex_total': [total_gex],
        'spy_max_pain': [max_pain_strike],
        'spy_call_wall': [call_wall],
        'spy_put_wall': [put_wall],
        'spy_pc_volume_ratio': [pc_volume_ratio],
        'spy_pc_oi_ratio': [pc_oi_ratio],
    }, index=[price_df['timestamp'].max()]) # 使用最新的時間戳

    logger.info("--- [Options Calculator] 完成 ---")
    return options_metrics


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
