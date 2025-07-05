# -*- coding: utf-8 -*-
"""
apps/daily_market_analyzer/db_manager.py 的單元測試。
"""
import unittest
import os
import time # 用於測試時間戳更新
from datetime import datetime, timedelta, timezone
import pandas as pd # 雖然主要測試 no_data_records，但 DBManager 整體依賴 pandas
from apps.daily_market_analyzer.db_manager import DBManager

class TestNoDataRecords(unittest.TestCase):
    """
    測試 DBManager 中與 no_data_records 資料表相關的功能。
    """
    def setUp(self):
        """
        為每個測試案例設定一個臨時的測試資料庫。
        """
        self.test_db_path = "data_workspace/temp/test_no_data_records.duckdb"
        # 清理舊的測試資料庫（如果存在）
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

        # 建立 DBManager 實例，這會自動呼叫 _setup_database
        self.db_manager = DBManager(db_path=self.test_db_path)
        # _setup_database 在 DBManager.__init__ 中被呼叫，會自動建立 no_data_records 表。

    def tearDown(self):
        """
        在每個測試案例結束後清理測試資料庫。
        """
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_record_no_data_range_insert(self):
        """
        測試 record_no_data_range 方法是否能成功插入新的無數據記錄。
        """
        ticker = "TEST.TICKER"
        interval = "1d"
        start_date = "2023-01-01"
        end_date = "2023-01-05"

        self.db_manager.record_no_data_range(ticker, interval, start_date, end_date)

        # 驗證記錄是否存在
        exists = self.db_manager.check_no_data_record_exists(ticker, interval, start_date, end_date, cooldown_days=1)
        self.assertTrue(exists, "新插入的無數據記錄應該存在且在冷卻期內。")

        # 可以進一步直接查詢資料庫驗證內容
        import duckdb # 需要導入 duckdb 以便直接查詢
        with duckdb.connect(self.test_db_path) as con:
            res = con.execute("SELECT ticker, interval, start_date, end_date FROM no_data_records").fetchone()
            self.assertIsNotNone(res, "資料庫中應該有一條記錄。")
            self.assertEqual(res[0], ticker)
            self.assertEqual(res[1], interval)
            self.assertEqual(res[2], start_date)
            self.assertEqual(res[3], end_date)

    def test_record_no_data_range_update_recorded_at(self):
        """
        測試當記錄已存在時，record_no_data_range 是否會更新 recorded_at 時間戳。
        """
        ticker = "UPDATE.ME"
        interval = "1h"
        start_date = "2023-02-01"
        end_date = "2023-02-03"

        # 第一次記錄
        self.db_manager.record_no_data_range(ticker, interval, start_date, end_date)
        import duckdb # 需要導入 duckdb 以便直接查詢
        with duckdb.connect(self.test_db_path) as con:
            recorded_at_1_str = con.execute("SELECT recorded_at FROM no_data_records WHERE ticker=?", [ticker]).fetchone()[0]

        # 等待一小段時間以確保時間戳不同
        time.sleep(0.01)

        # 第二次記錄相同範圍
        self.db_manager.record_no_data_range(ticker, interval, start_date, end_date)
        with duckdb.connect(self.test_db_path) as con:
            recorded_at_2_str = con.execute("SELECT recorded_at FROM no_data_records WHERE ticker=?", [ticker]).fetchone()[0]
            count = con.execute("SELECT COUNT(*) FROM no_data_records WHERE ticker=?", [ticker]).fetchone()[0]

        self.assertEqual(count, 1, "應該只有一條記錄，因為是更新操作。")

        # 轉換為 datetime 物件進行比較
        recorded_at_1 = datetime.fromisoformat(recorded_at_1_str)
        recorded_at_2 = datetime.fromisoformat(recorded_at_2_str)
        self.assertGreater(recorded_at_2, recorded_at_1, "第二次記錄的 recorded_at 應該晚於第一次。")

    def test_check_no_data_record_exists_positive_in_cooldown(self):
        """
        測試 check_no_data_record_exists 在記錄存在且在冷卻期內時返回 True。
        """
        ticker = "IN.COOL"
        interval = "5m"
        start_date = "2023-03-01"
        end_date = "2023-03-01"
        cooldown_days = 7

        self.db_manager.record_no_data_range(ticker, interval, start_date, end_date)

        exists = self.db_manager.check_no_data_record_exists(ticker, interval, start_date, end_date, cooldown_days)
        self.assertTrue(exists, "記錄應在冷卻期內被偵測到。")

    def test_check_no_data_record_exists_negative_outside_cooldown(self):
        """
        測試 check_no_data_record_exists 在記錄存在但超出冷卻期時返回 False。
        """
        ticker = "OUT.COOL"
        interval = "1d"
        start_date = "2023-04-01"
        end_date = "2023-04-02"
        cooldown_days = 1 # 短冷卻期

        # 手動插入一個較早的 recorded_at
        old_recorded_at = (datetime.now(timezone.utc) - timedelta(days=cooldown_days + 1)).isoformat()
        import duckdb # 需要導入 duckdb 以便直接查詢
        with duckdb.connect(self.test_db_path) as con:
            con.execute("INSERT INTO no_data_records (ticker, interval, start_date, end_date, recorded_at) VALUES (?, ?, ?, ?, ?)",
                        [ticker, interval, start_date, end_date, old_recorded_at])

        exists = self.db_manager.check_no_data_record_exists(ticker, interval, start_date, end_date, cooldown_days)
        self.assertFalse(exists, "超出冷卻期的記錄不應被偵測為有效。")

    def test_check_no_data_record_exists_negative_no_record(self):
        """
        測試 check_no_data_record_exists 在沒有匹配記錄時返回 False。
        """
        exists = self.db_manager.check_no_data_record_exists("NON.EXIST", "1m", "2023-05-01", "2023-05-01", 7)
        self.assertFalse(exists, "不存在的記錄不應被偵測到。")

    def test_check_no_data_record_exists_different_params(self):
        """
        測試 check_no_data_record_exists 在 ticker, interval, 或日期範圍不同時返回 False。
        """
        ticker = "DIFF.PARAM"
        interval = "1d"
        start_date = "2023-06-01"
        end_date = "2023-06-05"
        cooldown_days = 7

        self.db_manager.record_no_data_range(ticker, interval, start_date, end_date)

        # 不同 ticker
        self.assertFalse(self.db_manager.check_no_data_record_exists("OTHER.TICKER", interval, start_date, end_date, cooldown_days))
        # 不同 interval
        self.assertFalse(self.db_manager.check_no_data_record_exists(ticker, "1h", start_date, end_date, cooldown_days))
        # 不同 start_date
        self.assertFalse(self.db_manager.check_no_data_record_exists(ticker, interval, "2023-06-02", end_date, cooldown_days))
        # 不同 end_date
        self.assertFalse(self.db_manager.check_no_data_record_exists(ticker, interval, start_date, "2023-06-04", cooldown_days))

    def test_check_no_data_record_exists_cooldown_zero_or_negative(self):
        """
        測試當 cooldown_days 為 0 或負數時，check_no_data_record_exists 應始終返回 False。
        """
        ticker = "ZERO.COOL"
        interval = "1m"
        start_date = "2023-07-01"
        end_date = "2023-07-01"

        self.db_manager.record_no_data_range(ticker, interval, start_date, end_date)

        self.assertFalse(self.db_manager.check_no_data_record_exists(ticker, interval, start_date, end_date, 0),
                         "cooldown_days 為 0 時應返回 False。")
        self.assertFalse(self.db_manager.check_no_data_record_exists(ticker, interval, start_date, end_date, -5),
                         "cooldown_days 為負數時應返回 False。")

if __name__ == '__main__':
    # 為了讓測試在 apps/daily_market_analyzer 目錄下執行時能找到上層模組
    import sys
    import os
    # 將專案根目錄加入 sys.path
    # 假設 test_db_manager.py 在 apps/daily_market_analyzer/
    # 專案根目錄是向上兩層
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # 重新匯入 DBManager 以確保路徑正確 (如果需要)
    # from apps.daily_market_analyzer.db_manager import DBManager

    unittest.main()
