import pandas as pd
from pathlib import Path
from typing import Tuple

def load_ohlcv_data(file_path: Path, split_ratio: float = 0.7) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    從 CSV 檔案加載 OHLCV 數據，並將其分割為樣本內和樣本外數據集。

    :param file_path: CSV 檔案的路徑。
    :param split_ratio: 樣本內數據所佔的比例 (例如 0.7 代表 70%)。
    :return: 一個包含 (in_sample_df, out_of_sample_df) 的元組。
    """
    if not file_path.exists():
        raise FileNotFoundError(f"數據檔案不存在: {file_path}")

    # 根據作戰手冊，索引應為 'Date' 且欄位名稱應為小寫
    df = pd.read_csv(file_path, index_col='Date', parse_dates=True)
    df.columns = [col.lower() for col in df.columns]

    # 根據比例計算分割點
    split_point = int(len(df) * split_ratio)

    in_sample_df = df.iloc[:split_point]
    out_of_sample_df = df.iloc[split_point:]

    print(f"[DataLoader] 數據已分割：樣本內 {len(in_sample_df)} 筆, 樣本外 {len(out_of_sample_df)} 筆。")

    return in_sample_df, out_of_sample_df
