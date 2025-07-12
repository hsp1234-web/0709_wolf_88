# apps/report_generator/run.py
import argparse
import sys
from pathlib import Path

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    project_root = Path.cwd()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
# --- 標準化「路徑自我校正」樣板碼 END ---

from apps.report_generator.generator import ReportGenerator
from core.logger import LogManager

DEFAULT_DB_PATH = project_root / "analytics_mart.duckdb"
DEFAULT_OUTPUT_DIR = project_root / "output"


def main(log_manager: LogManager):
    parser = argparse.ArgumentParser(
        description="視覺化報告生成器：為指定標的生成包含複合信號標記的K線圖報告。"
    )
    parser.add_argument("--stock-id", required=True, type=str, help="要生成報告的股票代碼。")
    parser.add_argument("--start-date", required=True, type=str, help="報告開始日期 (YYYY-MM-DD)。")
    parser.add_argument("--end-date", required=True, type=str, help="報告結束日期 (YYYY-MM-DD)。")
    parser.add_argument("--timeframe", type=str, default="1d", help="報告的時間週期。預設為 '1d'。")
    parser.add_argument("--db-path", type=str, default=str(DEFAULT_DB_PATH), help=f"分析資料庫路徑 (預設: {DEFAULT_DB_PATH})")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help=f"報告輸出目錄 (預設: {DEFAULT_OUTPUT_DIR})")

    args = parser.parse_args()
    log_manager.log("INFO", f"接收到的參數: {args}")

    log_manager.log("INFO", f"指令：開始為股票 {args.stock_id} 生成報告...")
    log_manager.log("INFO", f"時間週期: {args.timeframe}")
    log_manager.log("INFO", f"日期範圍: {args.start_date} 至 {args.end_date}")

    output_path = Path(args.output_dir)
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log_manager.log("ERROR", f"創建輸出目錄 {output_path} 失敗: {e}")
        sys.exit(1)

    try:
        generator = ReportGenerator(db_path=args.db_path, log_manager=log_manager)
        report_path = generator.generate_report(
            stock_id=args.stock_id,
            start_date_str=args.start_date,
            end_date_str=args.end_date,
            timeframe=args.timeframe,
            output_dir=output_path,
        )
        if report_path:
            log_manager.log("INFO", f"報告已成功生成並儲存於: {report_path}")
        else:
            log_manager.log("WARNING", f"報告檔案未實際生成 (股票: {args.stock_id}, 週期: {args.timeframe})。")
    except Exception as e:
        log_manager.log("ERROR", f"生成報告時發生未預期錯誤: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Setup for standalone execution
    output_dir = project_root / "output"
    log_db_path = output_dir / "logs" / "standalone_test.sqlite"
    archive_dir = output_dir / "logs" / "archive"
    dummy_logger = LogManager(db_path=log_db_path, archive_dir=archive_dir)

    dummy_logger.log("INFO", "report_generator/run.py 作為腳本執行...")
    main(log_manager=dummy_logger)
    dummy_logger.archive_to_file()
