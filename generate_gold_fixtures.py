import os
import shutil
import logging
from io import StringIO
import pandas as pd

# 假設的模組路徑，請根據您的專案結構調整
from prometheus_fire_backend.modules.data_fetcher import TaifexClient
from prometheus_fire_backend.modules.http_client import HttpClient
from prometheus_fire_backend.modules.logger import LogManager # 或者一個簡單的 MockLogger

# --- 配置 ---
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
GOLD_FIXTURES_PATH = os.path.join(PROJECT_ROOT, "prometheus_fire_backend", "tests", "fixtures")
DATA_LAKE_TEMP_PATH = os.path.join(PROJECT_ROOT, "temp_data_lake_for_fixtures") # 臨時的 data_lake

TEST_DATE_STR = "2025-07-08" # 與測試用例一致的日期

# 與 test_api_e2e.py 中一致的模擬 CSV 內容
MOCK_INVESTORS_CSV_CONTENT = (
    "日期,身份別,多方交易口數,多方交易契約金額(百萬元),空方交易口數,空方交易契約金額(百萬元),多空交易口數淨額,多空交易契約金額淨額(百萬元),多方未平倉口數,多方未平倉契約金額(百萬元),空方未平倉口數,空方未平倉契約金額(百萬元),多空未平倉口數淨額,多空未平倉契約金額淨額(百萬元)\n"
    f"{TEST_DATE_STR.replace('-', '/')},自營商,266543,51886,240474,51465,26069,421,302016,101867,183199,43319,118817,58548\n"
    f"{TEST_DATE_STR.replace('-', '/')},投信,1357,3511,2647,8580,-1290,-5069,55561,213816,14379,57387,41182,156429\n"
    f"{TEST_DATE_STR.replace('-', '/')},外資及陸資,442679,367852,424911,334839,17768,33013,154210,139387,538032,416068,-383822,-276681\n"
)

MOCK_PC_RATIO_CSV_CONTENT = (
    "日期,賣權成交量,買權成交量,買賣權成交量比率%,賣權未平倉量,買權未平倉量,買賣權未平倉量比率%\n"
    f"{TEST_DATE_STR.replace('-', '/')},341931,385728,88.65,161864,150408,107.62,\n"
)

# 簡易日誌配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockLogger:
    def log_event(self, *args, **kwargs):
        pass # logger.info(f"MockLog: Event: {args}, Details: {kwargs}")
    def info(self, msg):
        logger.info(msg)
    def warning(self, msg):
        logger.warning(msg)
    def error(self, msg, exc_info=False):
        logger.error(msg, exc_info=exc_info)

def generate_fixture(taifex_client_instance: TaifexClient, data_type: str, date_str: str, mock_csv_content: str, fixture_filename: str):
    """
    使用 TaifexClient 生成指定數據類型的 Parquet 檔案，並將其複製到 fixtures 目錄。
    """
    logger.info(f"開始生成 {data_type} 的黃金基準檔案...")

    # TaifexClient 的 fetch_* 方法會調用 _save_to_data_lake
    # _save_to_data_lake 使用 taifex_client_instance.DATA_LAKE_ROOT
    # 我們需要臨時修改它，或者確保原始路徑存在並從那裡複製

    original_data_lake_root = taifex_client_instance.DATA_LAKE_ROOT
    # 讓 TaifexClient 寫入到一個臨時的、受控的 data_lake 路徑
    temp_data_lake_for_type = os.path.join(DATA_LAKE_TEMP_PATH, "raw", "taifex")
    taifex_client_instance.DATA_LAKE_ROOT = temp_data_lake_for_type

    # 確保臨時 data_lake 子目錄存在
    os.makedirs(os.path.join(temp_data_lake_for_type, data_type), exist_ok=True)

    logger.info(f"TaifexClient 將臨時寫入到: {temp_data_lake_for_type}")

    df = None
    if data_type == "institutional_investors":
        df = taifex_client_instance.fetch_institutional_investors(
            date_str=date_str,
            use_mock_data=True,
            mock_csv_content=mock_csv_content
        )
    elif data_type == "pc_ratio":
        df = taifex_client_instance.fetch_pc_ratio(
            date_str=date_str,
            use_mock_data=True,
            mock_csv_content=mock_csv_content
        )
    else:
        logger.error(f"未知的數據類型: {data_type}")
        # 恢復原始 DATA_LAKE_ROOT
        taifex_client_instance.DATA_LAKE_ROOT = original_data_lake_root
        return

    if df is None or df.empty:
        logger.error(f"從 TaifexClient未能獲取到 {data_type} 的 DataFrame。無法生成基準檔案。")
        taifex_client_instance.DATA_LAKE_ROOT = original_data_lake_root
        return

    # _save_to_data_lake 已經在 fetch_* 內部被調用，檔案應該已經在 temp_data_lake_for_type 中
    # 檔案名是 <date_str>.parquet
    generated_file_path = os.path.join(temp_data_lake_for_type, data_type, f"{date_str}.parquet")

    if not os.path.exists(generated_file_path):
        logger.error(f"預期生成的檔案 {generated_file_path} 未找到！TaifexClient 可能未成功儲存。")
        taifex_client_instance.DATA_LAKE_ROOT = original_data_lake_root
        return

    # 複製到 fixtures 目錄
    destination_path = os.path.join(GOLD_FIXTURES_PATH, fixture_filename)
    try:
        shutil.copy(generated_file_path, destination_path)
        logger.info(f"成功生成並複製 {data_type} 黃金基準檔案到: {destination_path}")
    except Exception as e:
        logger.error(f"複製檔案到 {destination_path} 失敗: {e}")
    finally:
        # 恢復原始 DATA_LAKE_ROOT
        taifex_client_instance.DATA_LAKE_ROOT = original_data_lake_root


if __name__ == "__main__":
    logger.info("開始生成黃金基準 Parquet 檔案...")
    os.makedirs(GOLD_FIXTURES_PATH, exist_ok=True)
    os.makedirs(DATA_LAKE_TEMP_PATH, exist_ok=True) # 創建臨時 data_lake 根目錄

    mock_log_manager = MockLogger() #LogManager(db_path="temp_fixture_gen_logs.sqlite")
    http_client = HttpClient() # 雖然不會真的發請求，但 TaifexClient 需要它

    # 實例化我們正在使用的 TaifexClient
    # 注意：TaifexClient 的 DATA_LAKE_ROOT 預設是 "data_lake/raw/taifex"
    # generate_fixture 會臨時覆蓋它
    client_for_fixtures = TaifexClient(log_manager=mock_log_manager, http_client=http_client)

    # 生成 institutional_investors 的黃金檔案
    generate_fixture(
        taifex_client_instance=client_for_fixtures,
        data_type="institutional_investors",
        date_str=TEST_DATE_STR,
        mock_csv_content=MOCK_INVESTORS_CSV_CONTENT,
        fixture_filename=f"golden_institutional_investors_{TEST_DATE_STR}.parquet"
    )

    # 生成 pc_ratio 的黃金檔案
    generate_fixture(
        taifex_client_instance=client_for_fixtures,
        data_type="pc_ratio",
        date_str=TEST_DATE_STR,
        mock_csv_content=MOCK_PC_RATIO_CSV_CONTENT,
        fixture_filename=f"golden_pc_ratio_{TEST_DATE_STR}.parquet"
    )

    http_client.close()
    # 如果 LogManager 真的寫了 db，記得 close
    # if isinstance(mock_log_manager, LogManager):
    #     mock_log_manager.close()

    # 清理臨時 data_lake
    try:
        shutil.rmtree(DATA_LAKE_TEMP_PATH)
        logger.info(f"已清理臨時目錄: {DATA_LAKE_TEMP_PATH}")
    except Exception as e:
        logger.error(f"清理臨時目錄 {DATA_LAKE_TEMP_PATH} 失敗: {e}")

    logger.info("黃金基準檔案生成完畢。")
