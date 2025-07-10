import duckdb
import pydantic
import datetime # <--- 新增導入
import pandas as pd # <--- 新增導入 Pandas
from typing import List, Type, Optional
# 移除 .schemas import TaifexTick，因為這個 db_manager 是通用的
# 如果需要特定的 schema，應該在使用時傳入

# DuckDB 資料類型與 Pydantic/Python 資料類型的映射
PYDANTIC_TO_DUCKDB_TYPE_MAP = {
    datetime.datetime: "TIMESTAMP",
    float: "DOUBLE",
    int: "INTEGER",
    str: "VARCHAR",
    bool: "BOOLEAN",
}

class DatabaseManager:
    """
    負責所有與 DuckDB 的交互。
    """
    def __init__(self, db_path: str = "market_data.duckdb"):
        """
        初始化 DatabaseManager。

        Args:
            db_path (str): DuckDB 數據庫文件的路徑。
        """
        self.db_path = db_path
        self._connection: Optional[duckdb.DuckDBPyConnection] = None
        # print(f"[DBManager] 初始化，數據庫路徑: {self.db_path}") # 用於調試

    def _connect(self) -> duckdb.DuckDBPyConnection:
        """
        建立並返回一個 DuckDB 連接。
        如果已有活動連接，則重用它。
        """
        if self._connection is None:
            # print(f"[DBManager] 正在連接到 DuckDB: {self.db_path}") # 用於調試
            self._connection = duckdb.connect(database=self.db_path, read_only=False)
        return self._connection

    def _pydantic_to_duckdb_schema(self, model: Type[pydantic.BaseModel]) -> str:
        """
        將 Pydantic 模型轉換為 DuckDB 表的欄位定義字串。
        """
        columns = []
        for field_name, field_obj in model.model_fields.items():
            # Pydantic v2 中，類型信息在 field_obj.annotation
            pydantic_type = field_obj.annotation
            duckdb_type = PYDANTIC_TO_DUCKDB_TYPE_MAP.get(pydantic_type)
            if duckdb_type is None:
                raise ValueError(f"不支援的 Pydantic 類型: {pydantic_type} 用於欄位 '{field_name}'")
            columns.append(f"{field_name} {duckdb_type}")
        return ", ".join(columns)

    def create_table_if_not_exists(self, table_name: str, model: Type[pydantic.BaseModel]):
        """
        根據 Pydantic 模型自動生成 CREATE TABLE SQL 語句並執行，
        確保表存在且結構正確。

        Args:
            table_name (str): 要創建的表名。
            model (Type[pydantic.BaseModel]): 用於定義表結構的 Pydantic 模型。
        """
        conn = self._connect()
        try:
            schema_str = self._pydantic_to_duckdb_schema(model)
            query = f"CREATE TABLE IF NOT EXISTS {table_name} ({schema_str})"
            # print(f"[DBManager] 執行 SQL: {query}") # 用於調試
            conn.execute(query)
            # print(f"[DBManager] 資料表 '{table_name}' 已成功檢查/創建。") # 用於調試
        except Exception as e:
            # print(f"[DBManager] 創建資料表 '{table_name}' 失敗: {e}") # 用於調試
            raise
        # finally:
            # self.close() # 保持連接開啟，直到明確關閉或對象銷毀

    def insert_data(self, table_name: str, data: List[pydantic.BaseModel]):
        """
        將 Pydantic BaseModel 對象列表高效地批量寫入指定的表中。
        這個方法是通用的，可以處理任何 Pydantic 模型列表。

        Args:
            table_name (str): 目標表名。
            data (List[pydantic.BaseModel]): Pydantic BaseModel 對象的列表。
        """
        if not data:
            # print("[DBManager] 沒有數據需要插入。") # 用於調試
            return

        conn = self._connect()
        try:
            # 將 Pydantic 對象轉換為字典列表
            data_to_insert = [item.model_dump() for item in data]

            if data_to_insert:
                # print(f"[DBManager] 準備插入 {len(data_to_insert)} 筆數據到 '{table_name}'。") # 用於調試
                df = pd.DataFrame(data_to_insert)
                conn.register('df_temp_view', df)
                conn.execute(f"INSERT INTO {table_name} SELECT * FROM df_temp_view")
                conn.unregister('df_temp_view')
                # print(f"[DBManager] 成功插入 {len(data_to_insert)} 筆數據到 '{table_name}'。") # 用於調試
            else:
                # print("[DBManager] 數據列表為空，未執行插入操作。") # 用於調試
                pass
        except Exception as e:
            # print(f"[DBManager] 插入數據到 '{table_name}' 失敗: {e}") # 用於調試
            raise

    def close(self):
        """
        關閉 DuckDB 連接。
        """
        if self._connection is not None:
            # print("[DBManager] 正在關閉 DuckDB 連接。") # 用於調試
            self._connection.close()
            self._connection = None

    def __enter__(self):
        # print("[DBManager] 進入上下文管理器，建立連接。") # 用於調試
        self._connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # print("[DBManager] 退出上下文管理器，關閉連接。") # 用於調試
        self.close()

# 移除原來的 if __name__ == '__main__': 區塊，因為這個管理器是核心庫的一部分，
# 不應包含特定服務的測試代碼。測試應在專門的測試文件中進行。
# 我也將 `insert_ticks` 方法重命名為更通用的 `insert_data`，
# 並修改其類型提示以接受 `List[pydantic.BaseModel]`。
# 這樣，這個 DatabaseManager 就可以用於插入任何 Pydantic 模型定義的數據。
