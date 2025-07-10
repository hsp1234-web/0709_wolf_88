# tests/unit/apps/etl_pipeline/test_aggregator.py
import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
from pathlib import Path
import pandas as pd

# --- 確保 apps.etl_pipeline.aggregator 可以被導入 ---
# 假設此測試腳本位於 tests/unit/apps/etl_pipeline/
# 專案根目錄是其上四層
try:
    current_script_path = Path(__file__).resolve()
    project_root_for_test = current_script_path.parent.parent.parent.parent
    if str(project_root_for_test) not in sys.path:
        sys.path.insert(0, str(project_root_for_test))
    # print(f"DEBUG [test_aggregator.py]: project_root_for_test = {project_root_for_test}")
except NameError:
    project_root_for_test = Path(os.getcwd()) # Fallback if __file__ is not defined
    if str(project_root_for_test) not in sys.path:
        sys.path.insert(0, str(project_root_for_test))
# --- 完成導入路徑設置 ---

from apps.etl_pipeline import aggregator

class TestAggregator(unittest.TestCase):

    def setUp(self):
        # 準備一些測試中會用到的通用參數
        self.product_id = "TESTPROD"
        self.start_date = "2023-01-01"
        self.end_date = "2023-01-02"
        self.test_argv = [
            self.product_id,
            self.start_date,
            self.end_date,
            "--source_db", "dummy_source.db",
            "--analytics_db", "dummy_analytics.db"
        ]
        # 將預設資料庫路徑指向臨時位置，避免測試影響真實檔案或依賴真實檔案
        # aggregator.DEFAULT_SOURCE_TICKS_DB_PATH = Path("./temp_test_source.db")
        # aggregator.DEFAULT_ANALYTICS_DB_PATH = Path("./temp_test_analytics.db")


    @patch('apps.etl_pipeline.aggregator.Path.exists')
    @patch('apps.etl_pipeline.aggregator.Path.mkdir')
    @patch('apps.etl_pipeline.aggregator.duckdb.connect')
    @patch('apps.etl_pipeline.aggregator.pd.DataFrame.to_sql', new_callable=MagicMock) # 如果有用 to_sql
    @patch('apps.etl_pipeline.aggregator.pd.read_sql_query', new_callable=MagicMock) # 如果有用 read_sql_query
    def test_run_aggregation_successful_execution(
        self, mock_read_sql, mock_to_sql, mock_duckdb_connect, mock_mkdir, mock_path_exists
    ):
        """
        測試 run_aggregation 在模擬的成功情境下是否能正確執行。
        """
        # 模擬 Path.exists() 總是返回 True (表示 DB 檔案存在或 dummy DB 創建成功)
        mock_path_exists.return_value = True

        # 模擬 duckdb.connect() 返回一個 MagicMock 連接物件
        mock_conn = MagicMock()
        mock_duckdb_connect.return_value.__enter__.return_value = mock_conn

        # 模擬 fetchdf() 返回一個非空的 DataFrame，包含必要欄位
        mock_ticks_df = MagicMock()
        mock_ticks_df.empty = False
        mock_ticks_df.configure_mock(**{
            "fetchdf.return_value": pd.DataFrame({
                'timestamp': pd.to_datetime(['2023-01-01 10:00:00', '2023-01-01 10:00:05']),
                'price': [100.0, 101.0],
                'volume': [10, 5]
            })
        })
        mock_conn.execute.return_value = mock_ticks_df # 使 execute().fetchdf() 成功

        # 模擬 DataFrame 的 resample 和 agg 操作，使其返回一個看起來合理的 OHLCV DataFrame
        # 這一部分比較複雜，如果聚合邏輯本身很複雜，可能需要更精細的 mock
        # 這裡簡化處理，假設 resample().agg() 能產生結果
        mock_ohlcv_df = pd.DataFrame({
            'timestamp': pd.to_datetime(['2023-01-01 10:00:00']),
            'open': [100.0], 'high': [101.0], 'low': [100.0], 'close': [101.0], 'volume': [15]
        })

        # 需要 mock pandas 的 resample().agg() 行為
        # 這通常比較棘手，因為它是鏈式調用。
        # 一種方法是 mock DataFrame 實例本身，並使其 resample 方法返回一個可配置的 mock
        mock_df_instance = MagicMock(spec=pd.DataFrame)
        mock_df_instance.empty = False # 假設 fetchdf 返回的 df 不是空的
        mock_df_instance.set_index.return_value = mock_df_instance # set_index 返回自身

        # 模擬 resample 返回的 Resampler 物件，該物件有 agg 方法
        mock_resampler = MagicMock()
        mock_resampler.agg.return_value = mock_ohlcv_df # agg 返回預期的 ohlcv_df
        mock_df_instance.resample.return_value = mock_resampler

        # 讓 duckdb execute().fetchdf() 返回的 DataFrame 實例是這個 mock_df_instance
        # 這需要確保 fetchdf 返回的是一個可以被 resample 的 DataFrame mock
        # 上面的 mock_ticks_df.fetchdf.return_value = pd.DataFrame(...) 已經返回了一個真實的 DataFrame
        # 我們需要讓這個真實的 DataFrame 在被調用 resample 時表現如預期
        # 或者，更簡單地，讓 _aggregate_ticks_to_ohlcv_internal 內部對 ticks_df 的操作被 mock掉
        # 此處選擇 mock `_aggregate_ticks_to_ohlcv_internal` 的核心部分來簡化

        with patch('apps.etl_pipeline.aggregator.pd.DataFrame.resample') as mock_resample:
            mock_resampler_instance = MagicMock()
            mock_resampler_instance.agg.return_value = mock_ohlcv_df
            mock_resample.return_value = mock_resampler_instance

            # 執行函數
            result = aggregator.run_aggregation(self.test_argv)

            # 驗證結果
            self.assertTrue(result, "run_aggregation 應在成功時返回 True")
            mock_duckdb_connect.assert_any_call(database="dummy_source.db", read_only=True)
            mock_duckdb_connect.assert_any_call(database="dummy_analytics.db", read_only=False)
            mock_conn.execute.assert_any_call(unittest.mock.ANY, [self.product_id, self.start_date, self.end_date]) # 檢查查詢 tick
            mock_conn.append.assert_called() # 驗證是否有數據被 append

    def test_run_aggregation_missing_arguments(self):
        """
        測試 run_aggregation 在缺少必要參數時是否按預期失敗 (argparse 會處理)。
        argparse 在參數不足時會調用 sys.exit(2)，我們需要捕獲它。
        """
        with self.assertRaises(SystemExit) as cm:
            aggregator.run_aggregation([self.product_id, self.start_date]) # 缺少 end_date
        self.assertEqual(cm.exception.code, 2)

        with self.assertRaises(SystemExit) as cm:
            aggregator.run_aggregation([self.product_id]) # 缺少 start_date, end_date
        self.assertEqual(cm.exception.code, 2)

        with self.assertRaises(SystemExit) as cm:
            aggregator.run_aggregation([]) # 缺少所有必要參數
        self.assertEqual(cm.exception.code, 2)

    @patch('apps.etl_pipeline.aggregator.Path.exists')
    @patch('apps.etl_pipeline.aggregator.Path.mkdir')
    @patch('apps.etl_pipeline.aggregator.duckdb.connect')
    def test_run_aggregation_source_db_not_exists_and_cannot_create_dummy(
        self, mock_duckdb_connect, mock_mkdir, mock_path_exists
    ):
        """
        測試當來源資料庫不存在且無法創建虛擬資料庫時，函數是否返回 False。
        """
        mock_path_exists.return_value = False # 模擬 DB 檔案不存在

        # 模擬 _create_dummy_source_db_if_needed 內部拋出 RuntimeError
        with patch('apps.etl_pipeline.aggregator._create_dummy_source_db_if_needed', side_effect=RuntimeError("Cannot create dummy DB")):
            # 構建參數，使其觸發創建 dummy DB 的邏輯
            # 這需要 source_db 等於 aggregator.DEFAULT_SOURCE_TICKS_DB_PATH
            # 我們可以通過 mock DEFAULT_SOURCE_TICKS_DB_PATH 或傳遞特定參數
            test_argv_for_dummy_fail = [
                self.product_id, self.start_date, self.end_date,
                "--source_db", str(aggregator.DEFAULT_SOURCE_TICKS_DB_PATH), # 確保觸發 dummy 邏輯
                "--analytics_db", "dummy_analytics.db"
            ]
            result = aggregator.run_aggregation(test_argv_for_dummy_fail)
            self.assertFalse(result, "run_aggregation 應在無法處理來源資料庫時返回 False")

    @patch('apps.etl_pipeline.aggregator._ensure_db_directory_exists', side_effect=Exception("Dir creation failed"))
    def test_run_aggregation_db_directory_creation_fails(self, mock_ensure_dir):
        """
        測試當資料庫目錄創建失敗時，函數是否返回 False。
        """
        result = aggregator.run_aggregation(self.test_argv)
        self.assertFalse(result, "run_aggregation 應在目錄創建失敗時返回 False")


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
