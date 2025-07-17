#!/usr/bin/env python

import sys
from pathlib import Path

# 將 src 目錄添加到 PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from prometheus.cli.main import app

if __name__ == "__main__":
    app()
