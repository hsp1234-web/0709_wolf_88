import duckdb
import json

DB_PATH = "prometheus_fire.duckdb"
TABLE_NAME = "backtest_results"

def save_result(result_data: dict):
    """將單筆計算結果儲存至 DuckDB。"""
    conn = duckdb.connect(DB_PATH)
    # 確保資料表存在
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            symbol VARCHAR,
            params VARCHAR,
            crossover_points INTEGER,
            last_price DOUBLE,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 插入數據
    conn.execute(
        f"INSERT INTO {TABLE_NAME} (symbol, params, crossover_points, last_price) VALUES (?, ?, ?, ?)",
        [
            result_data.get("symbol"),
            json.dumps(result_data.get("params", {})), # 將參數字典轉為 JSON 字串
            result_data.get("crossover_points"),
            result_data.get("last_price")
        ]
    )
    conn.close()
