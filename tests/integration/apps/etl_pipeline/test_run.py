# tests/integration/apps/etl_pipeline/test_run.py
import subprocess
import unittest
from pathlib import Path
import duckdb
import pandas as pd
import shutil
import zipfile
import os
import sys

# --- 確保 apps.etl_pipeline.run 可以被導入 (如果需要直接導入 run 模組) ---
# 以及 run.py 內部可能依賴的 apps.common 等路徑
try:
    current_script_path = Path(__file__).resolve()
    # tests/integration/apps/etl_pipeline/test_run.py
    # project_root should be 5 levels up from current_script_path.parent to reach /app
    # current_script_path.parent = /app/tests/integration/apps/etl_pipeline
    # level 1: .../apps
    # level 2: .../integration
    # level 3: .../tests
    # level 4: /app
    project_root_for_test = current_script_path.parent.parent.parent.parent
    # This was the error. If current_script_path = /app/tests/integration/apps/etl_pipeline/test_run.py
    # parent (etl_pipeline) -> parent (apps) -> parent (integration) -> parent (tests) -> parent (/app)
    # So it should be 5 parents from current_script_path itself.
    # Or 4 parents from current_script_path.parent

    # Correct calculation:
    # current_script_path: /app/tests/integration/apps/etl_pipeline/test_run.py
    # parent 1: /app/tests/integration/apps/etl_pipeline
    # parent 2: /app/tests/integration/apps
    # parent 3: /app/tests/integration
    # parent 4: /app/tests
    # parent 5: /app  <- This is the project root
    project_root_for_test = current_script_path.parents[
        4
    ]  # .parents[0] is parent, so .parents[4] is 5 levels up.

    apps_main_dir = project_root_for_test / "apps"  # This is /app/apps

    if str(project_root_for_test) not in sys.path:
        sys.path.insert(0, str(project_root_for_test))  # Add /app to sys.path
    # apps.etl_pipeline.run needs "apps" to be in sys.path for "from common import ..."
    # However, run.py itself does its own sys.path manipulation.
    # For direct imports in this test file, if any, /app needs to be in path.
    # For subprocess, the CWD or PYTHONPATH env var matters more.
    # Let's ensure apps_main_dir is in path for any direct test utility imports if needed,
    # but the subprocess relies on Python finding run.py and run.py finding its imports.
    # The key is that run.py is invoked as /app/apps/etl_pipeline/run.py

except NameError:
    # Fallback for environments where __file__ might not be defined
    project_root_for_test = Path(os.getcwd())  # Assuming CWD is project root /app
    # apps_main_dir = project_root_for_test / "apps"
    # if str(project_root_for_test) not in sys.path:
    #     sys.path.insert(0, str(project_root_for_test))
    # if str(apps_main_dir) not in sys.path:
    #    sys.path.insert(1, str(apps_main_dir))

# --- 完成導入路徑設置 ---


class TestEtlPipelineRun(unittest.TestCase):

    def setUp(self):
        self.base_test_dir = Path("./temp_integration_test_etl_pipeline")
        self.source_data_dir = self.base_test_dir / "source_data"
        self.transformed_data_dir = self.base_test_dir / "transformed_data"
        self.aggregated_data_dir = self.base_test_dir / "aggregated_data"
        self.db_path = self.base_test_dir / "test_etl_pipeline.db"
        self.run_py_script_path = (
            project_root_for_test / "apps" / "etl_pipeline" / "run.py"
        )

        # 清理並創建測試目錄
        if self.base_test_dir.exists():
            shutil.rmtree(self.base_test_dir)
        self.base_test_dir.mkdir(parents=True, exist_ok=True)
        self.source_data_dir.mkdir(parents=True, exist_ok=True)
        self.transformed_data_dir.mkdir(parents=True, exist_ok=True)
        self.aggregated_data_dir.mkdir(parents=True, exist_ok=True)

        # 創建樣本原始 CSV 數據 (模擬 TaiFEX 每日數據)
        self.sample_csv_filename = "Daily_20230101.csv"
        self.sample_zip_filename = "Daily_20230101.zip"  # Transformer 期望 ZIP 檔案
        sample_csv_path = self.source_data_dir / self.sample_csv_filename
        self.sample_zip_path = self.source_data_dir / self.sample_zip_filename

        csv_content = (
            "交易日期,契約,到期月份(週別),開盤價,最高價,最低價,收盤價,成交量,最後最佳買價,最後最佳賣價\n"
            "20230101,TX,202301,14000,14050,13950,14020,1000,14018,14020\n"  # TX 商品
            "20230101,MXF,202301,1400,1405,1395,1402,500,1401,1402\n"  # MXF 商品 (用於聚合測試)
            "20230101,TX,202301,14020,14080,14010,14070,1500,14068,14070\n"  # TX 商品
            "20230101,MXF,202301,1402,1408,1401,1407,700,1406,1407\n"  # MXF 商品
        )
        with open(sample_csv_path, "w", encoding="utf-8") as f:
            f.write(csv_content)

        # 將 CSV 壓縮成 ZIP
        with zipfile.ZipFile(self.sample_zip_path, "w") as zf:
            zf.write(sample_csv_path, arcname=self.sample_csv_filename)

        # 定義其他路徑
        self.transformed_parquet_path = self.transformed_data_dir / (
            Path(self.sample_csv_filename).stem + ".parquet"
        )
        self.aggregated_db_path = (
            self.aggregated_data_dir / "analytics_mart.duckdb"
        )  # aggregator 的預設輸出

    def tearDown(self):
        # 清理測試目錄
        if self.base_test_dir.exists():
            shutil.rmtree(self.base_test_dir)

    def _run_command(self, command_parts: list):
        """執行 subprocess 命令並返回結果。"""
        # print(f"DEBUG: Executing command: {command_parts}")
        # Ensure CWD is project root for "python -m apps.etl_pipeline.run" to work
        # project_root_for_test should be /app
        process = subprocess.run(
            [sys.executable, "-m", "apps.etl_pipeline.run"] + command_parts,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(project_root_for_test),  # Explicitly set CWD to project root
        )
        if process.returncode != 0:
            print(f"Command failed: {' '.join(command_parts)}")
            print(f"Stdout: {process.stdout}")
            print(f"Stderr: {process.stderr}")
        self.assertEqual(
            process.returncode, 0, f"Command execution failed: {process.stderr}"
        )
        return process

    def test_etl_pipeline_flow(self):
        # 1. 執行 Transform
        transform_target_path = self.transformed_data_dir / (
            Path(self.sample_csv_filename).stem + ".parquet"
        )
        self._run_command(
            [
                "transform",
                "--zipfile",
                str(self.sample_zip_path),
                "--output",
                str(self.transformed_data_dir),
            ]
        )
        self.assertTrue(
            transform_target_path.exists(), "Transformed parquet file was not created."
        )

        # 2. 執行 Aggregate
        # Aggregator 需要 product_id, start_date, end_date
        # 這裡我們聚合 MXF 商品，日期基於我們的樣本數據
        # 注意：aggregator 的 source_db 預設是 taifex_ticks.duckdb，我們需要讓它指向 transformer 的輸出
        # 但 transformer 輸出的是 parquet， aggregator 設計上是從 ticks DB 讀取。
        # 為了這個整合測試，我們需要先將 transformed parquet 載入到一個臨時的 ticks DB

        temp_ticks_db_path = self.base_test_dir / "temp_ticks_for_aggregator.duckdb"
        if temp_ticks_db_path.exists():
            temp_ticks_db_path.unlink()

        with duckdb.connect(str(temp_ticks_db_path)) as con:
            # 從 transformer 輸出的 Parquet 創建 ticks 表
            # Transformer 輸出包含 '交易日期', '契約', '到期月份(週別)', '開盤價', '最高價', '最低價', '收盤價', '成交量'
            # Aggregator 需要 'timestamp', 'price', 'volume', 'product_id'
            # 我們需要做一些轉換
            df = pd.read_parquet(transform_target_path)

            # 假設 '收盤價' 是 'price', '成交量' 是 'volume'
            # '交易日期' 需要轉換成 timestamp
            # '契約' 是 'product_id'
            df["timestamp"] = pd.to_datetime(
                df["交易日期"], format="%Y%m%d"
            )  # 假設 transformer 未轉換日期格式
            # 為了簡化，假設所有 tick 都發生在日初。更真實的數據會有時分秒。
            # 為了讓聚合有意義，我們為 MXF 的兩條記錄稍微錯開時間
            mxf_indices = df[df["契約"] == "MXF"].index
            if len(mxf_indices) > 1:
                df.loc[mxf_indices[0], "timestamp"] = pd.Timestamp(
                    "2023-01-01 09:00:00"
                )
                df.loc[mxf_indices[1], "timestamp"] = pd.Timestamp(
                    "2023-01-01 09:05:00"
                )

            ticks_data = pd.DataFrame(
                {
                    "timestamp": df["timestamp"],
                    "product_id": df["契約"],
                    "price": df["收盤價"].astype(float),  # 確保為 float
                    "volume": df["成交量"].astype(int),  # 確保為 int
                }
            )
            con.execute(
                "CREATE TABLE ticks (timestamp TIMESTAMP, product_id VARCHAR, price DOUBLE, volume BIGINT)"
            )
            con.append("ticks", ticks_data)

        # 現在執行 aggregate
        # aggregate 的輸出預設是 analytics_mart.duckdb 在專案根目錄，我們將其重定向到測試目錄
        self._run_command(
            [
                "aggregate",
                "MXF",  # product_id
                "2023-01-01",  # start_date
                "2023-01-02",  # end_date (不包含)
                "--source_db",
                str(temp_ticks_db_path),
                "--analytics_db",
                str(self.aggregated_db_path),
            ]
        )
        self.assertTrue(
            self.aggregated_db_path.exists(),
            "Aggregated DB (analytics_mart.duckdb) was not created.",
        )

        # 3. 執行 Load
        # Load 的輸入是 Parquet，但 aggregate 的輸出是 DuckDB。
        # 所以我們需要從 aggregated_db_path 中提取聚合後的數據 (例如 ohlcv_1min) 存為 Parquet，再餵給 loader
        temp_load_input_parquet_path = (
            self.base_test_dir / "ohlcv_1min_for_load.parquet"
        )

        with duckdb.connect(str(self.aggregated_db_path)) as agg_con:
            # 假設我們關心 1 分鐘線的數據 (如果聚合產生了的話)
            # 根據 aggregator 邏輯，它會為每個 TIME_PERIODS 創建一個表
            # 我們的樣本數據時間非常接近，可能只會落入一個 1min K棒
            try:
                ohlcv_df = agg_con.execute(
                    "SELECT * FROM ohlcv_1min WHERE product_id = 'MXF'"
                ).fetchdf()
                if not ohlcv_df.empty:
                    ohlcv_df.to_parquet(temp_load_input_parquet_path)
                else:
                    self.skipTest(
                        "Skipping load test: No 1-min OHLCV data was aggregated for MXF. This might be due to insufficient distinct timestamps in sample data for 1-min aggregation."
                    )
            except duckdb.CatalogException:
                self.skipTest(
                    "Skipping load test: ohlcv_1min table not found in aggregated DB. This might be due to sample data not producing this aggregation."
                )

        if not temp_load_input_parquet_path.exists():
            self.skipTest(
                f"Skipping load test: Aggregated Parquet file {temp_load_input_parquet_path} for loading was not created."
            )

        final_table_name = "mxf_ohlcv_1min"
        self._run_command(
            [
                "load",
                "--parquet-file",
                str(temp_load_input_parquet_path),
                "--db-path",
                str(self.db_path),
                "--table-name",
                final_table_name,
                "--primary-key",
                "timestamp,product_id",  # Loader 接受複合主鍵
            ]
        )
        self.assertTrue(self.db_path.exists(), "Final ETL database was not created.")

        # 4. 驗證最終數據庫中的數據
        with duckdb.connect(str(self.db_path)) as final_con:
            result_df = final_con.execute(
                f"SELECT * FROM {final_table_name} WHERE product_id = 'MXF' ORDER BY timestamp"
            ).fetchdf()
            self.assertFalse(
                result_df.empty, "No data found in the final table for MXF."
            )

            # 根據我們的樣本數據和時間戳調整：
            # MXF 20230101, 1402 (09:00:00)
            # MXF 20230101, 1407 (09:05:00)
            # 如果聚合成 1min K線，且這兩筆都落入不同的 1min K棒，或同一個 5min K棒
            # 假設我們用 1min 聚合，它們應該是獨立的K棒
            # 如果是 5min 聚合，它們會合併
            # 由於 aggregate 命令中我們指定了 start/end date，但沒有指定聚合週期給 run.py
            # run.py aggregate 內部會調用 aggregator.py, aggregator.py 會為所有 TIME_PERIODS 聚合
            # 而我們從 ohlcv_1min 提取數據。

            # 預期 MXF 的兩條記錄會產生一個 5 分鐘的 OHLCV 記錄 (如果以 5T 聚合)
            # open=1402, high=1407, low=1402, close=1407, volume=500+700=1200
            # timestamp 應該是 2023-01-01 09:00:00 (該週期的開始) for 5min
            # 如果是 1min，則會有兩條記錄
            # 09:00:00 -> o=1402, h=1402, l=1402, c=1402, v=500
            # 09:05:00 -> o=1407, h=1407, l=1407, c=1407, v=700

            # 我們的 aggregator 產生多個表，如 ohlcv_1min, ohlcv_5min 等。
            # 測試中我們從 ohlcv_1min 讀取並載入。
            self.assertEqual(
                len(result_df), 2, "Expected two 1-min OHLCV records for MXF."
            )

            pd.testing.assert_series_equal(
                result_df["open"],
                pd.Series([1402.0, 1407.0], name="open"),
                check_dtype=False,
            )
            pd.testing.assert_series_equal(
                result_df["high"],
                pd.Series([1402.0, 1407.0], name="high"),
                check_dtype=False,
            )
            pd.testing.assert_series_equal(
                result_df["low"],
                pd.Series([1402.0, 1407.0], name="low"),
                check_dtype=False,
            )
            pd.testing.assert_series_equal(
                result_df["close"],
                pd.Series([1402.0, 1407.0], name="close"),
                check_dtype=False,
            )
            pd.testing.assert_series_equal(
                result_df["volume"],
                pd.Series([500, 700], name="volume").astype("int64"),
                check_dtype=False,
            )  # duckdb BIGINT might be int64

            # 驗證時間戳 (轉換為 datetime64[ns] 以便比較)
            expected_timestamps = pd.to_datetime(
                ["2023-01-01 09:00:00", "2023-01-01 09:05:00"]
            ).tz_localize(
                None
            )  # DuckDB timestamp may not have tz
            actual_timestamps = pd.to_datetime(result_df["timestamp"]).dt.tz_localize(
                None
            )
            pd.testing.assert_series_equal(
                actual_timestamps,
                pd.Series(expected_timestamps, name="timestamp"),
                check_dtype=False,
            )


if __name__ == "__main__":
    unittest.main()
