#!/usr/bin/env python

import sys
from pathlib import Path

# 將 src 目錄添加到 PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from inject_env import inject_poetry_env
inject_poetry_env()

from prometheus.cli.main import app

if __name__ == "__main__":
    app()
