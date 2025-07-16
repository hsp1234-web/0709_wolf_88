import sys
from pathlib import Path
import subprocess
import os

def inject_poetry_env():
    """
    自動檢測並注入 Poetry 虛擬環境路徑。
    """
    if "VIRTUAL_ENV" in os.environ and "poetry" in os.environ["VIRTUAL_ENV"]:
        return

    try:
        result = subprocess.run(
            ["poetry", "env", "info", "-p"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and not result.stdout.strip():
             subprocess.run(["poetry", "shell"], check=True, text=True, input="exit\n")
             result = subprocess.run(
                 ["poetry", "env", "info", "-p"],
                 capture_output=True,
                 text=True,
                 check=True,
             )

        venv_path = Path(result.stdout.strip())

        site_packages = next(venv_path.glob("lib/python*/site-packages"))

        sys.path.insert(0, str(site_packages))

        project_root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(project_root / "src"))

    except (subprocess.CalledProcessError, FileNotFoundError, StopIteration) as e:
        print(f"--- [ERROR] Failed to inject Poetry environment: {e} ---")
        print("--- [ERROR] Please ensure you are in the project root and have run 'poetry install'. ---")
        sys.exit(1)
