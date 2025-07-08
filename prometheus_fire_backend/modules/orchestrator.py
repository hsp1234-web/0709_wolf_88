# prometheus_fire_backend/modules/orchestrator.py

import logging
from typing import Any, Dict, Optional
from datetime import datetime
from pathlib import Path # <--- 導入 Path

# 引入核心設定
from core.config import PROJECT_ROOT # <--- 導入 PROJECT_ROOT

# 引入 DataFetcher 和 HttpClient
from .data_fetcher import DataFetcher
from .http_client import HttpClient
from .data_fuser import DataFuser # <--- 導入 DataFuser
# from src.taifex_data_fetcher.client import TaifexClient # TaifexClient 現在由 DataFetcher 間接使用

# 配置基本的日誌記錄器
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__) # 改為使用模組級 logger，避免全域 basicConfig 衝突
orchestrator_logger = logging.getLogger(__name__) # 獨立的 logger
if not orchestrator_logger.hasHandlers(): # 避免重複添加 handler
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    orchestrator_logger.addHandler(handler)
    orchestrator_logger.setLevel(logging.INFO)


# 任務狀態常量
MISSION_STATUS_PENDING = "pending"
MISSION_STATUS_PROCESSING = "processing"
MISSION_STATUS_SUCCESS = "SUCCESS" # 與指令中的 SUCCESS 保持一致
MISSION_STATUS_FAILED = "failed"


class MainOrchestrator:
    """
    總調度器 (Main Orchestrator)。
    負責接收任務，編排 data_fetcher、data_fuser 等模組完成整個情報處理流程。
    """
    _mission_states: Dict[str, Dict[str, Any]] = {}

    def __init__(self, log_manager: Any): # <--- 移除 base_path 參數
        """
        初始化總調度器。

        Args:
            log_manager: 日誌管理器實例。
        """
        self.log_manager = log_manager
        self.http_client = HttpClient() # 創建 HttpClient 實例

        # self.project_root = PROJECT_ROOT # <--- 使用導入的 PROJECT_ROOT
        # self.data_lake_path = self.project_root / "data_lake" # <--- 定義 data_lake_path
        # self.mock_data_path = self.project_root / "mock_data" # <--- 定義 mock_data_path

        # 初始化 DataFetcher，傳入 log_manager 和 http_client
        # DataFetcher 內部會處理其自身的路徑需求，基於 PROJECT_ROOT
        # 我們將在 DataFetcher 的重構中處理這一點
        self.data_fetcher = DataFetcher(
            log_manager=self.log_manager,
            http_client=self.http_client,
            execution_mode="ADAPTIVE"
            # project_root=self.project_root # 或者直接將 PROJECT_ROOT 傳給它
        )
        self.data_fuser = DataFuser() # <--- 初始化 DataFuser

        orchestrator_logger.info(f"總調度器 (MainOrchestrator) 初始化完畢。專案根目錄使用: {PROJECT_ROOT}")
        MainOrchestrator._mission_states.clear()


    def start_mission(self, mission_params: Optional[Dict[str, Any]] = None) -> str:
        """
        開始一個新的情報任務。

        Args:
            mission_params: 任務參數字典。預期包含:
                            'type': 任務類型 (e.g., 'fetch_taifex')
                            'data_type': 數據類型 (e.g., 'institutional_investors', 'pc_ratio')
                            'date': 日期字串 'YYYY-MM-DD'
                            (其他參數...)
        Returns:
            str: 代表此任務的唯一 ID。
        """
        mission_id = self._generate_mission_id()

        if not mission_params:
            mission_params = {} # 確保 mission_params 是字典

        mission_id = self._generate_mission_id()

        # 從 API 傳來的 params 中提取 use_mock，預設為 True
        use_mock = mission_params.get("use_mock", True)
        # 處理 data_types
        data_types_param = mission_params.get("data_types")
        single_data_type_param = mission_params.get("data_type")

        final_data_types = []
        if data_types_param: # 如果提供了 data_types 列表
            final_data_types.extend(data_types_param)
        elif single_data_type_param: # 否則，如果提供了單一 data_type
            final_data_types.append(single_data_type_param)

        # 如果都沒有提供，預設抓取兩者 (或根據需求調整)
        if not final_data_types:
            final_data_types = ["institutional_investors", "pc_ratio"]

        # 更新 mission_params 以包含最終的 data_types 和 use_mock，以便 DataFetcher 使用
        internal_mission_params = mission_params.copy() # 創建副本以避免修改原始 API 參數字典
        internal_mission_params["data_types"] = final_data_types
        internal_mission_params["use_mock"] = use_mock # 確保 use_mock 被傳遞

        orchestrator_logger.info(f"任務 {mission_id} 開始。原始參數: {mission_params}, 處理後參數: {internal_mission_params}")
        MainOrchestrator._mission_states[mission_id] = {
            "status": MISSION_STATUS_PENDING,
            "params": internal_mission_params, # 儲存處理後的參數
            "message": "任務已接收，等待處理。",
            "details": {},
            "start_time": datetime.now().isoformat()
        }

        if self.log_manager:
            self.log_manager.log_event(
                event_type="mission_started",
                message=f"任務 {mission_id} 已啟動",
                details={"mission_id": mission_id, "params": internal_mission_params},
                source_module="MainOrchestrator",
                mission_id=mission_id
            )

        mission_type = internal_mission_params.get("type")

        if mission_type == "fetch_taifex":
            self._execute_fetch_taifex_task_with_datafetcher(mission_id, internal_mission_params)
        elif mission_type == "fetch_yfinance":
            self._execute_fetch_yfinance_task_with_datafetcher(mission_id, internal_mission_params)
        elif mission_type == "fuse_data":
            self._execute_fusion_task(mission_id, internal_mission_params)
        else:
            orchestrator_logger.warning(f"任務 {mission_id}: 未知的任務類型 '{mission_type}' 或未提供任務類型。")
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED,
                "message": f"任務失敗：未知的任務類型 '{mission_type}' 或未提供任務類型。",
                "end_time": datetime.now().isoformat()
            })
            if self.log_manager:
                self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} 因未知類型失敗。", details={"type": mission_type}, level="ERROR", mission_id=mission_id)

        return mission_id

    def _execute_fetch_taifex_task_with_datafetcher(self, mission_id: str, params: Dict[str, Any]):
        """使用 DataFetcher 執行獲取台指期數據的子任務。"""
        MainOrchestrator._mission_states[mission_id].update({
            "status": MISSION_STATUS_PROCESSING,
            "message": "正在透過 DataFetcher 處理 fetch_taifex 任務..."
        })
        orchestrator_logger.info(f"任務 {mission_id}: 正在執行 fetch_taifex 任務 (DataFetcher)。參數: {params}")

        date_str = params.get("date")
        data_types_to_fetch = params.get("data_types", [])
        use_mock = params.get("use_mock", True)

        if not date_str:
            orchestrator_logger.error(f"任務 {mission_id}: fetch_taifex 任務缺少 'date' 參數。")
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED,
                "message": "任務失敗：fetch_taifex 任務缺少 'date' 參數。",
                "end_time": datetime.now().isoformat()
            })
            if self.log_manager:
                self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} 因缺少日期參數失敗。", level="ERROR", mission_id=mission_id)
            return

        if not data_types_to_fetch: # Specific to Taifex as it fetches multiple data types
            orchestrator_logger.error(f"任務 {mission_id}: fetch_taifex 任務缺少 'data_types' 參數。")
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED,
                "message": "任務失敗：fetch_taifex 任務缺少 'data_types' 參數。",
                "end_time": datetime.now().isoformat()
            })
            if self.log_manager:
                self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} 因缺少 data_types 參數失敗。", level="ERROR", mission_id=mission_id)
            return

        try:
            fetcher_params = {
                "task_type": "FETCH_TAIFEX",
                "date": date_str,
                "data_types": data_types_to_fetch,
                "use_mock": use_mock
            }
            if use_mock and params.get("mock_data"):
                 fetcher_params["mock_data"] = params["mock_data"]

            fetch_results = self.data_fetcher.fetch_data_for_mission(mission_id, fetcher_params)

            all_successful = True
            errors_found = []
            successful_fetches = {}

            for dt in data_types_to_fetch:
                result_key = f"taifex_{dt}"
                error_key = f"taifex_{dt}_error"
                if result_key in fetch_results and fetch_results[result_key] is not None:
                    successful_fetches[dt] = f"Data for {dt} processed."
                    orchestrator_logger.info(f"任務 {mission_id}: {dt} 數據已由 DataFetcher 處理。")
                else:
                    all_successful = False
                    error_message = fetch_results.get(error_key, f"獲取 {dt} 數據時發生未知問題。")
                    errors_found.append(f"{dt}: {error_message}")
                    orchestrator_logger.warning(f"任務 {mission_id}: DataFetcher 未能成功獲取 {dt} 數據。錯誤: {error_message}")

            if all_successful and not errors_found:
                MainOrchestrator._mission_states[mission_id].update({
                    "status": MISSION_STATUS_SUCCESS,
                    "message": f"任務成功：所有請求的 Taifex 數據 ({', '.join(data_types_to_fetch)}) 已處理。",
                    "details": {"processed_data_types": data_types_to_fetch, "fetch_results_summary": successful_fetches},
                    "end_time": datetime.now().isoformat()
                })
                orchestrator_logger.info(f"任務 {mission_id} (Taifex) 成功完成。")
                if self.log_manager:
                    self.log_manager.log_event(event_type="mission_succeeded", message=f"任務 {mission_id} (Taifex) 成功。", details=successful_fetches, mission_id=mission_id)
            else:
                error_summary = "; ".join(errors_found)
                MainOrchestrator._mission_states[mission_id].update({
                    "status": MISSION_STATUS_FAILED,
                    "message": f"任務 (Taifex) 部分或完全失敗：{error_summary}",
                    "details": {"errors": errors_found, "successful_fetches": successful_fetches if successful_fetches else None},
                    "end_time": datetime.now().isoformat()
                })
                orchestrator_logger.error(f"任務 {mission_id} (Taifex) 失敗或部分失敗。錯誤: {error_summary}")
                if self.log_manager:
                     self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (Taifex) 失敗或部分失敗。", details={"errors": errors_found}, level="ERROR", mission_id=mission_id)

        except Exception as e:
            orchestrator_logger.error(f"任務 {mission_id} (Taifex): 執行 DataFetcher 任務時發生嚴重錯誤: {e}", exc_info=True)
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED,
                "message": f"任務 (Taifex) 失敗：執行 DataFetcher 時發生內部錯誤 - {str(e)}",
                "end_time": datetime.now().isoformat()
            })
            if self.log_manager:
                self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (Taifex) 因 DataFetcher 執行錯誤失敗。", details={"error": str(e)}, level="CRITICAL", mission_id=mission_id)

    def _execute_fetch_yfinance_task_with_datafetcher(self, mission_id: str, params: Dict[str, Any]):
        """使用 DataFetcher 執行獲取 Yahoo Finance OHLCV 數據的子任務。"""
        MainOrchestrator._mission_states[mission_id].update({
            "status": MISSION_STATUS_PROCESSING,
            "message": "正在透過 DataFetcher 處理 fetch_yfinance 任務..."
        })
        orchestrator_logger.info(f"任務 {mission_id}: 正在執行 fetch_yfinance 任務 (DataFetcher)。參數: {params}")

        date_str = params.get("date")
        ticker_symbol = params.get("ticker_symbol")
        use_mock = params.get("use_mock", True)

        if not date_str or not ticker_symbol:
            error_msg = f"任務 {mission_id}: fetch_yfinance 任務缺少 'date' 或 'ticker_symbol' 參數。"
            orchestrator_logger.error(error_msg)
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED,
                "message": f"任務失敗：{error_msg}",
                "end_time": datetime.now().isoformat()
            })
            if self.log_manager:
                self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (YFinance) 因缺少參數失敗。", details={"missing_date": not date_str, "missing_ticker": not ticker_symbol}, level="ERROR", mission_id=mission_id)
            return

        try:
            fetcher_params = {
                "task_type": "FETCH_YFINANCE",
                "date": date_str,
                "ticker_symbol": ticker_symbol,
                "use_mock": use_mock
            }
            if use_mock and params.get("mock_data"):
                 fetcher_params["mock_data"] = params["mock_data"]

            fetch_results = self.data_fetcher.fetch_data_for_mission(mission_id, fetcher_params)

            ticker_symbol_safe = ticker_symbol.replace('.', '_')
            result_key = f"yfinance_ohlcv_{ticker_symbol_safe}"
            error_key = f"yfinance_ohlcv_{ticker_symbol_safe}_error"

            if result_key in fetch_results and fetch_results[result_key] is not None:
                MainOrchestrator._mission_states[mission_id].update({
                    "status": MISSION_STATUS_SUCCESS,
                    "message": f"任務成功：股票 {ticker_symbol} 在 {date_str} 的 OHLCV 數據已處理。",
                    "details": {"ticker_symbol": ticker_symbol, "date": date_str, "result_info": f"DataFrame with {len(fetch_results[result_key])} rows retrieved."},
                    "end_time": datetime.now().isoformat()
                })
                orchestrator_logger.info(f"任務 {mission_id} (YFinance) 成功完成 for {ticker_symbol} on {date_str}.")
                if self.log_manager:
                    self.log_manager.log_event(event_type="mission_succeeded", message=f"任務 {mission_id} (YFinance) for {ticker_symbol} 成功。", details={"ticker": ticker_symbol, "date": date_str}, mission_id=mission_id)
            else:
                error_message = fetch_results.get(error_key, f"獲取 {ticker_symbol} OHLCV 數據時發生未知問題。")
                MainOrchestrator._mission_states[mission_id].update({
                    "status": MISSION_STATUS_FAILED,
                    "message": f"任務 (YFinance) 失敗：{error_message}",
                    "details": {"ticker_symbol": ticker_symbol, "date": date_str, "error": error_message},
                    "end_time": datetime.now().isoformat()
                })
                orchestrator_logger.error(f"任務 {mission_id} (YFinance) 失敗 for {ticker_symbol} on {date_str}. Error: {error_message}")
                if self.log_manager:
                     self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (YFinance) for {ticker_symbol} 失敗。", details={"ticker": ticker_symbol, "date": date_str, "error": error_message}, level="ERROR", mission_id=mission_id)

        except Exception as e:
            orchestrator_logger.error(f"任務 {mission_id} (YFinance): 執行 DataFetcher 任務時發生嚴重錯誤: {e}", exc_info=True)
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED,
                "message": f"任務 (YFinance) 失敗：執行 DataFetcher 時發生內部錯誤 - {str(e)}",
                "end_time": datetime.now().isoformat()
            })
            if self.log_manager:
                self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (YFinance) 因 DataFetcher 執行錯誤失敗。", details={"error": str(e)}, level="CRITICAL", mission_id=mission_id)

    def _execute_fusion_task(self, mission_id: str, params: Dict[str, Any]):
        """執行數據融合子任務。"""
        MainOrchestrator._mission_states[mission_id].update({
            "status": MISSION_STATUS_PROCESSING,
            "message": "正在處理數據融合任務..."
        })
        orchestrator_logger.info(f"任務 {mission_id}: 正在執行數據融合任務。參數: {params}")

        ticker_symbol = params.get("ticker_symbol")
        date_str = params.get("date")
        # API 可能不直接傳遞 data_type_to_fuse，DataFuser.fuse_data 有預設值 "daily_ohlcv"
        data_type_to_fuse = params.get("data_type_to_fuse", "daily_ohlcv")


        if not ticker_symbol or not date_str:
            error_msg = f"任務 {mission_id} (Fusion): 缺少 'ticker_symbol' 或 'date' 參數。"
            orchestrator_logger.error(error_msg)
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED,
                "message": f"任務失敗：{error_msg}",
                "end_time": datetime.now().isoformat()
            })
            if self.log_manager:
                self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (Fusion) 因缺少參數失敗。", details=params, level="ERROR", mission_id=mission_id)
            return

        try:
            golden_record_path = self.data_fuser.fuse_data(
                ticker_symbol=ticker_symbol,
                date_str=date_str,
                data_type_to_fuse=data_type_to_fuse
            )

            if golden_record_path:
                MainOrchestrator._mission_states[mission_id].update({
                    "status": MISSION_STATUS_SUCCESS,
                    "message": f"任務成功：股票 {ticker_symbol} 在 {date_str} 的數據已成功融合。",
                    "details": {
                        "ticker_symbol": ticker_symbol,
                        "date": date_str,
                        "data_type_fused": data_type_to_fuse,
                        "golden_record_path": str(golden_record_path)
                    },
                    "end_time": datetime.now().isoformat()
                })
                orchestrator_logger.info(f"任務 {mission_id} (Fusion) 成功完成 for {ticker_symbol} on {date_str}. 黃金記錄: {golden_record_path}")
                if self.log_manager:
                    self.log_manager.log_event(event_type="mission_succeeded", message=f"任務 {mission_id} (Fusion) for {ticker_symbol} on {date_str} 成功。", details={"path": str(golden_record_path)}, mission_id=mission_id)
            else:
                error_message = f"數據融合失敗 for {ticker_symbol} on {date_str}。DataFuser 未返回有效的黃金記錄路徑。"
                MainOrchestrator._mission_states[mission_id].update({
                    "status": MISSION_STATUS_FAILED,
                    "message": f"任務 (Fusion) 失敗：{error_message}",
                    "details": {"ticker_symbol": ticker_symbol, "date": date_str, "data_type_fused": data_type_to_fuse, "error": "Fusion process did not yield a golden record."},
                    "end_time": datetime.now().isoformat()
                })
                orchestrator_logger.error(f"任務 {mission_id} (Fusion) 失敗 for {ticker_symbol} on {date_str}. {error_message}")
                if self.log_manager:
                     self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (Fusion) for {ticker_symbol} on {date_str} 失敗。", details={"error": error_message}, level="ERROR", mission_id=mission_id)

        except Exception as e:
            orchestrator_logger.error(f"任務 {mission_id} (Fusion): 執行融合任務時發生嚴重錯誤: {e}", exc_info=True)
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED,
                "message": f"任務 (Fusion) 失敗：執行融合時發生內部錯誤 - {str(e)}",
                "end_time": datetime.now().isoformat()
            })
            if self.log_manager:
                self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (Fusion) 因執行錯誤失敗。", details={"error": str(e)}, level="CRITICAL", mission_id=mission_id)


    def get_mission_status(self, mission_id: str) -> Dict[str, Any]:
        """
        獲取指定任務的狀態。
        """
        orchestrator_logger.info(f"查詢任務 {mission_id} 的狀態。")
        if self.log_manager:
            self.log_manager.log_event(
                event_type="status_queried",
                message=f"查詢任務 {mission_id} 狀態",
                details={"mission_id": mission_id},
                source_module="MainOrchestrator",
                mission_id=mission_id
            )
        state = MainOrchestrator._mission_states.get(mission_id)
        if state:
            # 為了符合 MissionStatusResponse，我們需要確保返回的字典結構一致
            return {
                "mission_id": mission_id,
                "status": state.get("status", MISSION_STATUS_FAILED),
                "progress": 1.0 if state.get("status") == MISSION_STATUS_SUCCESS else (0.5 if state.get("status") == MISSION_STATUS_PROCESSING else 0.0),
                "message": state.get("message", "狀態訊息未提供。"),
                "details": state.get("details", {}),
                "start_time": state.get("start_time"), # 確保 start_time 被返回
                "end_time": state.get("end_time") # 確保 end_time 被返回 (如果任務已結束)
            }
        else:
            # 對於不存在的任務，也保持一致的返回結構
            return {
                "mission_id": mission_id,
                "status": MISSION_STATUS_FAILED,
                "progress": 0.0,
                "message": "任務 ID 不存在。",
                "details": {"error": "Mission ID not found."},
                "start_time": None,
                "end_time": datetime.now().isoformat() # 可以標記查詢時間為結束時間
            }


    def _generate_mission_id(self) -> str:
        """
        生成一個唯一的任務 ID。
        """
        import uuid
        return str(uuid.uuid4())

if __name__ == '__main__':
    # 簡易測試 (未來應移至 pytest)
    class MockLogManager:
        # def log_event(self, event_type: str, data: dict): # 舊簽名
        #     orchestrator_logger.info(f"[MockLogManager] 事件: {event_type}, 資料: {data}")

        def log_event(self, event_type: str, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None, source_module: Optional[str] = None, mission_id: Optional[str] = None, level: str = "INFO", raw_request: Optional[str] = None, raw_response: Optional[str] = None):
            log_entry = f"[{level}] ({source_module or 'MockSource'}) Mission ({mission_id or 'N/A'}): {event_type} - {message}. Details: {details}"
            print(log_entry)


    orchestrator_logger.info("--- 測試 MainOrchestrator ---")
    mock_logger_instance = MockLogManager()

    # project_root_for_test = os.path.abspath(os.path.join(current_script_path, "..", "..")) # 改用 PROJECT_ROOT
    # orchestrator = MainOrchestrator(log_manager=mock_logger_instance, base_path=project_root_for_test) # base_path 已移除
    orchestrator = MainOrchestrator(log_manager=mock_logger_instance)


    # data_lake 目錄結構假設由 TaifexClient 內部處理
    # 在這裡創建測試用的目錄時，也應該使用 pathlib 和 PROJECT_ROOT
    # 不過，TaifexClient 的重構會使其自行處理基於 PROJECT_ROOT 的路徑創建
    # DATA_LAKE_TAIFEX_ROOT = PROJECT_ROOT / "data_lake" / "raw" / "taifex" # TaifexClient 會處理
    # (DATA_LAKE_TAIFEX_ROOT / "institutional_investors").mkdir(parents=True, exist_ok=True)
    # (DATA_LAKE_TAIFEX_ROOT / "pc_ratio").mkdir(parents=True, exist_ok=True)
    # 由於 TaifexClient (prometheus_fire_backend/modules/data_fetcher.py 中的版本)
    # 內部有 DATA_LAKE_ROOT = "data_lake/raw/taifex" 並使用 os.makedirs，
    # 這裡暫時不需要手動創建，等待 TaifexClient 重構。
    # 為了讓測試能跑通，我們暫時保留 os.makedirs 但改用 PROJECT_ROOT。
    # 理想情況是 TaifexClient 初始化時就能處理好這些路徑。
    # 暫時保留舊的 os 導入以便 os.makedirs 能運作，之後會清理。
    # import os # <--- TaifexClient 現在會自行創建目錄，此處不再需要手動創建。
    # _test_data_lake_taifex_root = PROJECT_ROOT / "data_lake" / "raw" / "taifex"
    # os.makedirs(_test_data_lake_taifex_root / "institutional_investors", exist_ok=True)
    # os.makedirs(_test_data_lake_taifex_root / "pc_ratio", exist_ok=True)


    mock_investors_csv_content = (
        "日期,身份別,多方交易口數,多方交易契約金額(百萬元),空方交易口數,空方交易契約金額(百萬元),多空交易口數淨額,多空交易契約金額淨額(百萬元),多方未平倉口數,多方未平倉契約金額(百萬元),空方未平倉口數,空方未平倉契約金額(百萬元),多空未平倉口數淨額,多空未平倉契約金額淨額(百萬元)\n"
        "2025/07/08,自營商,1,1,1,1,0,0,1,1,1,1,0,0\n"
    )
    mock_pc_ratio_csv_content = (
        "日期,賣權成交量,買權成交量,買賣權成交量比率%,賣權未平倉量,買權未平倉量,買賣權未平倉量比率%\n"
        "2025/07/08,100,100,100.00,100,100,100.00,\n"
    )

    print("\n--- 測試 1: fetch_taifex - institutional_investors (模擬) ---")
    mission_params_inst_mock = {
        "type": "fetch_taifex", "date": "2025-07-08", "data_types": ["institutional_investors"], "use_mock": True,
        "mock_data": {"institutional_investors_csv": mock_investors_csv_content}
    }
    mission_id_inst_mock = orchestrator.start_mission(mission_params_inst_mock)
    status_inst_mock = orchestrator.get_mission_status(mission_id_inst_mock)
    print(f"任務 {mission_id_inst_mock} 狀態: {status_inst_mock}")
    assert status_inst_mock.get("status") == MISSION_STATUS_SUCCESS

    print("\n--- 測試 2: fetch_taifex - pc_ratio (模擬) ---")
    mission_params_pc_mock = {
        "type": "fetch_taifex", "date": "2025-07-08", "data_types": ["pc_ratio"], "use_mock": True,
        "mock_data": {"pc_ratio_csv": mock_pc_ratio_csv_content}
    }
    mission_id_pc_mock = orchestrator.start_mission(mission_params_pc_mock)
    status_pc_mock = orchestrator.get_mission_status(mission_id_pc_mock)
    print(f"任務 {mission_id_pc_mock} 狀態: {status_pc_mock}")
    assert status_pc_mock.get("status") == MISSION_STATUS_SUCCESS

    print("\n--- 測試 3: fetch_taifex - 真實數據模式 (預期 DataFetcher 內的 TaifexClient 嘗試網路請求) ---")
    # 此測試在無網路或目標網站無數據時，TaifexClient 的 fetch_* 方法應返回 None，
    # DataFetcher 應將此情況標記為錯誤。
    mission_params_live = {
        "type": "fetch_taifex", "date": "2030-01-01", # 未來日期，確保無數據
        "data_types": ["institutional_investors"], "use_mock": False
    }
    mission_id_live = orchestrator.start_mission(mission_params_live)
    status_live = orchestrator.get_mission_status(mission_id_live)
    print(f"任務 {mission_id_live} 狀態: {status_live}")
    assert status_live.get("status") == MISSION_STATUS_FAILED # 預期因無數據而失敗

    print("\n--- 測試 4: 缺少日期 ---")
    mission_params_no_date = {"type": "fetch_taifex", "data_types": ["pc_ratio"], "use_mock": True}
    mission_id_no_date = orchestrator.start_mission(mission_params_no_date)
    status_no_date = orchestrator.get_mission_status(mission_id_no_date)
    print(f"任務 {mission_id_no_date} 狀態: {status_no_date}")
    assert status_no_date.get("status") == MISSION_STATUS_FAILED
    assert "缺少 'date' 參數" in status_no_date.get("message", "")

    orchestrator_logger.info("--- Orchestrator __main__ 測試完畢 ---")

    if hasattr(orchestrator, 'http_client') and orchestrator.http_client:
        orchestrator.http_client.close()
        orchestrator_logger.info("Orchestrator 的 HttpClient 已關閉。")
