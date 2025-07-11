# apps/analysis_pipeline/run.py
import argparse
import sys
import os
from pathlib import Path

# --- 標準化「路徑自我校正」樣板碼 START ---
# 注意：這部分的路徑校正邏輯現在將使用 logger
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent.parent.parent
    # 核心日誌模組應在 sys.path 更新後導入，以確保能找到 core.logger
    # 但為了記錄路徑校正本身，我們暫時在這裡實例化一個臨時的 logger 或延遲 logger 的使用
except NameError:
    project_root = Path(os.getcwd()).resolve()
except Exception as e:
    # 如果連 project_root 都無法確定，日誌記錄會比較困難
    print(
        f"緊急錯誤: 在確定專案根目錄時發生初始錯誤 (apps/analysis_pipeline/run.py): {e}", file=sys.stderr
    )
    project_root = Path(".").resolve() # 備用，可能不準確

# 在 sys.path 更新後導入核心 logger
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.logger import get_logger
logger = get_logger(__name__)

# 現在記錄路徑校正的結果
try:
    # 重新獲取（或確認）路徑，這次是為了日誌記錄
    current_script_path_for_log = Path(__file__).resolve()
    project_root_for_log = current_script_path_for_log.parent.parent.parent
    if project_root_for_log != project_root : # 校驗一下之前的確定是否一致
         logger.warning(f"路徑校正過程中，project_root 的前後確定值不一致。初始: {project_root}, 日誌階段: {project_root_for_log}")
    logger.info(f"已將專案根目錄 {project_root_for_log} 添加到 sys.path (如果尚未存在)")
except NameError:
    # project_root 在上面 NameError 時已設定
    logger.warning(f"__file__ 未定義，專案路徑校正可能不準確。已將 {project_root} 加入 sys.path。")
except Exception as e:
    logger.error(f"專案路徑校正時發生錯誤: {e}")
# --- 標準化「路徑自我校正」樣板碼 END ---


# 統一的 DBManager 和分析器導入
# from apps.daily_market_analyzer.db_manager import DBManager # 暫時註解，模組不存在
# from apps.daily_market_analyzer.analysis_engine import AnalysisEngine as DailyMarketAnalysisEngine # 暫時註解，模組不存在
 # from apps.feature_analyzer.analyzer import ChimeraAnalyzer, LegacyQuadrantAnalyzer # 暫時註解，模組不存在
 # from apps.institutional_analyzer.analyzer import InstitutionalAnalyzer # 暫時註解，模組不存在
# from apps.strategic_analyzer.analyzer import StrategicAnalyzer # 暫時註解，模組不存在

# feature_analyzer 的 TIME_PERIODS 可能需要在此處定義或從其他地方導入
TIME_PERIODS_FOR_LEGACY_QUADRANT = {
    "1min": "1T", "5min": "5T", "15min": "15T",
    "1h": "1H", "4h": "4H", "1d": "1D",
}

def main():
    parser = argparse.ArgumentParser(description="統一分析管線執行器")
    # parser.add_argument(
        # "--analyzer",
        # required=True,
        # choices=[
            # # "daily_market", # 暫時移除，模組不存在
            # # "chimera_composite", # 暫時移除，模組不存在
            # # "chimera_pc_ratio", # 暫時移除，模組不存在
            # # "legacy_quadrant", # 暫時移除，模組不存在
            # "institutional", # 暫時移除，模組不存在
            # # "strategic", # 暫時移除，模組不存在
        # ],
        # help="要執行的分析器名稱 (部分分析器因模組缺失已暫時移除)",
    # )
    # 通用參數 (許多分析器可能需要這些)
    parser.add_argument("--db_path", default=str(project_root / "data_workspace" / "market_data.duckdb"), help="主資料庫路徑 (例如 market_data.duckdb)")
    parser.add_argument("--analytics_mart_db", default=str(project_root / "analytics_mart.duckdb"), help="分析結果資料庫路徑 (例如 analytics_mart.duckdb)")
    parser.add_argument("--legacy_quadrant_db", default=str(project_root / "data" / "analytics_mart.duckdb"), help="舊版四象限分析的資料庫路徑")

    parser.add_argument("--start_date", help="分析開始日期 (YYYY-MM-DD)")
    parser.add_argument("--end_date", help="分析結束日期 (YYYY-MM-DD)")
    parser.add_argument("--stock_ids", nargs="+", help="股票代碼列表 (例如 2330 TSM)") # nargs='+' 表示一個或多個
    parser.add_argument("--tickers", help="用於 daily_market_analyzer 的股票代碼列表，以逗號分隔")


    # daily_market_analyzer 特定參數 (這些是其原始 run.py 中的一部分)
    parser.add_argument("--dma_table_name", default="market_ohlcv_data", help="DailyMarketAnalyzer 的 OHLCV 資料表名稱")
    # 更多 DMA 參數可以按需添加，例如 force_refresh, no_data_cooldown_days 等。

    # institutional_analyzer 特定參數
    parser.add_argument("--finmind_api_token", default=os.getenv("FINMIND_API_TOKEN"), help="FinMind API Token")

    # feature_analyzer (Chimera P/C Ratio) 特定參數
    parser.add_argument("--pc_ratio_products", nargs="+", default=["TXO"], help="P/C Ratio 分析的目標產品")

    # strategic_analyzer 特定參數
    # analysis_date_str 由 start_date 參數間接提供或自動確定，此處無需額外參數

    # args = parser.parse_args() # 暫時註解掉，因為 analyzer 相關邏輯已移除

    # logger.info(f"請求執行的分析器: {args.analyzer}")
    # logger.info(f"主資料庫路徑: {args.db_path}")
    # logger.info(f"分析超市資料庫路徑: {args.analytics_mart_db}")


    # # 初始化 DBManager (大多數分析器需要它)
    # # 注意：不同的分析器可能期望 DBManager 連接到不同的資料庫檔案。
    # # StrategicAnalyzer 和 DailyMarketAnalyzer 使用主 market_data.duckdb。
    # # ChimeraAnalyzer 和 InstitutionalAnalyzer 使用 analytics_mart.duckdb。
    # # LegacyQuadrantAnalyzer 使用其特定的 --legacy_quadrant_db。

    # db_manager_main = None
    # # if args.analyzer in ["daily_market", "strategic"]: # 相關模組暫時移除
        # # db_manager_main = DBManager(db_path=args.db_path) # DMA 和 Strategic 用主 DB

    # analyzer_instance = None

    # try:
        # # if args.analyzer == "daily_market": # 相關模組暫時移除
            # # if not args.tickers or not args.start_date: # DMA 需要 tickers 和 start_date (至少)
                # # parser.error("--tickers 和 --start_date 是 daily_market 分析器的必要參數。")
            # # DailyMarketAnalysisEngine 的 __init__ 需要 ticker, date_str, table_name
            # # 這意味著 BaseAnalyzer 的 run() 模式（一次性執行）可能不完全適合 DMA 的原始設計（針對多個 ticker 和日期範圍的報告）
            # # 目前，我們假設 pipeline 將為單個 ticker 和單個日期運行 DMA
            # # TODO: 需要調整以更好地適應 DMA 的多 ticker/日期報告生成。
            # # 暫時，我們只取第一個 ticker 和 start_date 作為示例。
            # # 這部分需要在後續任務中仔細考慮如何將DMA的完整功能對應到pipeline。
            # # 一個可能的方案是 pipeline 接受日期範圍和 tickers 列表，然後循環調用。
            # # 但 BaseAnalyzer 本身是為單次運行設計的。
            # # first_ticker = args.tickers.split(',')[0].strip()
            # # logger.warning(f"Daily Market Analyzer 當前在 pipeline 中僅處理第一個 ticker ({first_ticker}) 和 start_date ({args.start_date})。完整功能遷移需要進一步設計。")
            # # analyzer_instance = DailyMarketAnalysisEngine(
                # # db_manager_instance=db_manager_main,
                # # ticker=first_ticker, # 示例：取第一個 ticker
                # # date_str=args.start_date, # 示例：使用 start_date
                # # table_name=args.dma_table_name
            # # )

        # # if args.analyzer == "chimera_composite": # 注意：由於 daily_market 被註解，這裡變成 if 而不是 elif # 相關模組暫時移除
            # # analyzer_instance = ChimeraAnalyzer(
                # # db_path=args.analytics_mart_db,
                # # analysis_type="composite",
                # # start_date=args.start_date,
                # # end_date=args.end_date,
                # # stock_ids=args.stock_ids
            # # )

        # # elif args.analyzer == "chimera_pc_ratio": # 相關模組暫時移除
            # # analyzer_instance = ChimeraAnalyzer(
                # # db_path=args.analytics_mart_db,
                # # analysis_type="pc_ratio",
                # # start_date=args.start_date,
                # # end_date=args.end_date,
                # # target_products=args.pc_ratio_products
            # # )

        # # elif args.analyzer == "legacy_quadrant": # 相關模組暫時移除
            # # logger.info(f"準備執行 Legacy Quadrant 分析。將為每個時間週期分別運行。")
            # # LegacyQuadrantAnalyzer 需要針對每個時間週期運行
            # # all_periods_succeeded = True
            # # for period in TIME_PERIODS_FOR_LEGACY_QUADRANT.keys():
                # # logger.info(f"  - 執行 Legacy Quadrant 分析: {period}...")
                # # try:
                    # # quadrant_analyzer = LegacyQuadrantAnalyzer(
                        # # db_path=args.legacy_quadrant_db, # 使用其特定的 DB 路徑
                        # # period_name=period
                    # # )
                    # # quadrant_analyzer.run()
                # # except Exception as e_quad:
                    # # logger.error(f"Legacy Quadrant 分析 ({period}) 失敗: {e_quad}")
                    # # all_periods_succeeded = False
            # # if all_periods_succeeded:
                # # logger.info("所有 Legacy Quadrant 分析週期已完成。")
            # # else:
                # # logger.warning("部分 Legacy Quadrant 分析週期執行失敗。")
            # # return # Legacy Quadrant 的循環執行在此處結束

        # if args.analyzer == "institutional": # 注意：由於其他 analyzer 被註解，這裡變成 if # 相關模組暫時移除
            # if not args.stock_ids or not args.start_date or not args.end_date:
                 # parser.error("--stock_ids, --start_date, --end_date 是 institutional 分析器的必要參數。")
            # # InstitutionalAnalyzer 通常針對單個 stock_id 操作
            # # 如果提供了多個 stock_ids，我們需要循環或讓分析器內部處理
            # # 目前，我們也只取第一個 stock_id 作為示例
            # first_stock_id_inst = args.stock_ids[0]
            # logger.warning(f"Institutional Analyzer 當前在 pipeline 中僅處理第一個 stock_id ({first_stock_id_inst})。")
            # analyzer_instance = InstitutionalAnalyzer(
                # stock_id=first_stock_id_inst,
                # start_date=args.start_date,
                # end_date=args.end_date,
                # api_token=args.finmind_api_token,
                # db_path=args.analytics_mart_db # Institutional 使用 analytics_mart_db
            # )

        # # elif args.analyzer == "strategic": # 相關模組暫時移除
            # # analyzer_instance = StrategicAnalyzer(
                # # db_manager=db_manager_main, # StrategicAnalyzer 使用主 DB
                # # analysis_date_str=args.start_date # StrategicAnalyzer 的 analysis_date_str 可以是 start_date
            # # )

        # else:
            # # 此處不應到達，因為 choices 已經限制了 analyzer 參數
            # logger.error(f"未知的分析器名稱 '{args.analyzer}'") # args.analyzer 將未定義
            # sys.exit(1)

        # if analyzer_instance:
            # logger.info(f"實例化分析器 {args.analyzer} 成功。準備執行 run()...") # args.analyzer 將未定義
            # analyzer_instance.run()
            # logger.info(f"分析器 {args.analyzer} 執行完畢。") # args.analyzer 將未定義
        # else:
            # # 這種情況只應該在 legacy_quadrant 之後發生，或者如果上面有邏輯錯誤
             # if args.analyzer != "legacy_quadrant": # args.analyzer 將未定義
                # logger.error(f"未能實例化分析器 {args.analyzer}")

    # except Exception as e:
        # logger.error(f"執行分析器 {args.analyzer} 時發生嚴重錯誤: {e}", exc_info=True) # args.analyzer 將未定義
        # # import traceback # traceback.print_exc() 可由 logger 的 exc_info=True 替代
        # # traceback.print_exc()
        # sys.exit(1)
    logger.info("(apps/analysis_pipeline/run.py) main() 執行被跳過，因為所有分析器模組的相關邏輯均已被註解。")

if __name__ == "__main__":
    main()
