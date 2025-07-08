# prometheus_fire_backend/console_api/main.py

from fastapi import FastAPI, HTTPException, Request # <--- 加入 Request
from contextlib import asynccontextmanager
import logging
from pathlib import Path # <--- 導入 Path
# import os # 用於推斷 project_base_path # <--- 移除 os

from prometheus_fire_backend.modules.logger import LogManager
from prometheus_fire_backend.modules.orchestrator import MainOrchestrator # 匯入 MainOrchestrator
from typing import Optional, Dict, Any, List # <--- 加入 List
from core.config import PROJECT_ROOT # <--- 導入 PROJECT_ROOT

# --- 全局變數與設定 ---
# LOG_DB_PATH = "logs/api_logs.sqlite" # <--- 改為基於 PROJECT_ROOT
DEFAULT_LOG_DB_PATH = PROJECT_ROOT / "logs" / "api_logs.sqlite"

# log_manager_instance: Optional[LogManager] = None # 改用 app.state
# orchestrator_instance: Optional[MainOrchestrator] = None # 全局 Orchestrator 實例 # 改用 app.state
# PROJECT_BASE_PATH: Optional[str] = None # 專案根目錄 # <--- 不再需要，使用 PROJECT_ROOT

# 配置日誌
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__) # FastAPI 自己的 logger

# --- FastAPI Lifespan 事件 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # global PROJECT_BASE_PATH # PROJECT_BASE_PATH 仍然可以是全局的，或者也放入 app.state # <--- 移除

    print("Lifespan: Startup sequence started.")
    # 推斷專案根目錄 (假設 main.py 在 prometheus_fire_backend/console_api/ 下)
    # PROJECT_BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")) # <--- 移除
    # print(f"Lifespan: 推斷的專案根目錄: {PROJECT_BASE_PATH}")
    # app.state.project_base_path = PROJECT_BASE_PATH # 存儲到 app.state # <--- 移除
    app.state.project_root = PROJECT_ROOT # FastAPI 的 state 中可以保存 Path 物件
    print(f"Lifespan: 專案根目錄 (from core.config): {app.state.project_root}")

    print("Lifespan: FastAPI 應用程式啟動中...")

    # LogManager 初始化時，如果其 db_path 參數是 Path 物件，它需要能處理
    # 或者我們在這裡傳入字串路徑
    log_db_path_to_use = DEFAULT_LOG_DB_PATH
    app.state.log_manager = LogManager(db_path=str(log_db_path_to_use)) # 確保 LogManager 接收 str
    print(f"Lifespan: LogManager 已初始化，日誌將寫入: {log_db_path_to_use}")
    app.state.log_manager.log_event(event_type="application_startup", message="FastAPI 應用程式已啟動。")

    # MainOrchestrator 的 base_path 參數已被移除，它會自行使用 PROJECT_ROOT
    app.state.orchestrator = MainOrchestrator(log_manager=app.state.log_manager)
    print(f"Lifespan: MainOrchestrator 已初始化: {app.state.orchestrator}")

    yield

    print("Lifespan: Shutdown sequence started.")
    if hasattr(app.state, 'orchestrator') and app.state.orchestrator:
        print("Lifespan: MainOrchestrator 正在關閉 (如果需要)...")

    if hasattr(app.state, 'log_manager') and app.state.log_manager:
        app.state.log_manager.log_event(event_type="application_shutdown", message="FastAPI 應用程式已關閉。")
        app.state.log_manager.close()
        print("Lifespan: LogManager 已關閉。")
    print("Lifespan: Shutdown sequence completed.")

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
