import typer
from pathlib import Path
import sys

# --- 標準路徑自我校正樣板 ---
try:
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from core.logger import LogManager
    from apps.tools.show_results import show_results
except ImportError as e:
    print(f"錯誤：導入應用模組失敗。錯誤訊息：{e}", file=sys.stderr)
    sys.exit(1)
# --- 樣板結束 ---

app = typer.Typer()

@app.command()
def show():
    output_dir = project_root / "output"
    log_db_path = output_dir / "logs" / "session.sqlite"
    archive_dir = output_dir / "logs" / "archive"
    log_manager = LogManager(db_path=log_db_path, archive_dir=archive_dir)
    show_results(log_manager)

if __name__ == "__main__":
    app()
