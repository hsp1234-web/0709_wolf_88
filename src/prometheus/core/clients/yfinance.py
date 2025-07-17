# core/clients/yfinance.py
# 此模組包含從 Yahoo Finance 下載市場數據的客戶端邏輯。

import traceback
from typing import (
    Any,
    List,
    cast,
)

import pandas as pd
import yfinance as yf

from .base import BaseAPIClient
from prometheus.core.logging.log_manager import LogManager

logger = LogManager.get_instance().get_logger("YFinanceClient")


class YFinanceClient(BaseAPIClient):
    """
    用於從 Yahoo Finance 下載市場數據的客戶端。
    此客戶端使用 yfinance 套件，不直接進行 HTTP 請求，
    因此不使用 BaseAPIClient 的 _request 方法。
    """

    def __init__(self):
        """
        初始化 YFinanceClient。
        Yahoo Finance 不需要 API Key 或特定的 Base URL (由 yfinance 套件處理)。
        """
        super().__init__(api_key=None, base_url=None)
        logger.info("YFinanceClient 初始化完成。")

    async def fetch_data(
        self, symbol: str, **kwargs
    ) -> pd.DataFrame:
        """
        非同步地從 Yahoo Finance 抓取指定商品代碼的 OHLCV 數據。
        """
        import asyncio

        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        period = kwargs.get("period")

        if not period and not (start_date and end_date):
            raise ValueError("必須提供 'period' 或 'start_date' 與 'end_date' 其中之一。")

        history_params = {
            "start": start_date,
            "end": end_date,
            "auto_adjust": kwargs.get("auto_adjust", False),
            "interval": kwargs.get("interval", "1d"),
            "actions": kwargs.get("actions", False),
        }
        if period:
            history_params["period"] = period
            history_params.pop("start", None)
            history_params.pop("end", None)

        logger.info(f"開始抓取數據：商品 {symbol}, 參數: {history_params}")

        def _sync_fetch():
            try:
                ticker_obj: Any = yf.Ticker(symbol)
                history_params.pop("progress", None)
                hist_data: Any = ticker_obj.history(**history_params)

                if hist_data is None or hist_data.empty:
                    logger.warning(f"商品 {symbol} 使用參數 {history_params} 未找到數據或返回為空。")
                    return pd.DataFrame()

                hist_data = cast(pd.DataFrame, hist_data)
                hist_data.reset_index(inplace=True)
                hist_data["symbol"] = symbol

                date_col_name = "Datetime" if "Datetime" in hist_data.columns else "Date"
                if date_col_name not in hist_data.columns:
                    logger.warning(f"未找到預期的日期欄位 ('Date' 或 'Datetime')。可用欄位: {hist_data.columns.tolist()}")
                    return pd.DataFrame()

                hist_data[date_col_name] = pd.to_datetime(hist_data[date_col_name], utc=True)
                hist_data[date_col_name] = hist_data[date_col_name].dt.tz_convert(None)

                if date_col_name != "date":
                    hist_data.rename(columns={date_col_name: "date"}, inplace=True)

                rename_map = {"Adj Close": "Adj_Close"}
                final_df = hist_data.rename(columns=rename_map)
                final_df["date"] = pd.to_datetime(final_df["date"])

                required_cols = ["date", "symbol", "Open", "High", "Low", "Close", "Adj_Close", "Volume"]
                cols_to_keep = []
                missing_cols = []

                for col in required_cols:
                    if col in final_df.columns:
                        cols_to_keep.append(col)
                    elif col == "Adj_Close" and "Close" in final_df.columns and history_params.get("auto_adjust") is True:
                        final_df["Adj_Close"] = final_df["Close"]
                        cols_to_keep.append("Adj_Close")
                    elif col not in final_df.columns:
                        missing_cols.append(col)

                if missing_cols:
                    logger.warning(f"抓取的數據中缺少以下預期欄位: {missing_cols} (Symbol: {symbol})。")

                valid_cols_to_keep = [col for col in cols_to_keep if col in final_df.columns]
                if not valid_cols_to_keep:
                    logger.warning(f"沒有有效的欄位可供選擇 (Symbol: {symbol})")
                    return pd.DataFrame()

                final_df = final_df[valid_cols_to_keep]

                logger.info(f"成功抓取並處理 {len(final_df)} 筆數據，商品: {symbol}。")
                return final_df

            except Exception as e:
                logger.error(f"抓取數據時發生錯誤 (Symbol: {symbol})：{e}", exc_info=True)
                return pd.DataFrame()

        return await asyncio.to_thread(_sync_fetch)

    async def fetch_multiple_symbols_data(
        self, symbols: List[str], **kwargs
    ) -> pd.DataFrame:
        import asyncio

        if not isinstance(symbols, list) or not symbols:
            logger.error("symbols 參數必須是一個非空列表。")
            return pd.DataFrame()

        tasks = [self.fetch_data(symbol=s, **kwargs) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_data_list = []
        for i, res in enumerate(results):
            if isinstance(res, pd.DataFrame) and not res.empty:
                all_data_list.append(res)
            elif isinstance(res, Exception):
                logger.error(
                    f"處理商品 {symbols[i]} 時發生錯誤: {res}", exc_info=True
                )

        if not all_data_list:
            logger.info("未從任何指定商品抓取到數據。")
            return pd.DataFrame()

        combined_df = pd.concat(all_data_list, ignore_index=True)
        logger.info(
            f"成功合併 {len(combined_df)} 筆來自 {len(all_data_list)} 個商品的數據。"
        )
        return combined_df

    def get_ticker(self, symbol: str) -> yf.Ticker:
        """
        獲取一個 yfinance Ticker 物件。
        """
        return yf.Ticker(symbol)

    def get_move_index(self, start_date: str, end_date: str) -> pd.Series:
        """從 yfinance 獲取 ICE BofA MOVE Index (^MOVE) 的歷史收盤價。"""
        logger.info(f"正在獲取 ^MOVE 指數數據，日期範圍: {start_date} 至 {end_date}")
        try:
            move_ticker = yf.Ticker("^MOVE")
            start_date_dt = pd.to_datetime(start_date)
            end_date_dt = pd.to_datetime(end_date)
            end_date_for_yf = (end_date_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            start_date_for_yf = start_date_dt.strftime("%Y-%m-%d")
            history = move_ticker.history(start=start_date_for_yf, end=end_date_for_yf)

            if history.empty:
                logger.warning(f"^MOVE 指數在 {start_date_for_yf} 至 {end_date_for_yf} 未返回任何數據。")
                return pd.Series(dtype="float64", name="Close")

            close_series = history["Close"]
            if not isinstance(close_series.index, pd.DatetimeIndex):
                close_series.index = pd.to_datetime(close_series.index)

            close_series = close_series[close_series.index <= end_date_dt]

            if close_series.empty:
                logger.warning(f"^MOVE 指數在篩選日期 ({start_date_dt.date()} 至 {end_date_dt.date()}) 後數據為空。")
                return pd.Series(dtype="float64", name="Close")

            logger.info(f"成功獲取 {len(close_series)} 筆 ^MOVE 指數數據。")
            return close_series
        except Exception as e:
            logger.error(f"獲取 ^MOVE 指數時失敗: {e}", exc_info=True)
            return pd.Series(dtype="float64", name="Close")


if __name__ == "__main__":
    print("--- YFinanceClient 重構後測試 (直接執行 core/clients/yfinance.py) ---")
    try:
        client = YFinanceClient()
        print("YFinanceClient 初始化成功。")

        print("\n測試獲取 AAPL 數據 (2023-12-01 至 2023-12-05)...")
        aapl_data = client.fetch_data(
            symbol="AAPL", start_date="2023-12-01", end_date="2023-12-05"
        )
        if aapl_data is not None and not aapl_data.empty:
            print(f"成功獲取 AAPL 數據 (共 {len(aapl_data)} 筆):")
            print(aapl_data.head())
        else:
            print("獲取 AAPL 數據返回空 DataFrame 或 None。")

        print("\n測試獲取 AAPL 和 MSFT 數據 (最近5天, 1d 間隔)...")
        multi_data = client.fetch_multiple_symbols_data(
            symbols=["AAPL", "MSFT", "NONEXISTENTICKER"],
            period="5d",
            interval="1d",
        )
        if multi_data is not None and not multi_data.empty:
            print(f"成功獲取多個商品數據 (共 {len(multi_data)} 筆):")
            print(multi_data.head())
            print("...")
            print(multi_data.tail())
            print(f"數據中包含的 Symbols: {multi_data['symbol'].unique()}")
        else:
            print("獲取多個商品數據返回空 DataFrame 或 None。")

        print("\n測試獲取 ^GSPC 數據 (最近1個月)...")
        gspc_data = client.fetch_data(symbol="^GSPC", period="1mo")
        if gspc_data is not None and not gspc_data.empty:
            print(f"成功獲取 ^GSPC 數據 (最近1個月，共 {len(gspc_data)} 筆):")
            print(gspc_data.head())
        else:
            print("獲取 ^GSPC 數據返回空 DataFrame 或 None。")

        print("\n測試獲取 SPY 數據 (最近1天, 1m 間隔)...")
        spy_intraday = client.fetch_data(symbol="SPY", period="1d", interval="1m")
        if spy_intraday is not None and not spy_intraday.empty:
            print(f"成功獲取 SPY 1分鐘數據 (共 {len(spy_intraday)} 筆):")
            assert "Date" in spy_intraday.columns
            assert "Datetime" not in spy_intraday.columns
            print(spy_intraday.head())
        else:
            print(
                "獲取 SPY 1分鐘數據返回空 DataFrame 或 None (可能是市場未開盤或超出 yfinance 限制)。"
            )

    except Exception as e:
        print(f"執行 YFinanceClient 測試期間發生未預期錯誤: {e}")
        traceback.print_exc()

    print("--- YFinanceClient 重構後測試結束 ---")
