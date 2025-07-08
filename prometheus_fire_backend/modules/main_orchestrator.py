# prometheus_fire_backend/modules/main_orchestrator.py

import logging
from typing import Any, Dict, Optional

# 配置基本的日誌記錄器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MainOrchestrator:
    """
    總調度器 (Main Orchestrator)。
    負責接收任務，編排 data_fetcher、data_fuser 等模組完成整個情報處理流程。
    """
    def __init__(self, data_fetcher: Any, data_fuser: Any, log_manager: Any):
        """
        初始化總調度器。

        Args:
            data_fetcher: 資料獲取器實例。
            data_fuser: 資料融合器實例。
            log_manager: 日誌管理器實例。
        """
        self.data_fetcher = data_fetcher
        self.data_fuser = data_fuser
        self.log_manager = log_manager
        logger.info("總調度器 (MainOrchestrator) 初始化完畢。")

    def start_mission(self, mission_params: Optional[Dict[str, Any]] = None) -> str:
        """
        開始一個新的情報任務。

        Args:
            mission_params: 任務參數字典。

        Returns:
            str: 代表此任務的唯一 ID。
        """
        mission_id = self._generate_mission_id()
        logger.info(f"任務 {mission_id} 開始。參數: {mission_params}")

        if self.log_manager:
            self.log_manager.log_event("mission_started", {"mission_id": mission_id, "params": mission_params})

        # 1. (未來) 解析任務參數，確定情報需求

        # 2. (未來) 指示 DataFetcher 獲取數據
        # raw_data = self.data_fetcher.fetch_data_for_mission(mission_id, mission_params)

        # 3. (未來) 指示 DataFuser 處理與融合數據
        # fused_data = self.data_fuser.fuse_data(mission_id, raw_data)

        # 4. (未來) 儲存結果或進一步處理

        logger.info(f"任務 {mission_id} 的初步流程已啟動（目前為樁實現）。")
        return mission_id

    def get_mission_status(self, mission_id: str) -> Dict[str, Any]:
        """
        獲取指定任務的狀態。

        Args:
            mission_id: 任務 ID。

        Returns:
            Dict[str, Any]: 包含任務狀態的字典。
        """
        logger.info(f"查詢任務 {mission_id} 的狀態。")
        if self.log_manager:
            self.log_manager.log_event("status_queried", {"mission_id": mission_id})

        # 在此階段，返回一個模擬的狀態
        # 未來會從任務管理系統或資料庫中查詢真實狀態
        return {
            "mission_id": mission_id,
            "status": "pending_in_orchestrator",
            "progress": 0.1, # 假設已完成10% (例如，任務已接收)
            "message": "任務已由總調度器接收，等待後續模組處理（樁實現）。",
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
    class MockDataFetcher:
        def fetch_data_for_mission(self, mission_id, params):
            logger.info(f"[MockDataFetcher] 正在為任務 {mission_id} 獲取數據，參數: {params}")
            return {"source1": "data1", "source2": "data2"}

    class MockDataFuser:
        def fuse_data(self, mission_id, raw_data):
            logger.info(f"[MockDataFuser] 正在為任務 {mission_id} 融合數據: {raw_data}")
            return {"fused_field": "fused_value"}

    class MockLogManager:
        def log_event(self, event_type: str, data: dict):
            logger.info(f"[MockLogManager] 事件: {event_type}, 資料: {data}")

    logger.info("--- 測試 MainOrchestrator (樁) ---")
    mock_fetcher = MockDataFetcher()
    mock_fuser = MockDataFuser()
    mock_logger = MockLogManager()

    orchestrator = MainOrchestrator(data_fetcher=mock_fetcher, data_fuser=mock_fuser, log_manager=mock_logger)

    test_mission_params = {"target": "test_target_A"}
    mission_id = orchestrator.start_mission(test_mission_params)
    print(f"啟動的任務 ID: {mission_id}")

    status = orchestrator.get_mission_status(mission_id)
    print(f"任務狀態: {status}")

    status_non_existent = orchestrator.get_mission_status("non_existent_id")
    print(f"不存在的任務狀態: {status_non_existent}")
    logger.info("--- 測試完畢 ---")
