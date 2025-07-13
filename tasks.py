import typer
from pipelines import p1_yfinance_etl

app = typer.Typer()

@app.command(name="run-yfinance-etl")
def run_yfinance_etl_task():
    """
    【數據管線】執行 P1: 從 Yahoo Finance 獲取市場日線數據。
    """
    target_tickers = ["SPY", "QQQ", "AAPL", "GOOG", "MSFT"]
    p1_yfinance_etl.run_pipeline(target_tickers)

@app.command()
def test():
    """
    執行所有單元測試。
    """
    import pytest
    pytest.main(["-v", "tests/"])

if __name__ == "__main__":
    app()
