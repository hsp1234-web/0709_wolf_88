# prometheus_fire_backend/modules/orchestrator.py

import logging
from typing import Any, Dict, Optional
from datetime import datetime
import os

# 假設 TaifexClient 位於 src.taifex_data_fetcher.client
# 為了讓 MainOrchestrator 能夠找到它，需要確保PYTHONPATH設定正確，
# 或者使用相對路徑導入（如果結構允許）。
# 這裡我們假設執行環境的PYTHONPATH包含了專案根目錄。
from src.taifex_data_fetcher.client import TaifexClient

# 配置基本的日誌記錄器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    # 簡單的內存任務狀態存儲 (用於模擬)
    # 在生產環境中，這應該是一個持久化的存儲，如 Redis 或資料庫
    _mission_states: Dict[str, Dict[str, Any]] = {}

    def __init__(self, data_fetcher: Optional[Any] = None, data_fuser: Optional[Any] = None, log_manager: Optional[Any] = None, base_path: Optional[str] = None):
        """
        初始化總調度器。

        Args:
            data_fetcher: (可選) 通用資料獲取器實例。
            data_fuser: (可選) 通用資料融合器實例。
            log_manager: (可選) 日誌管理器實例。
            base_path: (可選) 專案的根目錄路徑，用於解析相對路徑如 mock_data 和 data_lake。
                       如果為 None，則嘗試使用當前工作目錄的上一層作為根目錄（假設 modules 在根目錄的子目錄中）。
        """
        self.data_fetcher = data_fetcher
        self.data_fuser = data_fuser
        self.log_manager = log_manager

        if base_path:
            self.project_base_path = base_path
        else:
            # 假設 orchestrator.py 在 prometheus_fire_backend/modules/ 下
            # 則 project_base_path 是 ../../ (相對於此檔案)
            self.project_base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

        logger.info(f"總調度器 (MainOrchestrator) 初始化完畢。專案根目錄設定為: {self.project_base_path}")
        # 清理舊的任務狀態，以便測試時環境乾淨
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
            mission_params = {}

        logger.info(f"任務 {mission_id} 開始。參數: {mission_params}")
        MainOrchestrator._mission_states[mission_id] = {
            "status": MISSION_STATUS_PENDING,
            "params": mission_params,
            "message": "任務已接收，等待處理。",
            "details": {}
        }

        if self.log_manager:
            self.log_manager.log_event("mission_started", {"mission_id": mission_id, "params": mission_params})

        mission_type = mission_params.get("type")

        if mission_type == "fetch_taifex":
            self._execute_fetch_taifex_task(mission_id, mission_params)
        # elif mission_type == "other_type":
            # self._execute_other_task(mission_id, mission_params)
        else:
            logger.warning(f"任務 {mission_id}: 未知的任務類型 '{mission_type}' 或未提供任務類型。")
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED,
                "message": f"任務失敗：未知的任務類型 '{mission_type}' 或未提供任務類型。"
            })

        return mission_id

    def _execute_fetch_taifex_task(self, mission_id: str, params: Dict[str, Any]):
        """執行獲取台指期數據的子任務。"""
        MainOrchestrator._mission_states[mission_id]["status"] = MISSION_STATUS_PROCESSING
        MainOrchestrator._mission_states[mission_id]["message"] = "正在處理 fetch_taifex 任務..."
        logger.info(f"任務 {mission_id}: 正在執行 fetch_taifex 任務。")

        data_type = params.get("data_type")
        date_str = params.get("date")

        if not data_type or not date_str:
            logger.error(f"任務 {mission_id}: fetch_taifex 任務缺少 'data_type' 或 'date' 參數。")
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED,
                "message": "任務失敗：fetch_taifex 任務缺少 'data_type' 或 'date' 參數。"
            })
            return

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            logger.error(f"任務 {mission_id}: 日期格式錯誤 '{date_str}'，應為 YYYY-MM-DD。")
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED,
                "message": f"任務失敗：日期格式錯誤 '{date_str}'。"
            })
            return

        # 設定 mock_data 和 data_lake 的路徑，相對於專案根目錄
        mock_data_path = os.path.join(self.project_base_path, "mock_data")
        data_lake_path = os.path.join(self.project_base_path, "data_lake")

        # 確保 TaifexClient 使用的目錄存在
        os.makedirs(mock_data_path, exist_ok=True) # 雖然 mock 檔案應該已存在
        os.makedirs(data_lake_path, exist_ok=True)


        try:
            # 根據指令，總是使用 use_mock_data=True
            taifex_client = TaifexClient(
                use_mock_data=True,
                mock_data_path=mock_data_path,
                data_lake_path=data_lake_path
            )

            fetched_data = None
            if data_type == "institutional_investors":
                logger.info(f"任務 {mission_id}: 正在獲取三大法人籌碼數據 ({date_str})。")
                fetched_data = taifex_client.fetch_institutional_investors(target_date)
            elif data_type == "pc_ratio":
                logger.info(f"任務 {mission_id}: 正在獲取買賣權比率數據 ({date_str})。")
                fetched_data = taifex_client.fetch_pc_ratio(target_date)
            else:
                logger.error(f"任務 {mission_id}: fetch_taifex 任務中未知的 data_type '{data_type}'。")
                MainOrchestrator._mission_states[mission_id].update({
                    "status": MISSION_STATUS_FAILED,
                    "message": f"任務失敗：未知的 data_type '{data_type}'。"
                })
                return

            if fetched_data:
                logger.info(f"任務 {mission_id}: 數據獲取成功，準備儲存。")
                taifex_client.save_data(data=fetched_data, data_type=data_type, date=target_date)
                MainOrchestrator._mission_states[mission_id].update({
                    "status": MISSION_STATUS_SUCCESS,
                    "message": f"任務成功：{data_type} 數據已獲取並儲存。",
                    "details": {"file_path": os.path.join(data_lake_path, target_date.strftime("%Y-%m-%d"), f"{data_type}.json")}
                })
                logger.info(f"任務 {mission_id}: {data_type} 數據已成功儲存。")
            else:
                logger.warning(f"任務 {mission_id}: 未能從 TaifexClient ({data_type}, {date_str}) 獲取到數據。")
                MainOrchestrator._mission_states[mission_id].update({
                    "status": MISSION_STATUS_FAILED, # 或者一個更特定的狀態，如 "no_data_fetched"
                    "message": f"任務警告/失敗：未能從 TaifexClient 獲取到 {data_type} 數據。"
                })

        except Exception as e:
            logger.error(f"任務 {mission_id}: 執行 fetch_taifex 任務時發生錯誤: {e}", exc_info=True)
            MainOrchestrator._mission_states[mission_id].update({
                "status": MISSION_STATUS_FAILED,
                "message": f"任務失敗：執行時發生內部錯誤 - {str(e)}"
            })


    def get_mission_status(self, mission_id: str) -> Dict[str, Any]:
        """
        獲取指定任務的狀態。

        Args:
            mission_id: 任務 ID。

        Returns:
            Dict[str, Any]: 包含任務狀態的字典。如果任務不存在，返回特定訊息。
        """
        logger.info(f"查詢任務 {mission_id} 的狀態。")
        if self.log_manager:
            self.log_manager.log_event("status_queried", {"mission_id": mission_id})

        state = MainOrchestrator._mission_states.get(mission_id)
        if state:
            # 為了符合 MissionStatusResponse，我們需要確保返回的字典結構一致
            return {
                "mission_id": mission_id,
                "status": state.get("status", MISSION_STATUS_FAILED), # 提供預設值
                "progress": 0.0, # 簡單模擬，可以根據狀態細化
                "message": state.get("message", "狀態訊息未提供。"),
                "details": state.get("details", {})
            }
        else:
            return {
                "mission_id": mission_id,
                "status": MISSION_STATUS_FAILED, # 或者 "not_found"
                "progress": 0.0,
                "message": "任務 ID 不存在。",
                "details": {}
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
        def log_event(self, event_type: str, data: dict):
            logger.info(f"[MockLogManager] 事件: {event_type}, 資料: {data}")

    logger.info("--- 測試 MainOrchestrator ---")
    mock_logger_instance = MockLogManager()

    # 測試時，我們假設 mock_data 和 data_lake 目錄在專案根目錄下
    # MainOrchestrator 會嘗試使用 ../../ 作為 base_path
    # 執行此 __main__ 時，os.path.dirname(__file__) 是 prometheus_fire_backend/modules
    # ../../ 應該指向專案根目錄

    # 為了讓此處測試能找到 mock_data，我們需要確保 mock_data 目錄和其中的檔案存在
    # 假設執行 `python -m prometheus_fire_backend.modules.orchestrator` 從根目錄
    # 或者 `python prometheus_fire_backend/modules/orchestrator.py`
    current_script_path = os.path.dirname(os.path.abspath(__file__))
    project_root_for_test = os.path.abspath(os.path.join(current_script_path, "..", ".."))

    MOCK_DATA_DIR_FOR_TEST = os.path.join(project_root_for_test, "mock_data")
    DATA_LAKE_DIR_FOR_TEST = os.path.join(project_root_for_test, "data_lake")

    os.makedirs(MOCK_DATA_DIR_FOR_TEST, exist_ok=True)
    os.makedirs(DATA_LAKE_DIR_FOR_TEST, exist_ok=True)

    # 創建虛擬的模擬數據檔案給 __main__ 測試用
    dummy_institutional_investors_csv = os.path.join(MOCK_DATA_DIR_FOR_TEST, "institutional_investors.csv")
    with open(dummy_institutional_investors_csv, "w", encoding="utf-8") as f:
        f.write("日期,身份別,多方交易口數,多方交易契約金額(百萬元),空方交易口數,空方交易契約金額(百萬元),多空交易口數淨額,多空交易契約金額淨額(百萬元),多方未平倉口數,多方未平倉契約金額(百萬元),空方未平倉口數,空方未平倉契約金額(百萬元),多空未平倉口數淨額,多空未平倉契約金額淨額(百萬元)\n")
        f.write("2025/07/08,自營商,1,1,1,1,0,0,1,1,1,1,0,0\n")

    dummy_pc_ratio_csv = os.path.join(MOCK_DATA_DIR_FOR_TEST, "pc_ratio.csv")
    with open(dummy_pc_ratio_csv, "w", encoding="utf-8") as f:
        f.write("日期,賣權成交量,買權成交量,買賣權成交量比率%,賣權未平倉量,買權未平倉量,買賣權未平倉量比率%\n")
        f.write("2025/07/08,100,100,100.00,100,100,100.00,\n")


    orchestrator = MainOrchestrator(log_manager=mock_logger_instance, base_path=project_root_for_test)

    # 測試 fetch_taifex - institutional_investors
    mission_params_inst = {
        "type": "fetch_taifex",
        "data_type": "institutional_investors",
        "date": "2025-07-08"
    }
    mission_id_inst = orchestrator.start_mission(mission_params_inst)
    print(f"啟動的 fetch_taifex (institutional_investors) 任務 ID: {mission_id_inst}")
    status_inst = orchestrator.get_mission_status(mission_id_inst)
    print(f"任務狀態 (institutional_investors): {status_inst}")
    if status_inst.get("status") == MISSION_STATUS_SUCCESS:
        print(f"  >> 檔案應儲存於: {status_inst.get('details', {}).get('file_path')}")


    # 測試 fetch_taifex - pc_ratio
    mission_params_pc = {
        "type": "fetch_taifex",
        "data_type": "pc_ratio",
        "date": "2025-07-08"
    }
    mission_id_pc = orchestrator.start_mission(mission_params_pc)
    print(f"啟動的 fetch_taifex (pc_ratio) 任務 ID: {mission_id_pc}")
    status_pc = orchestrator.get_mission_status(mission_id_pc)
    print(f"任務狀態 (pc_ratio): {status_pc}")
    if status_pc.get("status") == MISSION_STATUS_SUCCESS:
         print(f"  >> 檔案應儲存於: {status_pc.get('details', {}).get('file_path')}")

    # 測試未知任務類型
    mission_params_unknown = {"type": "unknown_type"}
    mission_id_unknown = orchestrator.start_mission(mission_params_unknown)
    print(f"啟動的未知類型任務 ID: {mission_id_unknown}")
    status_unknown = orchestrator.get_mission_status(mission_id_unknown)
    print(f"任務狀態 (unknown): {status_unknown}")

    # 測試不存在的任務
    status_non_existent = orchestrator.get_mission_status("non_existent_id_123")
    print(f"不存在的任務狀態: {status_non_existent}")

    logger.info("--- Orchestrator __main__ 測試完畢 ---")
    # 清理創建的虛擬檔案和目錄 (可選)
    # os.remove(dummy_institutional_investors_csv)
    # os.remove(dummy_pc_ratio_csv)
    # if not os.listdir(MOCK_DATA_DIR_FOR_TEST): os.rmdir(MOCK_DATA_DIR_FOR_TEST)
    # if not os.listdir(DATA_LAKE_DIR_FOR_TEST): os.rmdir(DATA_LAKE_DIR_FOR_TEST)
    # 注意：如果 data_lake 內已有其他測試產生的檔案，這裡的 rmdir 會失敗
    # 更安全的做法是測試後清理特定的檔案，或在測試開始前確保 data_lake/2025-07-08 目錄是空的。
