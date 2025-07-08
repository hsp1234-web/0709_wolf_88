# prometheus_fire_backend/modules/data_fuser.py

import logging
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataFuser:
    """
    資料融合器 (Data Fuser)。
    負責根據預設的規則和優先級，將來自不同來源的（模擬）數據進行清洗、轉換和融合，
    最終生成「黃金記錄」(Golden Record)。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化資料融合器。

        Args:
            config (Optional[Dict[str, Any]]): 融合規則、優先級等設定。
        """
        self.config = config if config else {}
        logger.info("資料融合器 (DataFuser) 初始化完畢。")
        if self.config:
            logger.info(f"已配置的融合設定: {self.config}")

    def fuse_data(self, mission_id: str, raw_data_map: Dict[str, Any]) -> Dict[str, Any]:
        """
        執行資料融合。

        Args:
            mission_id (str): 當前任務的 ID。
            raw_data_map (Dict[str, Any]): 一個字典，鍵為資料來源名稱，值為從 DataFetcher 獲取到的原始數據。
                                           例如: {"yfinance_data": pd.DataFrame, "twitter_data": List[Tweet]}

        Returns:
            Dict[str, Any]: 融合後的黃金記錄。其結構取決於融合策略。
        """
        logger.info(f"任務 {mission_id}: 開始融合數據。接收到的來源: {list(raw_data_map.keys())}")

        # 這裡將是核心邏輯：
        # 1. 根據 self.config 中的規則，遍歷 raw_data_map 中的數據。
        # 2. 對每個來源的數據進行標準化/清洗。
        # 3. 根據優先級解決衝突（例如，如果多個來源都有 "公司名稱" 欄位，選擇哪個）。
        # 4. 合併欄位，生成統一的黃金記錄。

        # 樁實現：簡單地將所有數據合併到一個字典中，並添加一些融合資訊
        golden_record: Dict[str, Any] = {
            "mission_id": mission_id,
            "fused_fields": {},
            "fusion_log": []
        }

        priority = self.config.get("source_priority", []) # 例如: ["source_A", "source_B"]

        # 簡單的合併，如果有多個來源有相同鍵，後面的會覆蓋前面的（除非有優先級處理）
        # 更複雜的邏輯會在這裡實現
        for source_name, data_content in raw_data_map.items():
            if isinstance(data_content, dict):
                for key, value in data_content.items():
                    # 樁邏輯：簡單地將所有來源的 key 直接放入，不處理衝突
                    # 未來可以根據 key 和 source_name 進行更細緻的處理
                    if key not in golden_record["fused_fields"]:
                        golden_record["fused_fields"][key] = value
                        golden_record["fusion_log"].append(f"Added '{key}' from '{source_name}'")
                    else:
                        # 簡單的衝突日誌，實際應用中會有更複雜的解決策略
                        golden_record["fusion_log"].append(
                            f"Conflict for '{key}': existing value from other source, new from '{source_name}'. Kept existing (樁邏輯)."
                        )
            else:
                # 如果數據不是字典，直接以來源名稱為鍵儲存
                golden_record["fused_fields"][source_name] = data_content
                golden_record["fusion_log"].append(f"Added raw data block from '{source_name}'")


        logger.info(f"任務 {mission_id}: 數據融合完成（樁實現）。黃金記錄包含 {len(golden_record['fused_fields'])} 個欄位。")
        return golden_record

if __name__ == '__main__':
    # 簡易測試 (未來應移至 pytest)
    logger.info("--- 測試 DataFuser (樁) ---")

    fuser = DataFuser(config={"source_priority": ["source_A", "source_C"]})

    mock_raw_data = {
        "source_A": {"name": "Company A from Source A", "value": 100, "unique_A": "A's data"},
        "source_B": {"name": "Company B from Source B", "value": 150, "unique_B": "B's data", "extra_B": "Extra"},
        "source_C": {"description": "Description from C", "value": 120} # source_C value should be ignored if source_A is prioritized for "value"
    }

    golden_record = fuser.fuse_data("test_mission_fuse_001", mock_raw_data)
    print(f"融合後的黃金記錄: {golden_record}")

    # 測試空數據
    empty_record = fuser.fuse_data("test_mission_fuse_002", {})
    print(f"空的原始數據融合結果: {empty_record}")

    # 測試包含非字典數據
    mixed_data = {
        "source_dict": {"field": "value"},
        "source_list": [1, 2, 3],
        "source_string": "just a string"
    }
    mixed_record = fuser.fuse_data("test_mission_fuse_003", mixed_data)
    print(f"混合數據類型的融合結果: {mixed_record}")

    logger.info("--- 測試完畢 ---")
