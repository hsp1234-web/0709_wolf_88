import pandas as pd
from fredapi import Fred
from core.config import get_api_key
from core.db.db_manager import DBManager

def run():
    """
    從 FRED API 獲取宏觀經濟數據並存儲到數據庫中。
    """
    api_key = get_api_key("fred")
    if not api_key:
        raise ValueError("FRED API key not found in config.yml")

    fred = Fred(api_key=api_key)

    # 定義要獲取的宏觀經濟指標
    series_to_fetch = {
        "GDP": "GDP",               # Gross Domestic Product
        "UNRATE": "UNRATE",         # Unemployment Rate
        "CPIAUCSL": "CPI",          # Consumer Price Index
        "DFF": "Federal Funds Rate" # Federal Funds Effective Rate
    }

    all_series_data = []
    for series_id, name in series_to_fetch.items():
        try:
            data = fred.get_series(series_id)
            data = data.reset_index()
            data.columns = ['date', 'value']
            data['series'] = name
            all_series_data.append(data)
        except Exception as e:
            print(f"Failed to fetch {name} ({series_id}): {e}")

    if not all_series_data:
        print("No data fetched from FRED.")
        return

    # 合併所有數據
    df = pd.concat(all_series_data, ignore_index=True)
    df['date'] = pd.to_datetime(df['date'])

    # 存儲到數據庫
    db_manager = DBManager()
    db_manager.write_data("macro_daily_fred", df)
    print(f"Successfully fetched and stored {df.shape[0]} records for {len(series_to_fetch)} series in 'macro_daily_fred'.")

if __name__ == "__main__":
    run()
