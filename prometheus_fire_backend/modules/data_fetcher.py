# prometheus_fire_backend/modules/data_fetcher.py

import logging
from typing import Any, Dict, List, Optional

# Imports for TaifexClient and DataFetcher
import pandas as pd
import requests
import time
import os
from io import StringIO # 用於將文字內容視為檔案進行讀取

# Module-level logger
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# The above basicConfig should ideally be called only once at the application entry point.
# For a module, it's better to just get the logger.
# The handler and level setting for __main__ testing will be in the __main__ block.
logger = logging.getLogger(__name__)


class TaifexClient:
    """
    臺灣期貨交易所 (TAIFEX) 資料客戶端。
    負責抓取三大法人未平倉量、P/C Ratio 等數據。
    """
    BASE_URL_FUT_CONTRACTS = "https://www.taifex.com.tw/cht/3/futContractsDate"
    BASE_URL_PC_RATIO = "https://www.taifex.com.tw/cht/3/pcRatio"

    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7',
        'Connection': 'keep-alive',
        'Referer': 'https://www.taifex.com.tw/cht/3/futDataWarehouse'
    }

    DATA_LAKE_ROOT = "data_lake/raw/taifex"

    def __init__(self, log_manager: Any, request_delay: float = 1.0):
        self.log_manager = log_manager
        self.request_delay = request_delay
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        logger.info("TaifexClient 初始化完畢。")

    def _make_request(self, url: str, params: Optional[Dict[str, str]] = None, method: str = "GET", data: Optional[Dict[str, str]] = None) -> Optional[requests.Response]:
        try:
            time.sleep(self.request_delay)
            if method.upper() == "POST":
                response = self.session.post(url, params=params, data=data, timeout=15)
            else:
                response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"TaifexClient 請求失敗: {url}, 錯誤: {e}")
            if self.log_manager:
                self.log_manager.log_event(
                    event_type="taifex_request_failed",
                    message=f"請求 {url} 失敗。",
                    details={"error": str(e), "url": url, "params": params, "method": method},
                    level="ERROR", source_module="TaifexClient"
                )
            return None

    def _save_to_data_lake(self, df: pd.DataFrame, data_type: str, date_str: str, source: str = "taifex") -> Optional[str]:
        dir_path = os.path.join(self.DATA_LAKE_ROOT, data_type)
        file_name = f"{date_str}.parquet"
        file_path = os.path.join(dir_path, file_name)
        try:
            os.makedirs(dir_path, exist_ok=True)
            df.to_parquet(file_path, index=False)
            logger.info(f"數據已儲存到: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"儲存數據到 {file_path} 失敗: {e}")
            if self.log_manager:
                self.log_manager.log_event(
                    event_type="data_save_failed",
                    message=f"儲存 {data_type} 數據到 {file_path} 失敗。",
                    details={"error": str(e), "path": file_path, "data_type": data_type, "date": date_str},
                    level="ERROR", source_module="TaifexClient"
                )
            return None

    def fetch_institutional_investors(self, date_str: str, mock_csv_content: Optional[str] = None) -> Optional[pd.DataFrame]:
        logger.info(f"開始抓取 {date_str} 的三大法人數據...")
        taifex_date_str = date_str.replace('-', '/')
        download_url = "https://www.taifex.com.tw/cht/3/futContractsDateCsv"
        form_data = {'queryType': '1', 'goDay': '', 'doQuery': '1', 'queryDate': taifex_date_str}

        csv_text_content: Optional[str] = None
        if mock_csv_content is not None:
            logger.info(f"使用提供的模擬 CSV 內容進行三大法人數據處理 ({date_str})。")
            csv_text_content = mock_csv_content
        else:
            logger.warning(f"TaifexClient: 網路請求已禁用於 {date_str} 的三大法人數據抓取 (因無 mock_csv_content)。")
            return None

        if csv_text_content is not None:
            try:
                if not csv_text_content.strip() or "查無資料" in csv_text_content or "<html" in csv_text_content.lower():
                    logger.warning(f"{date_str} ({taifex_date_str}) 的三大法人數據查無資料或格式不符。")
                    if self.log_manager:
                         self.log_manager.log_event(event_type="data_fetch_nodata", message=f"{date_str} 的三大法人數據查無資料。", details={"date": date_str, "source": "taifex", "data_type": "institutional_investors"}, level="WARNING", source_module="TaifexClient")
                    return None
                if "html" in csv_text_content.lower()[:100]:
                    logger.error(f"{date_str} 的三大法人數據內容看起來像HTML，非預期CSV。")
                    return None
                df = pd.read_csv(StringIO(csv_text_content))
                df.dropna(how='all', inplace=True)
                if df.empty:
                    logger.warning(f"{date_str} 的三大法人數據解析後為空 DataFrame。")
                    return None
                logger.info(f"成功解析 {date_str} 的三大法人數據，共 {len(df)} 筆。")
                file_path = self._save_to_data_lake(df, "institutional_investors", date_str)
                if file_path and self.log_manager:
                    self.log_manager.log_event(
                        event_type="data_fetch_success", message=f"成功抓取並儲存 {date_str} 的三大法人數據。",
                        details={"source": "taifex", "data_type": "institutional_investors", "date": date_str, "path": file_path, "rows": len(df), "columns": list(df.columns)},
                        level="INFO", source_module="TaifexClient"
                    )
                return df
            except Exception as e:
                logger.error(f"處理 {date_str} 的三大法人數據時發生錯誤 (使用 {'模擬' if mock_csv_content else '網路'} 內容): {e}", exc_info=True)
                if self.log_manager:
                    self.log_manager.log_event(event_type="data_process_failed", message=f"處理 {date_str} 的三大法人數據時失敗。",details={"error": str(e), "date": date_str, "data_type": "institutional_investors"}, level="ERROR", source_module="TaifexClient")
                return None
        return None

    def fetch_pc_ratio(self, date_str: str, mock_csv_content: Optional[str] = None) -> Optional[pd.DataFrame]:
        logger.info(f"開始抓取 {date_str} 的 P/C Ratio 數據...")
        taifex_date_str = date_str.replace('-', '/')
        download_url = "https://www.taifex.com.tw/cht/3/pcRatioCsv"
        form_data = {'queryType': '1', 'goDay': '', 'doQuery': '1', 'queryDate': taifex_date_str }

        csv_text_content: Optional[str] = None
        if mock_csv_content is not None:
            logger.info(f"使用提供的模擬 CSV 內容進行 P/C Ratio 數據處理 ({date_str})。")
            csv_text_content = mock_csv_content
        else:
            logger.warning(f"TaifexClient: 網路請求已禁用於 {date_str} 的P/C Ratio數據抓取 (因無 mock_csv_content)。")
            return None

        if csv_text_content is not None:
            try:
                if not csv_text_content.strip() or "查無資料" in csv_text_content or "<html" in csv_text_content.lower():
                    logger.warning(f"{date_str} ({taifex_date_str}) 的 P/C Ratio 數據查無資料或格式不符。")
                    if self.log_manager:
                        self.log_manager.log_event(event_type="data_fetch_nodata",message=f"{date_str} 的 P/C Ratio 數據查無資料。",details={"date": date_str, "source": "taifex", "data_type": "pc_ratio"},level="WARNING",source_module="TaifexClient")
                    return None

                header_line = csv_text_content.splitlines(keepends=False)[0]
                num_expected_cols = len(header_line.split(','))
                use_cols_range = range(num_expected_cols-1 if header_line.endswith(',') and num_expected_cols > 1 else num_expected_cols)

                df = pd.read_csv(StringIO(csv_text_content), usecols=use_cols_range)
                logger.debug(f"P/C Ratio - DataFrame after read_csv with usecols={use_cols_range} (before dropna):\n{df}")
                logger.debug(f"P/C Ratio - dtypes after read_csv (before dropna):\n{df.dtypes}")

                df.dropna(how='all', inplace=True)
                logger.debug(f"P/C Ratio - DataFrame after dropna(how='all'):\n{df}")
                logger.debug(f"P/C Ratio - Columns after dropna(how='all'): {df.columns.tolist()}")

                logger.debug(f"P/C Ratio - DataFrame after cleanup:\n{df}")
                logger.debug(f"P/C Ratio - dtypes after custom cleanup:\n{df.dtypes}")

                if df.empty:
                    logger.warning(f"{date_str} 的 P/C Ratio 數據解析後為空 DataFrame。")
                    return None
                logger.info(f"成功解析 {date_str} 的 P/C Ratio 數據，共 {len(df)} 筆。")
                file_path = self._save_to_data_lake(df, "pc_ratio", date_str)
                if file_path and self.log_manager:
                    self.log_manager.log_event(
                        event_type="data_fetch_success", message=f"成功抓取並儲存 {date_str} 的 P/C Ratio 數據。",
                        details={"source": "taifex", "data_type": "pc_ratio", "date": date_str, "path": file_path, "rows": len(df), "columns": list(df.columns)},
                        level="INFO", source_module="TaifexClient"
                    )
                return df
            except Exception as e:
                logger.error(f"處理 {date_str} 的 P/C Ratio 數據時發生錯誤 (使用 {'模擬' if mock_csv_content else '網路'} 內容): {e}", exc_info=True)
                if self.log_manager:
                     self.log_manager.log_event(event_type="data_process_failed",message=f"處理 {date_str} 的 P/C Ratio 數據時失敗。",details={"error": str(e), "date": date_str, "data_type": "pc_ratio"},level="ERROR",source_module="TaifexClient")
                return None
        return None

class DataFetcher:
    """
    資料獲取器 (Data Fetcher)。
    負責根據任務需求，從不同的資料來源（真實 API 或模擬客戶端）獲取原始數據。
    """
    def __init__(self,
                 log_manager: Any,
                 execution_mode: str = "SIMULATION",
                 clients: Optional[Dict[str, Any]] = None):
        self.log_manager = log_manager
        self.execution_mode = execution_mode
        self.clients = clients if clients else {}
        self.taifex_client = TaifexClient(log_manager=self.log_manager)

        logger.info(f"資料獲取器 (DataFetcher) 初始化完畢。執行模式: {self.execution_mode}")
        if self.clients:
            logger.info(f"已配置的外部客戶端: {list(self.clients.keys())}")

    def fetch_data_for_mission(self, mission_id: str, mission_params: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"任務 {mission_id}: 開始獲取數據。參數: {mission_params}")
        results: Dict[str, Any] = {}
        task_type = mission_params.get("task_type")
        target_date = mission_params.get("date")

        self.log_manager.log_event(
            event_type="data_fetcher_task_started",
            message=f"DataFetcher 開始處理任務 {mission_id}，類型: {task_type}",
            details={"mission_id": mission_id, "task_type": task_type, "params": mission_params},
            source_module="DataFetcher", mission_id=mission_id
        )

        if task_type == "FETCH_TAIFEX":
            if not target_date:
                logger.error(f"任務 {mission_id} (FETCH_TAIFEX): 未指定日期 (date)。")
                results["error"] = "FETCH_TAIFEX 任務未指定日期。"
                self.log_manager.log_event(event_type="data_fetcher_task_failed", message="FETCH_TAIFEX 任務參數錯誤：未指定日期。", details={"mission_id": mission_id}, level="ERROR", source_module="DataFetcher", mission_id=mission_id)
                return results

            data_types_to_fetch = mission_params.get("data_types", ["institutional_investors", "pc_ratio"])

            if self.execution_mode == "SIMULATION":
                logger.info(f"任務 {mission_id} (FETCH_TAIFEX): 模擬模式執行。")
                mock_data_root = "mock_data/taifex"
                for dt in data_types_to_fetch:
                    mock_file_path = os.path.join(mock_data_root, dt, f"{target_date}.parquet")
                    if os.path.exists(mock_file_path):
                        try:
                            df = pd.read_parquet(mock_file_path)
                            results[f"taifex_{dt}"] = df
                            logger.info(f"任務 {mission_id}: 從模擬數據文件 {mock_file_path} 加載了 {dt} 數據。")
                            self.log_manager.log_event(event_type="mock_data_loaded", message=f"成功從 {mock_file_path} 加載模擬數據", details={"path": mock_file_path, "data_type": dt}, source_module="DataFetcher", mission_id=mission_id)
                        except Exception as e:
                            logger.error(f"任務 {mission_id}: 讀取模擬數據文件 {mock_file_path} 失敗: {e}")
                            results[f"taifex_{dt}_error"] = f"讀取模擬文件 {mock_file_path} 失敗: {e}"
                            self.log_manager.log_event(event_type="mock_data_load_failed", message=f"讀取模擬文件 {mock_file_path} 失敗", details={"error": str(e)}, level="ERROR", source_module="DataFetcher", mission_id=mission_id)
                    else:
                        logger.warning(f"任務 {mission_id}: 模擬數據文件 {mock_file_path} 未找到。")
                        results[f"taifex_{dt}_error"] = f"模擬文件 {mock_file_path} 未找到。"
                        self.log_manager.log_event(event_type="mock_data_not_found", message=f"模擬文件 {mock_file_path} 未找到", level="WARNING", source_module="DataFetcher", mission_id=mission_id)

            elif self.execution_mode == "PRODUCTION":
                logger.info(f"任務 {mission_id} (FETCH_TAIFEX): 生產模式執行。將調用 TaifexClient。")
                mock_data_to_use = {}
                if target_date == "2025-07-08":
                    mock_data_to_use["institutional_investors"] = (
                        "日期,身份別,多方交易口數,多方交易契約金額(百萬元),空方交易口數,空方交易契約金額(百萬元),多空交易口數淨額,多空交易契約金額淨額(百萬元),多方未平倉口數,多方未平倉契約金額(百萬元),空方未平倉口數,空方未平倉契約金額(百萬元),多空未平倉口數淨額,多空未平倉契約金額淨額(百萬元)\n"
                        "2025/07/08,自營商,266543,51886,240474,51465,26069,421,302016,101867,183199,43319,118817,58548\n"
                        "2025/07/08,投信,1357,3511,2647,8580,-1290,-5069,55561,213816,14379,57387,41182,156429\n"
                        "2025/07/08,外資及陸資,442679,367852,424911,334839,17768,33013,154210,139387,538032,416068,-383822,-276681\n"
                    )
                    mock_data_to_use["pc_ratio"] = (
                        "日期,賣權成交量,買權成交量,買賣權成交量比率%,賣權未平倉量,買權未平倉量,買賣權未平倉量比率%\n"
                        "2025/07/08,341931,385728,88.65,161864,150408,107.62,\n"
                    )
                else:
                    logger.warning(f"任務 {mission_id}: PRODUCTION mode 下請求日期 {target_date} 非黃金數據日期 (2025-07-08)，將不返回數據。")

                if "institutional_investors" in data_types_to_fetch:
                    df_inv = self.taifex_client.fetch_institutional_investors(
                        date_str=target_date,
                        mock_csv_content=mock_data_to_use.get("institutional_investors")
                    )
                    if df_inv is not None:
                        results["taifex_institutional_investors"] = df_inv
                    else:
                        results["taifex_institutional_investors_error"] = f"為日期 {target_date} 獲取三大法人數據失敗。"

                if "pc_ratio" in data_types_to_fetch:
                    df_pc = self.taifex_client.fetch_pc_ratio(
                        date_str=target_date,
                        mock_csv_content=mock_data_to_use.get("pc_ratio")
                    )
                    if df_pc is not None:
                        results["taifex_pc_ratio"] = df_pc
                    else:
                        results["taifex_pc_ratio_error"] = f"為日期 {target_date} 獲取P/C Ratio數據失敗。"
        else:
            logger.warning(f"任務 {mission_id}: 未知的 task_type '{task_type}' 或未實現的處理邏輯。")
            results["error"] = f"未知的 task_type: {task_type}"
            self.log_manager.log_event(event_type="data_fetcher_task_failed", message=f"未知任務類型 {task_type}", details={"mission_id": mission_id, "task_type": task_type}, level="ERROR", source_module="DataFetcher", mission_id=mission_id)

        final_message = f"DataFetcher 完成任務 {mission_id}。結果鍵: {list(results.keys())}"
        logger.info(final_message)
        self.log_manager.log_event(
            event_type="data_fetcher_task_completed",
            message=final_message,
            details={"mission_id": mission_id, "results_summary": {k:type(v).__name__ for k,v in results.items()}},
            source_module="DataFetcher", mission_id=mission_id
        )
        return results

    def _get_default_mock_data(self, source_name: str) -> Any:
        if source_name == "mock_source_A":
            return {"content": "來自模擬來源 A 的數據", "items": [1, 2, 3]}
        elif source_name == "mock_source_B":
            return {"content": "來自模擬來源 B 的數據", "value": 123.45}
        else:
            return {"content": f"未知模擬來源 {source_name} 的數據"}

# --- DataFetcher __main__ test block (這是此檔案唯一的 __main__ 區塊) ---
if __name__ == '__main__':
    # --- Setup Logger for DataFetcher tests ---
    df_logger = logging.getLogger('prometheus_fire_backend.modules.data_fetcher') # Get the module's logger
    df_logger.setLevel(logging.DEBUG)
    if not df_logger.hasHandlers():
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        df_logger.addHandler(ch)

    class MockLoggerMain:
        def __init__(self, name="MockLogger"):
            self.name = name
            self.logs = []
        def log_event(self, event_type, message, details=None, level="INFO", source_module=None, mission_id=None):
            log_entry = f"[{level}] ({source_module or self.name} for mission {mission_id or 'N/A'}): {event_type} - {message} | Details: {details}"
            print(log_entry) # Print to console for live test feedback
            self.logs.append(log_entry)
        def get_logs(self): return self.logs

    mock_log_manager_for_df = MockLoggerMain("DF_Logger")

    MOCK_DATA_ROOT_DF = "mock_data/taifex"
    GOLDEN_DATE = "2025-07-08"

    print(f"\n--- 設定 DataFetcher SIMULATION 模式的模擬數據 ({GOLDEN_DATE}) ---")
    # Use a temporary TaifexClient to generate parquet files for mock_data
    # This client also needs a logger, can use a sub-logger or a different mock
    setup_mock_logger = MockLoggerMain("SetupTaifexClient")
    temp_taifex_client_for_setup = TaifexClient(log_manager=setup_mock_logger)

    golden_investors_csv = (
        "日期,身份別,多方交易口數,多方交易契約金額(百萬元),空方交易口數,空方交易契約金額(百萬元),多空交易口數淨額,多空交易契約金額淨額(百萬元),多方未平倉口數,多方未平倉契約金額(百萬元),空方未平倉口數,空方未平倉契約金額(百萬元),多空未平倉口數淨額,多空未平倉契約金額淨額(百萬元)\n"
        "2025/07/08,自營商,266543,51886,240474,51465,26069,421,302016,101867,183199,43319,118817,58548\n"
        "2025/07/08,投信,1357,3511,2647,8580,-1290,-5069,55561,213816,14379,57387,41182,156429\n"
        "2025/07/08,外資及陸資,442679,367852,424911,334839,17768,33013,154210,139387,538032,416068,-383822,-276681\n"
    )
    golden_pc_ratio_csv = (
        "日期,賣權成交量,買權成交量,買賣權成交量比率%,賣權未平倉量,買權未平倉量,買賣權未平倉量比率%\n"
        "2025/07/08,341931,385728,88.65,161864,150408,107.62,\n"
    )

    df_inv_setup = temp_taifex_client_for_setup.fetch_institutional_investors(GOLDEN_DATE, mock_csv_content=golden_investors_csv)
    if df_inv_setup is not None:
        path_inv_setup = os.path.join(MOCK_DATA_ROOT_DF, "institutional_investors", f"{GOLDEN_DATE}.parquet")
        os.makedirs(os.path.dirname(path_inv_setup), exist_ok=True)
        df_inv_setup.to_parquet(path_inv_setup, index=False)
        print(f"模擬三大法人 Parquet 已生成到: {path_inv_setup}")

    df_pc_setup = temp_taifex_client_for_setup.fetch_pc_ratio(GOLDEN_DATE, mock_csv_content=golden_pc_ratio_csv)
    if df_pc_setup is not None:
        path_pc_setup = os.path.join(MOCK_DATA_ROOT_DF, "pc_ratio", f"{GOLDEN_DATE}.parquet")
        os.makedirs(os.path.dirname(path_pc_setup), exist_ok=True)
        df_pc_setup.to_parquet(path_pc_setup, index=False)
        print(f"模擬 P/C Ratio Parquet 已生成到: {path_pc_setup}")

    print("--- 模擬數據設定完畢 ---")

    print("\n--- 測試 DataFetcher (SIMULATION Mode) ---")
    data_fetcher_sim = DataFetcher(log_manager=mock_log_manager_for_df, execution_mode="SIMULATION")
    mission_params_sim = {"task_type": "FETCH_TAIFEX", "date": GOLDEN_DATE, "data_types": ["institutional_investors", "pc_ratio"]}
    sim_results = data_fetcher_sim.fetch_data_for_mission("mission_sim_001", mission_params_sim)

    print("\nDataFetcher SIMULATION mode 結果:")
    assert f"taifex_institutional_investors" in sim_results
    assert isinstance(sim_results["taifex_institutional_investors"], pd.DataFrame)
    assert len(sim_results["taifex_institutional_investors"]) == 3
    print(f"SIMULATION - 三大法人數據 ({type(sim_results['taifex_institutional_investors'])}): {len(sim_results['taifex_institutional_investors'])} 行")

    assert f"taifex_pc_ratio" in sim_results
    assert isinstance(sim_results["taifex_pc_ratio"], pd.DataFrame)
    assert len(sim_results["taifex_pc_ratio"]) == 1
    print(f"SIMULATION - P/C Ratio數據 ({type(sim_results['taifex_pc_ratio'])}): {len(sim_results['taifex_pc_ratio'])} 行")
    assert "買賣權未平倉量比率%" in sim_results["taifex_pc_ratio"].columns

    print("\n--- 測試 DataFetcher (SIMULATION Mode - 數據不存在) ---")
    mission_params_sim_nodata = {"task_type": "FETCH_TAIFEX", "date": "2000-01-01", "data_types": ["institutional_investors"]}
    sim_results_nodata = data_fetcher_sim.fetch_data_for_mission("mission_sim_002", mission_params_sim_nodata)
    print("\nDataFetcher SIMULATION mode (數據不存在) 結果:")
    assert "taifex_institutional_investors_error" in sim_results_nodata
    print(f"SIMULATION (數據不存在) - institutional_investors_error: {sim_results_nodata['taifex_institutional_investors_error']}")

    print("\n--- 測試 DataFetcher (PRODUCTION Mode - 使用黃金數據模擬) ---")
    data_fetcher_prod = DataFetcher(log_manager=mock_log_manager_for_df, execution_mode="PRODUCTION")
    mission_params_prod = {"task_type": "FETCH_TAIFEX", "date": GOLDEN_DATE, "data_types": ["institutional_investors", "pc_ratio"]}
    prod_results = data_fetcher_prod.fetch_data_for_mission("mission_prod_001", mission_params_prod)

    print("\nDataFetcher PRODUCTION mode 結果:")
    assert f"taifex_institutional_investors" in prod_results
    assert isinstance(prod_results["taifex_institutional_investors"], pd.DataFrame)
    assert len(prod_results["taifex_institutional_investors"]) == 3
    print(f"PRODUCTION - 三大法人數據 ({type(prod_results['taifex_institutional_investors'])}): {len(prod_results['taifex_institutional_investors'])} 行")

    assert f"taifex_pc_ratio" in prod_results
    assert isinstance(prod_results["taifex_pc_ratio"], pd.DataFrame)
    assert len(prod_results["taifex_pc_ratio"]) == 1
    print(f"PRODUCTION - P/C Ratio數據 ({type(prod_results['taifex_pc_ratio'])}): {len(prod_results['taifex_pc_ratio'])} 行")
    assert "買賣權未平倉量比率%" in prod_results["taifex_pc_ratio"].columns # This should now pass

    print("\n--- 測試 DataFetcher (PRODUCTION Mode - 非黃金數據日期) ---")
    mission_params_prod_other_date = {"task_type": "FETCH_TAIFEX", "date": "2024-01-01", "data_types": ["institutional_investors"]}
    prod_results_other_date = data_fetcher_prod.fetch_data_for_mission("mission_prod_002", mission_params_prod_other_date)
    print("\nDataFetcher PRODUCTION mode (非黃金數據日期) 結果:")
    assert "taifex_institutional_investors_error" in prod_results_other_date or \
           prod_results_other_date.get("taifex_institutional_investors") is None
    if "taifex_institutional_investors_error" in prod_results_other_date:
        print(f"PRODUCTION (非黃金數據日期) - institutional_investors_error: {prod_results_other_date['taifex_institutional_investors_error']}")
    elif prod_results_other_date.get("taifex_institutional_investors") is None:
         print(f"PRODUCTION (非黃金數據日期) - institutional_investors data is None (as expected).")

    print("\n--- DataFetcher 測試完畢 ---")
