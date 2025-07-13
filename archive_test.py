from pathlib import Path
from core.logger import LogManager

project_root = Path(__file__).resolve().parent
output_dir = project_root / "output"
log_db_path = output_dir / "logs" / "session.sqlite"
archive_dir = output_dir / "logs" / "archive"
final_archiver = LogManager(db_path=log_db_path, archive_dir=archive_dir)
final_archiver.archive_to_file()
