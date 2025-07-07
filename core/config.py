# config.py
import os
from pathlib import Path
import logging # 為了 LOG_LEVEL

# --- 基本路徑設定 ---
# __file__ 是目前檔案 (core/config.py) 的路徑
# .parent 會得到 core/
# .parent.parent 會得到專案的根目錄
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- 目標標的 ---
# 注意：yfinance 對於台股，通常需要在股票代號後加上 ".TW"
# FinMind API 使用的股票代號則不需要後綴 (例如 "2330")
# 主控腳本在調用各客戶端時需要注意此差異，或在此處統一處理。
# 為簡單起見，這裡先使用 yfinance 格式，FinMind 調用時需去除 .TW。
# 或者，可以維護一個更複雜的字典結構，例如：
# TARGETS = [
#     {'yfinance_id': '2330.TW', 'finmind_id': '2330', 'name': 'TSMC'},
#     {'yfinance_id': '2317.TW', 'finmind_id': '2317', 'name': 'Foxconn'},
# ]
# 目前先用簡單列表：
# TARGET_STOCK_IDS_YFINANCE = ['2330.TW', '2317.TW', '2454.TW', '0050.TW'] # yfinance 使用的ID
# TARGET_STOCK_IDS_FINMIND = [sid.replace('.TW', '') for sid in TARGET_STOCK_IDS_YFINANCE] # FinMind 使用的ID

# 全新的、統一的 TARGETS 列表
TARGETS = [
    {'id': '2330', 'yfinance_id': '2330.TW', 'name': '台積電'},
    {'id': '2317', 'yfinance_id': '2317.TW', 'name': '鴻海'},
    {'id': '2454', 'yfinance_id': '2454.TW', 'name': '聯發科'},
    {'id': '0050', 'yfinance_id': '0050.TW', 'name': '元大台灣50'},
]

# --- 資料庫路徑 ---
# 所有的分析結果和基礎數據都將存儲在這個 DuckDB 檔案中
ANALYTICS_DB_NAME = "analytics_mart.duckdb"
_default_analytics_db_path = str(PROJECT_ROOT / ANALYTICS_DB_NAME)
ANALYTICS_DB_PATH = os.getenv("KRONOS_ANALYTICS_DB_PATH", _default_analytics_db_path)

# --- 源 Tick 資料庫路徑 ---
# Time Aggregator 將從此資料庫讀取原始 Tick 數據
SOURCE_TICKS_DB_NAME = "taifex_ticks.duckdb"  # 建議的源資料庫名稱
_default_source_ticks_db_path = str(PROJECT_ROOT / SOURCE_TICKS_DB_NAME)
SOURCE_TICKS_DB_PATH = os.getenv("KRONOS_SOURCE_TICKS_DB_PATH", _default_source_ticks_db_path)

# --- 報告輸出目錄 ---
REPORTS_OUTPUT_DIR_NAME = "output_reports" # 修改目錄名以更清晰
_default_reports_output_dir = str(PROJECT_ROOT / REPORTS_OUTPUT_DIR_NAME)
REPORTS_OUTPUT_DIR = os.getenv("KRONOS_REPORTS_OUTPUT_DIR", _default_reports_output_dir)

# --- 日誌級別 ---
# 可選值: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

# --- API Tokens ---
# FinMind API Token (用於法人籌碼數據)
# 強烈建議從環境變數讀取，不要硬編碼在程式碼中
FINMIND_API_TOKEN = os.getenv("FINMIND_API_TOKEN")
# 如果需要 FMP (Financial Modeling Prep) API Token
# FMP_API_TOKEN = os.getenv("FMP_API_TOKEN")


# --- 各微應用 run.py 的相對路徑 (相對於專案根目錄) ---
# 這些是預設路徑，如果您的結構不同，可以在此修改
# 或者在主控腳本中動態構建
YFINANCE_CLIENT_RUN_PATH = str(PROJECT_ROOT / "apps" / "yfinance_client" / "run.py")
INSTITUTIONAL_ANALYZER_RUN_PATH = str(PROJECT_ROOT / "apps" / "institutional_analyzer" / "run.py")
FEATURE_ANALYZER_RUN_PATH = str(PROJECT_ROOT / "apps" / "feature_analyzer" / "run.py")
REPORT_GENERATOR_RUN_PATH = str(PROJECT_ROOT / "apps" / "report_generator" / "run.py")
TIME_AGGREGATOR_RUN_PATH = str(PROJECT_ROOT / "apps" / "time_aggregator" / "run.py") # 新增時間聚合器路徑

# --- 數據更新與分析的時間範圍參數 ---
# 這些可以根據需求調整
# yfinance OHLCV 數據獲取起始日期 (例如，獲取過去5年的數據)
YFINANCE_START_DATE_OFFSET_YEARS = 5

# 法人籌碼數據獲取起始日期 (例如，獲取過去1年的數據)
# FinMind API 對歷史數據範圍可能有免費版限制
INSTITUTIONAL_START_DATE_OFFSET_MONTHS = 12

# 特徵分析 (Chimera) 的股票ID列表 (通常與 TARGET_STOCK_IDS_YFINANCE 一致)
CHIMERA_ANALYSIS_STOCK_IDS = [target['yfinance_id'] for target in TARGETS] # 更新以使用新的 TARGETS 結構

# 報告生成的時間範圍 (例如，生成最近3個月的報告)
REPORT_START_DATE_OFFSET_MONTHS = 3

# --- 其他配置 ---
# 例如，subprocess 調用的超時時間 (秒)
SUBPROCESS_TIMEOUT = 300 # 5 分鐘

# 確保報告輸出目錄存在 (主控腳本也會檢查，但這裡也可以先定義)
# Path(REPORTS_OUTPUT_DIR).mkdir(parents=True, exist_ok=True) # 移到主控腳本中執行

if __name__ == '__main__':
    # 打印配置以供檢查 (當直接運行此檔案時)
    print(f"專案根目錄: {PROJECT_ROOT}")
    # print(f"目標股票 (yfinance): {TARGET_STOCK_IDS_YFINANCE}") # 已廢除
    # print(f"目標股票 (FinMind): {TARGET_STOCK_IDS_FINMIND}") # 已廢除
    print(f"統一目標列表 (TARGETS):")
    for target_info in TARGETS:
        print(f"  - {target_info}")
    print(f"分析資料庫路徑: {ANALYTICS_DB_PATH}")
    print(f"報告輸出目錄: {REPORTS_OUTPUT_DIR}")
    print(f"日誌級別: {LOG_LEVEL_STR} ({LOG_LEVEL})")
    print(f"FinMind API Token (是否已設定): {'是' if FINMIND_API_TOKEN else '否'}")

    print(f"\nYFinance Client Run Path: {YFINANCE_CLIENT_RUN_PATH}")
    print(f"Institutional Analyzer Run Path: {INSTITUTIONAL_ANALYZER_RUN_PATH}")
    print(f"Feature Analyzer Run Path: {FEATURE_ANALYZER_RUN_PATH}")
    print(f"Report Generator Run Path: {REPORT_GENERATOR_RUN_PATH}")

    print(f"\nYFinance Start Date Offset (Years): {YFINANCE_START_DATE_OFFSET_YEARS}")
    print(f"Institutional Data Start Date Offset (Months): {INSTITUTIONAL_START_DATE_OFFSET_MONTHS}")
    print(f"Report Start Date Offset (Months): {REPORT_START_DATE_OFFSET_MONTHS}")
    print(f"Subprocess Timeout: {SUBPROCESS_TIMEOUT} seconds")
