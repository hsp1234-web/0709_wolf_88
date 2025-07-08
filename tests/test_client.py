import unittest
import os
import shutil
import io
import json # <--- 匯入 json
import numpy as np # <--- 匯入 numpy (雖然類型檢查改為原生，但保留以防萬一其他地方用到)
from datetime import datetime
from unittest.mock import patch, mock_open

from src.taifex_data_fetcher.client import TaifexClient

class TestTaifexClientMockData(unittest.TestCase):
    """
    測試 TaifexClient 使用模擬數據時的行為。
    """
    # 使用相對於測試檔案的路徑，使其更可靠
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    MOCK_DATA_PATH = os.path.join(BASE_DIR, "test_mock_data_files")
    DATA_LAKE_PATH = os.path.join(BASE_DIR, "test_data_lake_files")

    INSTITUTIONAL_INVESTORS_MOCK_CONTENT = """日期,身份別,多方交易口數,多方交易契約金額(百萬元),空方交易口數,空方交易契約金額(百萬元),多空交易口數淨額,多空交易契約金額淨額(百萬元),多方未平倉口數,多方未平倉契約金額(百萬元),空方未平倉口數,空方未平倉契約金額(百萬元),多空未平倉口數淨額,多空未平倉契約金額淨額(百萬元)
2025/07/08,自營商,266543,51886,240474,51465,26069,421,302016,101867,183199,43319,118817,58548
2025/07/08,投信,1357,3511,2647,8580,-1290,-5069,55561,213816,14379,57387,41182,156429
2025/07/08,外資及陸資,442679,367852,424911,334839,17768,33013,154210,139387,538032,416068,-383822,-276681
"""
    PC_RATIO_MOCK_CONTENT = """日期,賣權成交量,買權成交量,買賣權成交量比率%,賣權未平倉量,買權未平倉量,買賣權未平倉量比率%
2025/07/08,341931,385728,88.65,161864,150408,107.62,
"""

    @classmethod
    def setUpClass(cls):
        """在所有測試開始前，建立模擬數據目錄和檔案。"""
        os.makedirs(cls.MOCK_DATA_PATH, exist_ok=True)
        with open(os.path.join(cls.MOCK_DATA_PATH, "institutional_investors.csv"), "w", encoding="utf-8") as f:
            f.write(cls.INSTITUTIONAL_INVESTORS_MOCK_CONTENT)
        with open(os.path.join(cls.MOCK_DATA_PATH, "pc_ratio.csv"), "w", encoding="utf-8") as f:
            f.write(cls.PC_RATIO_MOCK_CONTENT)
        os.makedirs(cls.DATA_LAKE_PATH, exist_ok=True)


    @classmethod
    def tearDownClass(cls):
        """在所有測試結束後，移除模擬數據目錄和 data_lake 目錄。"""
        if os.path.exists(cls.MOCK_DATA_PATH):
            shutil.rmtree(cls.MOCK_DATA_PATH)
        if os.path.exists(cls.DATA_LAKE_PATH):
            shutil.rmtree(cls.DATA_LAKE_PATH)

    def setUp(self):
        """每個測試方法執行前呼叫。"""
        self.client = TaifexClient(
            use_mock_data=True,
            mock_data_path=self.MOCK_DATA_PATH,
            data_lake_path=self.DATA_LAKE_PATH
        )
        self.test_date = datetime(2025, 7, 8)

    @patch('requests.get')
    def test_fetch_institutional_investors_mock_data(self, mock_requests_get):
        """測試使用模擬數據獲取三大法人籌碼。"""
        data = self.client.fetch_institutional_investors(self.test_date)
        mock_requests_get.assert_not_called()  # 確保沒有發出網路請求
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]["身份別"], "自營商")
        self.assertEqual(data[0]["多方交易口數"], 266543)
        self.assertIsInstance(data[0]["多方交易口數"], int) # 已改為原生 int
        self.assertEqual(data[1]["身份別"], "投信")
        self.assertEqual(data[2]["多空未平倉契約金額淨額(百萬元)"], -276681)
        self.assertIsInstance(data[2]["多空未平倉契約金額淨額(百萬元)"], int) # 已改為原生 int
        self.assertEqual(data[0]["日期"], "2025-07-08")


    @patch('requests.get')
    def test_fetch_pc_ratio_mock_data(self, mock_requests_get):
        """測試使用模擬數據獲取買賣權比率。"""
        data = self.client.fetch_pc_ratio(self.test_date)
        mock_requests_get.assert_not_called() # 確保沒有發出網路請求
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["賣權成交量"], 341931)
        self.assertIsInstance(data[0]["賣權成交量"], int) # 已改為原生 int
        self.assertEqual(data[0]["買權成交量"], 385728)
        self.assertIsInstance(data[0]["買權成交量"], int) # 已改為原生 int
        self.assertEqual(data[0]["買賣權成交量比率%"], 88.65)
        self.assertIsInstance(data[0]["買賣權成交量比率%"], float) # 已改為原生 float
        self.assertEqual(data[0]["買賣權未平倉量比率%"], 107.62)
        self.assertIsInstance(data[0]["買賣權未平倉量比率%"], float) # 已改為原生 float
        self.assertEqual(data[0]["日期"], "2025-07-08")
        # 檢查 CSV 中最後一欄的空值是否被正確處理為 None
        # 在我們的模擬數據中，pc_ratio.csv 最後一個欄位 '買賣權未平倉量比率%' 後面有一個逗號，
        # 這會導致 DictReader 將其後的空字串視為一個欄位的值（如果欄位名存在的話）
        # 或者如果欄位名不足，則可能報錯或忽略。
        # 在目前的 client._parse_csv_data 和 fetch_pc_ratio 中，
        # 我們是基於 expected_headers 來解析的，對於 pc_ratio.csv，
        # "買賣權未平倉量比率%" 是最後一個預期標頭。
        # 黃金數據的 pc_ratio.csv 在 "107.62" 後面有一個逗號，這意味著該行在技術上有一個額外的空欄位。
        # csv.DictReader 會忽略這個額外的欄位，因為它沒有對應的標頭。
        # 因此，我們不需要特別處理這個尾隨逗號導致的空值，除非它位於預期欄位內。
        # 我們的清洗邏輯 `elif value == "" and key.endswith("%"): row[key] = None`
        # 以及 `elif value == "": row[key] = None` 會處理欄位內部的空字串。

    def test_fetch_institutional_investors_file_not_found(self):
        """測試當三大法人模擬數據檔案不存在時的行為。"""
        # 暫時移除檔案來模擬檔案不存在的情況
        original_path = os.path.join(self.MOCK_DATA_PATH, "institutional_investors.csv")
        temp_path = os.path.join(self.MOCK_DATA_PATH, "institutional_investors_temp.csv")
        os.rename(original_path, temp_path)

        data = self.client.fetch_institutional_investors(self.test_date)
        self.assertIsNone(data)

        # 還原檔案
        os.rename(temp_path, original_path)

    def test_fetch_pc_ratio_file_not_found(self):
        """測試當買賣權比率模擬數據檔案不存在時的行為。"""
        original_path = os.path.join(self.MOCK_DATA_PATH, "pc_ratio.csv")
        temp_path = os.path.join(self.MOCK_DATA_PATH, "pc_ratio_temp.csv")
        os.rename(original_path, temp_path)

        data = self.client.fetch_pc_ratio(self.test_date)
        self.assertIsNone(data)

        os.rename(temp_path, original_path)

    def test_init_invalid_mock_data_path(self):
        """測試初始化時若 use_mock_data 為 True 但 mock_data_path 指向一個檔案，應拋出 FileExistsError。"""
        # 創建一個臨時檔案作為無效的 mock_data_path
        # self.DATA_LAKE_PATH 是在 setUpClass 中創建的臨時目錄
        invalid_path_as_file = os.path.join(self.DATA_LAKE_PATH, "i_am_a_file.txt")
        with open(invalid_path_as_file, "w") as f:
            f.write("This is a file, not a directory for mock data.")

        # TaifexClient 的 __init__ 中 self.mock_data_path.mkdir(parents=True, exist_ok=True)
        # 如果 mock_data_path 是一個檔案，mkdir 會拋出 FileExistsError。
        with self.assertRaises(FileExistsError):
            TaifexClient(use_mock_data=True, mock_data_path=invalid_path_as_file)

        # 清理創建的臨時檔案
        if os.path.exists(invalid_path_as_file):
            os.remove(invalid_path_as_file)

    @patch('src.taifex_data_fetcher.client.TaifexClient._fetch_from_url')
    def test_fetch_live_data_restricted(self, mock_fetch_from_url):
        """測試在 use_mock_data 為 False 時，獲取數據會因網路限制而返回 None。"""
        live_client = TaifexClient(use_mock_data=False, data_lake_path=self.DATA_LAKE_PATH)

        # 模擬 _fetch_from_url 因為網路限制不實際執行而是返回 None
        # (在目前的 client 實作中，若 use_mock_data=False，它會直接印出錯誤並返回None，不會呼叫 _fetch_from_url)
        # 因此，我們檢查 print 輸出或者直接看 fetch_* 方法的返回。
        # 為了更精確地測試"不發出網路請求"，我們保持 mock_requests_get

        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            data_inst = live_client.fetch_institutional_investors(self.test_date)
            self.assertIsNone(data_inst)
            self.assertIn("錯誤：目前設定為不使用模擬數據，但網路請求功能受限。", mock_stdout.getvalue())

        mock_fetch_from_url.assert_not_called() # 確保 _fetch_from_url (我們的網路層) 沒有被呼叫

        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            data_pc = live_client.fetch_pc_ratio(self.test_date)
            self.assertIsNone(data_pc)
            self.assertIn("錯誤：目前設定為不使用模擬數據，但網路請求功能受限。", mock_stdout.getvalue())

        mock_fetch_from_url.assert_not_called()

    def test_parse_csv_malformed_header(self):
        """測試解析 CSV 時標頭不符預期的情況。"""
        malformed_csv_data = "日期,錯誤標頭1,錯誤標頭2\n2025/07/08,val1,val2"
        expected_headers = ["日期", "正確標頭1", "正確標頭2"]
        # 直接測試私有方法 _parse_csv_data
        # 需要一個 client 實例來呼叫它
        parsed_data = self.client._parse_csv_data(malformed_csv_data, expected_headers)
        self.assertIsNone(parsed_data)

    def test_parse_csv_data_type_conversion(self):
        """測試數據類型轉換是否正確（例如日期和數字）。"""
        data = self.client.fetch_institutional_investors(self.test_date)
        self.assertIsNotNone(data, "Institutional investors data should not be None")
        self.assertTrue(len(data) > 0, "Institutional investors data should not be empty")
        self.assertIsInstance(data[0]["日期"], str)
        self.assertEqual(data[0]["日期"], "2025-07-08")
        self.assertIsInstance(data[0]["多方交易口數"], int) # 已改為原生 int
        self.assertIsInstance(data[0]["多方交易契約金額(百萬元)"], int) # 已改為原生 int

        pc_data = self.client.fetch_pc_ratio(self.test_date)
        self.assertIsNotNone(pc_data, "PC ratio data should not be None")
        self.assertTrue(len(pc_data) > 0, "PC ratio data should not be empty")
        self.assertIsInstance(pc_data[0]["日期"], str)
        self.assertEqual(pc_data[0]["日期"], "2025-07-08")
        self.assertIsInstance(pc_data[0]["賣權成交量"], int) # 已改為原生 int
        self.assertIsInstance(pc_data[0]["買賣權成交量比率%"], float) # 已改為原生 float

    def test_save_data_creates_file_and_subdir(self):
        """測試 save_data 是否能正確創建子目錄和檔案。"""
        data_to_save = [{"col1": "value1", "col2": 123}]
        data_type = "test_type"
        self.client.save_data(data_to_save, data_type, self.test_date)

        date_str = self.test_date.strftime("%Y-%m-%d")
        expected_dir = os.path.join(self.DATA_LAKE_PATH, date_str)
        expected_file = os.path.join(expected_dir, f"{data_type}.json")

        self.assertTrue(os.path.isdir(expected_dir), "日期子目錄未創建。")
        self.assertTrue(os.path.isfile(expected_file), "JSON 檔案未創建。")

        # 驗證檔案內容
        with open(expected_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data, data_to_save)

    def test_save_data_empty_data(self):
        """測試當傳入空數據列表時 save_data 的行為。"""
        empty_data = []
        data_type = "empty_test_type"

        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            self.client.save_data(empty_data, data_type, self.test_date)

        # 驗證沒有創建檔案
        date_str = self.test_date.strftime("%Y-%m-%d")
        expected_dir = os.path.join(self.DATA_LAKE_PATH, date_str) # 目錄可能因為其他測試已存在
        # os.makedirs(expected_dir, exist_ok=True) # 確保目錄存在以便檢查檔案

        # 即使目錄存在，檔案也不應該被創建
        file_path = os.path.join(expected_dir, f"{data_type}.json")
        self.assertFalse(os.path.exists(file_path), "空數據不應創建檔案。")

        # 驗證提示訊息
        self.assertIn(f"沒有數據可供儲存 ({data_type}", mock_stdout.getvalue())

    def test_save_data_with_fetched_data_serialization(self):
        """測試從 fetch_* 方法獲取的數據能被成功序列化並儲存。"""
        # 1. 獲取三大法人數據並儲存
        institutional_data = self.client.fetch_institutional_investors(self.test_date)
        self.assertIsNotNone(institutional_data)
        self.client.save_data(institutional_data, "institutional_investors", self.test_date)

        date_str = self.test_date.strftime("%Y-%m-%d")
        expected_file_inst = os.path.join(self.DATA_LAKE_PATH, date_str, "institutional_investors.json")
        self.assertTrue(os.path.isfile(expected_file_inst))
        with open(expected_file_inst, "r", encoding="utf-8") as f:
            saved_inst_data = json.load(f)
        self.assertEqual(saved_inst_data, institutional_data)
        # 檢查轉換後的類型
        self.assertIsInstance(saved_inst_data[0]["多方交易口數"], int)

        # 2. 獲取買賣權比率數據並儲存
        pc_ratio_data = self.client.fetch_pc_ratio(self.test_date)
        self.assertIsNotNone(pc_ratio_data)
        self.client.save_data(pc_ratio_data, "pc_ratio", self.test_date)

        expected_file_pc = os.path.join(self.DATA_LAKE_PATH, date_str, "pc_ratio.json")
        self.assertTrue(os.path.isfile(expected_file_pc))
        with open(expected_file_pc, "r", encoding="utf-8") as f:
            saved_pc_data = json.load(f)
        self.assertEqual(saved_pc_data, pc_ratio_data)
        self.assertIsInstance(saved_pc_data[0]["賣權成交量"], int)
        self.assertIsInstance(saved_pc_data[0]["買賣權成交量比率%"], float)


if __name__ == '__main__':
    # 需要匯入 json 才能運行 test_save_data_creates_file_and_subdir
    import json
    unittest.main()
