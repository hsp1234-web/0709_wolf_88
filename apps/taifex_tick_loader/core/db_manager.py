import duckdb
import pydantic
import datetime  # <--- 新增導入
import pandas as pd  # <--- 新增導入 Pandas
from typing import List, Type, Optional
from .schemas import TaifexTick  # 確保可以從同一個 core 目錄導入

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
                raise ValueError(
                    f"不支援的 Pydantic 類型: {pydantic_type} 用於欄位 '{field_name}'"
                )
            columns.append(f"{field_name} {duckdb_type}")
        return ", ".join(columns)

    def create_table_if_not_exists(
        self, table_name: str, model: Type[pydantic.BaseModel]
    ):
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
        except Exception:
            # print(f"[DBManager] 創建資料表 '{table_name}' 失敗: {e}") # 用於調試
            raise
        # finally:
        # self.close() # 保持連接開啟，直到明確關閉或對象銷毀

    def insert_ticks(self, table_name: str, ticks: List[TaifexTick]):
        """
        將 TaifexTick 對象列表高效地批量寫入指定的表中。

        Args:
            table_name (str): 目標表名。
            ticks (List[TaifexTick]): TaifexTick 對象的列表。
        """
        if not ticks:
            # print("[DBManager] 沒有數據需要插入。") # 用於調試
            return

        conn = self._connect()
        try:
            # 將 Pydantic 對象轉換為字典列表
            data_to_insert = [tick.model_dump() for tick in ticks]

            # 使用 DuckDB 的參數化查詢或 DataFrame 插入以獲得更佳性能和安全性
            # 這裡我們使用其內建的 append 功能，它對 DataFrame 非常友好
            # 首先檢查 data_to_insert 是否為空，避免 duckdb 在空列表上出錯
            if data_to_insert:
                # print(f"[DBManager] 準備插入 {len(data_to_insert)} 筆數據到 '{table_name}'。") # 用於調試
                # 將字典列表轉換為 Pandas DataFrame
                ticks_df = pd.DataFrame(data_to_insert)

                # 使用 DuckDB 的 register 方法註冊 DataFrame，然後執行 INSERT INTO SELECT
                # 或者，對於較新版本的 DuckDB，可以直接使用 conn.append(table_name, ticks_df)
                # 為了更廣泛的兼容性，我們這裡堅持使用 register + INSERT INTO
                conn.register("ticks_df_temp_view", ticks_df)
                conn.execute(
                    f"INSERT INTO {table_name} SELECT * FROM ticks_df_temp_view"
                )
                conn.unregister("ticks_df_temp_view")  # 註銷臨時視圖
                # print(f"[DBManager] 成功插入 {len(data_to_insert)} 筆數據到 '{table_name}'。") # 用於調試
            else:
                # print("[DBManager] 數據列表為空，未執行插入操作。") # 用於調試
                pass

        except Exception:
            # print(f"[DBManager] 插入數據到 '{table_name}' 失敗: {e}") # 用於調試
            raise
        # finally:
        # self.close() # 保持連接開啟

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


# 簡單的測試/使用範例
if __name__ == "__main__":
    print("正在執行 DatabaseManager 測試...")
    db_file = "test_market_data.duckdb"
    table_name = "bronze_taifex_ticks_test"

    # 清理舊的測試數據庫文件 (如果存在)
    import os

    if os.path.exists(db_file):
        os.remove(db_file)
    if os.path.exists(f"{db_file}.wal"):  # DuckDB 的 WAL 文件
        os.remove(f"{db_file}.wal")

    try:
        with DatabaseManager(db_path=db_file) as db_manager:
            print(
                f"1. 使用 Pydantic 模型 '{TaifexTick.__name__}' 創建資料表 '{table_name}'..."
            )
            db_manager.create_table_if_not_exists(table_name, TaifexTick)
            print(f"資料表 '{table_name}' 創建/檢查完畢。")

            print("\n2. 準備插入模擬 Tick 數據...")
            sample_ticks = [
                TaifexTick(
                    timestamp=datetime.datetime(2023, 9, 1, 9, 0, 0, 123456),
                    price=16700.0,
                    volume=5,
                    instrument="TXF202309",
                    tick_type="Trade",
                ),
                TaifexTick(
                    timestamp=datetime.datetime(2023, 9, 1, 9, 0, 1, 234567),
                    price=16701.0,
                    volume=2,
                    instrument="TXF202309",
                    tick_type="Trade",
                ),
                TaifexTick(
                    timestamp=datetime.datetime(2023, 9, 1, 9, 0, 1, 500000),
                    price=16700.0,
                    volume=10,
                    instrument="TXF202309",
                    tick_type="Trade",
                ),
            ]
            db_manager.insert_ticks(table_name, sample_ticks)
            print(f"成功插入 {len(sample_ticks)} 筆數據。")

            print("\n3. 驗證數據是否已寫入...")
            conn = db_manager._connect()  # 重新獲取連接 (如果之前關閉了) 或使用現有連接
            result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            if result:
                print(f"資料表 '{table_name}' 中的記錄數: {result[0]}")
                assert result[0] == len(sample_ticks)
            else:
                print(f"無法從 '{table_name}' 讀取記錄數。")

            result_all = conn.execute(f"SELECT * FROM {table_name}").fetchall()
            print(f"\n資料表 '{table_name}' 中的所有數據:")
            for row in result_all:
                print(row)

        print("\nDatabaseManager 測試執行完畢。")

    except Exception as e:
        print(f"DatabaseManager 測試過程中發生錯誤: {e}")
    finally:
        # 再次清理測試數據庫文件
        if os.path.exists(db_file):
            os.remove(db_file)
        if os.path.exists(f"{db_file}.wal"):
            os.remove(f"{db_file}.wal")
