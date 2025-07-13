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
    results = conn.execute(f"SELECT * FROM {TABLE_NAME}").fetchdf()
    conn.close()
    return results.to_dict(orient="records")

@app.get("/")
def read_root():
    """提供儀表板 HTML 檔案。"""
    return FileResponse('apps/dashboard/dashboard.html')
