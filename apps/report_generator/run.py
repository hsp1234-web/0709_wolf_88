# apps/report_generator/run.py
import argparse
import sys
import os
from pathlib import Path

# --- 路徑自我校正樣板碼 START ---
try:
    current_script_dir = Path(__file__).resolve().parent
    project_root = current_script_dir.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except Exception as e:
    print(f"專案路徑校正時發生錯誤 (run.py in report_generator): {e}", file=sys.stderr)
# --- 路徑自我校正樣板碼 END ---

from apps.report_generator.generator import ReportGenerator # 取消註解

# 預設資料庫路徑 (假設在專案根目錄)
DEFAULT_DB_PATH = project_root / "analytics_mart.duckdb"
# 預設報告輸出目錄 (假設在專案根目錄下的 output 資料夾)
DEFAULT_OUTPUT_DIR = project_root / "output"

def main():
    parser = argparse.ArgumentParser(description="視覺化報告生成器：為指定標的生成包含複合信號標記的K線圖報告。")
    parser.add_argument("--stock-id", required=True, type=str, help="要生成報告的股票代碼。")
    parser.add_argument("--start-date", required=True, type=str, help="報告開始日期 (YYYY-MM-DD)。")
    parser.add_argument("--end-date", required=True, type=str, help="報告結束日期 (YYYY-MM-DD)。")
    parser.add_argument("--db-path", type=str, default=str(DEFAULT_DB_PATH), help=f"分析資料庫路徑 (預設: {DEFAULT_DB_PATH})")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help=f"報告輸出目錄 (預設: {DEFAULT_OUTPUT_DIR})")

    args = parser.parse_args()

    print(f"指令：開始為股票 {args.stock_id} 生成報告...")
    print(f"日期範圍: {args.start_date} 至 {args.end_date}")
    print(f"使用資料庫: {args.db_path}")
    print(f"報告輸出至: {args.output_dir}")

    # 確保輸出目錄存在
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    try:
        generator = ReportGenerator(db_path=args.db_path) # 取消註解
        report_path = generator.generate_report(
            stock_id=args.stock_id,
            start_date_str=args.start_date,
            end_date_str=args.end_date,
            output_dir=Path(args.output_dir)
        ) # 取消註解
        if report_path: # 檢查 generate_report 是否成功返回路徑
            print(f"報告已成功生成並儲存於: {report_path}") # 取消註解
        else:
            print("報告生成失敗，未返回有效的報告路徑。")
            sys.exit(1) # 以錯誤碼退出
    except Exception as e:
        print(f"生成報告時發生錯誤: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
