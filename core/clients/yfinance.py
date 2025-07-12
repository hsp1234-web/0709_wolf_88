# core/clients/yfinance.py
# 此模組包含從 Yahoo Finance 下載市場數據的客戶端邏輯。

import traceback
from typing import (  # Added Any, cast. Optional, List were already there.
    Any,
    List,
    cast,
)

import pandas as pd
import yfinance as yf

from .base import BaseAPIClient


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
        print("資訊：YFinanceClient 初始化完成。")

    def fetch_data(
        self, symbol: str, **kwargs
    ) -> (
        pd.DataFrame
    ):  # Return type changed to pd.DataFrame from Optional[pd.DataFrame]
        """
        從 Yahoo Finance 抓取指定商品代碼的每日 OHLCV 數據。
        """
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        period = kwargs.get("period")

        if not period and (not start_date or not end_date):
            raise ValueError(
                "必須提供 'period' 或 'start_date' 與 'end_date' 其中之一。"
            )

        # 基礎參數
        history_params = {
            "start": start_date,
            "end": end_date,
            "auto_adjust": kwargs.get("auto_adjust", False),
            # "progress": kwargs.get("progress", False), # yfinance 0.2.40 不支援此參數
            "interval": kwargs.get("interval", "1d"),
            "actions": kwargs.get("actions", False),
        }
        # 如果提供了 period，則優先使用 period 並移除 start/end
        if period:
            history_params["period"] = period
            history_params.pop("start", None)
            history_params.pop("end", None)

        # 移除 progress=False，因為 yfinance 0.2.40 的 ticker.history() 不接受此參數
        # 在 YFinanceClient 的 fetch_data 方法中，我們不再明確傳遞 progress 參數給 ticker.history()
        # 如果 yfinance 的某些版本預設為 True，而我們不希望看到進度條，
        # 則可能需要尋找其他方式來抑制，但通常 yf.download(progress=False) 是針對頂層函數的。
        # 對於 Ticker().history()，如果它內部打印進度，可能無法直接透過參數關閉。
        # 但 yfinance 0.2.40 的 Ticker.history() 似乎不主動顯示進度。
        # 我們在 _test_run.py 中是 client.fetch_data(...)，progress 參數已在此處移除。

        print(
            f"資訊：YFinanceClient 開始抓取數據：商品 {symbol}, 參數: {history_params}"
        )

        try:
            ticker_obj: Any = yf.Ticker(symbol)
            # 確保 history_params 中不包含 progress (以防萬一 kwargs 中傳入了)
            history_params.pop("progress", None)
            hist_data: Any = ticker_obj.history(**history_params)

            # Check if hist_data is None or empty DataFrame before proceeding
            if hist_data is None or hist_data.empty:
                print(
                    f"警告：YFinanceClient - 商品 {symbol} 使用參數 {history_params} 未找到數據或返回為空。"
                )
                return (
                    pd.DataFrame()
                )  # Return empty DataFrame as per original logic for failure/no data

            # At this point, hist_data is a non-empty DataFrame (or yfinance would have errored/returned empty)
            # We can now safely cast it if needed, or proceed with operations
            hist_data = cast(pd.DataFrame, hist_data)

            hist_data.reset_index(inplace=True)
            hist_data["symbol"] = symbol

            date_col_name = "Datetime" if "Datetime" in hist_data.columns else "Date"
            if date_col_name not in hist_data.columns:
                print(
                    f"警告：YFinanceClient - 未找到預期的日期欄位 ('Date' 或 'Datetime')。可用欄位: {hist_data.columns.tolist()}"
                )
                return pd.DataFrame()

            # --- 核心修改點 START ---
            # 先將索引/欄位轉為 datetime 物件並強制轉換為 UTC
            hist_data[date_col_name] = pd.to_datetime(
                hist_data[date_col_name], utc=True
            )
            # 現在所有時間都帶有 UTC 時區，再進行統一清除，使其變為無時區的 UTC 時間
            hist_data[date_col_name] = hist_data[date_col_name].dt.tz_convert(None)
            # --- 核心修改點 END ---

            # 確保最終日期欄位名為 'Date'
            if (
                date_col_name != "Date" and "Date" not in hist_data.columns
            ):  # 避免意外覆蓋已存在的 "Date" 欄
                hist_data.rename(columns={date_col_name: "Date"}, inplace=True)
            elif (
                date_col_name == "Date" and date_col_name != "Date"
            ):  # 理論上不會發生，但作為防禦
                # 如果 date_col_name 是 "Date"，就不需要重命名
                pass

            rename_map = {"Adj Close": "Adj_Close"}
            final_df = hist_data.rename(columns=rename_map)
            final_df["Date"] = pd.to_datetime(final_df["Date"])

            required_cols = [
                "Date",
                "symbol",
                "Open",
                "High",
                "Low",
                "Close",
                "Adj_Close",
                "Volume",
            ]
            cols_to_keep = []
            missing_cols = []

            for col in required_cols:
                if col in final_df.columns:
                    cols_to_keep.append(col)
                elif (
                    col == "Adj_Close"
                    and "Close" in final_df.columns
                    and history_params["auto_adjust"] is True
                ):
                    final_df["Adj_Close"] = final_df["Close"]
                    cols_to_keep.append("Adj_Close")
                elif (
                    col not in final_df.columns
                ):  # only add to missing if not handled by auto_adjust case
                    missing_cols.append(col)

            if missing_cols:
                print(
                    f"警告：YFinanceClient - 抓取的數據中缺少以下預期欄位: {missing_cols} (Symbol: {symbol})。"
                )

            # Ensure all cols_to_keep actually exist before trying to select them
            # This can happen if auto_adjust is true, 'Adj_Close' is required but not initially present
            valid_cols_to_keep = [
                col for col in cols_to_keep if col in final_df.columns
            ]
            if (
                not valid_cols_to_keep
            ):  # If no valid columns remain (highly unlikely but a safeguard)
                print(
                    f"警告：YFinanceClient - 沒有有效的欄位可供選擇 (Symbol: {symbol})"
                )
                return pd.DataFrame()

            final_df = final_df[valid_cols_to_keep]

            print(
                f"資訊：YFinanceClient 成功抓取並處理 {len(final_df)} 筆數據，商品: {symbol}。"
            )
            return final_df

        except Exception as e:
            print(f"錯誤：YFinanceClient 抓取數據時發生錯誤 (Symbol: {symbol})：{e}")
            traceback.print_exc()
            return pd.DataFrame()

    def fetch_multiple_symbols_data(self, symbols: List[str], **kwargs) -> pd.DataFrame:
        if not isinstance(symbols, list) or not symbols:
            print(
                "錯誤：YFinanceClient.fetch_multiple_symbols_data - symbols 參數必須是一個非空列表。"
            )
            return pd.DataFrame()

        all_data_list = []
        for symbol_ticker in symbols:
            try:
                df_symbol = self.fetch_data(symbol=symbol_ticker, **kwargs)
                if (
                    df_symbol is not None and not df_symbol.empty
                ):  # Check for None as well
                    all_data_list.append(df_symbol)
            except Exception as e:
                print(
                    f"錯誤：YFinanceClient.fetch_multiple_symbols_data - 處理商品 {symbol_ticker} 時發生錯誤: {e}"
                )

        if not all_data_list:
            print(
                "資訊：YFinanceClient.fetch_multiple_symbols_data - 未從任何指定商品抓取到數據。"
            )
            return pd.DataFrame()

        combined_df = pd.concat(all_data_list, ignore_index=True)
        print(
            f"資訊：YFinanceClient.fetch_multiple_symbols_data - 成功合併 {len(combined_df)} 筆來自 {len(all_data_list)} 個商品的數據。"
        )
        return combined_df

    def get_move_index(self, start_date: str, end_date: str) -> pd.Series:
        """從 yfinance 獲取 ICE BofA MOVE Index (^MOVE) 的歷史收盤價。"""
        print(
            f"資訊：YFinanceClient 正在獲取 ^MOVE 指數數據，日期範圍: {start_date} 至 {end_date}"
        )
        try:
            move_ticker = yf.Ticker("^MOVE")
            # yfinance 的 end 參數不包含，所以需將結束日期加一天
            # 同時，確保 start_date 和 end_date 的格式正確
            start_date_dt = pd.to_datetime(start_date)
            end_date_dt = pd.to_datetime(end_date)

            end_date_for_yf = (end_date_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            start_date_for_yf = start_date_dt.strftime("%Y-%m-%d")

            history = move_ticker.history(start=start_date_for_yf, end=end_date_for_yf)

            if history.empty:
                print(
                    f"警告：^MOVE 指數在 {start_date_for_yf} 至 {end_date_for_yf} 未返回任何數據。"
                )
                return pd.Series(dtype="float64", name="Close")

            # 確保返回的是 Series，並且索引是 DatetimeIndex
            close_series = history["Close"]
            if not isinstance(close_series.index, pd.DatetimeIndex):
                close_series.index = pd.to_datetime(close_series.index)

            # 篩選掉結束日期之後的數據（因為我們加了一天）
            close_series = close_series[close_series.index <= end_date_dt]

            if close_series.empty:
                print(
                    f"警告：^MOVE 指數在篩選日期 ({start_date_dt.date()} 至 {end_date_dt.date()}) 後數據為空。"
                )
                return pd.Series(dtype="float64", name="Close")

            print(
                f"資訊：YFinanceClient 成功獲取 {len(close_series)} 筆 ^MOVE 指數數據。"
            )
            return close_series
        except Exception as e:
            print(f"錯誤：YFinanceClient 獲取 ^MOVE 指數時失敗: {e}")
            traceback.print_exc()  # 添加 traceback 以獲取更詳細的錯誤信息
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
