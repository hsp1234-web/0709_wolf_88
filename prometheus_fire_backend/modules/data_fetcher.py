# prometheus_fire_backend/modules/data_fetcher.py

import logging
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataFetcher:
    """
    資料獲取器 (Data Fetcher)。
    負責根據任務需求，從不同的資料來源（真實 API 或模擬客戶端）獲取原始數據。
    """
    def __init__(self, execution_mode: str = "SIMULATION", clients: Optional[Dict[str, Any]] = None):
        """
        初始化資料獲取器。

        Args:
            execution_mode (str): 執行模式 ("SIMULATION" 或 "PRODUCTION")。
            clients (Optional[Dict[str, Any]]): 一個字典，鍵為客戶端名稱，值為客戶端實例。
                                                 例如: {"yfinance_client": yfinance_client_instance,
                                                        "mock_yfinance_client": mock_yfinance_client_instance}
        """
        self.execution_mode = execution_mode
        self.clients = clients if clients else {}
        logger.info(f"資料獲取器 (DataFetcher) 初始化完畢。執行模式: {self.execution_mode}")
        if self.clients:
            logger.info(f"已配置的客戶端: {list(self.clients.keys())}")

    def fetch_data_for_mission(self, mission_id: str, mission_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        為指定任務獲取數據。

        Args:
            mission_id (str): 任務 ID。
            mission_params (Dict[str, Any]): 任務參數，可能包含目標、資料來源等。

        Returns:
            Dict[str, Any]: 一個字典，鍵為資料來源名稱，值為獲取到的數據。
                            例如: {"yfinance_data": pd.DataFrame, "twitter_data": List[Tweet]}
        """
        logger.info(f"任務 {mission_id}: 開始獲取數據。參數: {mission_params}")

        # 這裡將是核心邏輯：
        # 1. 分析 mission_params，確定需要哪些資料來源 (e.g., 'yfinance', 'twitter_api')
        # 2. 根據 self.execution_mode 選擇合適的客戶端 (真實或模擬)
        # 3. 調用客戶端獲取數據
        # 4. 聚合結果

        # 樁實現：返回模擬數據
        simulated_data = {}
        required_sources = mission_params.get("data_sources", ["mock_source_A", "mock_source_B"])

        for source_name in required_sources:
            client_to_use = None
            if self.execution_mode == "SIMULATION":
                client_key = f"mock_{source_name}_client" # 假設模擬客戶端有 mock_ 前綴
                if client_key in self.clients:
                    client_to_use = self.clients[client_key]
                else: # 如果沒有特定模擬客戶端，也可能有一個通用的模擬客戶端或直接返回樁數據
                    logger.warning(f"任務 {mission_id}: 模擬模式下找不到客戶端 {client_key}，將返回預設模擬數據。")
                    simulated_data[source_name] = self._get_default_mock_data(source_name)

            elif self.execution_mode == "PRODUCTION":
                client_key = f"{source_name}_client" # 假設真實客戶端無前綴
                if client_key in self.clients:
                    client_to_use = self.clients[client_key]
                else:
                    logger.error(f"任務 {mission_id}: 生產模式下找不到客戶端 {client_key}。")
                    simulated_data[source_name] = {"error": f"Client {client_key} not configured."}

            if client_to_use:
                try:
                    # 假設所有客戶端都有一個名為 'fetch' 或類似的方法
                    # 這個方法可能需要 mission_params 中的特定參數
                    # 例如: client_to_use.fetch(target=mission_params.get("target_keyword"))
                    logger.info(f"任務 {mission_id}: 使用客戶端 {client_key} 為來源 {source_name} 獲取數據。")
                    # 樁實現：假設客戶端返回一個簡單的字典
                    simulated_data[source_name] = client_to_use.fetch(params=mission_params)
                except Exception as e:
                    logger.error(f"任務 {mission_id}: 客戶端 {client_key} 獲取數據時出錯: {e}")
                    simulated_data[source_name] = {"error": str(e)}
            elif self.execution_mode == "SIMULATION" and client_key not in self.clients:
                pass # 已經處理過這種情況了
            else:
                 logger.warning(f"任務 {mission_id}: 未能為來源 {source_name} 找到或使用客戶端。")


        logger.info(f"任務 {mission_id}: 數據獲取完成（樁實現）。獲取到的來源: {list(simulated_data.keys())}")
        return simulated_data

    def _get_default_mock_data(self, source_name: str) -> Any:
        """輔助函數，返回特定來源的預設模擬數據。"""
        if source_name == "mock_source_A":
            return {"content": "來自模擬來源 A 的數據", "items": [1, 2, 3]}
        elif source_name == "mock_source_B":
            return {"content": "來自模擬來源 B 的數據", "value": 123.45}
        else:
            return {"content": f"未知模擬來源 {source_name} 的數據"}

if __name__ == '__main__':
    # 簡易測試 (未來應移至 pytest)
    class MockClientA:
        def fetch(self, params):
            logger.info(f"[MockClientA] Fetching with params: {params}")
            return {"client_A_data": "some data from A", "params_received": params}

    class MockClientB_Real:
        def fetch(self, params):
            logger.info(f"[MockClientB_Real] Fetching with params: {params}")
            # 模擬真實客戶端的行為，例如網路請求
            # raise ConnectionError("Failed to connect to real B service") # 模擬錯誤
            return {"client_B_real_data": "some data from real B"}

    logger.info("--- 測試 DataFetcher (樁) ---")

    # 測試模擬模式
    mock_clients_sim = {
        "mock_mock_source_A_client": MockClientA(), # 注意鍵名匹配 fetch_data_for_mission 中的邏輯
    }
    fetcher_sim = DataFetcher(execution_mode="SIMULATION", clients=mock_clients_sim)
    test_params_sim = {"data_sources": ["mock_source_A", "mock_source_C"], "target_keyword": "test"}
    data_sim = fetcher_sim.fetch_data_for_mission("test_mission_001", test_params_sim)
    print(f"模擬模式獲取到的數據: {data_sim}")

    # 測試生產模式 (假設有一個真實客戶端配置)
    mock_clients_prod = {
        "mock_source_A_client": MockClientA(), # 真實客戶端鍵名
        "another_source_client": MockClientB_Real()
    }
    fetcher_prod = DataFetcher(execution_mode="PRODUCTION", clients=mock_clients_prod)
    test_params_prod = {"data_sources": ["mock_source_A", "another_source", "unknown_source"], "target_keyword": "prod_test"}
    data_prod = fetcher_prod.fetch_data_for_mission("test_mission_002", test_params_prod)
    print(f"生產模式獲取到的數據: {data_prod}")

    logger.info("--- 測試完畢 ---")
