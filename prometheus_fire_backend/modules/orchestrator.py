# prometheus_fire_backend/modules/orchestrator.py

import logging
from typing import Any, Dict, Optional, List
from datetime import datetime
from pathlib import Path # <--- 導入 Path
import pandas as pd # <--- 導入 pandas

# 引入核心設定
from core.config import PROJECT_ROOT # <--- 導入 PROJECT_ROOT

# 引入 DataFetcher 和 HttpClient
from .data_fetcher import DataFetcher
from .http_client import HttpClient
from .data_fuser import DataFuser # <--- 導入 DataFuser
from .factor_engine import FactorEngine # <--- 導入 FactorEngine
from .backtester import Backtester # <--- 導入 Backtester
import importlib # <--- 導入 importlib

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
    負責接收任務，編排 data_fetcher、data_fuser、factor_engine 等模組完成整個情報處理流程。
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

        self.data_fetcher = DataFetcher(
            log_manager=self.log_manager,
            http_client=self.http_client,
            execution_mode="ADAPTIVE"
        )
        self.data_fuser = DataFuser() # <--- 初始化 DataFuser
        self.factor_engine = FactorEngine() # <--- 初始化 FactorEngine
        self.backtester = Backtester(log_manager=self.log_manager) # <--- 初始化 Backtester

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
        elif mission_type == "calculate_factors":
            self._execute_factor_calculation_task(mission_id, internal_mission_params)
        elif mission_type == "backtest": # <--- 新增回測任務類型
            self._execute_backtest_task(mission_id, internal_mission_params)
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

    def _execute_factor_calculation_task(self, mission_id: str, params: Dict[str, Any]):
        """執行因子計算子任務。"""
        MainOrchestrator._mission_states[mission_id].update({
            "status": MISSION_STATUS_PROCESSING,
            "message": "正在處理因子計算任務..."
        })
        orchestrator_logger.info(f"任務 {mission_id}: 正在執行因子計算任務。參數: {params}")

        ticker_symbol = params.get("ticker") # API 傳入的是 ticker
        date_str = params.get("date")

        if not ticker_symbol or not date_str:
            error_msg = f"任務 {mission_id} (FactorCalculation): 缺少 'ticker' 或 'date' 參數。"
            orchestrator_logger.error(error_msg)
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED,
                "message": f"任務失敗：{error_msg}",
                "end_time": datetime.now().isoformat()
            })
            if self.log_manager:
                self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (FactorCalculation) 因缺少參數失敗。", details=params, level="ERROR", mission_id=mission_id)
            return

        try:
            # DataFuser 的 golden record 路徑結構為:
            # PROJECT_ROOT / "data_warehouse" / "golden_records" / "daily" / {ticker_symbol} / {date_str}.parquet
            # FactorEngine 的 generate_and_store_daily_factors 預期一個包含多日數據的 DataFrame
            # 因此，我們需要讀取對應股票代號的所有黃金記錄，或者特定日期範圍的。
            # 指令要求 "讀取對應的黃金紀錄"，暗示單一檔案。
            # 然而，因子計算通常需要歷史序列。
            # 假設 FactorEngine 期望的 golden_ohlcv_df 是包含該日期之前足夠歷史數據的 DataFrame。
            # 目前的 DataFuser.fuse_data 只產生單一交易日的黃金紀錄。
            # 這表示我們需要調整策略：
            # 1. 修改 DataFuser 使其能產生包含歷史的黃金紀錄 (超出本次任務範圍)。
            # 2. 讓 FactorEngine 能夠處理單日黃金紀錄，但這會導致許多因子無法計算 (如移動平均)。
            # 3. 假設 "黃金紀錄" 指的是一個包含歷史數據的 Parquet 檔案，其命名可能與 date 有關，但不直接是 date.parquet。
            # 根據 FactorEngine 的 `generate_and_store_daily_factors`，它會迭代輸入 DataFrame 的每一天並儲存。
            # 這意味著輸入給 FactorEngine 的 DataFrame 應該是包含所需歷史數據的。
            # DataFuser 的 `fuse_data` 返回的路徑是 `PROJECT_ROOT / "data_warehouse" / "golden_records" / "daily" / ticker_symbol / f"{date_str}.parquet"`
            # 這個檔案只包含一天的數據。
            #
            # 重新審視指令: "讀取對應的黃金紀錄" -> 這可能指的是一個代表特定分析日期的黃金紀錄 *檔案*，
            # 而這個檔案本身應該包含計算因子所需的歷史數據。
            #
            # 假設黃金紀錄檔案的命名慣例是 `{ticker}_{date}.parquet` 且它包含了到該 `date` 為止的數據。
            # 這個假設需要與 DataFuser 的產出對齊。DataFuser 目前產出 `{date_str}.parquet` 在 `ticker_symbol` 目錄下。
            # 為了簡化，我們先假設黃金紀錄檔案的路徑是 DataFuser 產生的那個，並接受它只包含單日數據的限制。
            # 這將意味著許多因子無法正確計算，除非 FactorEngine 內部有能力去讀取更多歷史數據。
            # FactorEngine 的 `calculate_factors` 確實是基於傳入的 DataFrame 計算。
            #
            # 折衷方案：我們假設 start_factor_calculation_mission 傳入的 date 是 "分析基準日"，
            # 而黃金紀錄檔案是 `{ticker_symbol}_{date_str}_golden.parquet` 這種，它包含了到 date_str 為止的歷史數據。
            # 目前 DataFuser 產生的檔案是 `data_warehouse/golden_records/daily/{ticker_symbol}/{date_str}.parquet`
            # 為了測試，我們將使用這個單日檔案，並觀察結果。
            #
            # 最符合 FactorEngine 設計的黃金紀錄應該是 OHLCV 的歷史序列。
            # DataFetcher 的 `yfinance_ohlcv_{ticker_symbol_safe}` 產生的 Parquet 檔案是每日一個，
            # 但包含從開始到該日期的完整 OHLCV 序列。
            # 例如 `data_lake/processed/yfinance/daily/AAPL_2023-01-01.parquet`
            # 這更像是 FactorEngine 所需的輸入。
            #
            # 指令明確指出 "讀取對應的黃金紀錄"。黃金紀錄由 DataFuser 產生。
            # 所以我們必須使用 DataFuser 產生的檔案。
            # 這意味著 FactorEngine 目前的用法（期望多日數據以計算如SMA）與黃金紀錄的單日特性存在矛盾。
            #
            # 解決方案：遵循指令，讀取 DataFuser 產生的單日黃金紀錄。
            # 這將導致 FactorEngine 的 generate_and_store_daily_factors 只處理那一天，
            # 且移動平均等因子在那一天將是 NaN。
            # 這可能是預期行為，或者需要在後續階段改進 FactorEngine 或黃金紀錄的生成。

            golden_record_dir = PROJECT_ROOT / "data_warehouse" / "golden_records" / "daily" / ticker_symbol
            golden_record_path = golden_record_dir / f"{date_str}.parquet"

            if not golden_record_path.exists():
                error_msg = f"任務 {mission_id} (FactorCalculation): 黃金紀錄檔案不存在: {golden_record_path}"
                orchestrator_logger.error(error_msg)
                MainOrchestrator._mission_states[mission_id].update({
                    "status": MISSION_STATUS_FAILED,
                    "message": f"任務失敗：{error_msg}",
                    "end_time": datetime.now().isoformat()
                })
                if self.log_manager:
                    self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (FactorCalculation) 失敗，黃金紀錄不存在。", details={"path": str(golden_record_path)}, level="ERROR", mission_id=mission_id)
                return

            orchestrator_logger.info(f"任務 {mission_id}: 正在從 {golden_record_path} 讀取黃金紀錄...")
            golden_ohlcv_df = pd.read_parquet(golden_record_path)

            if golden_ohlcv_df.empty:
                error_msg = f"任務 {mission_id} (FactorCalculation): 從 {golden_record_path} 讀取的黃金紀錄為空。"
                orchestrator_logger.warning(error_msg)
                MainOrchestrator._mission_states[mission_id].update({
                    "status": MISSION_STATUS_FAILED,
                    "message": f"任務失敗：{error_msg}",
                    "end_time": datetime.now().isoformat()
                })
                if self.log_manager:
                    self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (FactorCalculation) 失敗，黃金紀錄為空。", details={"path": str(golden_record_path)}, level="WARNING", mission_id=mission_id)
                return

            # FactorEngine 的 generate_and_store_daily_factors 預期 ticker_symbol (已從 params 獲取)
            # 和一個 DataFrame。由於黃金紀錄是單日的，所以 DataFrame 只有一行。
            # FactorEngine 內部會迭代這個 DataFrame 的每一行 (即使只有一行)
            stored_factor_files = self.factor_engine.generate_and_store_daily_factors(
                golden_ohlcv_df=golden_ohlcv_df,
                ticker_symbol=ticker_symbol
            )

            if stored_factor_files:
                MainOrchestrator._mission_states[mission_id].update({
                    "status": MISSION_STATUS_SUCCESS,
                    "message": f"任務成功：股票 {ticker_symbol} 在 {date_str} 的因子已計算並儲存。",
                    "details": {
                        "ticker_symbol": ticker_symbol,
                        "date": date_str,
                        "golden_record_path": str(golden_record_path),
                        "stored_factor_files": [str(p) for p in stored_factor_files]
                    },
                    "end_time": datetime.now().isoformat()
                })
                orchestrator_logger.info(f"任務 {mission_id} (FactorCalculation) 成功完成 for {ticker_symbol} on {date_str}. 儲存的因子檔案: {len(stored_factor_files)}")
                if self.log_manager:
                    self.log_manager.log_event(event_type="mission_succeeded", message=f"任務 {mission_id} (FactorCalculation) for {ticker_symbol} on {date_str} 成功。", details={"files_count": len(stored_factor_files)}, mission_id=mission_id)
            else:
                # 即使黃金紀錄存在，也可能因為數據不足以計算任何因子 (例如 recipes 為空，或數據不符合因子計算要求) 而沒有儲存任何檔案
                warn_msg = f"因子計算任務完成，但沒有儲存任何因子檔案 for {ticker_symbol} on {date_str}。可能是因為數據不足或無有效因子產生。"
                MainOrchestrator._mission_states[mission_id].update({
                    "status": MISSION_STATUS_SUCCESS, # 任務本身沒有失敗，只是沒有產出
                    "message": warn_msg,
                    "details": {
                        "ticker_symbol": ticker_symbol,
                        "date": date_str,
                        "golden_record_path": str(golden_record_path),
                        "info": "No factor files were stored. This might be due to insufficient data in the golden record for the configured factors, or no factors being generated."
                    },
                    "end_time": datetime.now().isoformat()
                })
                orchestrator_logger.warning(f"任務 {mission_id} (FactorCalculation): {warn_msg}")
                if self.log_manager:
                     self.log_manager.log_event(event_type="mission_succeeded_with_warning", message=f"任務 {mission_id} (FactorCalculation) for {ticker_symbol} on {date_str} 完成但無因子檔案儲存。", details={"golden_record_path": str(golden_record_path)}, level="WARNING", mission_id=mission_id)

        except FileNotFoundError as fnf_e: # 更明確捕捉檔案未找到錯誤
            orchestrator_logger.error(f"任務 {mission_id} (FactorCalculation): 讀取黃金紀錄時檔案未找到: {fnf_e}", exc_info=False) # exc_info=False 因為訊息已足夠
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED,
                "message": f"任務 (FactorCalculation) 失敗：黃金紀錄檔案不存在 - {str(fnf_e)}",
                "end_time": datetime.now().isoformat()
            })
            if self.log_manager:
                self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (FactorCalculation) 因黃金紀錄檔案未找到而失敗。", details={"error": str(fnf_e)}, level="ERROR", mission_id=mission_id)

        except Exception as e:
            orchestrator_logger.error(f"任務 {mission_id} (FactorCalculation): 執行因子計算任務時發生嚴重錯誤: {e}", exc_info=True)
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED,
                "message": f"任務 (FactorCalculation) 失敗：執行時發生內部錯誤 - {str(e)}",
                "end_time": datetime.now().isoformat()
            })
            if self.log_manager:
                self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (FactorCalculation) 因執行錯誤失敗。", details={"error": str(e)}, level="CRITICAL", mission_id=mission_id)

    def _execute_backtest_task(self, mission_id: str, params: Dict[str, Any]):
        """執行回測子任務。"""
        MainOrchestrator._mission_states[mission_id].update({
            "status": MISSION_STATUS_PROCESSING,
            "message": "正在處理回測任務..."
        })
        orchestrator_logger.info(f"任務 {mission_id}: 正在執行回測任務。參數: {params}")

        strategy_id = params.get("strategy_id")
        price_source_path_str = params.get("price_source_path")
        factor_source_path_str = params.get("factor_source_path")
        initial_cash = params.get("initial_cash", 100000.0)
        commission_rate = params.get("commission_rate", 0.001)
        # start_date 和 end_date 可用於篩選已載入的數據，但首先要能載入包含該範圍的數據源
        # start_date_str = params.get("start_date")
        # end_date_str = params.get("end_date")

        required_params = {
            "strategy_id": strategy_id,
            "price_source_path": price_source_path_str,
            "factor_source_path": factor_source_path_str
        }
        missing_params = [k for k, v in required_params.items() if v is None]
        if missing_params:
            error_msg = f"任務 {mission_id} (Backtest): 缺少必要參數: {', '.join(missing_params)}。"
            orchestrator_logger.error(error_msg)
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED, "message": f"任務失敗：{error_msg}",
                "end_time": datetime.now().isoformat()
            })
            if self.log_manager:
                self.log_manager.log_event(event_type="mission_failed", message=error_msg, details=params, level="ERROR", mission_id=mission_id)
            return

        price_source_path = Path(price_source_path_str)
        factor_source_path = Path(factor_source_path_str)

        try:
            # 1. 載入數據
            orchestrator_logger.info(f"任務 {mission_id}: 載入價格數據從 {price_source_path}")
            if not price_source_path.exists():
                raise FileNotFoundError(f"價格數據檔案不存在: {price_source_path}")
            price_df = pd.read_parquet(price_source_path)
            if 'Date' in price_df.columns and price_df.index.name != 'Date': # 兼容舊格式，將 Date 欄設為索引
                price_df.set_index('Date', inplace=True)
            if not isinstance(price_df.index, pd.DatetimeIndex):
                 price_df.index = pd.to_datetime(price_df.index)


            orchestrator_logger.info(f"任務 {mission_id}: 載入因子數據從 {factor_source_path}")
            if not factor_source_path.exists():
                raise FileNotFoundError(f"因子數據檔案不存在: {factor_source_path}")
            factor_df = pd.read_parquet(factor_source_path)
            if 'Date' in factor_df.columns and factor_df.index.name != 'Date':
                factor_df.set_index('Date', inplace=True)
            if not isinstance(factor_df.index, pd.DatetimeIndex):
                factor_df.index = pd.to_datetime(factor_df.index)

            # (可選) 根據 start_date, end_date 篩選數據
            # if start_date_str: price_df = price_df[price_df.index >= pd.to_datetime(start_date_str)]
            # if end_date_str: price_df = price_df[price_df.index <= pd.to_datetime(end_date_str)]
            # factor_df = factor_df.reindex(price_df.index).ffill().bfill() # 對齊並填充因子數據

            # 2. 載入策略邏輯
            orchestrator_logger.info(f"任務 {mission_id}: 載入策略 '{strategy_id}'")
            strategy_module_name = f"prometheus_fire_backend.strategies.{strategy_id}_strategy"
            try:
                strategy_module = importlib.import_module(strategy_module_name)
                generate_signals_func = getattr(strategy_module, "generate_signals")
            except (ImportError, AttributeError) as e:
                raise ImportError(f"無法載入策略 '{strategy_id}' 從模組 '{strategy_module_name}': {e}")

            # 3. 生成訊號
            orchestrator_logger.info(f"任務 {mission_id}: 為策略 '{strategy_id}' 生成訊號")
            # 策略函數可能需要特定的因子欄位名，這些可以作為 params 的一部分傳入
            # 例如: params.get("strategy_params", {})
            entry_signals, exit_signals = generate_signals_func(price_df, factor_df) # **params.get("strategy_params", {}))

            # 4. 執行回測
            orchestrator_logger.info(f"任務 {mission_id}: 執行回測，策略 '{strategy_id}'")
            backtest_stats, error_msg = self.backtester.run_backtest(
                price_df=price_df,
                entry_signals=entry_signals,
                exit_signals=exit_signals,
                initial_cash=initial_cash,
                commission_rate=commission_rate
                # slippage_rate and ohlc_column_map can be added from params if needed
            )

            if error_msg:
                raise Exception(f"回測執行失敗: {error_msg}")

            if backtest_stats is None:
                 raise Exception("回測執行未返回任何統計數據，但也沒有明確錯誤訊息。")


            # 將 Pandas Series 轉換為字典以便 JSON 序列化
            stats_dict = backtest_stats.to_dict() if backtest_stats is not None else {}
            # 轉換 NaN 和 Infinity 以便 JSON 兼容
            for k, v in stats_dict.items():
                if pd.isna(v):
                    stats_dict[k] = None
                elif v == float('inf'):
                    stats_dict[k] = "Infinity"
                elif v == float('-inf'):
                    stats_dict[k] = "-Infinity"


            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_SUCCESS,
                "message": f"任務成功：策略 '{strategy_id}' 回測完成。",
                "details": {
                    "strategy_id": strategy_id,
                    "price_data_source": str(price_source_path),
                    "factor_data_source": str(factor_source_path),
                    "initial_cash": initial_cash,
                    "commission_rate": commission_rate,
                    "backtest_results": stats_dict
                },
                "end_time": datetime.now().isoformat()
            })
            orchestrator_logger.info(f"任務 {mission_id} (Backtest) 成功完成。策略: {strategy_id}")
            if self.log_manager:
                self.log_manager.log_event(
                    event_type="mission_succeeded",
                    message=f"任務 {mission_id} (Backtest) for strategy {strategy_id} 成功。",
                    details={"strategy": strategy_id, "num_stats": len(stats_dict)},
                    mission_id=mission_id
                )

        except FileNotFoundError as fnf_e:
            orchestrator_logger.error(f"任務 {mission_id} (Backtest): 數據檔案未找到: {fnf_e}", exc_info=False)
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED, "message": f"任務失敗：數據檔案未找到 - {str(fnf_e)}",
                "end_time": datetime.now().isoformat()
            })
            if self.log_manager:
                self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (Backtest) 因數據檔案未找到失敗。", details={"error": str(fnf_e)}, level="ERROR", mission_id=mission_id)
        except ImportError as imp_e:
            orchestrator_logger.error(f"任務 {mission_id} (Backtest): 策略載入失敗: {imp_e}", exc_info=False)
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED, "message": f"任務失敗：策略載入失敗 - {str(imp_e)}",
                "end_time": datetime.now().isoformat()
            })
            if self.log_manager:
                self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (Backtest) 因策略載入失敗。", details={"error": str(imp_e)}, level="ERROR", mission_id=mission_id)
        except Exception as e:
            orchestrator_logger.error(f"任務 {mission_id} (Backtest): 執行回測任務時發生嚴重錯誤: {e}", exc_info=True)
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED, "message": f"任務失敗：執行回測時發生內部錯誤 - {str(e)}",
                "end_time": datetime.now().isoformat()
            })
            if self.log_manager:
                self.log_manager.log_event(event_type="mission_failed", message=f"任務 {mission_id} (Backtest) 因執行錯誤失敗。", details={"error": str(e)}, level="CRITICAL", mission_id=mission_id)


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
