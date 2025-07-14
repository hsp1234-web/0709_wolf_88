import uvicorn
from fastapi import FastAPI
import duckdb
from fastapi.responses import FileResponse
from src.core.context import AppContext

def run_dashboard_service(ctx: AppContext, host: str, port: int):
    app = FastAPI()

    @app.get("/api/results")
    def get_results():
        conn = duckdb.connect("prometheus_fire.duckdb", read_only=True)
        results = conn.execute("SELECT * FROM backtest_results").fetchdf()
        conn.close()
        return results.to_dict(orient="records")

    @app.get("/")
    def read_root():
        return FileResponse('src/apps/dashboard/dashboard.html')

    ctx.log_manager.log("INFO", f"正在於 http://{host}:{port} 啟動儀表板...")
    uvicorn.run(app, host=host, port=port)
