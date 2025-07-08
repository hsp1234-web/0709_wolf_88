# -*- coding: utf-8 -*-
"""
軍火庫裝載機 (`loader.py`) 的整合測試腳本。

此腳本專注於驗證 `load_parquet_to_db` 函數在各種「入庫衝突」情境下的行為，
確保其健壯性、正確的錯誤處理、數據完整性以及資源清理。

測試原則：
1.  **完全本地**：嚴禁任何網路活動。所有測試都在臨時資料庫實例上進行。
2.  **動態模擬**：所有 Parquet 檔案在測試期間動態生成。
3.  **絕對潔淨**：使用 `setUp/tearDown` 確保每個測試都在乾淨的資料庫環境中開始，
    並在結束後清理所有臨時檔案與資料庫。
"""
import unittest
import os
import sys
import tempfile
from pathlib import Path
import pandas as pd
import duckdb
import shutil # 用於 tearDown 中的 rmtree
import logging
from unittest.mock import patch, MagicMock

# --- 標準化「路徑自我校正」樣板碼 START ---
try:
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    project_root = Path(os.getcwd())
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    print(f"警告：__file__ 未定義於 _test_harness_database_loader.py，專案路徑校正可能不準確。", file=sys.stderr)
# --- 標準化「路徑自我校正」樣板碼 END ---

from apps.database_loader.loader import load_parquet_to_db, SchemaMismatchError

class TestDatabaseLoader(unittest.TestCase):
    temp_dir_path: Path
    db_path: Path # 指向臨時資料庫檔案的路徑
    mock_logger: MagicMock

    def setUp(self):
        """為每個測試案例設置一個乾淨的臨時工作環境和資料庫。"""
        self.temp_dir_path = Path(tempfile.mkdtemp(prefix="test_db_loader_"))
        # 使用檔案型資料庫以方便檢查和跨進程鎖的模擬（雖然此處主要模擬 connect 失敗）
        self.db_path = self.temp_dir_path / "test_temp_main.duckdb"

        # 確保在每個測試開始前，舊的資料庫檔案 (如果存在) 被刪除
        if self.db_path.exists():
            self.db_path.unlink()

        self.mock_logger = MagicMock(spec=logging.Logger)
        # print(f"\n[SETUP] 測試 {self.id()} 的臨時目錄: {self.temp_dir_path}, 資料庫路徑: {self.db_path}")

    def tearDown(self):
        """在每個測試案例結束後清理臨時檔案和目錄。"""
        # 嘗試關閉任何可能的連接 (雖然 loader 內部會關閉)
        # DuckDB 在 Python 中通常不需要顯式關閉所有連接才允許刪除檔案，
        # 但這是一個好習慣，以防萬一。這裡我們依賴 loader.py 自身的 finally 塊。

        if self.temp_dir_path.exists():
            try:
                shutil.rmtree(self.temp_dir_path)
                # print(f"[TEARDOWN] 臨時目錄已成功刪除: {self.temp_dir_path}")
            except Exception as e:
                print(f"[TEARDOWN_ERROR] 清理臨時目錄 {self.temp_dir_path} 失敗: {e}", file=sys.stderr)

    def _create_dummy_parquet_file(self, data: dict, filename: str) -> Path:
        """輔助函數：在臨時目錄中創建一個 Parquet 檔案。"""
        file_path = self.temp_dir_path / filename
        df = pd.DataFrame(data)
        df.to_parquet(file_path, index=False)
        # print(f"[HELPER] 創建 Parquet 檔案: {file_path} 包含 {len(df)} 行")
        return file_path

    def _get_table_row_count(self, table_name: str) -> int:
        """輔助函數：獲取指定表格的總行數。"""
        if not self.db_path.exists():
            # print(f"[HELPER_WARN] _get_table_row_count: 資料庫檔案 {self.db_path} 不存在。")
            return 0 # 或者拋出錯誤，取決於預期
        try:
            with duckdb.connect(database=str(self.db_path), read_only=True) as conn:
                # 檢查表格是否存在
                res = conn.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table_name.lower()}'").fetchone()
                if res is None or res[0] == 0:
                    # print(f"[HELPER_INFO] _get_table_row_count: 表格 {table_name} 不存在。")
                    return 0

                count_result = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()
                # print(f"[HELPER] 表格 '{table_name}' 行數: {count_result[0] if count_result else 'N/A'}")
                return count_result[0] if count_result else 0
        except Exception as e:
            # print(f"[HELPER_ERROR] _get_table_row_count 讀取表格 '{table_name}' 行數時出錯: {e}")
            return -1 # 返回一個特殊值表示錯誤

    def _get_table_schema(self, table_name: str) -> list:
        """輔助函數：獲取指定表格的 schema (欄位名和類型)。"""
        schema_list = []
        if not self.db_path.exists():
            return schema_list
        try:
            with duckdb.connect(database=str(self.db_path), read_only=True) as conn:
                 # 檢查表格是否存在 (小寫比較，因為 DuckDB information_schema 通常是小寫)
                res = conn.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table_name.lower()}'").fetchone()
                if res is None or res[0] == 0:
                    return schema_list # 表格不存在

                # PRAGMA table_info('table_name') 返回: cid, name, type, notnull, dflt_value, pk
                pragma_result = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
                for col_info in pragma_result:
                    schema_list.append({'name': col_info[1], 'type': col_info[2].upper()})
            # print(f"[HELPER] 表格 '{table_name}' Schema: {schema_list}")
            return schema_list
        except Exception as e:
            # print(f"[HELPER_ERROR] _get_table_schema 獲取表格 '{table_name}' schema 時出錯: {e}")
            return [] # 表示錯誤或無法獲取

    def assert_log_contains(self, expected_substring: str, level: str = "error"):
        """斷言 mock_logger 的指定級別的日誌中包含特定子字串。"""
        log_calls = []
        if level == "error":
            log_calls = self.mock_logger.error.call_args_list
        elif level == "warning":
            log_calls = self.mock_logger.warning.call_args_list
        elif level == "info":
            log_calls = self.mock_logger.info.call_args_list
        elif level == "debug":
            log_calls = self.mock_logger.debug.call_args_list

        found = any(expected_substring in str(call_args[0]) for call_args in log_calls)
        self.assertTrue(found, f"預期的日誌子字串 '{expected_substring}' 未在 {level.upper()} 日誌中找到。\n捕獲到的 {level.upper()} 日誌: {log_calls}")

    # --- 接下來是各個測試案例 ---

    def test_load_parquet_idempotency_with_pk(self):
        """
        情境一 (Part A)：重複入庫，提供主鍵 (Idempotency with PK)
        測試：連續兩次載入相同的 Parquet 檔案 (有主鍵定義)，
              資料庫目標表格的總行數應保持不變。
        """
        table_name = "idempotency_test_pk"
        data = {'id': [1, 2, 3], 'value': ['A', 'B', 'C']}
        parquet_file = self._create_dummy_parquet_file(data, "data_with_pk.parquet")

        # 第一次載入
        load_parquet_to_db(str(parquet_file), str(self.db_path), table_name,
                           primary_key_column='id', logger=self.mock_logger)
        count_after_first_load = self._get_table_row_count(table_name)
        self.assertEqual(count_after_first_load, 3, "首次載入後行數應為3")

        # 第二次載入相同的檔案
        load_parquet_to_db(str(parquet_file), str(self.db_path), table_name,
                           primary_key_column='id', logger=self.mock_logger)
        count_after_second_load = self._get_table_row_count(table_name)

        self.assertEqual(count_after_second_load, count_after_first_load,
                         f"第二次載入相同檔案後 (有主鍵)，行數應與第一次載入後相同 ({count_after_first_load})，實際為 {count_after_second_load}")
        # 檢查是否包含 "冪等插入" 和 "0 行" 或 "未插入新行" 或 "無法獲取行數"
        log_found = any(
            ("冪等插入了 0 行新數據" in str(call_args[0])) or \
            ("進行冪等插入，未插入新行或無法確定行數" in str(call_args[0])) or \
            ("無法獲取冪等插入的行數" in str(call_args[0]) and "冪等插入操作已執行" in str(call_args[0]))
            for call_args in self.mock_logger.info.call_args_list + self.mock_logger.warning.call_args_list # 檢查 info 和 warning
        )
        self.assertTrue(log_found, f"未找到預期的冪等插入0行相關日誌。捕獲的日誌: INFO: {self.mock_logger.info.call_args_list}, WARNING: {self.mock_logger.warning.call_args_list}")

    def test_load_parquet_idempotency_no_pk_appends_data(self):
        """
        情境一 (Part B)：重複入庫，不提供主鍵 (Append behavior without PK)
        測試：連續兩次載入相同的 Parquet 檔案 (無主鍵定義進行冪等操作)，
              數據應被追加，總行數會增加。
        """
        table_name = "idempotency_test_no_pk"
        data = {'col_a': [10, 20], 'col_b': ['X', 'Y']}
        parquet_file = self._create_dummy_parquet_file(data, "data_no_pk.parquet")

        # 第一次載入 (表不存在，會創建並載入)
        load_parquet_to_db(str(parquet_file), str(self.db_path), table_name,
                           primary_key_column=None, logger=self.mock_logger)
        count_after_first_load = self._get_table_row_count(table_name)
        self.assertEqual(count_after_first_load, 2, "首次載入後行數應為2")

        # 第二次載入相同的檔案 (表已存在，無主鍵，應追加)
        load_parquet_to_db(str(parquet_file), str(self.db_path), table_name,
                           primary_key_column=None, logger=self.mock_logger)
        count_after_second_load = self._get_table_row_count(table_name)

        self.assertEqual(count_after_second_load, count_after_first_load * 2,
                         f"第二次載入相同檔案後 (無主鍵)，行數應為首次的兩倍 ({count_after_first_load * 2})，實際為 {count_after_second_load}")
        # 根據 loader.py 的邏輯，如果 last_successful_query_inserted_rows 不可用，會打印備用日誌
        log_found = any(
            (f"成功追加 2 行數據到 '{table_name}'" in str(call_args[0])) or \
            (f"追加數據到 '{table_name}' 完成 (可能插入0行或無法確定行數)" in str(call_args[0])) or \
            (f"無法獲取追加操作的行數" in str(call_args[0]) and "追加操作已執行" in str(call_args[0]))
            for call_args in self.mock_logger.info.call_args_list + self.mock_logger.warning.call_args_list # 檢查 info 和 warning
        )
        self.assertTrue(log_found, f"未找到預期的追加數據相關日誌。捕獲的日誌: INFO: {self.mock_logger.info.call_args_list}, WARNING: {self.mock_logger.warning.call_args_list}")

    def test_load_parquet_schema_mismatch(self):
        """
        情境二：軍火規格變更（Schema Mismatch）
        測試：當嘗試載入的 Parquet 檔案 schema 與現有表格 schema 不匹配時，
              應拋出 SchemaMismatchError，且資料庫內容和結構不應改變。
        """
        table_name = "schema_mismatch_test"

        # 載入 Schema V1
        data_v1 = {'date': pd.to_datetime(['2023-01-01']), 'price': [100.0]}
        parquet_v1 = self._create_dummy_parquet_file(data_v1, "schema_v1.parquet")
        load_parquet_to_db(str(parquet_v1), str(self.db_path), table_name, logger=self.mock_logger)

        count_after_v1 = self._get_table_row_count(table_name)
        schema_after_v1 = self._get_table_schema(table_name)
        self.assertEqual(count_after_v1, 1)
        self.assertEqual(len(schema_after_v1), 2)
        self.assertTrue(any(col['name'].lower() == 'date' for col in schema_after_v1))
        self.assertTrue(any(col['name'].lower() == 'price' for col in schema_after_v1))

        # 準備 Schema V2 (多一個 'volume' 欄位)
        data_v2 = {'date': pd.to_datetime(['2023-01-02']), 'price': [101.0], 'volume': [1000]}
        parquet_v2 = self._create_dummy_parquet_file(data_v2, "schema_v2_extra_col.parquet")

        # 嘗試載入 Schema V2，預期拋出 SchemaMismatchError
        with self.assertRaises(SchemaMismatchError) as context:
            load_parquet_to_db(str(parquet_v2), str(self.db_path), table_name, logger=self.mock_logger)

        self.assertIn(f"Parquet 檔案 '{parquet_v2.name}' 的 schema 與現有表格 '{table_name}' 的 schema 不匹配", str(context.exception))
        self.assert_log_contains(f"Schema 不匹配：欄位數量不同。", level="warning") # _compare_schemas 中的日誌

        # 驗收：資料庫內容和結構未改變
        count_after_failed_v2_load = self._get_table_row_count(table_name)
        schema_after_failed_v2_load = self._get_table_schema(table_name)

        self.assertEqual(count_after_failed_v2_load, count_after_v1, "Schema不匹配後，行數不應改變")
        self.assertEqual(schema_after_failed_v2_load, schema_after_v1, "Schema不匹配後，表格schema不應改變")

        # 準備 Schema V3 (少一個 'price' 欄位)
        data_v3 = {'date': pd.to_datetime(['2023-01-03'])}
        parquet_v3 = self._create_dummy_parquet_file(data_v3, "schema_v3_missing_col.parquet")

        with self.assertRaises(SchemaMismatchError) as context_v3:
            load_parquet_to_db(str(parquet_v3), str(self.db_path), table_name, logger=self.mock_logger)

        self.assertIn(f"Parquet 檔案 '{parquet_v3.name}' 的 schema 與現有表格 '{table_name}' 的 schema 不匹配", str(context_v3.exception))
        self.assert_log_contains(f"Schema 不匹配：欄位數量不同。", level="warning")

        count_after_failed_v3_load = self._get_table_row_count(table_name)
        schema_after_failed_v3_load = self._get_table_schema(table_name)
        self.assertEqual(count_after_failed_v3_load, count_after_v1, "Schema不匹配(欄位減少)後，行數不應改變")
        self.assertEqual(schema_after_failed_v3_load, schema_after_v1, "Schema不匹配(欄位減少)後，表格schema不應改變")

        # 準備 Schema V4 (欄位名不同)
        data_v4 = {'datum': pd.to_datetime(['2023-01-04']), 'wert': [100.0]} # datum vs date, wert vs price
        parquet_v4 = self._create_dummy_parquet_file(data_v4, "schema_v4_diff_name.parquet")

        with self.assertRaises(SchemaMismatchError) as context_v4:
            load_parquet_to_db(str(parquet_v4), str(self.db_path), table_name, logger=self.mock_logger)

        self.assertIn(f"Parquet 檔案 '{parquet_v4.name}' 的 schema 與現有表格 '{table_name}' 的 schema 不匹配", str(context_v4.exception)) # 修正 "의" 為 "的"
        self.assert_log_contains(f"Schema 不匹配：欄位名稱在位置 0 不同", level="warning") # 假設 date 是第一個比較

        count_after_failed_v4_load = self._get_table_row_count(table_name)
        schema_after_failed_v4_load = self._get_table_schema(table_name)
        self.assertEqual(count_after_failed_v4_load, count_after_v1, "Schema不匹配(欄位名不同)後，行數不應改變")
        self.assertEqual(schema_after_failed_v4_load, schema_after_v1, "Schema不匹配(欄位名不同)後，表格schema不應改變")

    @patch('apps.database_loader.loader.duckdb.connect')
    def test_load_parquet_handles_db_locking(self, mock_duckdb_connect: MagicMock):
        """
        情境三：軍火庫意外上鎖（Database Locking）
        測試：當 duckdb.connect 拋出 IOException (模擬資料庫鎖定) 時，
              load_parquet_to_db 應能捕捉此異常，不崩潰，並記錄錯誤。
        """
        table_name = "db_lock_test"
        data = {'id': [1], 'value': ['A']}
        parquet_file = self._create_dummy_parquet_file(data, "dummy_data_for_lock_test.parquet")

        # 配置 mock_duckdb_connect 以拋出模擬的鎖定錯誤
        mock_duckdb_connect.side_effect = duckdb.IOException("Simulated database is locked error from connect")

        # 執行被測函數
        load_parquet_to_db(str(parquet_file), str(self.db_path), table_name, logger=self.mock_logger)

        # 驗收：mock_duckdb_connect 被呼叫了
        mock_duckdb_connect.assert_called_once_with(database=str(self.db_path), read_only=False)

        # 驗收：日誌包含預期的錯誤訊息
        self.assert_log_contains("[ERROR] 軍火庫已被鎖定，暫時無法訪問資料庫", level="error")
        self.assert_log_contains("Simulated database is locked error from connect", level="error")

        # 驗收：資料庫檔案不應被創建或修改 (因為連接就失敗了)
        # 注意：如果 db_path 是 ':memory:'，則此檢查無意義。但我們用的是檔案路徑。
        # setUp 中會刪除舊的 db_path，所以如果連接失敗，它應該不存在，或者為空。
        # 由於 load_parquet_to_db 內部沒有在 connect 失敗時顯式刪除 db_path 的邏輯，
        # 我們主要關心的是沒有表格被創建。
        self.assertEqual(self._get_table_row_count(table_name), 0, "資料庫連接失敗，不應創建表格或載入數據")
        # 也可以檢查 self.db_path 是否存在，如果 duckdb.connect 在失敗前會創建空檔案的話。
        # 但更重要的是表格內容。

    def test_load_parquet_success_and_batch_nature(self):
        """
        情境四：正常情境 (Happy Path) 及批次載入驗證 (間接)
        測試：成功將 Parquet 檔案載入到新表格和已存在表格中。
              批次載入特性通過 loader.py 的代碼結構來保證 (使用 SELECT * FROM read_parquet)。
        """
        table_name = "happy_path_table"

        # 1. 載入到新表格
        data1 = {'col_id': [1, 2, 3], 'name': ['X', 'Y', 'Z'], 'value': [1.1, 2.2, 3.3]}
        parquet1 = self._create_dummy_parquet_file(data1, "happy_data1.parquet")

        load_parquet_to_db(str(parquet1), str(self.db_path), table_name,
                           primary_key_column='col_id', logger=self.mock_logger)

        self.assertEqual(self._get_table_row_count(table_name), 3, "首次載入到新表後行數應為3")
        df_loaded1 = duckdb.connect(str(self.db_path)).execute(f"SELECT * FROM \"{table_name}\" ORDER BY col_id").df()
        pd.testing.assert_frame_equal(df_loaded1, pd.DataFrame(data1), check_dtype=False) # 類型可能因DB而略有差異，重點是值

        self.assert_log_contains(f"成功創建表格 '{table_name}' 並從 '{parquet1.name}' 載入數據。", level="info")

        # 2. 載入更多數據到已存在的表格 (有新數據，有重複數據)
        data2 = {'col_id': [3, 4, 5], 'name': ['Z_updated', 'W', 'V'], 'value': [3.33, 4.4, 5.5]} # id=3 重複
        parquet2 = self._create_dummy_parquet_file(data2, "happy_data2_more.parquet")

        # 清除上一次的 mock logger 呼叫記錄，以便檢查本次呼叫的日誌
        self.mock_logger.reset_mock()

        load_parquet_to_db(str(parquet2), str(self.db_path), table_name,
                           primary_key_column='col_id', logger=self.mock_logger)

        # 總行數應為 3 (來自 data1) + 2 (來自 data2 的新行 id=4,5) = 5
        # 因為 id=3 的數據已存在，不應重複插入
        self.assertEqual(self._get_table_row_count(table_name), 5, "載入更多數據 (含重複PK) 後總行數應為5")
        log_found_pk_insert = any(
            ("冪等插入了 2 行新數據" in str(call_args[0])) or \
            # 下面這個是備用日誌，如果行數無法確定但操作仍執行
            ("進行冪等插入" in str(call_args[0]) and "無法確定行數" in str(call_args[0])) or \
            ("無法獲取冪等插入的行數" in str(call_args[0]) and "冪等插入操作已執行" in str(call_args[0]))
            for call_args in self.mock_logger.info.call_args_list + self.mock_logger.warning.call_args_list
        )
        self.assertTrue(log_found_pk_insert, f"未找到預期的冪等插入2行相關日誌。捕獲的日誌: INFO: {self.mock_logger.info.call_args_list}, WARNING: {self.mock_logger.warning.call_args_list}")


        # 驗證數據內容 (較複雜，抽查或全量比較)
        expected_data_after_load2 = {
            'col_id': [1, 2, 3, 4, 5],
            'name': ['X', 'Y', 'Z', 'W', 'V'], # 注意 id=3 的 'name' 仍是 'Z'，因為我們是 INSERT ... WHERE NOT EXISTS
            'value': [1.1, 2.2, 3.3, 4.4, 5.5] # id=3 的 'value' 仍是 3.3
        }
        df_expected_after_load2 = pd.DataFrame(expected_data_after_load2)
        df_loaded2 = duckdb.connect(str(self.db_path)).execute(f"SELECT * FROM \"{table_name}\" ORDER BY col_id").df()

        # DuckDB 可能會將浮點數類型讀取為 DECIMAL 或 DOUBLE，Pandas 預設是 float64
        # 進行比較時，可以先轉換類型或使用 check_dtype=False，並關注值的近似相等性（如果需要）
        pd.testing.assert_frame_equal(df_loaded2, df_expected_after_load2, check_dtype=False)

        # 3. 載入數據到已存在的表格，不使用主鍵 (應追加)
        data3 = {'col_id': [6, 7], 'name': ['P', 'Q'], 'value': [6.6, 7.7]}
        parquet3 = self._create_dummy_parquet_file(data3, "happy_data3_append.parquet")

        self.mock_logger.reset_mock()
        load_parquet_to_db(str(parquet3), str(self.db_path), table_name,
                           primary_key_column=None, logger=self.mock_logger) # 不提供 PK

        # 總行數應為 5 (之前) + 2 (新追加) = 7
        self.assertEqual(self._get_table_row_count(table_name), 7, "追加數據 (無PK) 後總行數應為7")
        # self.assert_log_contains(f"成功追加 2 行數據到 '{table_name}'", level="info")
        log_found_append = any(
            (f"成功追加 2 行數據到 '{table_name}'" in str(call_args[0])) or \
            (f"追加數據到 '{table_name}' 完成" in str(call_args[0])) or \
            (f"無法獲取追加操作的行數" in str(call_args[0]) and "追加操作已執行" in str(call_args[0]))
            for call_args in self.mock_logger.info.call_args_list + self.mock_logger.warning.call_args_list
        )
        self.assertTrue(log_found_append, f"未找到預期的追加數據相關日誌 for table '{table_name}'. Logs: INFO: {self.mock_logger.info.call_args_list}, WARNING: {self.mock_logger.warning.call_args_list}")

if __name__ == '__main__':
    unittest.main()
