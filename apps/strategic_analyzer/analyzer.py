# -*- coding: utf-8 -*-
"""
普羅米修斯之火 - 戰略分析器核心

本模組定義了 StrategicAnalyzer 類別，用於將計算出的量化因子，
轉譯成直觀的「紅、黃、綠」燈信號，並提供相應的市場解讀。
"""

import pandas as pd
# 稍後會需要 DBManager，先註釋掉，待 DBManager 路徑確認或傳入方式確定
# from apps.daily_market_analyzer.db_manager import DBManager

class StrategicAnalyzer:
    """
    戰略分析器核心類別。
    負責從資料庫讀取因子數據，根據預設規則生成紅黃綠信號，並產生解讀。
    """

    def __init__(self, db_manager):
        """
        初始化戰略分析器。

        Args:
            db_manager: DBManager 的實例，用於數據庫操作。
        """
        self.db_manager = db_manager
        print("INFO: 戰略分析器 (StrategicAnalyzer) 初始化完畢。")

    def _get_latest_factor_value(self, factor_name: str, ticker: str = None, date_offset: int = 0) -> float | None:
        """
        從 FactorStore_Daily 獲取指定因子最近的值。

        Args:
            factor_name (str): 因子名稱。
            ticker (str, optional): Ticker 名稱。如果因子不與特定 ticker 相關 (如宏觀因子)，則省略。
            date_offset (int, optional): 日期偏移量，0 表示最新日期，1 表示次新，以此類推。

        Returns:
            float | None: 因子值，如果找不到則返回 None。
        """
        query = """
        SELECT factor_value
        FROM FactorStore_Daily
        WHERE factor_name = ?
        """
        params = [factor_name]

        if ticker:
            query += " AND ticker = ? "
            params.append(ticker)

        query += " ORDER BY date DESC LIMIT 1 OFFSET ?;"
        params.append(date_offset)

        try:
            result_df = self.db_manager.execute_query(query, params)
            if not result_df.empty:
                return result_df['factor_value'].iloc[0]
            else:
                # print(f"DEBUG (_get_latest_factor_value): 找不到因子 {factor_name} (Ticker: {ticker}, Offset: {date_offset}) 的數據。")
                return None
        except Exception as e:
            print(f"錯誤 (_get_latest_factor_value): 讀取因子 {factor_name} (Ticker: {ticker}) 失敗: {e}")
            return None

    def _get_latest_market_price(self, ticker: str, date_offset: int = 0) -> float | None:
        """
        從 MarketPrices_Daily 獲取指定 ticker 的最新收盤價。
        注意: MarketPrices_Daily 的主表名可能由 DBManager 初始化時的 target_ohlcv_table_name 決定。
              這裡假設為 'MarketPrices_Daily'，如果 DBManager 內部有更動態的處理，此處可能需要調整。
              但通常 FactorEngine 也是基於 MarketPrices_Daily，所以應該一致。

        Args:
            ticker (str): Ticker 名稱。
            date_offset (int, optional): 日期偏移量，0 表示最新日期，1 表示次新，以此類推。

        Returns:
            float | None: 最新收盤價，如果找不到則返回 None。
        """
        # 假設 MarketPrices_Daily 表名固定，或者 self.db_manager 有方法獲取正確的日線行情表名
        # 目前的 DBManager 設計中，ohlcv_table_name 主要用於主要的 OHLCV 數據，
        # FactorEngine 的 get_prices_for_ticker 也直接查詢 MarketPrices_Daily。
        # 因此這裡也直接使用 MarketPrices_Daily。
        query = """
        SELECT close
        FROM MarketPrices_Daily
        WHERE ticker = ? AND interval = '1d' -- 確保是日線數據
        ORDER BY datetime DESC
        LIMIT 1 OFFSET ?;
        """
        params = [ticker, date_offset]
        try:
            result_df = self.db_manager.execute_query(query, params)
            if not result_df.empty:
                return result_df['close'].iloc[0]
            else:
                # print(f"DEBUG (_get_latest_market_price): 找不到 Ticker {ticker} (Offset: {date_offset}) 的日線收盤價數據。")
                return None
        except Exception as e:
            print(f"錯誤 (_get_latest_market_price): 讀取 Ticker {ticker} 收盤價失敗: {e}")
            return None

    def _get_factor_series(self, factor_name: str, ticker: str = None, limit: int = 20) -> pd.Series:
        """
        從 FactorStore_Daily 獲取指定因子最近的一系列值。

        Args:
            factor_name (str): 因子名稱。
            ticker (str, optional): Ticker 名稱。
            limit (int, optional): 需要獲取的數據點數量。

        Returns:
            pd.Series: 包含因子值的 Series，索引為日期。如果找不到數據則返回空 Series。
        """
        query = """
        SELECT date, factor_value
        FROM FactorStore_Daily
        WHERE factor_name = ?
        """
        params = [factor_name]

        if ticker:
            query += " AND ticker = ? "
            params.append(ticker)

        query += " ORDER BY date DESC LIMIT ?;"
        params.append(limit)

        try:
            result_df = self.db_manager.execute_query(query, params)
            if not result_df.empty:
                result_df['date'] = pd.to_datetime(result_df['date'])
                # 將 series 按日期升序排列，以便計算移動平均
                return pd.Series(result_df['factor_value'].values, index=result_df['date']).sort_index()
            else:
                # print(f"DEBUG (_get_factor_series): 找不到因子 {factor_name} (Ticker: {ticker}, Limit: {limit}) 的數據系列。")
                return pd.Series(dtype=float) # 返回空的 float Series
        except Exception as e:
            print(f"錯誤 (_get_factor_series): 讀取因子系列 {factor_name} (Ticker: {ticker}) 失敗: {e}")
            return pd.Series(dtype=float)


    def generate_daily_signals(self, analysis_date_str: str | None = None) -> pd.DataFrame:
        """
        生成每日的紅黃綠信號和解讀。

        Args:
            analysis_date_str (str, optional): 指定分析的日期 (YYYY-MM-DD)。
                                             如果為 None，則嘗試基於數據庫中最新數據的日期進行分析。
                                             目前版本將主要基於最新數據 (date_offset=0)。

        Returns:
            pd.DataFrame: 包含每日信號的 DataFrame，欄位應符合 StrategicDashboard_Daily 表結構:
                          ['date', 'indicator_name', 'signal', 'value', 'commentary']
        """
        signals_data = []
        current_analysis_date = None

        # TODO: 確定分析日期邏輯。
        # 如果 analysis_date_str 提供了，我們理論上應該獲取該日期的因子值。
        # 但 _get_latest_factor_value 目前是基於偏移量。
        # 為了簡化 v1.0，我們先假設總是分析 "最新" 的數據 (offset=0)。
        # 未來的版本可以增強這裡的日期選擇邏輯。
        # 現在，我們需要一個日期來填充 'date' 欄位。
        # 我們可以嘗試從 FactorStore_Daily 獲取最新的日期作為 current_analysis_date。
        try:
            latest_date_df = self.db_manager.execute_query("SELECT MAX(date) as max_date FROM FactorStore_Daily")
            if not latest_date_df.empty and latest_date_df['max_date'].iloc[0] is not None:
                current_analysis_date = pd.to_datetime(latest_date_df['max_date'].iloc[0]).date()
                print(f"INFO (StrategicAnalyzer): 自動設定分析日期為資料庫中最新因子日期: {current_analysis_date}")
            else: # 如果 FactorStore_Daily 為空，嘗試從 MarketPrices_Daily 獲取
                latest_market_date_df = self.db_manager.execute_query("SELECT MAX(CAST(datetime AS DATE)) as max_date FROM MarketPrices_Daily WHERE interval = '1d'")
                if not latest_market_date_df.empty and latest_market_date_df['max_date'].iloc[0] is not None:
                    current_analysis_date = pd.to_datetime(latest_market_date_df['max_date'].iloc[0]).date()
                    print(f"INFO (StrategicAnalyzer): 自動設定分析日期為資料庫中最新市場行情日期: {current_analysis_date}")
                else: # 如果都找不到，使用執行腳本的當前日期
                    current_analysis_date = pd.Timestamp.now().date()
                    print(f"警告 (StrategicAnalyzer): 無法從資料庫確定最新日期，使用當前系統日期: {current_analysis_date} 作為分析日期。")

            if analysis_date_str: # 如果用戶指定了日期，優先使用它 (但仍需注意因子獲取邏輯是基於 offset)
                current_analysis_date = pd.to_datetime(analysis_date_str).date()
                print(f"INFO (StrategicAnalyzer): 使用指定分析日期: {current_analysis_date}")

        except Exception as e:
            print(f"錯誤 (StrategicAnalyzer): 確定分析日期失敗: {e}。將使用當前系統日期。")
            current_analysis_date = pd.Timestamp.now().date()


        if not current_analysis_date:
            print("錯誤 (StrategicAnalyzer): 無法確定分析日期，終止信號生成。")
            return pd.DataFrame(columns=['date', 'indicator_name', 'signal', 'value', 'commentary'])

        # --- 殖利率曲線斜率 (YIELD_CURVE_SLOPE) ---
        indicator_name_yc = "YIELD_CURVE_SLOPE"
        yc_signal = "YELLOW" # 預設信號
        yc_value = None
        yc_commentary = "殖利率曲線斜率數據不足或計算失敗。"

        # 讀取 spread_10y_2y 因子
        # 我們假設分析的是最新的數據，所以 date_offset=0
        spread_10y_2y_value = self._get_latest_factor_value(factor_name="spread_10y_2y", ticker="US_TREASURY", date_offset=0)
        yc_value = spread_10y_2y_value # 將原始值存儲到 yc_value

        if spread_10y_2y_value is not None:
            # 規則：若利差 < 0 bps，信號為 RED。若利差 > 25 bps，信號為 GREEN。其餘為 YELLOW。
            # 注意：因子中的值通常是直接的數值，例如 0.01 代表 1%。bps 需要乘以 10000。
            # 但此處的因子 spread_10y_2y 已經是利差值，例如 -0.005 表示 -0.5% 或 -50 bps。
            # 假設因子值本身就是以百分比的小數形式儲存，例如 0.01 代表 1%。
            # 那麼 0 bps 對應 0.0，25 bps 對應 0.0025。
            # 我們需要確認 FactorStore_Daily 中 spread_10y_2y 的單位。
            # 假設它存儲的是實際的利差值 (如 0.001 for 0.1% or 10bps)。
            # 所以規則中的 bps 需要轉換：0 bps -> 0.0, 25 bps -> 0.0025

            # 為了清晰，我們假設因子值直接是 bps 單位 / 100，即 spread 本身就是百分比的小數形式
            # 例如，如果利差是 10bps，存儲的值是 0.0010
            # 如果利差是 -5bps，存儲的值是 -0.0005
            # 規則的閾值：0 bps -> 0.0; 25 bps -> 0.0025 (即 0.25%)

            # 重新思考：如果因子值是 -0.1 (表示 -0.1% 或 -10 bps), 那與 0 bps (0.0) 和 25 bps (0.0025) 比較時，
            # 應該是 spread_10y_2y_value (單位是百分比的小數形式)
            # < 0.0 (0 bps) -> RED
            # > 0.0025 (25 bps) -> GREEN

            value_in_percent = spread_10y_2y_value # 假設因子值是百分比的小數形式, e.g., 0.01 for 1%
            yc_value = value_in_percent * 100 # 轉換為百分點展示 (e.g., 1.0 for 1%)

            if value_in_percent < 0.0: # 小於 0 bps
                yc_signal = "RED"
                yc_commentary = f"殖利率曲線倒掛 ({value_in_percent*10000:.2f} bps)。衰退風險上升。"
            elif value_in_percent > 0.0025: # 大於 25 bps (0.25%)
                yc_signal = "GREEN"
                yc_commentary = f"殖利率曲線陡峭 ({value_in_percent*10000:.2f} bps)。經濟前景健康。"
            else: # 0 至 25 bps 之間
                yc_signal = "YELLOW"
                yc_commentary = f"殖利率曲線平坦 ({value_in_percent*10000:.2f} bps)。經濟前景中性/需觀察。"
        else:
            print(f"警告 (StrategicAnalyzer): 未能獲取 {indicator_name_yc} 的因子數據 (spread_10y_2y)。")
            # yc_value 已經是 None, yc_commentary 已設預設值

        signals_data.append({
            "date": current_analysis_date,
            "indicator_name": indicator_name_yc,
            "signal": yc_signal,
            "value": yc_value, # 儲存百分點值
            "commentary": yc_commentary
        })

        # --- 市場恐慌指數 (MARKET_VOLATILITY) ---
        indicator_name_vix = "MARKET_VOLATILITY"
        vix_signal = "YELLOW" # 預設信號
        vix_value = None
        vix_commentary = "市場恐慌指數 (VIX) 數據不足或計算失敗。"

        # 讀取 ^VIX 的收盤價
        vix_close_value = self._get_latest_market_price(ticker="^VIX", date_offset=0)
        vix_value = vix_close_value # 儲存原始值

        if vix_close_value is not None:
            # 規則：若 VIX > 30，信號為 RED。若 VIX < 20，信號為 GREEN。其餘為 YELLOW。
            if vix_close_value > 30:
                vix_signal = "RED"
                vix_commentary = f"VIX 指數 ({vix_close_value:.2f}) > 30。市場極度恐慌。"
            elif vix_close_value < 20:
                vix_signal = "GREEN"
                vix_commentary = f"VIX 指數 ({vix_close_value:.2f}) < 20。市場情緒樂觀/自滿。"
            else: # 20 <= VIX <= 30
                vix_signal = "YELLOW"
                vix_commentary = f"VIX 指數 ({vix_close_value:.2f}) 介於 20-30 之間。市場情緒警覺。"
        else:
            print(f"警告 (StrategicAnalyzer): 未能獲取 {indicator_name_vix} 的數據 (^VIX 收盤價)。")
            # vix_value 已經是 None, vix_commentary 已設預設值

        signals_data.append({
            "date": current_analysis_date,
            "indicator_name": indicator_name_vix,
            "signal": vix_signal,
            "value": vix_value,
            "commentary": vix_commentary
        })

        # --- 信用風險偏好 (CREDIT_RISK_APPETITE) ---
        indicator_name_credit = "CREDIT_RISK_APPETITE"
        credit_signal = "YELLOW" # 預設信號
        credit_value = None # 將存儲最新的因子值
        credit_commentary = "信用風險偏好數據不足或計算失敗。"
        ma_period = 20

        # 讀取 credit_spread_proxy (HYG/LQD 價格比率) 的最近 N 期數據 (例如 MA20 需要至少20期)
        # 為了確保有足夠數據計算當日的 MA，我們需要 limit = ma_period
        # _get_factor_series 返回的是按日期升序的 Series
        credit_spread_series = self._get_factor_series(factor_name="HYG_LQD_price_ratio", ticker="CREDIT_SPREAD", limit=ma_period)

        if not credit_spread_series.empty and len(credit_spread_series) >= 1: # 至少要有1期數據才能獲取最新值
            latest_value = credit_spread_series.iloc[-1]
            credit_value = latest_value # 儲存最新因子值以供 dashboard value 欄位使用

            if len(credit_spread_series) >= ma_period:
                # 計算 20 日移動平均線
                # rolling(window=ma_period) 創建一個滾動窗口
                # .mean() 計算窗口內的平均值
                # .iloc[-1] 獲取序列中最後一個 MA 值，即對應最新數據點的 MA
                ma_20 = credit_spread_series.rolling(window=ma_period).mean().iloc[-1]

                if pd.notna(latest_value) and pd.notna(ma_20):
                    # 規則：若該比率低於其 20 日移動平均線，信號為 RED。若高於，則為 GREEN。
                    if latest_value < ma_20:
                        credit_signal = "RED"
                        credit_commentary = f"信用利差代理 ({latest_value:.4f}) 低於其 {ma_period}日均線 ({ma_20:.4f})。避險情緒升溫。"
                    else: # 等於或高於
                        credit_signal = "GREEN"
                        credit_commentary = f"信用利差代理 ({latest_value:.4f}) 高於或等於其 {ma_period}日均線 ({ma_20:.4f})。風險偏好良好。"
                else:
                    credit_commentary = f"信用風險偏好數據 (值: {latest_value:.4f}, MA({ma_period}): {ma_20:.4f}) 不足以計算信號 (可能包含NaN)。"
                    print(f"警告 (StrategicAnalyzer): {indicator_name_credit} 的最新值或MA({ma_period})為NaN。")
            else:
                credit_commentary = f"信用風險偏好數據不足 {ma_period} 日，無法計算 {ma_period}日均線。"
                print(f"警告 (StrategicAnalyzer): {indicator_name_credit} 的數據點 ({len(credit_spread_series)}) 不足 {ma_period} 個，無法計算移動平均。")
        else:
            print(f"警告 (StrategicAnalyzer): 未能獲取 {indicator_name_credit} 的因子數據 (HYG_LQD_price_ratio)。")
            # credit_value 已經是 None, credit_commentary 已設預設值

        signals_data.append({
            "date": current_analysis_date,
            "indicator_name": indicator_name_credit,
            "signal": credit_signal,
            "value": credit_value, # 儲存最新的原始因子值
            "commentary": credit_commentary
        })

        if not signals_data:
            print("警告 (StrategicAnalyzer): 未能生成任何信號數據。")
            return pd.DataFrame(columns=['date', 'indicator_name', 'signal', 'value', 'commentary'])

        signals_df = pd.DataFrame(signals_data)
        return signals_df


if __name__ == '__main__':
    # 此處可以添加一些用於測試 StrategicAnalyzer 的代碼
    # 例如:
    # from apps.daily_market_analyzer.db_manager import DBManager # 假設 DBManager 可用
    # db_path = "../../data_workspace/market_data.duckdb" # 調整為實際路徑
    # db_manager_instance = DBManager(db_path)
    # analyzer = StrategicAnalyzer(db_manager_instance)
    print("戰略分析器 (StrategicAnalyzer) 核心類別已定義。")
