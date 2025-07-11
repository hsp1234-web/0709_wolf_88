# apps/report_generator/run.py
import argparse
import sys
import os
from pathlib import Path

# 移除路徑自我校正樣板碼
from apps.report_generator.generator import ReportGenerator  # 移到頂部

# project_root 現在需要以其他方式定義，或者依賴於調用者正確設定 PYTHONPATH
# 為了讓代碼在移除樣板碼後仍能定義 DEFAULT_DB_PATH，我們假設運行時 CWD 是專案根目錄
# 或者，這些預設路徑應該從一個統一的配置模組讀取
project_root = Path(os.getcwd())  # 假設執行時 CWD 是專案根目錄
DEFAULT_DB_PATH = project_root / "analytics_mart.duckdb"
# 預設報告輸出目錄
DEFAULT_OUTPUT_DIR = (
    project_root / "output"
)  # 指揮官建議的 output 資料夾，之前是 output_reports


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

    print(f"指令：開始為股票 {args.stock_id} 生成報告...")
    print(f"時間週期: {args.timeframe}")  # 新增日誌
    print(f"日期範圍: {args.start_date} 至 {args.end_date}")
    print(f"使用資料庫: {args.db_path}")
    print(f"報告輸出至: {args.output_dir}")

    # 確保輸出目錄存在
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        generator = ReportGenerator(db_path=args.db_path)
        report_path = generator.generate_report(
            stock_id=args.stock_id,
            start_date_str=args.start_date,
            end_date_str=args.end_date,
            timeframe=args.timeframe,
            output_dir=output_path,
        )
        if report_path:
            print(f"報告已成功生成並儲存於: {report_path}")
            sys.exit(0)
        else:
            # 如果 report_path 為 None，表示 generate_report 內部已處理了錯誤訊息（例如無數據）
            # 這裡我們打印一個警告，並以成功碼退出，避免阻塞主流程。
            print(
                f"警告：報告檔案未實際生成 (股票: {args.stock_id}, 週期: {args.timeframe})。詳情請查看 generate_report 內部日誌。"
            )
            sys.exit(0)  # 以成功碼退出
    except ImportError as ie:  # 特別處理 Plotly 可能未安裝的情況
        print(f"發生導入錯誤: {ie}", file=sys.stderr)
        print("請確保已安裝所有必要的套件 (例如 plotly)。", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(
            f"生成報告時發生未預期錯誤 (股票: {args.stock_id}, 週期: {args.timeframe}): {e}",
            file=sys.stderr,
        )
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
