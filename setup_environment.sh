#!/bin/bash

# --- Phase 1: Create requirements.txt inside the sandbox using a Here Document ---
echo "--- Generating requirements.txt within the execution environment ---"
cat <<-EOF > requirements.txt
numpy==1.26.4
pandas==2.2.2
pandas-ta==0.3.14b
yfinance
duckdb
requests
pytest-mock
# Add any other required packages here, one per line
EOF

echo "--- requirements.txt created successfully. Content: ---"
cat requirements.txt
echo "--------------------------------------------------------"

# --- Phase 2: Create virtual environment and install dependencies ---
echo "--- Creating Python virtual environment ---"
python3 -m venv .venv
source .venv/bin/activate

echo "--- Installing dependencies from the generated requirements.txt ---"
pip install -r requirements.txt

echo "--- Standard environment setup complete. ---"
