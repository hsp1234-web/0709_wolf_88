# prometheus_fire_backend/console_api/main.py

from fastapi import FastAPI, HTTPException, Request # <--- 加入 Request
from contextlib import asynccontextmanager
import logging
from pathlib import Path # <--- 導入 Path
# import os # 用於推斷 project_base_path # <--- 移除 os

from prometheus_fire_backend.modules.logger import LogManager
from prometheus_fire_backend.modules.orchestrator import MainOrchestrator # 匯入 MainOrchestrator
from prometheus_fire_backend.modules.metadata_manager import FactorMetadataManager # <--- 導入 FactorMetadataManager
from typing import Optional, Dict, Any, List # <--- 加入 List
from core.config import PROJECT_ROOT # <--- 導入 PROJECT_ROOT

# --- 全局變數與設定 ---
# LOG_DB_PATH = "logs/api_logs.sqlite" # <--- 改為基於 PROJECT_ROOT
DEFAULT_LOG_DB_PATH = PROJECT_ROOT / "logs" / "api_logs.sqlite"
DEFAULT_FACTOR_METADATA_DB_PATH = PROJECT_ROOT / "data_warehouse" / "factor_details.db" # <--- 元數據庫路徑

# log_manager_instance: Optional[LogManager] = None # 改用 app.state
# orchestrator_instance: Optional[MainOrchestrator] = None # 全局 Orchestrator 實例 # 改用 app.state
# PROJECT_BASE_PATH: Optional[str] = None # 專案根目錄 # <--- 不再需要，使用 PROJECT_ROOT

# 配置日誌
# logging.basicConfig(level=logging.INFO) # 應避免在模組中使用全局 basicConfig
api_logger = logging.getLogger("prometheus_fire_backend.console_api") # 使用明確的 logger 名稱
if not api_logger.hasHandlers(): # 避免重複添加 handler
    handler = logging.StreamHandler()
    # 更詳細的日誌格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')
    handler.setFormatter(formatter)
    api_logger.addHandler(handler)
    api_logger.setLevel(logging.INFO) # 可由環境變數等配置


# --- FastAPI Lifespan 事件 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    api_logger.info("Lifespan: Startup sequence initiated.")
    app.state.project_root = PROJECT_ROOT
    api_logger.info(f"Lifespan: Project root set to: {app.state.project_root}")

    # 初始化 LogManager
    api_logger.info("Lifespan: Initializing LogManager...")
    try:
        log_db_path_to_use = DEFAULT_LOG_DB_PATH
        log_db_path_to_use.parent.mkdir(parents=True, exist_ok=True) # 確保日誌目錄存在
        app.state.log_manager = LogManager(db_path=str(log_db_path_to_use))
        api_logger.info(f"Lifespan: LogManager initialized. Log database: {log_db_path_to_use}")
        app.state.log_manager.log_event(
            event_type="application_startup_phase1",
            message="LogManager initialized successfully.",
            source_module="console_api.main"
        )
    except Exception as e:
        api_logger.critical(f"Lifespan: CRITICAL error initializing LogManager: {e}", exc_info=True)
        app.state.log_manager = None # 標記為初始化失敗
        # 根據策略，可以決定是否終止應用程式啟動
        # raise RuntimeError("Failed to initialize LogManager, application cannot start.") from e

    # 初始化 MainOrchestrator
    api_logger.info("Lifespan: Initializing MainOrchestrator...")
    if app.state.log_manager:
        try:
            app.state.orchestrator = MainOrchestrator(log_manager=app.state.log_manager)
            api_logger.info("Lifespan: MainOrchestrator initialized.")
            app.state.log_manager.log_event(
                event_type="application_startup_phase2",
                message="MainOrchestrator initialized successfully.",
                source_module="console_api.main"
            )
        except Exception as e:
            api_logger.critical(f"Lifespan: CRITICAL error initializing MainOrchestrator: {e}", exc_info=True)
            app.state.orchestrator = None
            # raise RuntimeError("Failed to initialize MainOrchestrator, application cannot start.") from e
    else:
        api_logger.error("Lifespan: MainOrchestrator cannot be initialized because LogManager failed.")
        app.state.orchestrator = None
        # raise RuntimeError("LogManager not available, MainOrchestrator initialization skipped.")

    # 初始化 FactorMetadataManager 並同步因子元數據
    api_logger.info("Lifespan: Initializing FactorMetadataManager and syncing factor recipes...")
    app.state.factor_metadata_manager = None # 預設為 None
    try:
        # FactorMetadataManager 的 __init__ 會確保其 db 目錄存在
        # 使用在檔案頂部定義的 DEFAULT_FACTOR_METADATA_DB_PATH
        factor_metadata_manager = FactorMetadataManager(db_path=DEFAULT_FACTOR_METADATA_DB_PATH)
        app.state.factor_metadata_manager = factor_metadata_manager # 儲存實例（可選）

        sync_status = factor_metadata_manager.sync_recipes_to_db()
        if sync_status:
            api_logger.info("Lifespan: Factor recipes successfully synced to the metadata database.")
        else:
            api_logger.warning("Lifespan: Factor recipes sync to metadata database may have encountered issues or had no data to sync. Check FactorMetadataManager logs for details.")

        if app.state.log_manager:
            app.state.log_manager.log_event(
                event_type="factor_metadata_sync_completed",
                message=f"Factor metadata sync status: {'Success' if sync_status else 'Issues/NoData'}.",
                details={"sync_successful": sync_status, "db_path": str(DEFAULT_FACTOR_METADATA_DB_PATH)},
                source_module="console_api.main",
                level="INFO" if sync_status else "WARNING"
            )
    except Exception as e:
        api_logger.error(f"Lifespan: Error during FactorMetadataManager initialization or sync: {e}", exc_info=True)
        if app.state.log_manager:
            app.state.log_manager.log_event(
                event_type="factor_metadata_sync_failed",
                message=f"Factor metadata sync critically failed: {str(e)}",
                details={"error": str(e), "db_path": str(DEFAULT_FACTOR_METADATA_DB_PATH)},
                source_module="console_api.main",
                level="ERROR"
            )
        # 根據策略，可以選擇是否讓應用程式繼續

    if app.state.log_manager:
        app.state.log_manager.log_event(event_type="application_startup_complete", message="FastAPI application startup sequence finished.", source_module="console_api.main")
    api_logger.info("Lifespan: Startup sequence completed.")
    yield

    api_logger.info("Lifespan: Shutdown sequence initiated.")
    if hasattr(app.state, 'orchestrator') and app.state.orchestrator and hasattr(app.state.orchestrator, 'http_client') and app.state.orchestrator.http_client:
        api_logger.info("Lifespan: Closing Orchestrator's HttpClient...")
        await app.state.orchestrator.http_client.close_async() # 假設 http_client 有 close_async
        api_logger.info("Lifespan: Orchestrator's HttpClient closed.")

    if hasattr(app.state, 'log_manager') and app.state.log_manager:
        api_logger.info("Lifespan: Closing LogManager...")
        app.state.log_manager.log_event(event_type="application_shutdown", message="FastAPI application shutting down.", source_module="console_api.main")
        app.state.log_manager.close() # LogManager 的 close 通常是同步的
        api_logger.info("Lifespan: LogManager closed.")
    api_logger.info("Lifespan: Shutdown sequence completed.")

app = FastAPI(
    title="普羅米修斯之火 API",
    description="後端情報處理核心 API，代號「鋼鐵心臟」。",
    version="v1.0",
    lifespan=lifespan
)

@app.get("/")
async def read_root():
    """
    根路徑，用於檢查服務是否正在運行。
    """
    # 訪問 app.state 中的 log_manager
    current_log_manager = getattr(app.state, 'log_manager', None)
    if current_log_manager:
        current_log_manager.log_api_call(endpoint="/", method="GET", status_code=200)
    return {"message": "歡迎來到普羅米修斯之火 🔥 - 「鋼鐵心臟」API"}

# --- Pydantic Models ---
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any # 確認 Any 和 Dict 已匯入

class MissionParameters(BaseModel):
    """
    啟動任務時傳遞的參數模型。
    """
    type: str = Field(..., description="任務類型，例如 'fetch_taifex'。")
    # 針對 fetch_taifex 的特定參數 (可選，取決於任務類型)
    data_type: Optional[str] = Field(None, description="數據類型，例如 'institutional_investors' 或 'pc_ratio'。") # 將在 Orchestrator 中組合成 list
    date: Optional[str] = Field(None, description="目標日期，格式 YYYY-MM-DD。")

    # 新增 use_mock 參數
    use_mock: bool = Field(True, description="是否使用模擬數據。True 表示使用模擬數據，False 表示嘗試真實數據獲取。")

    # 允許多個 data_types
    data_types: Optional[List[str]] = Field(None, description="要抓取的數據類型列表，例如 ['institutional_investors', 'pc_ratio']。如果提供，將覆蓋單一 data_type。")


    # 可以添加其他通用參數或特定任務的參數
    # extra_params: Optional[Dict[str, Any]] = Field(None, description="其他任務特定參數")

    model_config = {
        "extra": "allow"  # 允許額外的欄位，以便傳遞給 Orchestrator
    }

class StartMissionResponse(BaseModel):
    """
    啟動任務的回應模型。
    """
    mission_id: str = Field(..., description="唯一任務 ID")
    message: str = Field(default="任務已成功接收並開始處理", description="回應訊息")
    initial_status: Optional[Dict[str, Any]] = Field(None, description="任務的初始狀態")


class MissionStatusResponse(BaseModel):
    """
    查詢任務狀態的回應模型。與 Orchestrator 返回的結構保持一致。
    """
    mission_id: str
    status: str
    progress: float
    message: str
    details: Optional[Dict[str, Any]] = None
    start_time: Optional[str] = None # 確保與 Orchestrator 回應一致
    end_time: Optional[str] = None   # 確保與 Orchestrator 回應一致


class FusionMissionParameters(BaseModel):
    """
    啟動數據融合任務時傳遞的參數模型。
    """
    ticker_symbol: str = Field(..., description="要進行數據融合的股票代號，例如 '0050.TW'。")
    date: str = Field(..., description="要進行數據融合的目標日期，格式 YYYY-MM-DD。")
    data_type_to_fuse: Optional[str] = Field("daily_ohlcv", description="要融合的數據類型，預設為 'daily_ohlcv'。")

    model_config = {
        "extra": "allow" # 允許額外欄位，儘管此處可能不需要
    }

class FactorMissionParameters(BaseModel):
    """
    啟動因子計算任務時傳遞的參數模型。
    """
    ticker: str = Field(..., description="要計算因子的股票代號，例如 'AAPL' 或 '0050.TW'。")
    date: str = Field(..., description="因子計算的目標日期（通常對應黃金紀錄的日期），格式 YYYY-MM-DD。")
    # use_mock 和其他通用參數可以由 Orchestrator 處理，這裡專注於因子任務的核心參數

    model_config = {
        "extra": "allow"
    }

class BacktestMissionParameters(BaseModel):
    """
    啟動回測任務時傳遞的參數模型。
    """
    ticker: str = Field(..., description="要進行回測的股票代號。")
    strategy_id: str = Field(..., description="要使用的策略的唯一標識符 (例如 'sma_cross')。")
    price_source_path: str = Field(..., description="包含歷史價格數據 (OHLCV) 的 Parquet 檔案路徑。")
    factor_source_path: str = Field(..., description="包含預計算因子數據的 Parquet 檔案路徑。")
    start_date: Optional[str] = Field(None, description="回測開始日期 (YYYY-MM-DD)。如果提供，將篩選數據源。")
    end_date: Optional[str] = Field(None, description="回測結束日期 (YYYY-MM-DD)。如果提供，將篩選數據源。")
    initial_cash: float = Field(100000.0, description="回測的初始資金。")
    commission_rate: float = Field(0.001, description="交易手續費率 (例如 0.001 代表 0.1%)。")
    # 可選：策略特定參數
    strategy_params: Optional[Dict[str, Any]] = Field(None, description="傳遞給策略生成函數的特定參數。")


    model_config = {
        "extra": "allow" # 允許 Orchestrator 可能需要的其他參數
    }

class OptimizationMissionParameters(BaseModel):
    """
    啟動投資組合優化任務時傳遞的參數模型。
    """
    asset_price_paths_dict: Dict[str, str] = Field(..., description="一個字典，鍵為資產ID，值為該資產歷史價格數據 (Parquet) 的路徑。")
    optimization_target: str = Field(..., description="優化目標，例如 'max_sharpe', 'min_volatility', 'hrp'。")
    risk_free_rate: float = Field(0.02, description="無風險利率，用於夏普比率等計算。")
    target_volatility: Optional[float] = Field(None, description="目標年化波動率 (用於 'efficient_risk' 優化)。")
    target_return: Optional[float] = Field(None, description="目標年化回報率 (用於 'efficient_return' 優化)。")
    weight_bounds: Optional[List[float]] = Field([0.0, 1.0], description="個別資產權重的上下限列表，例如 [0, 1]。")
    covariance_method: Optional[str] = Field("ledoit_wolf", description="計算協方差矩陣的方法。")
    expected_returns_method: Optional[str] = Field("mean_historical_return", description="計算預期回報的方法。")

    model_config = {
        "extra": "allow"
    }

# --- API Endpoints ---

@app.post("/api/v1/start_mission", response_model=StartMissionResponse, tags=["Mission Control"])
async def start_mission_endpoint(params: MissionParameters, request: Request): # 注入 Request
    """
    啟動一個新的情報蒐集與處理任務。
    """
    current_orchestrator = getattr(request.app.state, 'orchestrator', None)
    current_log_manager = getattr(request.app.state, 'log_manager', None)

    if not current_orchestrator:
        # 打印調試信息
        print(f"API Error: Orchestrator not found in app.state. app.state keys: {list(request.app.state.__dict__.keys() if hasattr(request.app.state, '__dict__') else [])}")
        raise HTTPException(status_code=503, detail="總調度器尚未初始化，服務暫不可用。")

    mission_params_dict = params.model_dump()
    print(f"API 接收到任務啟動請求。參數: {mission_params_dict}")

    try:
        mission_id = current_orchestrator.start_mission(mission_params=mission_params_dict)
        initial_status_dict = current_orchestrator.get_mission_status(mission_id)

        response_data = StartMissionResponse(
            mission_id=mission_id,
            message=f"任務 {mission_id} 已成功啟動。",
            initial_status=initial_status_dict
        )

        if current_log_manager:
            current_log_manager.log_api_call(
                endpoint="/api/v1/start_mission",
                method="POST",
                mission_id=mission_id,
                request_body=mission_params_dict,
                response_body=response_data.model_dump(),
                status_code=200
            )
        return response_data
    except Exception as e:
        print(f"啟動任務時發生錯誤: {e}") # 記錄到伺服器日誌
        if current_log_manager:
             current_log_manager.log_api_call(
                endpoint="/api/v1/start_mission",
                method="POST",
                request_body=mission_params_dict,
                status_code=500,
                error_message=str(e)
            )
        raise HTTPException(status_code=500, detail=f"啟動任務時發生內部錯誤: {str(e)}")


@app.get("/api/v1/mission_status/{mission_id}", response_model=MissionStatusResponse, tags=["Mission Control"])
async def get_mission_status_endpoint(mission_id: str, request: Request): # 注入 Request
    """
    查詢指定任務的當前狀態與進度。
    """
    current_orchestrator = getattr(request.app.state, 'orchestrator', None)
    current_log_manager = getattr(request.app.state, 'log_manager', None)

    if not current_orchestrator:
        raise HTTPException(status_code=503, detail="總調度器尚未初始化，服務暫不可用。")

    print(f"API 接收到狀態查詢請求。Mission ID: {mission_id}")

    status_dict = current_orchestrator.get_mission_status(mission_id)

    if "不存在" in status_dict.get("message", "") and status_dict.get("status", "").lower() == "failed": # 根據 Orchestrator 的實際返回調整
        if current_log_manager:
            current_log_manager.log_api_call(
                endpoint=f"/api/v1/mission_status/{mission_id}",
                method="GET",
                mission_id=mission_id,
                status_code=404,
                response_body=status_dict
            )
        raise HTTPException(status_code=404, detail=status_dict)

    response_data = MissionStatusResponse(**status_dict)

    if current_log_manager:
        current_log_manager.log_api_call(
            endpoint=f"/api/v1/mission_status/{mission_id}",
            method="GET",
            mission_id=mission_id,
            response_body=response_data.model_dump(),
            status_code=200
        )
    return response_data


@app.post("/api/v1/start_fusion_mission", response_model=StartMissionResponse, tags=["Mission Control"])
async def start_fusion_mission_endpoint(params: FusionMissionParameters, request: Request):
    """
    啟動一個新的數據融合任務。
    """
    current_orchestrator = getattr(request.app.state, 'orchestrator', None)
    current_log_manager = getattr(request.app.state, 'log_manager', None)

    if not current_orchestrator:
        print(f"API Error: Orchestrator not found in app.state during fusion mission start.")
        raise HTTPException(status_code=503, detail="總調度器尚未初始化，服務暫不可用。")

    # 構造傳遞給 MainOrchestrator.start_mission 的參數
    # MainOrchestrator 的 start_mission 會根據 'type' 來分派任務
    mission_params_dict = {
        "type": "fuse_data",  # 告訴 Orchestrator 這是個融合任務
        "ticker_symbol": params.ticker_symbol,
        "date": params.date,
        "data_type_to_fuse": params.data_type_to_fuse
        # use_mock 和 mock_data 通常不適用於融合任務，因為融合是基於已存在的原始數據
    }
    print(f"API 接收到融合任務啟動請求。參數: {mission_params_dict}")

    try:
        mission_id = current_orchestrator.start_mission(mission_params=mission_params_dict)
        initial_status_dict = current_orchestrator.get_mission_status(mission_id)

        response_data = StartMissionResponse(
            mission_id=mission_id,
            message=f"數據融合任務 {mission_id} 已成功啟動。",
            initial_status=initial_status_dict
        )

        if current_log_manager:
            current_log_manager.log_api_call(
                endpoint="/api/v1/start_fusion_mission",
                method="POST",
                mission_id=mission_id,
                request_body=mission_params_dict, # 使用轉換後的 dict
                response_body=response_data.model_dump(),
                status_code=200
            )
        return response_data
    except Exception as e:
        print(f"啟動融合任務時發生錯誤: {e}")
        if current_log_manager:
             current_log_manager.log_api_call(
                endpoint="/api/v1/start_fusion_mission",
                method="POST",
                request_body=mission_params_dict,
                status_code=500,
                error_message=str(e)
            )
        raise HTTPException(status_code=500, detail=f"啟動融合任務時發生內部錯誤: {str(e)}")

@app.post("/api/v1/start_factor_mission", response_model=StartMissionResponse, tags=["Factor Engine"])
async def start_factor_mission_endpoint(params: FactorMissionParameters, request: Request):
    """
    啟動一個新的因子計算任務。
    """
    current_orchestrator = getattr(request.app.state, 'orchestrator', None)
    current_log_manager = getattr(request.app.state, 'log_manager', None)

    if not current_orchestrator:
        print(f"API Error: Orchestrator not found in app.state during factor mission start.")
        raise HTTPException(status_code=503, detail="總調度器尚未初始化，服務暫不可用。")

    # 構造傳遞給 MainOrchestrator.start_mission 的參數
    mission_params_dict = {
        "type": "calculate_factors",  # 告訴 Orchestrator 這是個因子計算任務
        "ticker": params.ticker,
        "date": params.date
        # Orchestrator 的 _execute_factor_calculation_task 會處理這些參數
    }
    print(f"API 接收到因子計算任務啟動請求。參數: {mission_params_dict}")

    try:
        mission_id = current_orchestrator.start_mission(mission_params=mission_params_dict)
        initial_status_dict = current_orchestrator.get_mission_status(mission_id)

        response_data = StartMissionResponse(
            mission_id=mission_id,
            message=f"因子計算任務 {mission_id} 已成功啟動。",
            initial_status=initial_status_dict
        )

        if current_log_manager:
            current_log_manager.log_api_call(
                endpoint="/api/v1/start_factor_mission",
                method="POST",
                mission_id=mission_id,
                request_body=mission_params_dict,
                response_body=response_data.model_dump(),
                status_code=200
            )
        return response_data
    except Exception as e:
        print(f"啟動因子計算任務時發生錯誤: {e}")
        if current_log_manager:
             current_log_manager.log_api_call(
                endpoint="/api/v1/start_factor_mission",
                method="POST",
                request_body=mission_params_dict,
                status_code=500,
                error_message=str(e)
            )
        raise HTTPException(status_code=500, detail=f"啟動因子計算任務時發生內部錯誤: {str(e)}")


@app.post("/api/v1/start_backtest_mission", response_model=StartMissionResponse, tags=["Backtesting"])
async def start_backtest_mission_endpoint(params: BacktestMissionParameters, request: Request):
    """
    啟動一個新的回測任務。
    """
    current_orchestrator = getattr(request.app.state, 'orchestrator', None)
    current_log_manager = getattr(request.app.state, 'log_manager', None)

    if not current_orchestrator:
        api_logger.error("API Error: Orchestrator not found in app.state during backtest mission start.")
        raise HTTPException(status_code=503, detail="總調度器尚未初始化，服務暫不可用。")

    # 構造傳遞給 MainOrchestrator.start_mission 的參數
    # Orchestrator 的 _execute_backtest_task 將處理這些參數
    mission_params_dict = {
        "type": "backtest",
        "ticker": params.ticker,
        "strategy_id": params.strategy_id,
        "price_source_path": params.price_source_path,
        "factor_source_path": params.factor_source_path,
        "start_date": params.start_date,
        "end_date": params.end_date,
        "initial_cash": params.initial_cash,
        "commission_rate": params.commission_rate,
        "strategy_params": params.strategy_params
    }
    api_logger.info(f"API 接收到回測任務啟動請求。參數: {mission_params_dict}")

    try:
        mission_id = current_orchestrator.start_mission(mission_params=mission_params_dict)
        initial_status_dict = current_orchestrator.get_mission_status(mission_id)

        response_data = StartMissionResponse(
            mission_id=mission_id,
            message=f"回測任務 {mission_id} (策略: {params.strategy_id}, 股票: {params.ticker}) 已成功啟動。",
            initial_status=initial_status_dict
        )

        if current_log_manager:
            current_log_manager.log_api_call(
                endpoint="/api/v1/start_backtest_mission",
                method="POST",
                mission_id=mission_id,
                request_body=mission_params_dict,
                response_body=response_data.model_dump(),
                status_code=200
            )
        return response_data
    except Exception as e:
        api_logger.error(f"啟動回測任務時發生錯誤: {e}", exc_info=True)
        if current_log_manager:
             current_log_manager.log_api_call(
                endpoint="/api/v1/start_backtest_mission",
                method="POST",
                request_body=mission_params_dict,
                status_code=500,
                error_message=str(e)
            )
        raise HTTPException(status_code=500, detail=f"啟動回測任務時發生內部錯誤: {str(e)}")


@app.post("/api/v1/start_optimization_mission", response_model=StartMissionResponse, tags=["Portfolio Optimization"])
async def start_optimization_mission_endpoint(params: OptimizationMissionParameters, request: Request):
    """
    啟動一個新的投資組合優化任務。
    """
    current_orchestrator = getattr(request.app.state, 'orchestrator', None)
    current_log_manager = getattr(request.app.state, 'log_manager', None)

    if not current_orchestrator:
        api_logger.error("API Error: Orchestrator not found in app.state during optimization mission start.")
        raise HTTPException(status_code=503, detail="總調度器尚未初始化，服務暫不可用。")

    mission_params_dict = {
        "type": "portfolio_optimization",
        "asset_price_paths_dict": params.asset_price_paths_dict,
        "optimization_target": params.optimization_target,
        "risk_free_rate": params.risk_free_rate,
        "target_volatility": params.target_volatility,
        "target_return": params.target_return,
        "weight_bounds": params.weight_bounds,
        "covariance_method": params.covariance_method,
        "expected_returns_method": params.expected_returns_method
    }
    api_logger.info(f"API 接收到投資組合優化任務啟動請求。參數: {mission_params_dict}")

    try:
        mission_id = current_orchestrator.start_mission(mission_params=mission_params_dict)
        initial_status_dict = current_orchestrator.get_mission_status(mission_id)

        response_data = StartMissionResponse(
            mission_id=mission_id,
            message=f"投資組合優化任務 {mission_id} (目標: {params.optimization_target}) 已成功啟動。",
            initial_status=initial_status_dict
        )

        if current_log_manager:
            current_log_manager.log_api_call(
                endpoint="/api/v1/start_optimization_mission",
                method="POST",
                mission_id=mission_id,
                request_body=mission_params_dict,
                response_body=response_data.model_dump(),
                status_code=200
            )
        return response_data
    except Exception as e:
        api_logger.error(f"啟動投資組合優化任務時發生錯誤: {e}", exc_info=True)
        if current_log_manager:
             current_log_manager.log_api_call(
                endpoint="/api/v1/start_optimization_mission",
                method="POST",
                request_body=mission_params_dict,
                status_code=500,
                error_message=str(e)
            )
        raise HTTPException(status_code=500, detail=f"啟動投資組合優化任務時發生內部錯誤: {str(e)}")


# 為了能夠透過 uvicorn 運行，我們可以在這裡加入一個簡易的啟動方式
if __name__ == "__main__":
    import uvicorn
    # 確保 uvicorn 從專案根目錄運行，以便模組導入正常
    # 例如在專案根目錄 /app 下執行:
    # uvicorn prometheus_fire_backend.console_api.main:app --reload
    # 或者 python -m uvicorn prometheus_fire_backend.console_api.main:app --reload

    # 如果要直接執行 python prometheus_fire_backend/console_api/main.py，
    # 則需要確保PYTHONPATH包含專案根目錄 /app，或者 uvicorn 的 app_dir 設定正確。
    # 這裡的 app_dir 試圖讓直接執行此檔案時 uvicorn 能找到 `prometheus_fire_backend` 模組。
    # 它假設此檔案 (main.py) 在 project_root/prometheus_fire_backend/console_api/ 內。
    # 所以 ".." 指向 project_root/prometheus_fire_backend/
    # 再 ".." 指向 project_root/
    # 因此 app_dir 指向的是包含 prometheus_fire_backend 這個頂層套件的目錄。
    # 現在我們直接使用 PROJECT_ROOT
    uvicorn.run(
        "prometheus_fire_backend.console_api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        # app_dir 設定為此檔案所在目錄的再上兩層目錄
        # app_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")) # <--- 修改
        app_dir=str(PROJECT_ROOT) # <--- 使用 PROJECT_ROOT
    )
