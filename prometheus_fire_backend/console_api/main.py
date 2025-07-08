# prometheus_fire_backend/console_api/main.py

from fastapi import FastAPI, Request, Response
from contextlib import asynccontextmanager
import logging

# 載入 LogManager (現已更名為 logger.py)
# 假設 uvicorn 從專案根目錄啟動 (e.g., /app)
# 則 'prometheus_fire_backend' 應該在 PYTHONPATH 中或可被解析
from prometheus_fire_backend.modules.logger import LogManager # 檔案名改為 logger, 類名仍為 LogManager
from typing import Optional # <--- 導入 Optional

# --- 全局變數與設定 ---
# 在真實應用中，這些應來自設定檔
LOG_DB_PATH = "logs/api_logs.sqlite" # 和 LogManager 預設的 logs/logs.sqlite 分開或統一
log_manager_instance: Optional[LogManager] = None

# 配置 FastAPI 的日誌，使其與我們的 LogManager 協同工作或分開
# logging.basicConfig(level=logging.INFO) # 應用程式級別的基礎日誌配置
# fastapi_logger = logging.getLogger("fastapi") # 可以獲取fastapi的logger進行配置

# --- FastAPI Lifespan 事件 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 應用程式啟動時
    global log_manager_instance
    print("FastAPI 應用程式啟動中...")
    log_manager_instance = LogManager(db_path=LOG_DB_PATH)
    print(f"LogManager 已初始化，日誌將寫入: {LOG_DB_PATH}")
    log_manager_instance.log_event(event_type="application_startup", message="FastAPI 應用程式已啟動。")
    yield
    # 應用程式關閉時
    print("FastAPI 應用程式關閉中...")
    if log_manager_instance:
        log_manager_instance.log_event(event_type="application_shutdown", message="FastAPI 應用程式已關閉。")
        log_manager_instance.close()
        print("LogManager 已關閉。")

app = FastAPI(
    title="普羅米修斯之火 API",
    description="後端情報處理核心 API，代號「鋼鐵心臟」。",
    version="v1.0",
    lifespan=lifespan # 使用 lifespan 管理啟動與關閉事件
)

@app.get("/")
async def read_root():
    """
    根路徑，用於檢查服務是否正在運行。
    """
    if log_manager_instance:
        log_manager_instance.log_api_call(endpoint="/", method="GET", status_code=200)
    return {"message": "歡迎來到普羅米修斯之火 🔥 - 「鋼鐵心臟」API"}

# 為了能夠透過 uvicorn 運行，我們可以在這裡加入一個簡易的啟動方式
# 但在實際部署時，通常會直接使用 uvicorn 命令列工具
if __name__ == "__main__":
    import uvicorn
    # 注意：在生產環境中，應從設定檔讀取 host 和 port
    # 這裡的 reload=True 僅適用於開發環境
    # 需要確保 uvicorn 從專案根目錄運行，以便模組導入正常
    # 例如在專案根目錄 /app 下執行:
    # uvicorn prometheus_fire_backend.console_api.main:app --reload
    # 或者 python -m uvicorn prometheus_fire_backend.console_api.main:app --reload

    # 如果要直接執行 python prometheus_fire_backend/console_api/main.py，
    # 則需要確保PYTHONPATH包含專案根目錄 /app。
    # 或者在執行前 `export PYTHONPATH=/app:$PYTHONPATH` (或 Windows 的 set)
    import os
    # The app string should be relative to the project root if uvicorn is run from there.
    # If running this script directly, uvicorn needs to know where `prometheus_fire_backend` is.
    # Setting app_dir=".." tells uvicorn to look in the parent directory of this file's directory
    # for the module 'prometheus_fire_backend.console_api.main'
    # This is only relevant if running `python console_api/main.py`
    # For `uvicorn prometheus_fire_backend.console_api.main:app` from root, this block isn't critical.
    uvicorn.run("prometheus_fire_backend.console_api.main:app", host="127.0.0.1", port=8000, reload=True, app_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


import uuid
from pydantic import BaseModel, Field
from typing import Optional

# --- API Request Models ---

class MissionParameters(BaseModel):
    """
    任務參數模型。目前為空，可根據後續需求擴展。
    例如：
    target_keyword: str = Field(..., description="目標關鍵字")
    data_sources: list[str] = Field([], description="指定資料來源")
    """
    pass

# --- API Response Models ---

class StartMissionResponse(BaseModel):
    """
    啟動任務的回應模型。
    """
    mission_id: str = Field(..., description="唯一任務 ID")
    message: str = Field(default="任務已成功接收", description="回應訊息")

class MissionStatusResponse(BaseModel):
    """
    查詢任務狀態的回應模型。
    """
    mission_id: str = Field(..., description="唯一任務 ID")
    status: str = Field(default="pending", description="任務當前狀態 (e.g., pending, processing, completed, failed)")
    progress: float = Field(default=0.0, description="任務進度百分比 (0.0 to 1.0)")
    message: str = Field(default="任務已接收，等待處理", description="狀態相關訊息")
    details: Optional[dict] = Field(None, description="其他詳細資訊")


# --- API Endpoints ---

@app.post("/api/v1/start_mission", response_model=StartMissionResponse, tags=["Mission Control"])
async def start_mission(params: Optional[MissionParameters] = None):
    """
    啟動一個新的情報蒐集與處理任務。

    接收任務參數，立即返回一個虛構的 `mission_id`。
    實際的任務處理將在背景異步執行（未來實現）。
    """
    mission_id = str(uuid.uuid4())
    # 在此階段，我們僅返回 mission_id，不執行任何實際操作。
    # 未來，這裡會觸發 MainOrchestrator
    print(f"接收到任務啟動請求。參數: {params.model_dump_json() if params else '無'}. 分配 Mission ID: {mission_id}") # 使用 model_dump_json 獲取 Pydantic 參數

    response_data = StartMissionResponse(mission_id=mission_id)

    if log_manager_instance:
        log_manager_instance.log_api_call(
            endpoint="/api/v1/start_mission",
            method="POST",
            mission_id=mission_id,
            request_body=params.model_dump() if params else None, # Pydantic model to dict
            response_body=response_data.model_dump(),
            status_code=200 # Assuming success
        )
    return response_data

@app.get("/api/v1/mission_status/{mission_id}", response_model=MissionStatusResponse, tags=["Mission Control"])
async def get_mission_status(mission_id: str):
    """
    查詢指定任務的當前狀態與進度。

    接收 `mission_id`，返回一個靜態的模擬進度 JSON。
    """
    print(f"接收到狀態查詢請求。Mission ID: {mission_id}")
    # 在此階段，我們返回一個固定的模擬狀態。
    # 未來，這裡會向 MainOrchestrator 或狀態管理器查詢真實狀態。
    response_data = MissionStatusResponse(
        mission_id=mission_id,
        status="simulated_pending",
        progress=0.25,
        message="模擬狀態：任務正在排隊等待處理。",
        details={"simulation_note": "此為固定回應，用於 API 樁測試。"}
    )
    if log_manager_instance:
        log_manager_instance.log_api_call(
            endpoint=f"/api/v1/mission_status/{mission_id}",
            method="GET",
            mission_id=mission_id,
            response_body=response_data.model_dump(),
            status_code=200 # Assuming success
        )
    return response_data
