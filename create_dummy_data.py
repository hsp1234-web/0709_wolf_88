from pathlib import Path

import numpy as np
import pandas as pd


def create_dummy_ohlcv_data():
    """
    建立一個用於測試的虛構 OHLCV CSV 檔案。
    """
    DATA_DIR = Path("data")
    DATA_DIR.mkdir(exist_ok=True)
    file_path = DATA_DIR / "ohlcv_data.csv"

    date_range = pd.to_datetime(
        pd.date_range(start="2022-01-01", periods=1000, freq="D")
    )

    open_prices = np.random.uniform(90, 110, size=1000)

    data = {
        "Date": date_range,
        "Open": open_prices,
        "High": open_prices + np.random.uniform(0, 5, size=1000),
        "Low": open_prices - np.random.uniform(0, 5, size=1000),
        "Close": open_prices + np.random.uniform(-2, 2, size=1000),
        "Volume": np.random.randint(100000, 500000, size=1000),
    }

    df = pd.DataFrame(data)

    df.to_csv(file_path, index=False)
    print(f"已成功建立虛構數據檔案於: {file_path}")


if __name__ == "__main__":
    create_dummy_ohlcv_data()
