# prometheus_fire_backend/modules/log_manager.py

import logging
import sqlite3
import json
from datetime import datetime
from typing import Any, Dict, Optional, List # Added List here

# 與其他模組分開配置 logger，避免basicConfig衝突
module_logger = logging.getLogger(__name__) # Renamed to avoid conflict with global 'logger'

# 確保 module_logger 至少有一個處理器，以便在 __main__ 外也能看到日誌輸出
if not module_logger.hasHandlers():
    handler = logging.StreamHandler() # 輸出到 stderr
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    module_logger.addHandler(handler)
    module_logger.setLevel(logging.INFO) # 設定預設級別，可由應用調整
    # module_logger.propagate = False # 如果不希望日誌向 root logger 傳播


class LogManager:
    """
    中心化日誌管理器 (LogManager)。
    負責將應用程式的關鍵事件、API 呼叫、錯誤等記錄到結構化的日誌存儲中（例如 SQLite 資料庫）。
    """
    def __init__(self, db_path: str = "logs/logs.sqlite"):
        """
        初始化日誌管理器。

        Args:
            db_path (str): SQLite 資料庫檔案的路徑。
        """
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        module_logger.info(f"LogManager __init__ called for db_path: {self.db_path}")
        try:
            self._ensure_db_and_table()
            module_logger.info(f"日誌管理器 (LogManager) 初始化成功。日誌資料庫: {self.db_path}")
        except Exception as e:
            module_logger.error(f"LogManager 初始化過程中 _ensure_db_and_table 失敗: {e}", exc_info=True)
            # 即使初始化失敗，也可能希望應用繼續運行，但日誌功能會受限

    def _get_connection(self) -> sqlite3.Connection:
        """獲取資料庫連接。如果連接不存在或已關閉，則創建新連接。"""
        if self._conn is None:
            module_logger.info(f"嘗試建立到 {self.db_path} 的 SQLite 連接。")
            try:
                # 確保 logs 目錄存在
                import os
                db_dir = os.path.dirname(self.db_path)
                if db_dir and not os.path.exists(db_dir): # 檢查 db_dir 是否為空 (例如 db_path="logs.sqlite")
                    module_logger.info(f"日誌目錄 {db_dir} 不存在，正在創建...")
                    os.makedirs(db_dir, exist_ok=True)
                    module_logger.info(f"日誌目錄 {db_dir} 已創建 (或已存在)。")

                self._conn = sqlite3.connect(self.db_path, check_same_thread=False) # check_same_thread=False for FastAPI
                self._conn.row_factory = sqlite3.Row # 方便按列名訪問
                module_logger.info(f"已成功連接到 SQLite 資料庫: {self.db_path}")

                # <<<< 新增檔案存在性檢查 >>>>
                abs_db_path = os.path.abspath(self.db_path)
                cwd = os.getcwd()
                module_logger.info(f"Python CWD: {cwd}. Absolute DB path: {abs_db_path}.")
                if os.path.exists(self.db_path): # 或使用 abs_db_path 進行檢查
                    module_logger.info(f"確認：資料庫檔案 {self.db_path} (絕對路徑: {abs_db_path}) 在 connect 後存在。")
                else:
                    module_logger.warning(f"警告：資料庫檔案 {self.db_path} (絕對路徑: {abs_db_path}) 在 connect 後不存在！")
                # <<<< 結束新增檢查 >>>>

            except sqlite3.Error as e:
                module_logger.error(f"無法連接到日誌資料庫 {self.db_path}: {e}", exc_info=True)
                raise # 重新拋出異常，讓調用者知道連接失敗
            except OSError as oe: # 捕捉 os.makedirs 可能的錯誤
                module_logger.error(f"創建日誌目錄時發生 OS 錯誤 for {self.db_path}: {oe}", exc_info=True)
                raise
        return self._conn

    def _ensure_db_and_table(self):
        """確保資料庫檔案和日誌表存在。"""
        module_logger.info(f"確保資料庫表 system_logs 存在於 {self.db_path}...")
        try:
            conn = self._get_connection() # 這會處理目錄創建和連接本身
            cursor = conn.cursor()
            module_logger.info(f"Executing CREATE TABLE IF NOT EXISTS system_logs on {self.db_path}")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    event_type TEXT NOT NULL,
                    source_module TEXT,
                    mission_id TEXT,
                    level TEXT DEFAULT 'INFO', -- e.g., INFO, WARNING, ERROR, CRITICAL, API_CALL
                    message TEXT,
                    details TEXT, -- JSON string for additional structured data
                    raw_request TEXT, -- For API calls, the raw request body
                    raw_response TEXT -- For API calls, the raw response body
                )
            """)
            conn.commit()
        except sqlite3.Error as e:
            module_logger.error(f"建立日誌表時出錯: {e}")
        # 不在此處關閉連接，保持連接以供後續使用

    def log_event(self,
                  event_type: str,
                  message: Optional[str] = None,
                  details: Optional[Dict[str, Any]] = None,
                  source_module: Optional[str] = None,
                  mission_id: Optional[str] = None,
                  level: str = "INFO",
                  raw_request: Optional[str] = None,
                  raw_response: Optional[str] = None):
        """
        記錄一個通用事件。

        Args:
            event_type (str): 事件的類型 (e.g., "mission_started", "data_fetched", "api_error").
            message (Optional[str]): 事件的描述性訊息。
            details (Optional[Dict[str, Any]]): 包含事件相關結構化數據的字典，將轉為 JSON 字串儲存。
            source_module (Optional[str]): 觸發事件的模組名稱。
            mission_id (Optional[str]): 與事件相關的任務 ID (如果適用)。
            level (str): 日誌級別 (INFO, WARNING, ERROR, etc.)。
            raw_request (Optional[str]): API 請求內容。
            raw_response (Optional[str]): API 回應內容。
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            details_json: Optional[str] = None
            if details:
                try:
                    details_json = json.dumps(details)
                except TypeError as te:
                    module_logger.warning(f"無法將日誌詳情序列化為 JSON: {te}. 詳情: {details}")
                    details_json = json.dumps({"error": "Serialization failed", "original_details": str(details)})

            sql = """
                INSERT INTO system_logs
                (event_type, message, details, source_module, mission_id, level, raw_request, raw_response, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            # 使用 datetime.now() 来确保时间戳的准确性
            current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


            cursor.execute(sql, (
                event_type,
                message,
                details_json,
                source_module,
                mission_id,
                level.upper(),
                raw_request,
                raw_response,
                current_timestamp
            ))
            conn.commit()
            # module_logger.debug(f"事件已記錄: {event_type} - {message}") # 避免過多日誌輸出
        except sqlite3.Error as e:
            module_logger.error(f"記錄事件到 SQLite 時出錯: {e}")
        except Exception as ex: # Catch any other unexpected errors
            module_logger.error(f"記錄事件時發生未知錯誤: {ex}")

    def log_api_call(self,
                     endpoint: str,
                     method: str,
                     mission_id: Optional[str] = None,
                     request_body: Optional[Any] = None,
                     response_body: Optional[Any] = None,
                     status_code: Optional[int] = None,
                     source_ip: Optional[str] = None):
        """
        專門用於記錄 API 呼叫的輔助方法。
        """
        message = f"API Call: {method} {endpoint}"
        if status_code:
            message += f" -> Status: {status_code}"

        details_dict: Dict[str, Any] = {"endpoint": endpoint, "method": method}
        if status_code is not None: # Ensure status_code=0 is also logged
            details_dict["status_code"] = status_code
        if source_ip:
            details_dict["source_ip"] = source_ip

        # 處理 request_body 和 response_body 的序列化
        req_str: Optional[str] = None
        if request_body:
            try:
                req_str = json.dumps(request_body) if not isinstance(request_body, str) else request_body
            except Exception:
                req_str = str(request_body) # Fallback to string representation

        res_str: Optional[str] = None
        if response_body:
            try:
                res_str = json.dumps(response_body) if not isinstance(response_body, str) else response_body
            except Exception:
                res_str = str(response_body) # Fallback

        self.log_event(
            event_type="api_call",
            message=message,
            details=details_dict,
            source_module="console_api",
            mission_id=mission_id,
            level="INFO", # API 呼叫通常是 INFO 級別，除非出錯
            raw_request=req_str,
            raw_response=res_str
        )

    def get_logs(self, limit: int = 100, event_type: Optional[str] = None, mission_id: Optional[str] = None) -> List[Dict]:
        """
        從資料庫檢索日誌。
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            query = "SELECT * FROM system_logs"
            conditions = []
            params = []

            if event_type:
                conditions.append("event_type = ?")
                params.append(event_type)
            if mission_id:
                conditions.append("mission_id = ?")
                params.append(mission_id)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, tuple(params))
            logs = [dict(row) for row in cursor.fetchall()] # 將 sqlite3.Row 轉換為字典
            return logs
        except sqlite3.Error as e:
            module_logger.error(f"檢索日誌時出錯: {e}")
            return []

    def close(self):
        """關閉資料庫連接。"""
        if self._conn:
            self._conn.close()
            self._conn = None
            module_logger.info("日誌管理器資料庫連接已關閉。")


if __name__ == '__main__':
    # 簡易測試 (未來應移至 pytest 或由應用程式統一管理)
    # 配置一個簡單的控制台日誌輸出，以便在測試時看到 module_logger 的輸出
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    module_logger.info("--- 測試 LogManager (樁) ---")
    # 重要：測試時使用不同的資料庫路徑，避免污染主日誌檔
    test_db_path = "logs/test_logs.sqlite"
    import os
    if os.path.exists(test_db_path):
        os.remove(test_db_path) # 清理舊的測試資料庫

    log_manager = LogManager(db_path=test_db_path)

    log_manager.log_event(
        event_type="test_event_1",
        message="這是一個測試事件。",
        details={"key1": "value1", "number": 123},
        source_module="test_script",
        mission_id="test_mission_log_001",
        level="DEBUG"
    )

    log_manager.log_api_call(
        endpoint="/api/test",
        method="POST",
        mission_id="test_mission_log_002",
        request_body={"param": "test"},
        response_body={"result": "ok"},
        status_code=200,
        source_ip="127.0.0.1"
    )

    log_manager.log_event(
        event_type="another_event",
        message="又一個事件，這次是警告。",
        level="WARNING",
        source_module="main_tester"
    )

    retrieved_logs = log_manager.get_logs(limit=5)
    module_logger.info(f"檢索到的日誌 ({len(retrieved_logs)} 條):")
    for log_entry in retrieved_logs:
        # 為了更簡潔的輸出，details 可能會很長
        if log_entry.get("details") and len(log_entry["details"]) > 50 :
            log_entry["details"] = log_entry["details"][:50] + "..."
        print(log_entry)

    # 測試按 mission_id 檢索
    mission_logs = log_manager.get_logs(mission_id="test_mission_log_001")
    module_logger.info(f"Mission 'test_mission_log_001' 的日誌 ({len(mission_logs)} 條): {mission_logs}")

    log_manager.close() # 確保關閉連接
    module_logger.info(f"測試日誌已寫入到 {test_db_path}")
    module_logger.info("--- 測試完畢 ---")
