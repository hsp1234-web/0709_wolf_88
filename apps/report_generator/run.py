# apps/report_generator/run.py
import argparse
import sys
import os
from pathlib import Path

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent.parent.parent
except NameError:
    project_root = Path(os.getcwd()).resolve()
except Exception as e:
    print(
        f"緊急錯誤: 在確定專案根目錄時發生初始錯誤 (apps/report_generator/run.py): {e}", file=sys.stderr
    )
    project_root = Path(".").resolve()

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.logger import get_logger
logger = get_logger(__name__)

logger.debug(f"專案根目錄設定為: {project_root} (日誌來自 report_generator/run.py)")
# --- 標準化「路徑自我校正」樣板碼 END ---

from apps.report_generator.generator import ReportGenerator

# project_root 現在由上面的樣板碼定義
DEFAULT_DB_PATH = project_root / "analytics_mart.duckdb"
DEFAULT_OUTPUT_DIR = project_root / "output"


def main():
    parser = argparse.ArgumentParser(
        description="視覺化報告生成器：為指定標的生成包含複合信號標記的K線圖報告。"
    )
    parser.add_argument(
        "--stock-id", required=True, type=str, help="要生成報告的股票代碼。"
    )
    parser.add_argument(
        "--start-date", required=True, type=str, help="報告開始日期 (YYYY-MM-DD)。"
    )
    parser.add_argument(
        "--end-date", required=True, type=str, help="報告結束日期 (YYYY-MM-DD)。"
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="1d",
        help="報告的時間週期 (例如: '1min', '5min', '1h', '1d', '1w', '1m')。預設為 '1d' (日線)。",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(DEFAULT_DB_PATH),
        help=f"分析資料庫路徑 (預設: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"報告輸出目錄 (預設: {DEFAULT_OUTPUT_DIR})",
    )

    args = parser.parse_args()
    logger.info(f"接收到的參數: {args}")

    logger.info(f"指令：開始為股票 {args.stock_id} 生成報告...")
    logger.info(f"時間週期: {args.timeframe}")
    logger.info(f"日期範圍: {args.start_date} 至 {args.end_date}")
    logger.info(f"使用資料庫: {args.db_path}")
    logger.info(f"報告輸出至: {args.output_dir}")

    # 確保輸出目錄存在
    output_path = Path(args.output_dir)
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"創建輸出目錄 {output_path} 失敗: {e}", exc_info=True)
        sys.exit(1)


    try:
        generator = ReportGenerator(db_path=args.db_path) # ReportGenerator 內部也應使用 logger
        report_path = generator.generate_report(
            stock_id=args.stock_id,
            start_date_str=args.start_date,
            end_date_str=args.end_date,
            timeframe=args.timeframe,
            output_dir=output_path,
        )
        if report_path:
            logger.info(f"報告已成功生成並儲存於: {report_path}")
            sys.exit(0)
        else:
            logger.warning(
                f"報告檔案未實際生成 (股票: {args.stock_id}, 週期: {args.timeframe})。詳情請查看 generate_report 內部日誌。"
            )
            sys.exit(0)  # 以成功碼退出
    except ImportError as ie:
        logger.error(f"發生導入錯誤: {ie}. 請確保已安裝所有必要的套件 (例如 plotly)。", exc_info=True)
        sys.exit(1)
    except Exception as e:
        logger.error(
            f"生成報告時發生未預期錯誤 (股票: {args.stock_id}, 週期: {args.timeframe}): {e}",
            exc_info=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    logger.info("report_generator/run.py 作為腳本執行...")
    main()
