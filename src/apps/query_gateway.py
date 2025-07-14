import uvicorn
from fastapi import FastAPI
import duckdb
from fastapi.responses import FileResponse
from src.core.context import AppContext

def run_dashboard_service(ctx: AppContext, host: str, port: int):
    app = FastAPI()

    @app.get("/api/results")
    def get_results():
        try:
            conn = duckdb.connect("prometheus_fire.duckdb", read_only=True)
            results = conn.execute("SELECT * FROM backtest_results").fetchdf()
            conn.close()
            return results.to_dict(orient="records")
        except duckdb.Error:
            return []

    # === 新增 API 端點 ===
    @app.get("/api/evolution_logs")
    def get_evolution_logs():
        """提供所有演化日誌的 API。"""
        try:
            conn = duckdb.connect("prometheus_fire.duckdb", read_only=True)
            logs = conn.execute("SELECT * FROM evolution_logs ORDER BY generation").fetchdf()
            conn.close()
            return logs.to_dict(orient="records")
        except duckdb.Error:
            return [] # 如果資料表不存在，返回空列表

    @app.get("/")
    def read_root():
        return FileResponse('src/apps/dashboard/dashboard.html')

    ctx.log_manager.log("INFO", f"正在於 http://{host}:{port} 啟動儀表板...")
    uvicorn.run(app, host=host, port=port)
