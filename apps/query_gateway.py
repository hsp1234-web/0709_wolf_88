from fastapi import FastAPI
from fastapi.responses import FileResponse
import duckdb

app = FastAPI()
DB_PATH = "prometheus_fire.duckdb"
TABLE_NAME = "backtest_results"

@app.get("/api/results")
def get_results():
    """提供所有回測結果的 API。"""
    conn = duckdb.connect(DB_PATH, read_only=True)
    try:
        # 檢查資料表是否存在
        tables = conn.execute("SHOW TABLES").fetchall()
        if (TABLE_NAME,) not in tables:
            return [] # 如果不存在，返回空列表

        results = conn.execute(f"SELECT * FROM {TABLE_NAME}").fetchdf()
        return results.to_dict(orient="records")
    finally:
        conn.close()

@app.get("/")
def read_root():
    """提供儀表板 HTML 檔案。"""
    return FileResponse('apps/dashboard/dashboard.html')
