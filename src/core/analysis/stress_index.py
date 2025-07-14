# -*- coding: utf-8 -*-
"""
核心分析引擎：金融壓力指數計算器

功能：
- 整合多個數據客戶端 (FRED, NYFed) 以獲取原始數據。
- 對不同頻率的數據進行對齊、預處理與衍生指標計算。
- 使用 Z-Score 方法對各項指標進行標準化。
- 將標準化後的分數合成為一個綜合的每日壓力指數。
- 提供視覺化功能，將壓力指數繪製成互動式圖表。
"""

from typing import Dict

import pandas as pd
import plotly.graph_objects as go

# 導入我們經過驗證的數據客戶端
from core.clients.fred import FredClient
from core.clients.nyfed import NYFedClient


class StressIndexCalculator:
    """
    負責計算綜合金融壓力指數的引擎。
    """

    def __init__(self, rolling_window: int = 252):
        """
        初始化計算器。

        Args:
            rolling_window (int): 用於計算 Z-Score 的滾動窗口大小，預設為 252 (約一個交易年)。
        """
        print("資訊：正在初始化壓力指數計算引擎...")
        self.fred_client = FredClient()
        self.nyfed_client = NYFedClient()
        self.rolling_window = rolling_window

        # 定義計算所需的指標及其在 FRED 中的代碼
        self.fred_series = {
            "VIX": "VIXCLS",
            "DGS10": "DGS10",
            "DGS2": "DGS2",
            "Reserves": "WRESBAL",
            "SOFR": "SOFR",
        }
        print(f"資訊：引擎初始化完畢。滾動窗口設定為 {self.rolling_window} 天。")

    def _fetch_all_data(self) -> Dict[str, pd.DataFrame]:
        """
        從所有數據源獲取原始數據。
        """
        print("\n--- [階段 1] 數據獲取 ---")
        data_frames = {}

        # 獲取 FRED 數據
        for name, symbol in self.fred_series.items():
            try:
                # 確保傳遞 observation_start 和 observation_end 以獲取足夠歷史數據
                # 這裡假設我們至少需要滾動窗口 + 一段額外數據
                # 實際應用中，日期範圍可能需要更精確的控制
                data_frames[name] = self.fred_client.fetch_data(
                    symbol,
                    observation_start="2000-01-01",  # 示例起始日期
                )
            except Exception as e:
                print(f"錯誤：獲取 FRED 指標 {name} ({symbol}) 失敗: {e}")
                data_frames[name] = pd.DataFrame()  # 創建空 DataFrame 以免後續出錯

        # 獲取紐約聯儲數據
        try:
            nyfed_df = self.nyfed_client.fetch_data(
                symbol="DUMMY_NYFED_SYMBOL_IGNORED"
            )  # Symbol is ignored by NYFedClient
            if not nyfed_df.empty:
                if "Date" in nyfed_df.columns and "Total_Positions" in nyfed_df.columns:
                    nyfed_df["Date"] = pd.to_datetime(nyfed_df["Date"])
                    nyfed_df.set_index("Date", inplace=True)
                    # 將欄位名稱更改為 'NYFed_Positions' 以便於識別和合併
                    data_frames["NYFed_Positions"] = nyfed_df[
                        ["Total_Positions"]
                    ].rename(columns={"Total_Positions": "NYFed_Positions"})
                    print(
                        f"資訊：NYFed 數據獲取成功，共 {len(data_frames['NYFed_Positions'])} 筆。"
                    )
                else:
                    print(
                        f"錯誤：NYFed 數據缺少 'Date' 或 'Total_Positions' 欄位。可用欄位: {nyfed_df.columns.tolist()}"
                    )
                    data_frames["NYFed_Positions"] = pd.DataFrame(
                        columns=["NYFed_Positions"]
                    ).set_index(pd.to_datetime([]))
            else:
                print("錯誤：獲取紐約聯儲一級交易商數據返回為空 DataFrame。")
                data_frames["NYFed_Positions"] = pd.DataFrame(
                    columns=["NYFed_Positions"]
                ).set_index(pd.to_datetime([]))
        except Exception as e:
            print(f"錯誤：獲取紐約聯儲一級交易商數據時發生嚴重錯誤: {e}")
            data_frames["NYFed_Positions"] = pd.DataFrame(
                columns=["NYFed_Positions"]
            ).set_index(pd.to_datetime([]))

        # 確保所有 FRED DataFrame 都有 Date Index (fredapi client 通常會處理好)
        # 並將 FRED series 的欄位名直接設為其指標名稱 (如 'VIX', 'DGS10')
        for name, df_item in data_frames.items():
            if name == "NYFed_Positions":  # NYFed data is already processed
                continue
            if not df_item.empty:
                if not isinstance(df_item.index, pd.DatetimeIndex):
                    # This case should ideally not happen if FredClient works as expected
                    print(
                        f"警告：FRED 數據框 '{name}' 的索引不是 DatetimeIndex。將嘗試轉換。"
                    )
                    if "Date" in df_item.columns:  # Should not happen with fredapi
                        df_item["Date"] = pd.to_datetime(df_item["Date"])
                        df_item.set_index("Date", inplace=True)
                    elif df_item.index.name == "Date" and not isinstance(
                        df_item.index, pd.DatetimeIndex
                    ):
                        df_item.index = pd.to_datetime(df_item.index)
                    else:
                        print(f"錯誤：FRED 數據框 '{name}' 索引轉換失敗。")
                        data_frames[name] = pd.DataFrame(columns=[name]).set_index(
                            pd.to_datetime([])
                        )  # Empty df with correct name
                        continue  # Skip renaming if conversion failed

                # FredClient.fetch_data returns a DataFrame with the series name as the column name.
                # We want to ensure the column name in our `data_frames` dict matches the `name` key.
                if name in df_item.columns:
                    data_frames[name] = df_item[
                        [name]
                    ]  # Select only the relevant column
                elif (
                    len(df_item.columns) == 1
                ):  # If only one column, assume it's the correct one
                    df_item.columns = [name]
                    data_frames[name] = df_item
                else:
                    print(
                        f"警告：FRED 數據框 '{name}' 的欄位與預期不符: {df_item.columns.tolist()}。將嘗試使用第一個欄位。"
                    )
                    if not df_item.empty and len(df_item.columns) > 0:
                        df_item_renamed = df_item.iloc[:, [0]].copy()
                        df_item_renamed.columns = [name]
                        data_frames[name] = df_item_renamed
                    else:  # Fallback to empty
                        data_frames[name] = pd.DataFrame(columns=[name]).set_index(
                            pd.to_datetime([])
                        )
            else:  # If df_item was empty from fetch
                data_frames[name] = pd.DataFrame(columns=[name]).set_index(
                    pd.to_datetime([])
                )

        print("--- [階段 1] 數據獲取完成 ---")
        return data_frames

    def _preprocess_and_align(self, raw_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        對數據進行預處理、計算衍生指標並對齊到統一的交易日曆。
        """
        print("\n--- [階段 2] 數據預處理與對齊 ---")

        # 過濾掉空的 DataFrame
        valid_data_frames = {
            name: df
            for name, df in raw_data.items()
            if not df.empty and isinstance(df.index, pd.DatetimeIndex)
        }

        if not valid_data_frames:
            print("錯誤：所有原始數據均為空或無效，無法進行預處理。")
            return pd.DataFrame()

        # 合併所有數據，使用 outer join 保留所有日期
        # 確保在合併前，所有 DataFrame 的索引都是 DatetimeIndex
        temp_dfs_to_concat = []
        for name, df_item in valid_data_frames.items():
            if not isinstance(df_item.index, pd.DatetimeIndex):  # 再次檢查
                print(
                    f"警告：在合併前發現 {name} 的索引不是 DatetimeIndex。跳過此數據。"
                )
                continue
            # 確保欄位名唯一，防止合併時衝突 (例如 FRED 和 NYFed 都返回 'Value')
            # FredClient 返回的 DataFrame 欄位名應該是 symbol name, NYFedClient 是 Total_Positions
            # VIXClient 返回的是 VIX, DGS10Client 是 DGS10 etc.
            # 這裡假設 fetch_data 已經處理好欄位名
            temp_dfs_to_concat.append(df_item)

        if not temp_dfs_to_concat:
            print("錯誤：沒有有效的 DataFrame 可以合併。")
            return pd.DataFrame()

        combined_df = pd.concat(temp_dfs_to_concat, axis=1, join="outer")

        if combined_df.empty:
            print("錯誤：合併後的 DataFrame 為空。")
            return pd.DataFrame()

        # 建立一個包含所有日期的標準日曆 (每日頻率)
        min_date = combined_df.index.min()
        max_date = combined_df.index.max()

        if pd.isna(min_date) or pd.isna(max_date):
            print("錯誤：無法確定合併數據的日期範圍。")
            return pd.DataFrame()

        full_date_range = pd.date_range(start=min_date, end=max_date, freq="D")
        aligned_df = combined_df.reindex(full_date_range)

        # **關鍵步驟**：使用前向填充處理週末與假日
        # 對於某些指標 (如 VIX)，週末值應與週五相同
        # 對於利率等，也通常用前一個交易日的值填充
        aligned_df.ffill(inplace=True)

        # 計算衍生指標：殖利率曲線斜率 (10年期 - 2年期)
        if "DGS10" in aligned_df.columns and "DGS2" in aligned_df.columns:
            # 確保 DGS10 和 DGS2 是數值型
            aligned_df["DGS10"] = pd.to_numeric(aligned_df["DGS10"], errors="coerce")
            aligned_df["DGS2"] = pd.to_numeric(aligned_df["DGS2"], errors="coerce")
            aligned_df["Yield_Spread"] = aligned_df["DGS10"] - aligned_df["DGS2"]
            print("資訊：已計算衍生指標：殖利率曲線斜率 (Yield_Spread)。")
        else:
            print("警告：無法計算殖利率曲線斜率，缺少 DGS10 或 DGS2 數據。")

        # 移除原始利率，只保留利差 (如果已計算)
        # 確保只移除我們定義在 self.fred_series 中的原始利率欄位名
        cols_to_drop = []
        if "DGS10" in self.fred_series.values():
            cols_to_drop.append("DGS10")  # noqa: E701
        if "DGS2" in self.fred_series.values():
            cols_to_drop.append("DGS2")  # noqa: E701

        # 檢查這些列是否存在於 aligned_df 中再刪除
        existing_cols_to_drop = [
            col for col in cols_to_drop if col in aligned_df.columns
        ]
        if existing_cols_to_drop:
            aligned_df.drop(columns=existing_cols_to_drop, inplace=True)
            print(f"資訊：已移除原始利率欄位: {existing_cols_to_drop}。")

        # 篩選出我們實際要用於 Z-score 計算的欄位
        # 這些欄位應該是 VIX, Yield_Spread, Reserves, SOFR, NYFed_Positions (Total_Positions)
        final_columns_for_zscore = []
        if "VIX" in aligned_df.columns:
            final_columns_for_zscore.append("VIX")  # noqa: E701
        if "Yield_Spread" in aligned_df.columns:
            final_columns_for_zscore.append("Yield_Spread")  # noqa: E701
        if "Reserves" in aligned_df.columns:
            final_columns_for_zscore.append("Reserves")  # noqa: E701
        if "SOFR" in aligned_df.columns:
            final_columns_for_zscore.append("SOFR")  # noqa: E701
        # **修正**: 檢查 'NYFed_Positions' 而不是 'Total_Positions'
        if "NYFed_Positions" in aligned_df.columns:
            final_columns_for_zscore.append("NYFed_Positions")  # noqa: E701

        if not final_columns_for_zscore:
            print("錯誤：沒有可用於 Z-score 計算的最終欄位。")
            return pd.DataFrame()

        aligned_df = aligned_df[final_columns_for_zscore]

        # 刪除任何在滾動窗口開始前因數據不足而產生的完全缺失的行
        aligned_df.dropna(how="all", inplace=True)  # 如果一行所有指標都缺失則刪除
        # 刪除在計算滾動 Z-score 前因數據序列開頭導致的個別指標的 NaN (這步會在 _normalize_to_zscore 中處理)

        if aligned_df.empty:
            print("錯誤：預處理和對齊後的 DataFrame 為空。")
            return pd.DataFrame()

        print(
            f"--- [階段 2] 數據預處理與對齊完成。最終用於標準化的數據維度: {aligned_df.shape} ---"
        )
        print(f"用於標準化的欄位: {aligned_df.columns.tolist()}")
        return aligned_df

    def _normalize_to_zscore(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        將所有指標轉換為其滾動 Z-Score。
        """
        print(
            f"\n--- [階段 3] 指標標準化 (Z-Score, {self.rolling_window}天滾動窗口) ---"
        )
        if df.empty:
            print("錯誤：傳入標準化的 DataFrame 為空。")
            return pd.DataFrame()

        zscore_df = pd.DataFrame(index=df.index)
        for col in df.columns:
            # 確保數據是數值型
            series_to_normalize = pd.to_numeric(df[col], errors="coerce")

            if series_to_normalize.isnull().all():
                print(
                    f"警告：欄位 {col} 在轉換為數值型後全為 NaN，無法計算 Z-score。跳過此欄位。"
                )
                zscore_df[f"{col}_zscore"] = (
                    pd.NA
                )  # 或 pd.Series([pd.NA]*len(df), index=df.index)
                continue

            rolling_mean = series_to_normalize.rolling(
                window=self.rolling_window, min_periods=int(self.rolling_window / 2)
            ).mean()
            rolling_std = series_to_normalize.rolling(
                window=self.rolling_window, min_periods=int(self.rolling_window / 2)
            ).std()

            # 避免除以零或極小的標準差
            # 如果標準差接近零 (例如，小於 1e-6)，則 Z-score 可能會變得非常大或不穩定
            # 在這種情況下，我們可能認為該時期的 Z-score 為 0 (即沒有偏離均值)
            # 或者使用一個小的正數代替0，以避免除零錯誤，但這仍可能導致極端值。
            # 這裡選擇將 std 為 0 的替換為 1，這樣 Z-score 會是 0 (如果 x == mean) 或 x - mean
            rolling_std.loc[rolling_std.abs() < 1e-6] = 1.0

            zscore_values = (series_to_normalize - rolling_mean) / rolling_std
            zscore_df[f"{col}_zscore"] = zscore_values
            print(
                f"資訊：已計算 {col}_zscore。有效值數量: {zscore_values.notna().sum()}/{len(zscore_values)}"
            )

        # 刪除因滾動窗口導致開頭產生的 NaN 行
        zscore_df.dropna(how="all", inplace=True)  # 如果一行所有 z-score 都是 NaN

        if zscore_df.empty:
            print("錯誤：標準化後的 DataFrame 為空 (可能是滾動窗口過大或數據不足)。")
            return pd.DataFrame()

        print(f"--- [階段 3] 標準化完成。Z-score 數據維度: {zscore_df.shape} ---")
        return zscore_df

    def _aggregate_index(self, zscores: pd.DataFrame) -> pd.DataFrame:
        """
        將所有 Z-Score 合成為最終的壓力指數。
        """
        print("\n--- [階段 4] 壓力指數合成 ---")
        if zscores.empty:
            print("錯誤：傳入合成的 Z-scores DataFrame 為空。")
            return pd.DataFrame()

        final_index = pd.DataFrame(index=zscores.index)

        # 複製一份以進行方向調整
        adjusted_zscores = zscores.copy()

        # **關鍵步驟**：統一指標方向，確保分數越高代表壓力越大
        # 利差 (Yield_Spread_zscore) 越低 (例如倒掛)，壓力越大，所以 Z-Score 需要反轉
        if "Yield_Spread_zscore" in adjusted_zscores.columns:
            adjusted_zscores["Yield_Spread_zscore"] *= -1
            print("資訊：已反轉 'Yield_Spread_zscore' 方向。")

        # 總準備金 (Reserves_zscore) 越低，流動性越緊，壓力越大，Z-Score 需要反轉
        if "Reserves_zscore" in adjusted_zscores.columns:
            adjusted_zscores["Reserves_zscore"] *= -1
            print("資訊：已反轉 'Reserves_zscore' 方向。")

        # 一級交易商持有量 (NYFed_Positions_zscore, 來自 NYFed) 越高，通常代表市場風險偏好較高，
        # 或銀行系統壓力較小 (他們有能力持有更多證券)。因此，持有量增加應對應壓力減小。
        # 所以，如果持有量 Z-score 越高，壓力越小，我們需要反轉它。
        # **修正**: 檢查 'NYFed_Positions_zscore'
        if "NYFed_Positions_zscore" in adjusted_zscores.columns:
            adjusted_zscores["NYFed_Positions_zscore"] *= -1
            print(
                "資訊：已反轉 'NYFed_Positions_zscore' 方向 (假設持有量越高壓力越小)。"
            )

        # VIX (VIX_zscore) 和 SOFR (SOFR_zscore) 天然與壓力正相關，無需調整
        # VIX 越高，市場恐慌，壓力越大。
        # SOFR 越高 (短期融資利率)，融資成本越高，壓力越大。

        # 確保只對實際存在的欄位進行平均
        valid_zscore_cols = [
            col
            for col in adjusted_zscores.columns
            if adjusted_zscores[col].notna().any()
        ]
        if not valid_zscore_cols:
            print("錯誤：沒有有效的 Z-score 欄位可用於合成指數。")
            return pd.DataFrame(columns=["Stress_Index"], index=zscores.index)

        print(f"資訊：用於合成指數的 (調整後) Z-score 欄位: {valid_zscore_cols}")
        final_index["Stress_Index"] = adjusted_zscores[valid_zscore_cols].mean(axis=1)

        # 再次去除可能因某些行只有部分指標有值而導致的 NaN
        final_index.dropna(inplace=True)

        if final_index.empty:
            print("錯誤：合成後的最終壓力指數為空。")
            return pd.DataFrame()

        print(f"--- [階段 4] 合成完成。最終指數數據維度: {final_index.shape} ---")
        return final_index

    def calculate(self) -> pd.DataFrame:
        """
        執行完整的壓力指數計算流程。

        Returns:
            pd.DataFrame: 包含每日壓力指數的最終 DataFrame。
        """
        print("\n" + "=" * 20 + " 開始執行壓力指數計算流程 " + "=" * 20)
        raw_data = self._fetch_all_data()

        # 檢查是否有任何數據被獲取
        if not any(not df.empty for df in raw_data.values()):
            print("錯誤：所有數據源均未能獲取數據。無法繼續計算。")
            return pd.DataFrame(columns=["Stress_Index"]).set_index(pd.to_datetime([]))

        processed_data = self._preprocess_and_align(raw_data)
        if processed_data.empty:
            print("錯誤：數據預處理和對齊後無數據。無法繼續計算。")
            return pd.DataFrame(columns=["Stress_Index"]).set_index(pd.to_datetime([]))

        normalized_data = self._normalize_to_zscore(processed_data)
        if normalized_data.empty:
            print("錯誤：數據標準化後無數據。無法繼續計算。")
            return pd.DataFrame(columns=["Stress_Index"]).set_index(pd.to_datetime([]))

        stress_index = self._aggregate_index(normalized_data)
        if stress_index.empty:
            print("錯誤：壓力指數合成後無數據。")
            return pd.DataFrame(columns=["Stress_Index"]).set_index(pd.to_datetime([]))

        print("=" * 20 + " 壓力指數計算流程執行完畢 " + "=" * 20 + "\n")
        return stress_index

    def close_all_sessions(self):
        """安全地關閉所有客戶端的 session。"""
        print("資訊：正在關閉所有客戶端連線...")
        if hasattr(self, "fred_client") and self.fred_client:
            self.fred_client.close_session()
        if hasattr(self, "nyfed_client") and self.nyfed_client:
            self.nyfed_client.close_session()
        print("資訊：所有客戶端連線已關閉。")


def plot_stress_index(df: pd.DataFrame, title: str = "每日綜合金融壓力指數"):
    """
    使用 Plotly 將壓力指數視覺化。

    Args:
        df (pd.DataFrame): 包含 'Stress_Index' 欄位的 DataFrame。
        title (str): 圖表的標題。
    """
    print("\n--- [階段 5] 產生視覺化圖表 ---")
    if df.empty or "Stress_Index" not in df.columns:
        print("錯誤：壓力指數數據為空或缺少 'Stress_Index' 欄位，無法繪製圖表。")
        return

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["Stress_Index"],
            mode="lines",
            name="綜合金融壓力指數",
            line=dict(color="crimson", width=2),
        )
    )

    # 添加水平零線，作為壓力正常水平的參考
    fig.add_hline(
        y=0,
        line_width=1,
        line_dash="dash",
        line_color="gray",
        annotation_text="基準線",
        annotation_position="bottom right",
    )

    # 可以考慮添加一些統計線，例如 +1/-1 標準差
    mean_val = df["Stress_Index"].mean()
    std_val = df["Stress_Index"].std()
    fig.add_hline(
        y=mean_val + std_val,
        line_width=1,
        line_dash="dot",
        line_color="rgba(0,100,80,0.5)",
        annotation_text="+1 SD",
        annotation_position="bottom right",
    )
    fig.add_hline(
        y=mean_val - std_val,
        line_width=1,
        line_dash="dot",
        line_color="rgba(0,100,80,0.5)",
        annotation_text="-1 SD",
        annotation_position="bottom right",
    )

    fig.update_layout(
        title={
            "text": title,
            "y": 0.9,
            "x": 0.5,
            "xanchor": "center",
            "yanchor": "top",
            "font": {"size": 20},
        },
        xaxis_title="日期",
        yaxis_title="壓力指數 (Z-Score 標準化)",
        template="plotly_white",  # 使用簡潔的白色主題
        legend_title_text="指標",
        xaxis_rangeslider_visible=True,  # 添加日期範圍滑塊
    )

    # 嘗試在瀏覽器中顯示圖表
    # fig.show() # 這在無 GUI 環境中可能會有問題，或需要額外配置
    # 如果 fig.show() 有問題，可以考慮保存為 HTML
    try:
        fig.show()
        print("--- [階段 5] 圖表已嘗試在瀏覽器中顯示 ---")
    except Exception as e:
        print(f"錯誤：顯示 Plotly 圖表時發生問題: {e}")
        print("提示：在某些環境下 (如無頭伺服器)，Plotly 可能無法直接顯示圖表。")
        # 可以考慮將圖表保存為 HTML 文件
        # html_path = "stress_index_chart.html"
        # fig.write_html(html_path)
        # print(f"圖表已保存至 {html_path}")


if __name__ == "__main__":
    print("=" * 60)
    print("          開始執行金融壓力指數計算與視覺化測試腳本")
    print("=" * 60)

    # 確保您的 config.yml 中已填寫有效的 FRED API Key
    # ConfigManager 應該在導入 client 時已經被初始化並載入設定

    calculator = None  # 初始化為 None
    try:
        # 1. 初始化計算引擎
        # 使用兩年滾動窗口 (約 252*2 = 504 個交易日)
        # 為了得到有意義的 Z-score，需要至少兩倍窗口的數據，所以起始日期要足夠早
        calculator = StressIndexCalculator(rolling_window=252 * 2)

        # 2. 執行計算
        final_stress_index = calculator.calculate()

        # 3. 顯示結果
        print("\n--- [計算結果] ---")
        if not final_stress_index.empty:
            print(f"最終壓力指數數據點數量: {len(final_stress_index)}")
            print("壓力指數統計摘要:")
            print(final_stress_index["Stress_Index"].describe())
            print("\n最新的 10 筆壓力指數數據:")
            print(final_stress_index.tail(10))
        else:
            print("錯誤：最終計算出的壓力指數為空。")

        # 4. 繪製圖表
        if not final_stress_index.empty:
            plot_stress_index(
                final_stress_index, title="每日綜合金融壓力指數 (滾動窗口 2年)"
            )
        else:
            print("\n錯誤：最終壓力指數為空，無法繪製圖表。")

    except ValueError as ve:  # 例如金鑰未設定
        print(f"\n執行過程中發生設定相關錯誤: {ve}")
    except Exception as e:
        print(f"\n執行過程中發生嚴重錯誤: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if calculator:  # 確保 calculator 實例存在
            calculator.close_all_sessions()

    print("\n" + "=" * 60)
    print("                          測試腳本執行完畢")
    print("=" * 60)
