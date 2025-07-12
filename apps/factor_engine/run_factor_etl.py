# -*- coding: utf-8 -*-
"""
普羅米修斯之火 - 因子提取、轉換、加載 (ETL) 主執行腳本
"""

import os  # 用於數據庫路徑

# 為了能夠直接執行此腳本，需要確保 apps 目錄在 Python 的搜索路徑中
# 這通常通過設置 PYTHONPATH 或在專案根目錄執行來實現
# 例如: PYTHONPATH=. python apps/factor_engine/run_factor_etl.py
# 或者，如果你的 IDE 或執行環境正確設置了根目錄，則可能不需要額外操作。
# 臨時添加專案根目錄到 sys.path，以便於直接執行
import sys

import pandas as pd

project_root_for_direct_run = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if project_root_for_direct_run not in sys.path:
    sys.path.insert(0, project_root_for_direct_run)
    # 暫時使用 print，因為 logger 還未初始化
    print(
        f"DEBUG (run_factor_etl.py direct run): "
        f"已將專案根目錄 {project_root_for_direct_run} 添加到 sys.path"
    )

from core.logger import get_logger  # noqa: E402

logger = get_logger(__name__)


def run_etl():
    from apps.daily_market_analyzer.db_manager import (
        DBManager,  # noqa: E402, 假設此模組路徑在 sys.path 更新後有效
    )
    from apps.factor_engine.engine import (
        FactorEngine,  # noqa: E402, 假設此模組路徑在 sys.path 更新後有效
    )
    """
    執行完整的因子提取、計算和儲存流程。
    """
    logger.info("開始執行因子 ETL 流程...")

    # 假設資料庫檔案位於 data_workspace/market_data.duckdb
    # TODO: 應該從統一的配置文件中讀取數據庫路徑
    db_file_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "data_workspace", "market_data.duckdb"
    )
    logger.info(f"因子 ETL 使用的資料庫路徑: {db_file_path}")
    db_manager = DBManager(db_path=db_file_path)
    factor_engine = FactorEngine(db_manager=db_manager)

    # 1. 從 MarketPrices_Daily 表中獲取所有不重複的 ticker
    logger.info("正在從 MarketPrices_Daily 獲取所有 tickers...")
    try:
        tickers_df = db_manager.execute_query(
            "SELECT DISTINCT ticker FROM MarketPrices_Daily"
        )
        if tickers_df.empty:
            logger.warning(
                "MarketPrices_Daily 中沒有找到任何 ticker。因子 ETL 流程終止。"
            )
            return
        tickers_list = tickers_df["ticker"].tolist()
        logger.info(f"共找到 {len(tickers_list)} 個 tickers。")
    except Exception as e:
        logger.error(f"無法從 MarketPrices_Daily 獲取 tickers: {e}", exc_info=True)
        return

    all_factors_to_store = []

    for ticker_index, ticker in enumerate(tickers_list):
        logger.info(f"正在處理 ticker {ticker_index + 1}/{len(tickers_list)}: {ticker}")

        # 2a. 使用 FactorEngine 讀取其價格歷史
        price_data_df = factor_engine.get_prices_for_ticker(ticker)

        if price_data_df.empty:
            logger.warning(f"未能獲取 {ticker} 的價格數據，跳過此 ticker。")
            continue

        # 確保索引名為 'datetime'，方便後續轉換
        if price_data_df.index.name != "datetime":
            price_data_df.index.name = "datetime"

        # 2b. 計算因子
        # 價格波動率 (hv_20d)
        hv_20d = factor_engine.calculate_price_volatility(
            price_data_df.copy(), n_days=20
        )  # 使用 .copy() 避免 SettingWithCopyWarning
        # 成交量波動率 (volume_hv_20d)
        volume_hv_20d = factor_engine.calculate_volume_volatility(
            price_data_df.copy(), n_days=20
        )
        # RSI (rsi_14)
        rsi_14 = factor_engine.calculate_rsi(price_data_df.copy(), n_days=14)

        # 2c. 將結果整理成符合 FactorStore_Daily 結構的 DataFrame
        factors_for_current_ticker = []

        # 處理 hv_20d
        if hv_20d is not None and not hv_20d.empty:
            hv_df = hv_20d.reset_index()  # datetime 索引變為欄位
            hv_df.columns = ["date", "factor_value"]
            hv_df["ticker"] = ticker
            hv_df["factor_name"] = "hv_20d"
            # 轉換 date 為 YYYY-MM-DD 格式的字串，如果它是 datetime 物件
            hv_df["date"] = pd.to_datetime(hv_df["date"]).dt.date
            factors_for_current_ticker.append(
                hv_df[["ticker", "date", "factor_name", "factor_value"]].dropna()
            )

        # 處理 volume_hv_20d
        if volume_hv_20d is not None and not volume_hv_20d.empty:
            vol_hv_df = volume_hv_20d.reset_index()
            vol_hv_df.columns = ["date", "factor_value"]
            vol_hv_df["ticker"] = ticker
            vol_hv_df["factor_name"] = "volume_hv_20d"
            vol_hv_df["date"] = pd.to_datetime(vol_hv_df["date"]).dt.date
            factors_for_current_ticker.append(
                vol_hv_df[["ticker", "date", "factor_name", "factor_value"]].dropna()
            )

        # 處理 rsi_14
        if rsi_14 is not None and not rsi_14.empty:
            rsi_df = rsi_14.reset_index()
            rsi_df.columns = ["date", "factor_value"]
            rsi_df["ticker"] = ticker
            rsi_df["factor_name"] = (
                "rsi_14d"  # 保持與 pandas-ta 輸出一致性，或統一為 rsi_14
            )
            rsi_df["date"] = pd.to_datetime(rsi_df["date"]).dt.date
            factors_for_current_ticker.append(
                rsi_df[["ticker", "date", "factor_name", "factor_value"]].dropna()
            )

        if factors_for_current_ticker:
            current_ticker_factors_df = pd.concat(
                factors_for_current_ticker, ignore_index=True
            )
            all_factors_to_store.append(current_ticker_factors_df)
            logger.info(
                f"為 {ticker} 計算並準備了 "
                f"{len(current_ticker_factors_df)} 筆因子數據。"
            )
        else:
            logger.info(f"未能為 {ticker} 計算出任何因子數據。")

    # Ticker 相關因子已收集在 all_factors_to_store (list of DataFrames)

    # 3. 計算殖利率曲線因子
    logger.info("開始計算殖利率曲線相關因子...")
    treasury_yields_data = factor_engine.get_treasury_yields()
    if not treasury_yields_data.empty:
        yield_spread_factors = factor_engine.calculate_yield_spreads(
            treasury_yields_data
        )
        if not yield_spread_factors.empty:
            # 將寬表格式 (date 為索引, 各利差為欄位) 的殖利率因子轉換為長表格式，以符合
            # FactorStore_Daily 的 (ticker, date, factor_name, factor_value) 結構。
            yield_spread_factors_long = yield_spread_factors.reset_index().melt(
                id_vars="date",  # 將 'date' 索引轉換為欄位，並作為融合時的ID變數
                var_name="factor_name",  # 其餘欄位名 (如 'spread_10y_2y')
                # 變為 'factor_name' 欄的值
                value_name="factor_value",
            )
            yield_spread_factors_long["ticker"] = "US_TREASURY"  # 特殊 ticker 名稱
            yield_spread_factors_long["date"] = pd.to_datetime(
                yield_spread_factors_long["date"]
            ).dt.date
            yield_spread_factors_long = yield_spread_factors_long[
                ["ticker", "date", "factor_name", "factor_value"]
            ].dropna()
            all_factors_to_store.append(yield_spread_factors_long)
            logger.info(
                f"計算並準備了 {len(yield_spread_factors_long)} 筆殖利率曲線因子數據。"
            )
        else:
            logger.info("未能計算出殖利率曲線因子數據。")
    else:
        logger.info("未能獲取公債殖利率數據，跳過殖利率曲線因子計算。")

    # 4. 計算信用利差代理因子
    logger.info("開始計算信用利差代理因子...")
    credit_spread_proxy_factor = factor_engine.calculate_credit_spread_proxy()
    if not credit_spread_proxy_factor.empty:
        # credit_spread_proxy_factor DataFrame 結構: date (索引), HYG_LQD_price_ratio (欄位)
        # 將其轉換為 FactorStore_Daily 的長表格式。
        credit_spread_proxy_long = (
            credit_spread_proxy_factor.reset_index()
        )  # date 索引變為 'date' 欄
        # 此時欄位為 ['date', 'HYG_LQD_price_ratio']
        credit_spread_proxy_long.rename(
            columns={"HYG_LQD_price_ratio": "factor_value"}, inplace=True
        )
        credit_spread_proxy_long["factor_name"] = (
            "HYG_LQD_price_ratio"  # 設定固定的因子名稱
        )
        credit_spread_proxy_long["ticker"] = "CREDIT_SPREAD"  # 特殊 ticker 名稱
        credit_spread_proxy_long["date"] = pd.to_datetime(
            credit_spread_proxy_long["date"]
        ).dt.date
        # 確保欄位順序符合 FactorStore_Daily 並移除空值
        credit_spread_proxy_long = credit_spread_proxy_long[
            ["ticker", "date", "factor_name", "factor_value"]
        ].dropna()
        all_factors_to_store.append(credit_spread_proxy_long)
        logger.info(
            f"計算並準備了 {len(credit_spread_proxy_long)} 筆信用利差代理因子數據。"
        )
    else:
        logger.info("未能計算出信用利差代理因子數據。")

    # 5. 合併所有因子數據並存入資料庫
    if (
        all_factors_to_store
    ):  # 此時 all_factors_to_store 包含之前 ticker 因子 (如果有的話) 和新計算的宏觀因子
        # 重新合併，因為之前 ticker_factors_df 可能未加入 all_factors_to_store
        # 或者，應該在 ticker 循環後就將 ticker_factors_df 加入 all_factors_to_store
        # 修正：all_factors_to_store 在 ticker 循環中已經收集了數據
        # 所以這裡直接用 all_factors_to_store 即可

        final_factors_df = pd.concat(all_factors_to_store, ignore_index=True)
        if not final_factors_df.empty:
            logger.info(
                f"ETL 流程總共計算出 {len(final_factors_df)} 筆因子數據，準備寫入資料庫..."
            )
            db_manager.insert_factors(final_factors_df)
            logger.info("所有因子數據已成功寫入 FactorStore_Daily。")
        else:
            logger.info("ETL 流程最終未產生任何可儲存的因子數據。")
    else:
        # 這個情況應該是 ticker 因子和宏觀因子都沒有產生
        logger.info("ETL 流程未產生任何可儲存的因子數據。")

    logger.info("因子 ETL 流程執行完畢。")


if __name__ == "__main__":
    # 在此處，logger 應該已經由頂部的 get_logger(__name__) 初始化
    logger.info("直接執行 run_factor_etl.py 腳本...")
    # sys.path 的修改已在檔案頂部完成
    run_etl()
