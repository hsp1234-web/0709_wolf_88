import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import duckdb
import pandas as pd
from src.core.context import AppContext

DB_PATH = "prometheus_fire.duckdb"
TABLE_NAME = "backtest_results"

# 將 uvicorn.run 的啟動邏輯封裝成一個函數
def run_dashboard_service(ctx: AppContext, host: str, port: int):
    # FastAPI 應用實例現在在函數內部創建
    app = FastAPI()

    @app.get("/api/results")
    def get_results():
        try:
            with duckdb.connect(database=DB_PATH, read_only=True) as con:
                df = con.execute(f"SELECT * FROM {TABLE_NAME} ORDER BY id DESC LIMIT 20").fetchdf()
            return df.to_dict(orient="records")
        except duckdb.CatalogException:
            return {"error": "No results table found. Please run a backtest first."}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/", response_class=HTMLResponse)
    def read_root():
        with open("src/apps/dashboard/dashboard.html", "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)

    ctx.log_manager.log("INFO", f"正在於 http://{host}:{port} 啟動儀表板...")
    uvicorn.run(app, host=host, port=port)
