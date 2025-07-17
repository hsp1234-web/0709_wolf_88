# core/pipelines/steps/loaders.py
from __future__ import annotations

import datetime
import logging
import os

import duckdb
import pandas as pd
import numpy as np
from typing import List, Dict, Any

from prometheus.core.pipelines.base_step import BaseETLStep, BaseStep
from src.prometheus.core.clients.client_factory import ClientFactory

# --- 依賴管理的說明 ---
# 理想情況下，`DatabaseManager` 和 `TaifexTick` 應該是 `core` 的一部分，
# 或者位於一個可被 `core` 和 `apps` 共享的通用庫中。
# 目前，`apps.taifex_tick_loader.core` 依賴於 `pydantic`。
# 如果 `pydantic` 未安裝或 `PYTHONPATH` 未正確設定，導致以下導入失敗，
# 此步驟將使用簡化的 fallback 邏輯。
# 警告：Fallback 邏輯可能與完整實現存在差異。

try:
    # 假設 apps 目錄與 core 目錄在同一級別，並且都在 PYTHONPATH 中
    from apps.taifex_tick_loader.core.db_manager import DatabaseManager
    from apps.taifex_tick_loader.core.schemas import TaifexTick

    # 檢查 TaifexTick 是否真的是 Pydantic 模型，以確認導入是否符合預期
    if not hasattr(TaifexTick, "model_fields"):  # Pydantic v2 check
        raise ImportError(
            "TaifexTick from apps.taifex_tick_loader.core.schemas does not appear to be a Pydantic v2 model."
        )
    IMPORTED_APP_DEPS = True
    logging.info(
        "Successfully imported DatabaseManager and TaifexTick from apps.taifex_tick_loader.core"
    )
except ImportError as e:
    logging.warning(
        f"Could not import dependencies from apps.taifex_tick_loader.core: {e}. "
        "TaifexTickLoaderStep will use simplified fallback logic for DB interaction and schema. "
        "Ensure 'pydantic' is installed and PYTHONPATH is correctly configured if full functionality is required."
    )
    IMPORTED_APP_DEPS = False

    # Fallback: Define a simple TaifexTick if import fails
    class TaifexTick(dict):  # Simplified fallback
        @staticmethod
        def model_validate(data_dict):  # Mock Pydantic v2's model_validate
            return TaifexTick(data_dict)

        def model_dump(self):  # Mock Pydantic v2's model_dump
            return self

    # Fallback: Define a simplified DatabaseManager
    class DatabaseManager:
        def __init__(self, db_path):
            self.db_path = db_path
            self.conn = None
            self.logger = logging.getLogger("FallbackDatabaseManager")

        def __enter__(self):
            self.logger.info(f"Using fallback DatabaseManager for {self.db_path}")
            if os.path.exists(self.db_path):
                self.logger.debug(
                    f"Fallback: Removing existing DB file: {self.db_path}"
                )
                os.remove(self.db_path)
            if os.path.exists(f"{self.db_path}.wal"):
                self.logger.debug(
                    f"Fallback: Removing existing WAL file: {self.db_path}.wal"
                )
                os.remove(f"{self.db_path}.wal")
            self.conn = duckdb.connect(self.db_path)
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.conn:
                self.conn.close()
                self.logger.info(
                    f"Fallback DatabaseManager connection closed for {self.db_path}"
                )

        def create_table_if_not_exists(
            self, table_name: str, model_schema_ignored
        ):  # schema ignored in fallback
            if not self.conn:
                return  # noqa: E701
            # Fallback schema based on expected DataFrame structure
            # This must align with the DataFrame created from simulated_ticks_data
            fallback_schema_sql = """
                CREATE TABLE IF NOT EXISTS {} (
                    timestamp TIMESTAMP,
                    price DOUBLE,
                    volume BIGINT,
                    instrument VARCHAR,
                    tick_type VARCHAR
                )
            """.format(
                table_name
            )  # Use format for duckdb compatibility if f-string causes issues
            self.conn.execute(fallback_schema_sql)
            self.logger.info(
                f"Fallback: Ensured table '{table_name}' with predefined schema."
            )

        def insert_ticks(self, table_name: str, ticks_input: list | pd.DataFrame):
            if not self.conn:
                return  # noqa: E701

            if isinstance(ticks_input, pd.DataFrame):
                ticks_df = ticks_input
            elif isinstance(ticks_input, list) and all(
                isinstance(t, dict) for t in ticks_input
            ):
                ticks_df = pd.DataFrame(ticks_input)
            elif isinstance(ticks_input, list) and all(
                hasattr(t, "model_dump") for t in ticks_input
            ):  # Pydantic-like objects
                ticks_df = pd.DataFrame([t.model_dump() for t in ticks_input])
            else:
                self.logger.error("Fallback: Unsupported type for insert_ticks.")
                return

            if not ticks_df.empty:
                # Ensure column types are compatible with DuckDB table
                # Convert timestamp to datetime if it's not (e.g. from Pydantic's datetime)
                if "timestamp" in ticks_df.columns:
                    ticks_df["timestamp"] = pd.to_datetime(ticks_df["timestamp"])

                self.conn.register("ticks_df_temp_view", ticks_df)
                self.conn.execute(
                    f"INSERT INTO {table_name} SELECT * FROM ticks_df_temp_view"
                )
                self.conn.unregister("ticks_df_temp_view")
                self.logger.info(
                    f"Fallback: Inserted {len(ticks_df)} records into '{table_name}'."
                )
            else:
                self.logger.info("Fallback: No data to insert.")


class LoadRawDataFromWarehouseStep(BaseETLStep):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def execute(self, data: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame:
        ticker = kwargs.get("ticker")

        # --- [臨時修復] ---
        # 如果沒有提供 ticker，我們假設這是一個通用管線，並載入一個預設的、廣泛的數據集。
        # 這是為了讓 P1, P2, P3 能夠在沒有特定 ticker 的情況下運行。
        if not ticker:
            self.logger.info("未提供 ticker，載入通用數據集...")
            # 模擬一個包含多個 tickers 的通用數據集
            dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=100))
            df1 = pd.DataFrame({
                "date": dates, "symbol": "SPY",
                "open": [300 + i for i in range(100)], "high": [305 + i for i in range(100)],
                "low": [295 + i for i in range(100)], "close": [302 + i for i in range(100)],
                "volume": [10000000 + i * 10000 for i in range(100)],
            })
            df2 = pd.DataFrame({
                "date": dates, "symbol": "QQQ",
                "open": [200 + i for i in range(100)], "high": [205 + i for i in range(100)],
                "low": [195 + i for i in range(100)], "close": [202 + i for i in range(100)],
                "volume": [15000000 + i * 12000 for i in range(100)],
            })
            return pd.concat([df1, df2], ignore_index=True)

        self.logger.info(f"正在為資產 {ticker} 載入原始數據...")
        # 模擬返回一個包含虛擬數據的 DataFrame
        date_range = pd.to_datetime(
            pd.date_range(start="2022-01-01", periods=300, freq="D")
        )
        open_prices = np.random.uniform(90, 110, size=300)
        df = pd.DataFrame({
            "open": open_prices,
            "high": open_prices + np.random.uniform(0, 5, size=300),
            "low": open_prices - np.random.uniform(0, 5, size=300),
            "close": open_prices + np.random.uniform(-2, 2, size=300),
            "volume": np.random.randint(100000, 500000, size=300),
        }, index=date_range)
        df.columns = [col.lower() for col in df.columns]
        return df

class TaifexTickLoaderStep(BaseETLStep):
    def __init__(
        self,
        db_path: str = "market_data_loader_step.duckdb",
        table_name: str = "bronze_taifex_ticks_loader_step",
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db_path = db_path
        self.table_name = table_name
        self.logger.info(
            f"TaifexTickLoaderStep initialized. DB: '{self.db_path}', Table: '{self.table_name}'. Imported app deps: {IMPORTED_APP_DEPS}"
        )

    def execute(self, data: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame | None:
        self.logger.info(
            f"Executing TaifexTickLoaderStep. Output to table '{self.table_name}' in db '{self.db_path}'."
        )

        simulated_ticks_data_dicts = [
            {
                "timestamp": datetime.datetime(2023, 10, 1, 9, 0, 0, 100000),
                "price": 16500.0,
                "volume": 2,
                "instrument": "TXF202310",
                "tick_type": "Trade",
            },
            {
                "timestamp": datetime.datetime(2023, 10, 1, 9, 0, 1, 200000),
                "price": 16501.0,
                "volume": 3,
                "instrument": "TXF202310",
                "tick_type": "Trade",
            },
            {
                "timestamp": datetime.datetime(2023, 10, 1, 9, 0, 2, 300000),
                "price": 16500.5,
                "volume": 1,
                "instrument": "TXF202310",
                "tick_type": "Trade",
            },
        ]

        ticks_df = pd.DataFrame(simulated_ticks_data_dicts)
        ticks_df["timestamp"] = pd.to_datetime(ticks_df["timestamp"])
        # Ensure 'volume' is integer as per fallback schema if it was float from DataFrame creation
        ticks_df["volume"] = ticks_df["volume"].astype("int64")

        self.logger.info(
            f"Successfully simulated fetching {len(ticks_df)} Tick records."
        )

        try:
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
                self.logger.info(f"Created directory for database: {db_dir}")

            with DatabaseManager(db_path=self.db_path) as db_manager:
                if IMPORTED_APP_DEPS:
                    # Using original DatabaseManager, expects Pydantic model for schema and list of Pydantic objects
                    db_manager.create_table_if_not_exists(self.table_name, TaifexTick)
                    simulated_pydantic_ticks = [
                        TaifexTick.model_validate(row)
                        for row in simulated_ticks_data_dicts
                    ]
                    db_manager.insert_ticks(self.table_name, simulated_pydantic_ticks)
                    self.logger.info(
                        f"Used original DatabaseManager. Wrote {len(simulated_pydantic_ticks)} records."
                    )
                else:
                    # Using fallback DatabaseManager, expects table name and DataFrame (or list of dicts)
                    db_manager.create_table_if_not_exists(
                        self.table_name, None
                    )  # Schema ignored in fallback
                    db_manager.insert_ticks(
                        self.table_name, ticks_df.to_dict("records")
                    )  # Pass list of dicts to fallback
                    self.logger.info(
                        f"Used fallback DatabaseManager. Wrote {len(ticks_df)} records."
                    )

        except Exception as e:
            self.logger.error(
                f"Error during database operation in TaifexTickLoaderStep: {e}",
                exc_info=True,
            )
            # Decide if this error should halt the pipeline or just log and return the DataFrame
            # For now, log and return DataFrame to allow pipeline to continue if DB write is not critical for next step

        self.logger.info("TaifexTickLoaderStep execution finished.")
        return ticks_df


class LoadStockDataStep(BaseStep):
    """
    一個 Pipeline 步驟，用於從 yfinance 加載股票數據。
    """

    def __init__(self, symbols: List[str], client_factory: ClientFactory):
        """
        初始化步驟。

        :param symbols: 要加載的股票代號列表。
        :param client_factory: 客戶端工廠。
        """
        self.symbols = symbols
        self.yfinance_client = client_factory.get_client('yfinance')
        self.logger = logging.getLogger(self.__class__.__name__)

    async def run(self, data: Any = None, context: Dict[str, Any] = None) -> pd.DataFrame:
        """
        執行數據加載。

        :param data: 上一步的輸出 (在此被忽略)。
        :param context: Pipeline 的共享上下文。
        :return: 包含所有股票數據的單一 DataFrame。
        """
        self.logger.info(f"開始從 yfinance 加載股票數據，目標: {self.symbols}")
        all_data = []

        for symbol in self.symbols:
            try:
                self.logger.debug(f"正在為 {symbol} 獲取數據...")
                stock_data = await self.yfinance_client.fetch_data(symbol, period="1y") # 載入一年數據作為範例
                if stock_data.empty:
                    self.logger.warning(f"無法為 {symbol} 獲取數據，可能該代號無效或無數據。")
                    continue

                stock_data['symbol'] = symbol
                all_data.append(stock_data)
                self.logger.debug(f"成功加載 {symbol} 的 {len(stock_data)} 筆數據。")

            except Exception as e:
                self.logger.error(f"加載 {symbol} 數據時出錯: {e}", exc_info=True)

        if not all_data:
            self.logger.error("未能加載任何股票數據。")
            # 返回一個空的 DataFrame，下游步驟應能處理這種情況
            return pd.DataFrame()

        # 將所有數據合併成一個大的 DataFrame
        combined_df = pd.concat(all_data)
        self.logger.info(f"成功加載並合併了 {len(all_data)} 支股票的數據。")

        # --- [修復] ---
        # 將所有列名標準化為小寫，以避免與數據庫模式的大小寫不匹配問題
        combined_df.columns = [col.lower() for col in combined_df.columns]

        # 重置索引，因為 yfinance 返回的數據中，日期是索引
        combined_df = combined_df.reset_index()

        return combined_df


class LoadCryptoDataStep(BaseStep):
    """
    一個 Pipeline 步驟，用於從 yfinance 加載加密貨幣數據。
    """

    def __init__(self, symbols: List[str], client_factory: ClientFactory):
        """
        初始化步驟。

        :param symbols: 要加載的加密貨幣代號列表 (例如: ['BTC-USD', 'ETH-USD'])。
        :param client_factory: 客戶端工廠。
        """
        self.symbols = symbols
        self.yfinance_client = client_factory.get_client('yfinance')
        self.logger = logging.getLogger(self.__class__.__name__)

    async def run(self, data: Any = None, context: Dict[str, Any] = None) -> pd.DataFrame:
        """
        執行數據加載。

        :param data: 上一步的輸出 (在此被忽略)。
        :param context: Pipeline 的共享上下文。
        :return: 包含所有加密貨幣數據的單一 DataFrame。
        """
        self.logger.info(f"開始從 yfinance 加載加密貨幣數據，目標: {self.symbols}")
        all_data = []

        for symbol in self.symbols:
            try:
                self.logger.debug(f"正在為 {symbol} 獲取數據...")
                # 為加密貨幣獲取更長的歷史數據以進行相關性計算
                crypto_data = await self.yfinance_client.fetch_data(symbol, period="2y")
                if crypto_data.empty:
                    self.logger.warning(f"無法為 {symbol} 獲取數據，可能該代號無效或無數據。")
                    continue

                crypto_data['symbol'] = symbol
                all_data.append(crypto_data)
                self.logger.debug(f"成功加載 {symbol} 的 {len(crypto_data)} 筆數據。")

            except Exception as e:
                self.logger.error(f"加載 {symbol} 數據時出錯: {e}", exc_info=True)

        if not all_data:
            self.logger.error("未能加載任何加密貨幣數據。")
            return pd.DataFrame()

        combined_df = pd.concat(all_data)
        self.logger.info(f"成功加載並合併了 {len(all_data)} 種加密貨幣的數據。")

        # --- [修復] ---
        # 將所有列名標準化為小寫，以避免與數據庫模式的大小寫不匹配問題
        combined_df.columns = [col.lower() for col in combined_df.columns]

        # 重置索引，因為 yfinance 返回的數據中，日期是索引
        combined_df = combined_df.reset_index()

        return combined_df


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    test_db_path = "temp_test_tick_loader_step.duckdb"
    # Clean up before test
    if os.path.exists(test_db_path):
        os.remove(test_db_path)  # noqa: E701
    if os.path.exists(f"{test_db_path}.wal"):
        os.remove(f"{test_db_path}.wal")  # noqa: E701

    loader_step = TaifexTickLoaderStep(db_path=test_db_path, table_name="test_ticks")
    loaded_data = loader_step.execute()

    if loaded_data is not None:
        print("\n--- Loaded Data (DataFrame) ---")
        print(loaded_data)
        print(f"\nData types:\n{loaded_data.dtypes}")

        if os.path.exists(test_db_path):
            print(
                f"\n--- Verifying data in database '{test_db_path}', table '{loader_step.table_name}' ---"
            )
            try:
                with duckdb.connect(test_db_path) as conn:
                    count = conn.execute(
                        f"SELECT COUNT(*) FROM {loader_step.table_name}"
                    ).fetchone()[0]
                    print(f"Number of records in table: {count}")
                    assert count == len(
                        loaded_data
                    ), "Mismatch in DB count and DataFrame length"
                    if count > 0:
                        sample_records = conn.execute(
                            f"SELECT * FROM {loader_step.table_name} LIMIT 3"
                        ).df()
                        print("Sample records from DB:")
                        print(sample_records)
            except Exception as e:
                print(f"Error verifying data in DB: {e}")
    else:
        print("Loader step did not return data.")

    # Clean up after test
    # if os.path.exists(test_db_path): os.remove(test_db_path)
    # if os.path.exists(f"{test_db_path}.wal"): os.remove(f"{test_db_path}.wal")
    # print(f"\nCleaned up test database: {test_db_path}")
