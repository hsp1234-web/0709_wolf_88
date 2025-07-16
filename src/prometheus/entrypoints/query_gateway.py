import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path

# --- 檔案路徑 ---
REPORTS_DIR = Path("data/reports")
ANALYSIS_REPORT_PATH = REPORTS_DIR / "analysis_report.md"
EQUITY_CURVE_PATH = REPORTS_DIR / "equity_curve.png"

app = FastAPI(
    title="普羅米修斯之火 - 神諭儀表板 API",
    description="提供由 AI 分析師生成的最新策略洞察報告。",
    version="1.0.0",
)

@app.get("/api/v1/reports/latest",
         summary="獲取最新分析報告",
         response_description="包含 Markdown 報告內容的 JSON 物件")
def get_latest_report():
    """
    讀取並回傳最新的 Markdown 分析報告。
    """
    if not ANALYSIS_REPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="分析報告不存在。請先執行 'analyze' 指令。")

    try:
        with open(ANALYSIS_REPORT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return JSONResponse(content={"report_content": content})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"讀取報告時發生錯誤: {e}")

@app.get("/api/v1/reports/equity_curve.png",
         summary="獲取權益曲線圖",
         response_description="權益曲線的 PNG 圖片檔案")
def get_equity_curve():
    """
    直接提供權益曲線的圖片檔案。
    """
    if not EQUITY_CURVE_PATH.exists():
        raise HTTPException(status_code=404, detail="權益曲線圖不存在。請先執行 'analyze' 指令。")

    return FileResponse(EQUITY_CURVE_PATH, media_type="image/png")

@app.get("/")
def serve_report_at_root():
    """
    直接在根目錄提供最新的分析報告 JSON。
    """
    return get_latest_report()

def run_dashboard_service(ctx, host: str, port: int):
    """啟動 FastAPI 儀表板服務。"""
    # ctx 參數保留以符合現有 cli 結構，但在此處未使用
    print(f"INFO:     正在於 http://{host}:{port} 啟動神諭儀表板後端...")
    uvicorn.run(app, host=host, port=port, log_level="info")
