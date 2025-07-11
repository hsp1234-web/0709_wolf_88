# apps/etl_pipeline/run.py
import argparse
import sys  # For sys.exit and stderr

# 移除路徑自我校正樣板碼

# 導入所有功能模組 - 移到頂部
from . import aggregator
from . import transformer
from . import loader


def main():
    parser = argparse.ArgumentParser(
        description="Unified ETL Pipeline Orchestrator. Call a specific ETL step with its own arguments.",
        usage="python -m apps.etl_pipeline.run <step> [step-specific arguments]",
    )
    parser.add_argument(
        "step",
        choices=["aggregate", "transform", "load"],
        help=(
            "The ETL step to execute: \n"
            "'aggregate': Aggregates time-series data. \n"
            "'transform': Transforms raw data (e.g., TAIFEX ZIPs). \n"
            "'load': Loads data into the database."
        ),
    )
    # 使用 parse_known_args() 以便將剩餘參數傳遞給子模組
    # sys.argv[1] 是 step，sys.argv[2:] 是 remaining_argv
    args, remaining_argv = parser.parse_known_args(
        sys.argv[1:]
    )  # Pass only arguments after script name

    exit_code = 0  # Default to success

    if args.step == "aggregate":
        print("--- 啟動統一ETL管線：時間聚合任務 ---")
        # aggregator.run_aggregation 期望接收一個參數列表
        # 它內部會用自己的 argparse 解析 remaining_argv
        success = aggregator.run_aggregation(remaining_argv)
        if success:
            print("--- 時間聚合任務完成 ---")
        else:
            print("--- 時間聚合任務失敗 ---", file=sys.stderr)
            exit_code = 1

    elif args.step == "transform":
        print("--- 啟動統一ETL管線：數據轉換任務 ---")
        success = transformer.run_transformation(remaining_argv)
        if success:
            print("--- 數據轉換任務完成 ---")
        else:
            print("--- 數據轉換任務失敗 ---", file=sys.stderr)
            exit_code = 1

    elif args.step == "load":
        print("--- 啟動統一ETL管線：數據加載任務 ---")
        success = loader.run_loading(remaining_argv)
        if success:
            print("--- 數據加載任務完成 ---")
        else:
            print("--- 數據加載任務失敗 ---", file=sys.stderr)
            exit_code = 1

    else:
        # argparse choices should prevent this, but as a safeguard:
        print(f"錯誤：未知的步驟 '{args.step}'。", file=sys.stderr)
        parser.print_help(sys.stderr)
        exit_code = 1

    if exit_code != 0:
        sys.exit(exit_code)


if __name__ == "__main__":
    # 範例調用方式 (從專案根目錄執行):
    # python -m apps.etl_pipeline.run aggregate MXF1 2023-01-01 2023-01-02 --source_db ./taifex_ticks.duckdb --analytics_db ./analytics_mart.duckdb
    # python -m apps.etl_pipeline.run transform --zipfile ./data/rym/FUT/Daily_2023_12_20.zip --output ./temp_output_transformer
    # python -m apps.etl_pipeline.run load --parquet-file ./temp_output_transformer/Daily_2023_12_20.parquet --db-path ./analytics_mart.duckdb --table-name transformed_taifex --primary-key some_id_column_if_any
    main()
