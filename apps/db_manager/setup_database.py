# apps/db_manager/setup_database.py
from pathlib import Path

import duckdb

# --- 資料庫檔案設定 ---
# 根據【核心架構原則】，所有腳本應具備路徑獨立性。
# 此處假設 poetry run 將從專案根目錄執行此腳本。
DB_FILENAME = "prometheus_fire.duckdb"
DB_PATH = Path(DB_FILENAME)

# --- SQL 指令：定義 `hourly_time_series` 表格結構 ---
# 使用 IF NOT EXISTS 確保此腳本可以重複安全執行，不會因表格已存在而報錯。
CREATE_HOURLY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS hourly_time_series (
    -- 主鍵
    "timestamp" TIMESTAMP PRIMARY KEY,

    -- A. 基礎價格數據 (Basic Price Data)
    spy_open DOUBLE,
    spy_high DOUBLE,
    spy_low DOUBLE,
    spy_close DOUBLE,
    spy_volume BIGINT,
    qqq_close DOUBLE,
    tlt_close DOUBLE,
    btc_usd_close DOUBLE,
    nq_f_close DOUBLE,
    es_f_close DOUBLE,
    ym_f_close DOUBLE,
    cl_f_close DOUBLE,
    gc_f_close DOUBLE,
    si_f_close DOUBLE,
    zb_f_close DOUBLE,
    zn_f_close DOUBLE,
    zt_f_close DOUBLE,
    zf_f_close DOUBLE,
    gld_close DOUBLE,
    shy_close DOUBLE,
    iei_close DOUBLE,
    aapl_close DOUBLE,
    msft_close DOUBLE,
    nvda_close DOUBLE,
    goog_close DOUBLE,
    tsm_close DOUBLE,
    "601318_ss_close" DOUBLE,
    "688981_ss_close" DOUBLE,
    "0981_hk_close" DOUBLE,

    -- B. 核心技術指標 (Core Technical Indicators)
    spy_rsi_14_1h DOUBLE,
    spy_macd_signal_1h DOUBLE,
    spy_bbands_width_pct_1h DOUBLE,
    spy_vwap_1h DOUBLE,
    spy_atr_14_1h DOUBLE,
    spy_vwap_deviation_pct_1h DOUBLE,
    spy_momentum_1h_100 DOUBLE,
    spy_bollinger_band_upper_1h DOUBLE,
    spy_bollinger_band_lower_1h DOUBLE,
    spy_bb_middle_band_20h DOUBLE,
    spy_bb_upper_band_20h DOUBLE,
    spy_bb_lower_band_20h DOUBLE,
    spy_bb_band_width_pct_20h DOUBLE,
    spy_bb_percent_b_20h DOUBLE,

    -- C. 選擇權衍生數據 (Options-Derived Data)
    spy_gex_total DOUBLE,
    spy_gex_flip_level DOUBLE,
    spy_max_pain DOUBLE,
    spy_call_wall_strike DOUBLE,
    spy_put_wall_strike DOUBLE,
    spy_pc_ratio_volume DOUBLE,
    spy_pc_ratio_oi DOUBLE,
    spy_iv_atm_1m DOUBLE,
    spy_skew_quantified DOUBLE,
    spy_vanna_exposure DOUBLE,
    spy_charm_exposure DOUBLE,
    vvix_close DOUBLE
);
"""

# --- SQL 指令：為表格添加註解 ---
COMMENT_ON_TABLE_SQL = """
COMMENT ON TABLE hourly_time_series IS '儲存【普羅米修斯之火】專案所需的小時級別金融時間序列數據。'
'模板化指標欄位 (如 [商品代號]_obv_1h) 將在後續計畫中根據具體需求擴充。';
"""


def setup_database():
    """
    主函數：連接到 DuckDB 並建立 hourly_time_series 表格。
    """
    print(f"--- [階段 1] 準備建立資料庫於: {DB_PATH.resolve()} ---")
    con = None
    try:
        # 連接到資料庫檔案，如果不存在將會自動創建
        con = duckdb.connect(database=str(DB_PATH), read_only=False)
        print("--- [階段 2] 資料庫連接成功。正在執行 Schema 建立指令... ---")

        # 執行 SQL 建立表格
        con.execute(CREATE_HOURLY_TABLE_SQL)
        print("✔ 表格 'hourly_time_series' 已成功建立 (或已存在)。")

        # 執行 SQL 添加註解
        con.sql(COMMENT_ON_TABLE_SQL)
        print("✔ 表格註解已成功添加。")

        print("--- [階段 3] 驗證表格結構 ---")
        result = con.execute("PRAGMA table_info('hourly_time_series');").fetchall()
        print(f"✔ 驗證成功！表格 'hourly_time_series' 當前包含 {len(result)} 個欄位。")

    except Exception as e:
        print(f"❌ 建立資料庫時發生嚴重錯誤: {e}")
    finally:
        if con:
            con.close()
            print("--- [完成] 資料庫連接已關閉。---")


if __name__ == "__main__":
    setup_database()
