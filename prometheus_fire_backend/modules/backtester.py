import logging
import pandas as pd
import vectorbt as vbt
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class Backtester:
    """
    回測引擎 (Backtester)。
    使用 vectorbt 執行向量化回測。
    """

    def __init__(self, log_manager: Optional[Any] = None):
        """
        初始化回測引擎。

        Args:
            log_manager: 可選的日誌管理器實例。
        """
        self.log_manager = log_manager
        logger.info("回測引擎 (Backtester) 初始化完畢。")

    def run_backtest(self,
                     price_df: pd.DataFrame,
                     entry_signals: pd.Series,
                     exit_signals: pd.Series,
                     initial_cash: float = 100000.0,
                     commission_rate: float = 0.001, # e.g., 0.1%
                     slippage_rate: float = 0.0,    # e.g., 0.05%
                     ohlc_column_map: Optional[Dict[str, str]] = None
                    ) -> Tuple[Optional[pd.Series], Optional[str]]:
        """
        執行向量化回測。

        Args:
            price_df (pd.DataFrame): 價格數據，索引為日期時間。
                                     預期欄位為 'Open', 'High', 'Low', 'Close'。
                                     如果欄位名不同，可透過 ohlc_column_map 提供映射。
            entry_signals (pd.Series): 布林型買入訊號序列，索引與 price_df 對齊。
            exit_signals (pd.Series): 布林型賣出訊號序列，索引與 price_df 對齊。
            initial_cash (float): 初始資金。
            commission_rate (float): 交易手續費率 (例如 0.001 代表 0.1%)。
            slippage_rate (float): 交易滑價率 (例如 0.0005 代表 0.05%)。
            ohlc_column_map (Optional[Dict[str, str]]):
                一個字典，用於將 price_df 中的欄位名映射到 vectorbt 期望的名稱。
                例如: {"open_price": "Open", "close_price": "Close", ...}

        Returns:
            Tuple[Optional[pd.Series], Optional[str]]:
                - pd.Series: 包含回測績效統計數據的 Pandas Series。如果回測失敗則為 None。
                - str: 錯誤訊息字串。如果成功則為 None。
        """
        logger.info(f"開始執行回測。初始資金: {initial_cash}, 手續費率: {commission_rate}, 滑價率: {slippage_rate}")
        logger.info(f"價格數據筆數: {len(price_df)}, 買入訊號筆數: {len(entry_signals)}, 賣出訊號筆數: {len(exit_signals)}")

        if price_df.empty:
            logger.error("價格數據為空，無法執行回測。")
            return None, "價格數據為空。"
        if entry_signals.empty or exit_signals.empty:
            logger.warning("買入或賣出訊號為空。回測可能會產生無交易結果。")
            # 允許繼續，vectorbt 會處理無交易的情況

        # 確保索引一致
        if not price_df.index.equals(entry_signals.index) or not price_df.index.equals(exit_signals.index):
            logger.warning("價格數據和訊號的索引不完全一致。將嘗試對齊...")
            try:
                common_index = price_df.index.intersection(entry_signals.index).intersection(exit_signals.index)
                if common_index.empty:
                    logger.error("價格數據和訊號的索引沒有共同部分，無法對齊。")
                    return None, "價格數據和訊號的索引無法對齊。"

                price_df = price_df.loc[common_index]
                entry_signals = entry_signals.loc[common_index]
                exit_signals = exit_signals.loc[common_index]
                logger.info(f"數據和訊號已對齊到 {len(common_index)} 筆共同索引。")
            except Exception as e:
                logger.error(f"對齊價格數據和訊號索引時發生錯誤: {e}", exc_info=True)
                return None, f"對齊價格數據和訊號索引時發生錯誤: {e}"


        # 處理欄位名映射
        price_data_for_vbt = price_df.copy()
        expected_cols = {"Open": "Open", "High": "High", "Low": "Low", "Close": "Close"}
        if ohlc_column_map:
            for user_col, vbt_col in ohlc_column_map.items():
                if user_col in price_data_for_vbt.columns and vbt_col in expected_cols:
                    expected_cols[vbt_col] = user_col # 使用者提供的欄位名

        rename_dict = {}
        missing_cols = []
        for vbt_col_standard, current_col_name_in_df in expected_cols.items():
            if current_col_name_in_df not in price_data_for_vbt.columns:
                # 如果標準的 vbt_col_standard (Open, High, Low, Close) 也不在，才算 missing
                if vbt_col_standard not in price_data_for_vbt.columns:
                    missing_cols.append(vbt_col_standard)
                # 否則，如果 current_col_name_in_df 是標準名且已存在，則不需要重命名
            elif current_col_name_in_df != vbt_col_standard : # 如果 df 中的欄位名不是標準 vbt 名稱
                 rename_dict[current_col_name_in_df] = vbt_col_standard

        if missing_cols:
            msg = f"價格數據中缺少必要的 OHLC 欄位: {', '.join(missing_cols)} (在映射後)。"
            logger.error(msg)
            return None, msg

        if rename_dict:
            logger.info(f"將價格數據欄位重命名以符合 vectorbt 標準: {rename_dict}")
            price_data_for_vbt.rename(columns=rename_dict, inplace=True)


        try:
            portfolio = vbt.Portfolio.from_signals(
                close=price_data_for_vbt['Close'], # vectorbt 需要收盤價
                open=price_data_for_vbt['Open'],   # 也傳遞開盤價以支持更精確的回測 (例如，隔日開盤交易)
                high=price_data_for_vbt['High'],
                low=price_data_for_vbt['Low'],
                entries=entry_signals,
                exits=exit_signals,
                init_cash=initial_cash,
                fees=commission_rate, # 手續費
                slippage=slippage_rate, # 滑價
                freq='D' # 假設為日頻數據，可根據實際情況調整
            )

            stats = portfolio.stats()
            logger.info("回測執行成功。")
            logger.debug(f"回測績效統計:\n{stats}")
            return stats, None

        except Exception as e:
            logger.error(f"執行 vectorbt 回測時發生錯誤: {e}", exc_info=True)
            return None, f"執行 vectorbt 回測時發生錯誤: {e}"

if __name__ == '__main__':
    # --- 簡易測試 (未來應移至 pytest) ---
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')

    # 創建模擬數據
    num_days = 100
    date_index = pd.date_range(start="2023-01-01", periods=num_days, freq='B')

    close_prices = pd.Series(100 + np.random.randn(num_days).cumsum(), index=date_index)
    open_prices = close_prices - np.random.uniform(0, 1, num_days)
    high_prices = pd.concat([close_prices, open_prices], axis=1).max(axis=1) + np.random.uniform(0, 1, num_days)
    low_prices = pd.concat([close_prices, open_prices], axis=1).min(axis=1) - np.random.uniform(0, 1, num_days)

    price_df_test = pd.DataFrame({
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices
    })

    # 模擬訊號 (例如，每10天買入，5天後賣出)
    entry_signals_test = pd.Series(False, index=date_index)
    exit_signals_test = pd.Series(False, index=date_index)
    entry_signals_test.iloc[::10] = True
    exit_signals_test.iloc[5::10] = True # 確保賣出在買入之後

    # 初始化並運行回測
    backtester = Backtester()

    print("--- 測試1: 標準輸入 ---")
    stats1, error1 = backtester.run_backtest(
        price_df=price_df_test.copy(),
        entry_signals=entry_signals_test.copy(),
        exit_signals=exit_signals_test.copy(),
        initial_cash=100000,
        commission_rate=0.001
    )

    if error1:
        print(f"測試1 錯誤: {error1}")
    else:
        print("測試1 績效統計:")
        print(stats1)
        assert stats1 is not None
        assert 'Total Return [%]' in stats1
        assert 'Sharpe Ratio' in stats1

    print("\n--- 測試2: 自訂欄位名 ---")
    price_df_custom_cols = price_df_test.copy()
    price_df_custom_cols.rename(columns={
        "Open": "open_p", "High": "high_p", "Low": "low_p", "Close": "close_p"
    }, inplace=True)

    col_map = {"open_p": "Open", "high_p": "High", "low_p": "Low", "close_p": "Close"}

    stats2, error2 = backtester.run_backtest(
        price_df=price_df_custom_cols,
        entry_signals=entry_signals_test.copy(),
        exit_signals=exit_signals_test.copy(),
        ohlc_column_map=col_map
    )
    if error2:
        print(f"測試2 錯誤: {error2}")
    else:
        print("測試2 績效統計:")
        print(stats2)
        assert stats2 is not None
        # 簡單比較總回報是否大致相同 (考慮到欄位名處理不應影響結果)
        if stats1 is not None:
             pd.testing.assert_series_equal(stats1, stats2, check_dtype=False, rtol=1e-5)


    print("\n--- 測試3: 缺少必要欄位 (Close) ---")
    price_df_missing = price_df_test.copy().drop(columns=['Close'])
    stats3, error3 = backtester.run_backtest(
        price_df=price_df_missing,
        entry_signals=entry_signals_test.copy(),
        exit_signals=exit_signals_test.copy()
    )
    assert stats3 is None
    assert error3 is not None
    print(f"測試3 錯誤: {error3} (預期之中)")

    print("\n--- 測試4: 數據索引不對齊 ---")
    entry_signals_shifted = entry_signals_test.copy()
    entry_signals_shifted.index = entry_signals_shifted.index.shift(1, freq='B') # 索引向後移動一天

    stats4, error4 = backtester.run_backtest(
        price_df=price_df_test.copy(),
        entry_signals=entry_signals_shifted, # 使用不對齊的訊號
        exit_signals=exit_signals_test.copy()
    )
    # 預期會對齊，並且可能結果不同或有警告
    if error4:
        print(f"測試4 錯誤/警告: {error4}")
    else:
        print("測試4 (索引對齊後) 績效統計:")
        print(stats4)
        assert stats4 is not None # 應該能成功執行

    print("\n--- Backtester 簡易測試完畢 ---")
