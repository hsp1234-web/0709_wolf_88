# -*- coding: utf-8 -*-
"""
普羅米修斯之火 - 因子提取、轉換、加載 (ETL) 主執行腳本
"""

import sys
from pathlib import Path

import pandas as pd

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parents[
        2
    ]  # apps/factor_engine/run_factor_etl.py -> project_root
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    project_root = Path.cwd()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
# --- 標準化「路徑自我校正」樣板碼 END ---


def run_etl(log_manager):
    from apps.daily_market_analyzer.db_manager import DBManager
    from apps.factor_engine.engine import FactorEngine

    """
    執行完整的因子提取、計算和儲存流程。
    """
    log_manager.log("INFO", "開始執行因子 ETL 流程...")

    # 假設資料庫檔案位於 data_workspace/market_data.duckdb
    # TODO: 應該從統一的配置文件中讀取數據庫路徑
    db_file_path = project_root / "data_workspace" / "market_data.duckdb"
    log_manager.log("INFO", f"因子 ETL 使用的資料庫路徑: {db_file_path}")
    db_manager = DBManager(db_path=str(db_file_path))
    factor_engine = FactorEngine(
        db_manager=db_manager, log_manager=log_manager
    )  # 傳遞 log_manager

    # 1. 從 MarketPrices_Daily 表中獲取所有不重複的 ticker
    log_manager.log("INFO", "正在從 MarketPrices_Daily 獲取所有 tickers...")
    try:
        tickers_df = db_manager.execute_query(
            "SELECT DISTINCT ticker FROM MarketPrices_Daily"
        )
        if tickers_df.empty:
            log_manager.log(
                "WARNING",
                "MarketPrices_Daily 中沒有找到任何 ticker。因子 ETL 流程終止。",
            )
            return
        tickers_list = tickers_df["ticker"].tolist()
        log_manager.log("INFO", f"共找到 {len(tickers_list)} 個 tickers。")
    except Exception as e:
        log_manager.log("ERROR", f"無法從 MarketPrices_Daily 獲取 tickers: {e}")
        return

    all_factors_to_store = []

    for ticker_index, ticker in enumerate(tickers_list):
        log_manager.log(
            "INFO", f"正在處理 ticker {ticker_index + 1}/{len(tickers_list)}: {ticker}"
        )

        # 2a. 使用 FactorEngine 讀取其價格歷史
        price_data_df = factor_engine.get_prices_for_ticker(ticker)

        if price_data_df.empty:
            log_manager.log("WARNING", f"未能獲取 {ticker} 的價格數據，跳過此 ticker。")
            continue

        # 確保索引名為 'datetime'，方便後續轉換
        if price_data_df.index.name != "datetime":
            price_data_df.index.name = "datetime"

        # 2b. 計算因子
        hv_20d = factor_engine.calculate_price_volatility(
            price_data_df.copy(), n_days=20
        )
        volume_hv_20d = factor_engine.calculate_volume_volatility(
            price_data_df.copy(), n_days=20
        )
        rsi_14 = factor_engine.calculate_rsi(price_data_df.copy(), n_days=14)

        # 2c. 將結果整理成符合 FactorStore_Daily 結構的 DataFrame
        factors_for_current_ticker = []

        if hv_20d is not None and not hv_20d.empty:
            hv_df = hv_20d.reset_index()
            hv_df.columns = ["date", "factor_value"]
            hv_df["ticker"] = ticker
            hv_df["factor_name"] = "hv_20d"
            hv_df["date"] = pd.to_datetime(hv_df["date"]).dt.date
            factors_for_current_ticker.append(hv_df.dropna())

        if volume_hv_20d is not None and not volume_hv_20d.empty:
            vol_hv_df = volume_hv_20d.reset_index()
            vol_hv_df.columns = ["date", "factor_value"]
            vol_hv_df["ticker"] = ticker
            vol_hv_df["factor_name"] = "volume_hv_20d"
            vol_hv_df["date"] = pd.to_datetime(vol_hv_df["date"]).dt.date
            factors_for_current_ticker.append(vol_hv_df.dropna())

        if rsi_14 is not None and not rsi_14.empty:
            rsi_df = rsi_14.reset_index()
            rsi_df.columns = ["date", "factor_value"]
            rsi_df["ticker"] = ticker
            rsi_df["factor_name"] = "rsi_14d"
            rsi_df["date"] = pd.to_datetime(rsi_df["date"]).dt.date
            factors_for_current_ticker.append(rsi_df.dropna())

        if factors_for_current_ticker:
            current_ticker_factors_df = pd.concat(
                factors_for_current_ticker, ignore_index=True
            )
            all_factors_to_store.append(current_ticker_factors_df)
            log_manager.log(
                "INFO",
                f"為 {ticker} 計算並準備了 "
                f"{len(current_ticker_factors_df)} 筆因子數據。",
            )
        else:
            log_manager.log("INFO", f"未能為 {ticker} 計算出任何因子數據。")

    # 3. 計算殖利率曲線因子
    log_manager.log("INFO", "開始計算殖利率曲線相關因子...")
    treasury_yields_data = factor_engine.get_treasury_yields()
    if not treasury_yields_data.empty:
        yield_spread_factors = factor_engine.calculate_yield_spreads(
            treasury_yields_data
        )
        if not yield_spread_factors.empty:
            yield_spread_factors_long = yield_spread_factors.reset_index().melt(
                id_vars="date", var_name="factor_name", value_name="factor_value"
            )
            yield_spread_factors_long["ticker"] = "US_TREASURY"
            yield_spread_factors_long["date"] = pd.to_datetime(
                yield_spread_factors_long["date"]
            ).dt.date
            all_factors_to_store.append(yield_spread_factors_long.dropna())
            log_manager.log(
                "INFO",
                f"計算並準備了 {len(yield_spread_factors_long)} 筆殖利率曲線因子數據。",
            )
        else:
            log_manager.log("INFO", "未能計算出殖利率曲線因子數據。")
    else:
        log_manager.log("INFO", "未能獲取公債殖利率數據，跳過殖利率曲線因子計算。")

    # 4. 計算信用利差代理因子
    log_manager.log("INFO", "開始計算信用利差代理因子...")
    credit_spread_proxy_factor = factor_engine.calculate_credit_spread_proxy()
    if not credit_spread_proxy_factor.empty:
        credit_spread_proxy_long = credit_spread_proxy_factor.reset_index()
        credit_spread_proxy_long.rename(
            columns={"HYG_LQD_price_ratio": "factor_value"}, inplace=True
        )
        credit_spread_proxy_long["factor_name"] = "HYG_LQD_price_ratio"
        credit_spread_proxy_long["ticker"] = "CREDIT_SPREAD"
        credit_spread_proxy_long["date"] = pd.to_datetime(
            credit_spread_proxy_long["date"]
        ).dt.date
        all_factors_to_store.append(credit_spread_proxy_long.dropna())
        log_manager.log(
            "INFO",
            f"計算並準備了 {len(credit_spread_proxy_long)} 筆信用利差代理因子數據。",
        )
    else:
        log_manager.log("INFO", "未能計算出信用利差代理因子數據。")

    # 5. 合併所有因子數據並存入資料庫
    if all_factors_to_store:
        final_factors_df = pd.concat(all_factors_to_store, ignore_index=True)
        if not final_factors_df.empty:
            log_manager.log(
                "INFO",
                f"ETL 流程總共計算出 {len(final_factors_df)} 筆因子數據，"
                "準備寫入資料庫...",
            )
            db_manager.insert_factors(final_factors_df)
            log_manager.log("INFO", "所有因子數據已成功寫入 FactorStore_Daily。")
        else:
            log_manager.log("INFO", "ETL 流程最終未產生任何可儲存的因子數據。")
    else:
        log_manager.log("INFO", "ETL 流程未產生任何可儲存的因子數據。")

    log_manager.log("INFO", "因子 ETL 流程執行完畢。")


if __name__ == "__main__":
    from core.logger import LogManager

    output_dir = project_root / "output"
    log_db_path = output_dir / "logs" / "standalone_test.sqlite"
    archive_dir = output_dir / "logs" / "archive"

    dummy_logger = LogManager(db_path=log_db_path, archive_dir=archive_dir)
    dummy_logger.log("INFO", "直接執行 run_factor_etl.py 腳本...")
    run_etl(log_manager=dummy_logger)
    dummy_logger.archive_to_file()
