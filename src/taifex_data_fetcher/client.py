import csv
import io
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

class TaifexClient:
    """
    用於從台灣期貨交易所 (TAIFEX) 獲取市場數據的客戶端。

    該客戶端可以從 TAIFEX 網站獲取數據，或從本地模擬數據檔案讀取數據。
    獲取的數據將被處理並儲存到指定的 `data_lake` 目錄中。

    使用範例:
        # 使用即時數據
        client = TaifexClient(data_lake_path="data_lake")
        # 使用模擬數據
        # client = TaifexClient(data_lake_path="data_lake", use_mock_data=True, mock_data_path="mock_data")

        # 獲取三大法人籌碼數據
        # institutional_data = client.fetch_institutional_investors(datetime(2025, 7, 8))
        # if institutional_data:
        #     client.save_data(institutional_data, "institutional_investors", datetime(2025, 7, 8))

        # 獲取買賣權比率數據
        # pc_ratio_data = client.fetch_pc_ratio(datetime(2025, 7, 8))
        # if pc_ratio_data:
        #     client.save_data(pc_ratio_data, "pc_ratio", datetime(2025, 7, 8))
    """

    BASE_URL = "https://www.taifex.com.tw/cht/3"
    INSTITUTIONAL_INVESTORS_URL = f"{BASE_URL}/IFutureOptallDataDown"
    PC_RATIO_URL = f"{BASE_URL}/ratioOptionsDailyDown"

    def __init__(self, data_lake_path: str = "data_lake", use_mock_data: bool = False, mock_data_path: str = "mock_data"):
        """
        初始化 TaifexClient。

        Args:
            data_lake_path (str): 儲存數據的 data_lake 目錄路徑。
            use_mock_data (bool): 是否使用模擬數據。預設為 False。
            mock_data_path (str): 模擬數據檔案所在的目錄路徑。預設為 "mock_data"。
        """
        self.data_lake_path = data_lake_path
        self.use_mock_data = use_mock_data
        self.mock_data_path = mock_data_path
        os.makedirs(self.data_lake_path, exist_ok=True)
        if self.use_mock_data and not os.path.isdir(self.mock_data_path):
            raise ValueError(f"模擬數據路徑 {self.mock_data_path} 不存在或不是一個目錄。")

    def _fetch_from_url(self, url: str, params: Dict[str, str]) -> Optional[str]:
        """
        私有輔助方法，用於從指定的 URL 獲取數據。

        Args:
            url (str): 要獲取數據的 URL。
            params (Dict[str, str]): 請求參數。

        Returns:
            Optional[str]: 獲取的 CSV 數據文本，如果請求失敗則返回 None。
        """
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()  # 如果 HTTP 請求返回不成功的狀態碼，則拋出 HTTPError 異常
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"從 URL {url} 獲取數據時發生錯誤: {e}")
            return None

    def _read_mock_data(self, filename: str) -> Optional[str]:
        """
        私有輔助方法，用於從模擬數據檔案讀取數據。

        Args:
            filename (str): 模擬數據檔案的名稱 (例如 "institutional_investors.csv")。

        Returns:
            Optional[str]: 檔案內容文本，如果檔案不存在或讀取失敗則返回 None。
        """
        mock_file_path = os.path.join(self.mock_data_path, filename)
        try:
            with open(mock_file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print(f"模擬數據檔案 {mock_file_path} 未找到。")
            return None
        except IOError as e:
            print(f"讀取模擬數據檔案 {mock_file_path} 時發生錯誤: {e}")
            return None

    def _parse_csv_data(self, csv_data: str, expected_headers: List[str]) -> Optional[List[Dict[str, Any]]]:
        """
        私有輔助方法，用於解析 CSV 格式的數據。

        Args:
            csv_data (str): CSV 格式的數據文本。
            expected_headers (List[str]): 預期的 CSV 標頭列表。

        Returns:
            Optional[List[Dict[str, Any]]]: 解析後的數據列表，每個元素是一個字典。如果解析失敗則返回 None。
        """
        try:
            # 使用 StringIO 將字符串數據模擬成檔案對象
            data_io = io.StringIO(csv_data)
            reader = csv.DictReader(data_io)
            # 驗證標頭是否符合預期
            if list(reader.fieldnames) != expected_headers:
                print(f"CSV 標頭與預期不符。預期: {expected_headers}, 實際: {reader.fieldnames}")
                return None
            return list(reader)
        except Exception as e:
            print(f"解析 CSV 數據時發生錯誤: {e}")
            return None

    def fetch_institutional_investors(self, date: datetime) -> Optional[List[Dict[str, Any]]]:
        """
        獲取指定日期的三大法人籌碼數據。

        Args:
            date (datetime): 要獲取數據的日期。

        Returns:
            Optional[List[Dict[str, Any]]]: 解析後的三大法人籌碼數據列表，如果獲取或解析失敗則返回 None。
        """
        formatted_date = date.strftime("%Y/%m/%d")
        csv_data = None

        if self.use_mock_data:
            print(f"正在從模擬檔案讀取三大法人籌碼數據 ({formatted_date})...")
            csv_data = self._read_mock_data("institutional_investors.csv")
        else:
            print(f"正在從 TAIFEX 網站獲取三大法人籌碼數據 ({formatted_date})...")
            params = {
                "queryStartDate": formatted_date,
                "queryEndDate": formatted_date,
                "commodityId": "" # 空白表示所有商品
            }
            # 注意：TAIFEX 的這個下載功能通常直接下載檔案，而不是返回文本。
            # 實際應用中，可能需要調整 _fetch_from_url 或直接使用 requests 下載檔案。
            # 這裡假設它返回 CSV 文本以便與模擬數據流程一致。
            # 根據 TAIFEX 網站的實際行為，這裡的 URL 和參數可能需要調整。
            # 該 URL `INSTITUTIONAL_INVESTORS_URL` (cht/3/IFutureOptallDataDown)
            # 預期是 POST 請求，並且 Content-Type 是 application/x-www-form-urlencoded
            # 為了簡化，我們暫時假設 GET 請求能返回類似 CSV 的數據，或者模擬數據會覆蓋此邏輯。
            # 根據 TAIFEX 網站的實際 CSV 格式，標頭可能需要調整。
            # 這裡的 params 是基於對 TAIFEX 表單的觀察，實際 API 可能不同。
            # 真正的下載連結可能是動態生成的，或者需要特定的 session/cookie。
            # 由於目前指令是不能發送真實網路請求，這裡的網路請求邏輯僅為佔位。
            print("警告：真實網路請求邏輯尚未針對三大法人數據進行完整測試和驗證。")
            # csv_data = self._fetch_from_url(self.INSTITUTIONAL_INVESTORS_URL, params)
            # 由於不能發出網路請求，我們在這裡返回一個提示，如果 use_mock_data 為 False。
            if not self.use_mock_data:
                print("錯誤：目前設定為不使用模擬數據，但網路請求功能受限。請啟用模擬數據或解除網路限制。")
                return None


        if not csv_data:
            return None

        # 模擬數據的標頭
        expected_headers = [
            "日期", "身份別", "多方交易口數", "多方交易契約金額(百萬元)", "空方交易口數",
            "空方交易契約金額(百萬元)", "多空交易口數淨額", "多空交易契約金額淨額(百萬元)",
            "多方未平倉口數", "多方未平倉契約金額(百萬元)", "空方未平倉口數", "空方未平倉契約金額(百萬元)",
            "多空未平倉口數淨額", "多空未平倉契約金額淨額(百萬元)"
        ]
        parsed_data = self._parse_csv_data(csv_data, expected_headers)

        if parsed_data:
            # 進行數據類型轉換和清洗
            for row_idx, row in enumerate(parsed_data):
                for key, value in list(row.items()): # Use list(row.items()) to allow modification
                    if key is None:
                        print(f"警告：在 institutional_investors 的第 {row_idx} 行發現一個 None 的鍵，值為 '{value}'。將忽略此鍵值對。")
                        del row[key] # 或以其他方式處理
                        continue
                    if key == "日期":
                        try:
                            row[key] = pd.to_datetime(value).strftime("%Y-%m-%d")
                        except Exception as e:
                            print(f"警告：日期欄位 '{key}' 值 '{value}' 轉換錯誤: {e}")
                            row[key] = None
                    elif key != "身份別":
                        original_value = value
                        try:
                            if value is None or str(value).strip() == "":
                                row[key] = None
                            else:
                                # 移除千分位逗號並轉換為數字
                                numeric_value = pd.to_numeric(str(value).replace(",", ""))
                                # 將 numpy 數值類型轉換為 Python 原生類型以便 JSON 序列化
                                if pd.api.types.is_integer_dtype(numeric_value):
                                    row[key] = int(numeric_value)
                                elif pd.api.types.is_float_dtype(numeric_value):
                                    row[key] = float(numeric_value)
                                else:
                                    row[key] = numeric_value # 保持原樣 (可能嗎？)
                        except ValueError:
                            print(f"警告：欄位 '{key}' 的值 '{original_value}' 無法轉換為數字。")
                            row[key] = None # 或者保持原樣，或設為特定錯誤標記
            return parsed_data
        return None

    def fetch_pc_ratio(self, date: datetime) -> Optional[List[Dict[str, Any]]]:
        """
        獲取指定日期的買賣權比率數據。

        Args:
            date (datetime): 要獲取數據的日期。

        Returns:
            Optional[List[Dict[str, Any]]]: 解析後的買賣權比率數據列表，如果獲取或解析失敗則返回 None。
        """
        formatted_date = date.strftime("%Y/%m/%d")
        csv_data = None

        if self.use_mock_data:
            print(f"正在從模擬檔案讀取買賣權比率數據 ({formatted_date})...")
            csv_data = self._read_mock_data("pc_ratio.csv")
        else:
            print(f"正在從 TAIFEX 網站獲取買賣權比率數據 ({formatted_date})...")
            params = {
                "queryStartDate": formatted_date,
                "queryEndDate": formatted_date,
            }
            # 同樣，這裡的網路請求邏輯僅為佔位。
            print("警告：真實網路請求邏輯尚未針對買賣權比率數據進行完整測試和驗證。")
            # csv_data = self._fetch_from_url(self.PC_RATIO_URL, params)
            if not self.use_mock_data:
                print("錯誤：目前設定為不使用模擬數據，但網路請求功能受限。請啟用模擬數據或解除網路限制。")
                return None

        if not csv_data:
            return None

        # 模擬數據的標頭
        expected_headers = [
            "日期", "賣權成交量", "買權成交量", "買賣權成交量比率%",
            "賣權未平倉量", "買權未平倉量", "買賣權未平倉量比率%"
        ]
        parsed_data = self._parse_csv_data(csv_data, expected_headers)

        if parsed_data:
            # 進行數據類型轉換和清洗
            for row_idx, row in enumerate(parsed_data):
                for key, value in list(row.items()): # Use list(row.items()) to allow modification
                    if key is None:
                        print(f"警告：在 pc_ratio 的第 {row_idx} 行發現一個 None 的鍵，值為 '{value}'。將忽略此鍵值對。")
                        del row[key] # 或以其他方式處理
                        continue
                    if key == "日期":
                        try:
                            row[key] = pd.to_datetime(value).strftime("%Y-%m-%d")
                        except Exception as e:
                            print(f"警告：日期欄位 '{key}' 值 '{value}' 轉換錯誤: {e}")
                            row[key] = None
                    elif value is None or str(value).strip() == "":
                        # 對於空值或僅包含空白的字符串，直接設為 None
                        # 這也包括了原本 `value == ""` 的情況
                        row[key] = None
                    else:
                        original_value = value
                        try:
                            cleaned_value = str(value).replace(",", "")
                            # 百分比欄位和其他數值欄位都嘗試轉換為數字
                            numeric_value = pd.to_numeric(cleaned_value)
                            # 將 numpy 數值類型轉換為 Python 原生類型以便 JSON 序列化
                            if pd.api.types.is_integer_dtype(numeric_value):
                                row[key] = int(numeric_value)
                            elif pd.api.types.is_float_dtype(numeric_value):
                                row[key] = float(numeric_value)
                            else:
                                # 如果 pd.to_numeric 返回了非 float/int 的東西 (例如 Decimal，但不常見)
                                # 或者無法判斷的類型，則先嘗試轉換為 float，不行就保持原樣
                                try:
                                    row[key] = float(numeric_value)
                                except (TypeError, ValueError):
                                    row[key] = numeric_value # Fallback
                        except ValueError:
                            print(f"警告：欄位 '{key}' 的值 '{original_value}' 無法轉換為數字。")
                            row[key] = None
            return parsed_data
        return None

    def save_data(self, data: List[Dict[str, Any]], data_type: str, date: datetime) -> None:
        """
        將獲取的數據儲存到 data_lake。

        數據將儲存到 `self.data_lake_path` 下以日期命名的子目錄中。
        檔案名稱將是 `data_type.json` (例如 `institutional_investors.json`)。

        Args:
            data (List[Dict[str, Any]]): 要儲存的數據列表。
            data_type (str): 數據的類型 (例如 "institutional_investors", "pc_ratio")。
            date (datetime): 數據對應的日期。
        """
        if not data:
            print(f"沒有數據可供儲存 ({data_type} for {date.strftime('%Y-%m-%d')})。")
            return

        date_str = date.strftime("%Y-%m-%d")
        output_dir = os.path.join(self.data_lake_path, date_str)
        os.makedirs(output_dir, exist_ok=True)

        file_path = os.path.join(output_dir, f"{data_type}.json")

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"數據已成功儲存到 {file_path}")
        except IOError as e:
            print(f"儲存數據到 {file_path} 時發生錯誤: {e}")
        except TypeError as e:
            print(f"序列化數據時發生錯誤 (可能是數據中包含無法JSON序列化的類型): {e}")

if __name__ == '__main__':
    # 建立一個範例 TaifexClient 並使用模擬數據
    print("初始化 TaifexClient (使用模擬數據)...")
    # 假設 mock_data 目錄與 client.py 在同一層級的父目錄下
    # 即執行時，工作目錄是 taifex-data-platform，則 mock_data 路徑應為 "mock_data"
    # 如果 client.py 是從 src/taifex_data_fetcher/ 直接執行，mock_data 路徑應為 "../../mock_data"
    # 為了讓 main 中的測試更可靠，我們假定執行時的工作目錄是專案根目錄
    client = TaifexClient(use_mock_data=True, mock_data_path="mock_data", data_lake_path="data_lake")

    target_date = datetime(2025, 7, 8)

    print("\n--- 測試獲取三大法人籌碼數據 ---")
    institutional_data = client.fetch_institutional_investors(target_date)
    if institutional_data:
        print("成功獲取並解析三大法人籌碼數據:")
        for row in institutional_data:
            print(row)
        client.save_data(institutional_data, "institutional_investors", target_date)
    else:
        print("獲取三大法人籌碼數據失敗。")

    print("\n--- 測試獲取買賣權比率數據 ---")
    pc_ratio_data = client.fetch_pc_ratio(target_date)
    if pc_ratio_data:
        print("成功獲取並解析買賣權比率數據:")
        for row in pc_ratio_data:
            print(row)
        client.save_data(pc_ratio_data, "pc_ratio", target_date)
    else:
        print("獲取買賣權比率數據失敗。")

    print("\n--- 測試 data_lake 內容 ---")
    expected_institutional_file = os.path.join("data_lake", target_date.strftime("%Y-%m-%d"), "institutional_investors.json")
    if os.path.exists(expected_institutional_file):
        print(f"檔案 {expected_institutional_file} 已建立。")
        with open(expected_institutional_file, "r", encoding="utf-8") as f:
            saved_institutional_data = json.load(f)
            # 簡單比較長度
            if institutional_data and len(saved_institutional_data) == len(institutional_data):
                 print("儲存的三大法人數據長度與原始解析數據一致。")
            else:
                 print("儲存的三大法人數據長度與原始解析數據不一致。")

    expected_pc_ratio_file = os.path.join("data_lake", target_date.strftime("%Y-%m-%d"), "pc_ratio.json")
    if os.path.exists(expected_pc_ratio_file):
        print(f"檔案 {expected_pc_ratio_file} 已建立。")
        with open(expected_pc_ratio_file, "r", encoding="utf-8") as f:
            saved_pc_data = json.load(f)
            if pc_ratio_data and len(saved_pc_data) == len(pc_ratio_data):
                 print("儲存的買賣權比率數據長度與原始解析數據一致。")
            else:
                 print("儲存的買賣權比率數據長度與原始解析數據不一致。")

    print("\n--- 測試使用不存在的模擬數據檔案 ---")
    # 暫時修改 mock_data_path 來觸發錯誤，或直接嘗試讀取不存在的檔案
    # 這裡我們直接嘗試讀取一個不存在的 mock file
    class TempClientNoMock(TaifexClient):
        def _read_mock_data(self, filename: str) -> Optional[str]:
            if filename == "non_existent_file.csv":
                 return super()._read_mock_data("non_existent_file.csv") # 觸發 FileNotFoundError
            return super()._read_mock_data(filename)

    temp_client = TempClientNoMock(use_mock_data=True, mock_data_path="mock_data")
    print("嘗試獲取不存在的模擬數據...")
    non_existent_data = temp_client._read_mock_data("non_existent_file.csv") # 內部方法調用，僅為測試
    if non_existent_data is None:
        print("成功處理不存在的模擬數據檔案 (返回 None)。")
    else:
        print("處理不存在的模擬數據檔案失敗。")


    print("\n--- 測試初始化時模擬數據路徑不存在 ---")
    try:
        client_invalid_mock_path = TaifexClient(use_mock_data=True, mock_data_path="non_existent_mock_data_path")
        print("初始化 TaifexClient 時未檢測到無效的 mock_data_path。")
    except ValueError as e:
        print(f"成功捕捉到無效的 mock_data_path: {e}")

    print("\n--- 測試網路請求（目前應受限並提示） ---")
    live_client = TaifexClient(use_mock_data=False)
    print("嘗試獲取三大法人數據 (非模擬)...")
    live_client.fetch_institutional_investors(target_date)
    print("嘗試獲取買賣權比率數據 (非模擬)...")
    live_client.fetch_pc_ratio(target_date)
    print("\n測試完成。")
