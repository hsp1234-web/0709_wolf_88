import pandas as pd
from pathlib import Path

def load_ohlcv_data(file_path: Path) -> pd.DataFrame:
    """
    從指定的 CSV 檔案加載 OHLCV 數據。
    """
    if not file_path.exists():
        raise FileNotFoundError(f"數據檔案不存在: {file_path}")

    data = pd.read_csv(file_path)

    # 假設 CSV 有 'timestamp', 'open', 'high', 'low', 'close', 'volume' 這幾列
    # 並將 'timestamp' 設置為索引
    if 'timestamp' in data.columns:
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        data.set_index('timestamp', inplace=True)

    return data
