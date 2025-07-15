import sqlite3

import pandas as pd
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse

from prometheus.core.context import AppContext


def run_dashboard_service(ctx: AppContext, host: str, port: int):
    app = FastAPI()

    @app.get("/api/results")
    def get_results():
        try:
            conn = sqlite3.connect("output/results.sqlite")
            df = pd.read_sql_query("SELECT * FROM backtest_results", conn)
            conn.close()
            return df.to_dict(orient="records")
        except sqlite3.OperationalError:
            return []

    @app.get("/api/evolution_logs")
    def get_evolution_logs():
        """提供所有演化日誌的 API。"""
        try:
            # This part still uses DuckDB as it's a separate concern.
            import duckdb

            conn = duckdb.connect("prometheus_fire.duckdb", read_only=True)
            logs = conn.execute(
                "SELECT * FROM evolution_logs ORDER BY generation"
            ).fetchdf()
            conn.close()
            return logs.to_dict(orient="records")
        except Exception:
            return []

    @app.get("/")
    def read_root():
        return FileResponse("src/apps/dashboard/dashboard.html")

    ctx.log_manager.log("INFO", f"正在於 http://{host}:{port} 啟動儀表板...")
    uvicorn.run(app, host=host, port=port)
