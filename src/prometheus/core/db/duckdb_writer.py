import duckdb
import pandas as pd

class DuckDBWriter:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS recon_results (
                category VARCHAR,
                ticker VARCHAR,
                interval VARCHAR,
                label VARCHAR,
                status VARCHAR,
                count INTEGER,
                start_date VARCHAR,
                end_date VARCHAR
            )
        """)

    def write(self, data):
        df = pd.DataFrame([data])
        self.conn.append('recon_results', df)

    def close(self):
        self.conn.close()
