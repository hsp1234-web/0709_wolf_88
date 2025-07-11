# apps/analysis_pipeline/run.py
import argparse
import sys
import os
from pathlib import Path

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    print(f"INFO (analysis_pipeline/run.py): 已將專案根目錄 {project_root} 添加到 sys.path")
except NameError:
    project_root = Path(os.getcwd()).resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    print(
        f"警告 (analysis_pipeline/run.py): __file__ 未定義，專案路徑校正可能不準確。已將 {project_root} 加入 sys.path。",
        file=sys.stderr,
    )
except Exception as e:
    print(
        f"專案路徑校正時發生錯誤 (apps/analysis_pipeline/run.py): {e}", file=sys.stderr
    )
# --- 標準化「路徑自我校正」樣板碼 END ---

# 統一的 DBManager 和分析器導入
from apps.daily_market_analyzer.db_manager import DBManager
from apps.daily_market_analyzer.analysis_engine import AnalysisEngine as DailyMarketAnalysisEngine
from apps.feature_analyzer.analyzer import ChimeraAnalyzer, LegacyQuadrantAnalyzer
from apps.institutional_analyzer.analyzer import InstitutionalAnalyzer
from apps.strategic_analyzer.analyzer import StrategicAnalyzer

# feature_analyzer 的 TIME_PERIODS 可能需要在此處定義或從其他地方導入
TIME_PERIODS_FOR_LEGACY_QUADRANT = {
    "1min": "1T", "5min": "5T", "15min": "15T",
    "1h": "1H", "4h": "4H", "1d": "1D",
}

def main():
    parser = argparse.ArgumentParser(description="統一分析管線執行器")
    parser.add_argument(
        "--analyzer",
        required=True,
        choices=[
            "daily_market",
            "chimera_composite",
            "chimera_pc_ratio",
            "legacy_quadrant",
            "institutional",
            "strategic",
        ],
        help="要執行的分析器名稱",
    )
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

    args = parser.parse_args()

    print(f"INFO: 請求執行的分析器: {args.analyzer}")
    print(f"INFO: 主資料庫路徑: {args.db_path}")
    print(f"INFO: 分析超市資料庫路徑: {args.analytics_mart_db}")


    # 初始化 DBManager (大多數分析器需要它)
    # 注意：不同的分析器可能期望 DBManager 連接到不同的資料庫檔案。
    # StrategicAnalyzer 和 DailyMarketAnalyzer 使用主 market_data.duckdb。
    # ChimeraAnalyzer 和 InstitutionalAnalyzer 使用 analytics_mart.duckdb。
    # LegacyQuadrantAnalyzer 使用其特定的 --legacy_quadrant_db。

    db_manager_main = None
    if args.analyzer in ["daily_market", "strategic"]:
        db_manager_main = DBManager(db_path=args.db_path) # DMA 和 Strategic 用主 DB

    analyzer_instance = None

    try:
        if args.analyzer == "daily_market":
            if not args.tickers or not args.start_date: # DMA 需要 tickers 和 start_date (至少)
                parser.error("--tickers 和 --start_date 是 daily_market 分析器的必要參數。")
            # DailyMarketAnalysisEngine 的 __init__ 需要 ticker, date_str, table_name
            # 這意味著 BaseAnalyzer 的 run() 模式（一次性執行）可能不完全適合 DMA 的原始設計（針對多個 ticker 和日期範圍的報告）
            # 目前，我們假設 pipeline 將為單個 ticker 和單個日期運行 DMA
            # TODO: 需要調整以更好地適應 DMA 的多 ticker/日期報告生成。
            # 暫時，我們只取第一個 ticker 和 start_date 作為示例。
            # 這部分需要在後續任務中仔細考慮如何將DMA的完整功能對應到pipeline。
            # 一個可能的方案是 pipeline 接受日期範圍和 tickers 列表，然後循環調用。
            # 但 BaseAnalyzer 本身是為單次運行設計的。
            first_ticker = args.tickers.split(',')[0].strip()
            print(f"警告: Daily Market Analyzer 當前在 pipeline 中僅處理第一個 ticker ({first_ticker}) 和 start_date ({args.start_date})。完整功能遷移需要進一步設計。")
            analyzer_instance = DailyMarketAnalysisEngine(
                db_manager_instance=db_manager_main,
                ticker=first_ticker, # 示例：取第一個 ticker
                date_str=args.start_date, # 示例：使用 start_date
                table_name=args.dma_table_name
            )

        elif args.analyzer == "chimera_composite":
            analyzer_instance = ChimeraAnalyzer(
                db_path=args.analytics_mart_db,
                analysis_type="composite",
                start_date=args.start_date,
                end_date=args.end_date,
                stock_ids=args.stock_ids
            )

        elif args.analyzer == "chimera_pc_ratio":
            analyzer_instance = ChimeraAnalyzer(
                db_path=args.analytics_mart_db,
                analysis_type="pc_ratio",
                start_date=args.start_date,
                end_date=args.end_date,
                target_products=args.pc_ratio_products
            )

        elif args.analyzer == "legacy_quadrant":
            print(f"INFO: 準備執行 Legacy Quadrant 分析。將為每個時間週期分別運行。")
            # LegacyQuadrantAnalyzer 需要針對每個時間週期運行
            all_periods_succeeded = True
            for period in TIME_PERIODS_FOR_LEGACY_QUADRANT.keys():
                print(f"  - 執行 Legacy Quadrant 分析: {period}...")
                try:
                    quadrant_analyzer = LegacyQuadrantAnalyzer(
                        db_path=args.legacy_quadrant_db, # 使用其特定的 DB 路徑
                        period_name=period
                    )
                    quadrant_analyzer.run()
                except Exception as e_quad:
                    print(f"錯誤: Legacy Quadrant 分析 ({period}) 失敗: {e_quad}", file=sys.stderr)
                    all_periods_succeeded = False
            if all_periods_succeeded:
                print("INFO: 所有 Legacy Quadrant 分析週期已完成。")
            else:
                print("警告: 部分 Legacy Quadrant 分析週期執行失敗。", file=sys.stderr)
            return # Legacy Quadrant 的循環執行在此處結束

        elif args.analyzer == "institutional":
            if not args.stock_ids or not args.start_date or not args.end_date:
                 parser.error("--stock_ids, --start_date, --end_date 是 institutional 分析器的必要參數。")
            # InstitutionalAnalyzer 通常針對單個 stock_id 操作
            # 如果提供了多個 stock_ids，我們需要循環或讓分析器內部處理
            # 目前，我們也只取第一個 stock_id 作為示例
            first_stock_id_inst = args.stock_ids[0]
            print(f"警告: Institutional Analyzer 當前在 pipeline 中僅處理第一個 stock_id ({first_stock_id_inst})。")
            analyzer_instance = InstitutionalAnalyzer(
                stock_id=first_stock_id_inst,
                start_date=args.start_date,
                end_date=args.end_date,
                api_token=args.finmind_api_token,
                db_path=args.analytics_mart_db # Institutional 使用 analytics_mart_db
            )

        elif args.analyzer == "strategic":
            analyzer_instance = StrategicAnalyzer(
                db_manager=db_manager_main, # StrategicAnalyzer 使用主 DB
                analysis_date_str=args.start_date # StrategicAnalyzer 的 analysis_date_str 可以是 start_date
            )

        else:
            # 此處不應到達，因為 choices 已經限制了 analyzer 參數
            print(f"錯誤: 未知的分析器名稱 '{args.analyzer}'", file=sys.stderr)
            sys.exit(1)

        if analyzer_instance:
            print(f"INFO: 實例化分析器 {args.analyzer} 成功。準備執行 run()...")
            analyzer_instance.run()
            print(f"INFO: 分析器 {args.analyzer} 執行完畢。")
        else:
            # 這種情況只應該在 legacy_quadrant 之後發生，或者如果上面有邏輯錯誤
             if args.analyzer != "legacy_quadrant":
                print(f"錯誤: 未能實例化分析器 {args.analyzer}", file=sys.stderr)

    except Exception as e:
        print(f"執行分析器 {args.analyzer} 時發生嚴重錯誤: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
