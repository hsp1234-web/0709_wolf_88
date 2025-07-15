from pathlib import Path

import duckdb
import pandas as pd


class DataWarehouse:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.db_path))

    def execute_query(self, query: str, params=None):
        return self.conn.execute(query, params)

    def get_results(self, query: str, params=None) -> pd.DataFrame:
        return self.conn.execute(query, params).fetchdf()

    def table_exists(self, table_name: str) -> bool:
        try:
            self.conn.execute(f"DESCRIBE {table_name}")
            return True
        except duckdb.CatalogException:
            return False

    def close(self):
        self.conn.close()


class RawDataWarehouse(DataWarehouse):
    def __init__(self, db_path: str):
        super().__init__(db_path)
        self._create_log_table()

    def _create_log_table(self):
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS raw_import_log (
                file_path VARCHAR PRIMARY KEY,
                content_blob BLOB,
                format_fingerprint VARCHAR
            );
        """)

    def is_file_processed(self, file_path: str) -> bool:
        result = self.execute_query(
            "SELECT COUNT(*) FROM raw_import_log WHERE file_path = ?", (file_path,)
        ).fetchone()
        return result[0] > 0 if result else False

    def log_processed_file(self, file_path: str, content: bytes, fingerprint: str):
        self.execute_query(
            "INSERT INTO raw_import_log VALUES (?, ?, ?)",
            (file_path, content, fingerprint),
        )


class AnalyticsDataWarehouse(DataWarehouse):
    def create_daily_futures_table(self):
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS daily_futures (
                "交易日期" VARCHAR,
                "契約代碼" VARCHAR,
                "到期月份(週別)" VARCHAR,
                "開盤價" VARCHAR,
                "最高價" VARCHAR,
                "最低價" VARCHAR,
                "收盤價" VARCHAR,
                "成交量" VARCHAR
            );
        """)

    def insert_daily_futures(self, df: pd.DataFrame):
        self.conn.register('df_to_load', df)
        self.execute_query(
            "INSERT INTO daily_futures SELECT * FROM df_to_load"
        )
