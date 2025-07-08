# tests/mock_data_utils.py
"""
此模組提供用於測試的模擬數據生成函數。
"""
import pandas as pd
import numpy as np # 導入 numpy
from datetime import datetime, timedelta

def generate_mock_ohlcv_data() -> dict[str, pd.DataFrame]:
    """
    生成模擬的 yfinance OHLCV DataFrame 數據。
    返回一個字典，鍵為股票代碼，值為對應的 DataFrame。
    """
    data = {}
    symbols = {
        "MOCK_AAPL": {"start_price": 150.0, "volatility": 0.02, "start_volume": 1000000},
        "MOCK_TSLA": {"start_price": 250.0, "volatility": 0.03, "start_volume": 1500000},
        "0050": {"start_price": 120.0, "volatility": 0.01, "start_volume": 500000} # 模擬 0050 (非 0050.TW)
    }

    base_date = datetime(2024, 1, 1)
    dates = [base_date + timedelta(days=i) for i in range(7)]

    for symbol, params in symbols.items():
        df_data = []
        current_price = params["start_price"]
        current_volume = params["start_volume"]
        for date in dates:
            open_price = current_price
            high_price = open_price * (1 + params["volatility"] * np.random.uniform(0, 1))
            low_price = open_price * (1 - params["volatility"] * np.random.uniform(0, 1))
            close_price = np.random.uniform(low_price, high_price)
            volume = int(current_volume * np.random.uniform(0.8, 1.2))

            df_data.append({
                "Date": pd.Timestamp(date), # yfinance Ticker.history() 返回的 Date 是索引
                "Open": open_price,
                "High": high_price,
                "Low": low_price,
                "Close": close_price,
                "Adj Close": close_price * 0.99, # 隨便給個 Adj Close
                "Volume": volume,
                # "symbol": symbol # yfinance Ticker().history() 不直接返回 symbol 欄位，是在 client.py 中添加的
            })
            current_price = close_price

        df = pd.DataFrame(df_data)
        df.set_index("Date", inplace=True) # 將 Date 設為索引，以匹配 yf.Ticker().history() 的行為
        data[symbol] = df
    return data

def generate_mock_taifex_ticks_data() -> pd.DataFrame:
    """
    生成模擬的台指期貨 Tick DataFrame 數據。
    """
    product_id = "MOCK_TXF"
    base_datetime = datetime(2024, 1, 1, 8, 45, 0)
    num_ticks_per_minute = 3
    minutes_to_generate = 5

    ticks_data = []
    current_price = 17000.0

    for i in range(minutes_to_generate):
        for j in range(num_ticks_per_minute):
            timestamp = base_datetime + timedelta(minutes=i, seconds=(j * (60 // num_ticks_per_minute)))
            price_change = np.random.uniform(-0.5, 0.5)
            current_price += price_change
            volume = np.random.randint(1, 11)
            ticks_data.append({
                "timestamp": pd.Timestamp(timestamp),
                "product_id": product_id,
                "price": round(current_price, 2),
                "volume": volume,
                "qty": volume # 根據分析，同時提供 volume 和 qty
            })

    return pd.DataFrame(ticks_data)

def generate_mock_treasury_yields_data() -> pd.DataFrame:
    """
    生成模擬的公債殖利率 DataFrame 數據。
    """
    yield_data = []
    terms = ["2 Yr", "10 Yr", "3 Mo"] # 匹配 FactorEngine 中 get_treasury_yields 的原始 term 格式
    base_date = datetime(2024, 1, 1)
    dates = [base_date + timedelta(days=i) for i in range(7)]

    base_yields = {"2 Yr": 0.04, "10 Yr": 0.035, "3 Mo": 0.05}

    for date in dates:
        for term in terms:
            yield_val = base_yields[term] + np.random.uniform(-0.001, 0.001)
            yield_data.append({
                "date": pd.Timestamp(date).tz_localize('UTC'), # FactorEngine 期望 UTC
                "term": term,
                "yield": round(yield_val, 4)
            })

    return pd.DataFrame(yield_data)

def generate_mock_taifex_pc_ratios_data() -> pd.DataFrame:
    """
    生成模擬的台指選擇權 P/C Ratio DataFrame 數據。
    """
    pc_data = []
    product_id = "TXO" # ReportGenerator 查找 TXO
    base_date = datetime(2024, 1, 1)
    dates = [base_date + timedelta(days=i) for i in range(7)]

    base_pc_volume = 0.9
    base_pc_oi = 0.95

    for date in dates:
        pc_volume = base_pc_volume + np.random.uniform(-0.05, 0.05)
        pc_oi = base_pc_oi + np.random.uniform(-0.05, 0.05)
        pc_data.append({
            "trading_date": pd.Timestamp(date).date(), # ReportGenerator 期望 date 物件
            "product_id": product_id,
            "pc_volume_ratio": round(pc_volume, 2),
            "pc_oi_ratio": round(pc_oi, 2)
        })

    return pd.DataFrame(pc_data)

def generate_mock_chimera_signals_data(stock_ids: list[str]) -> pd.DataFrame:
    """
    生成模擬的 Chimera Daily Signals DataFrame 數據。
    """
    signals_data = []
    base_date = datetime(2024, 1, 1)
    dates = [base_date + timedelta(days=i) for i in range(7)]

    possible_signals = [
        "價漲量增_法人買超", "價跌量增_法人賣超",
        "盤整量縮_法人中性", "價漲量平_籌碼未知"
    ]

    for stock_id in stock_ids:
        # ReportGenerator 在合併 chimera_df 時會篩選 stock_id，
        # 因此這裡的 stock_id 必須與 ohlcv 的 stock_id 匹配 (例如 '0050', 'MOCK_AAPL')
        actual_stock_id = stock_id # 這裡的 stock_id 應該是傳入的，例如 "0050" 或 "MOCK_AAPL"

        for date_dt in dates:
            # composite_signal 欄位
            composite_signal = np.random.choice(possible_signals)
            # 其他欄位 (price_volume_label, institutional_flow_label) 可以簡化或從 composite_signal 推斷
            # 為了簡單起見，我們只填充必要的欄位
            signals_data.append({
                "date": pd.Timestamp(date_dt).date(), # ReportGenerator 期望 date 物件
                "stock_id": actual_stock_id,
                "price_volume_label": composite_signal.split('_')[0] if '_' in composite_signal else "未知",
                "institutional_flow_label": composite_signal.split('_')[1] if '_' in composite_signal else "未知",
                "composite_signal": composite_signal
            })

    return pd.DataFrame(signals_data)

if __name__ == '__main__':
    # 測試生成函數
    mock_ohlcv = generate_mock_ohlcv_data()
    print("--- Mock OHLCV Data (MOCK_AAPL) ---")
    print(mock_ohlcv["MOCK_AAPL"].head())

    mock_ticks = generate_mock_taifex_ticks_data()
    print("\n--- Mock Taifex Ticks Data ---")
    print(mock_ticks.head())

    mock_yields = generate_mock_treasury_yields_data()
    print("\n--- Mock Treasury Yields Data ---")
    print(mock_yields.head())

    mock_pc_ratios = generate_mock_taifex_pc_ratios_data()
    print("\n--- Mock Taifex P/C Ratios Data ---")
    print(mock_pc_ratios.head())

    mock_chimera_signals = generate_mock_chimera_signals_data(stock_ids=["MOCK_AAPL", "0050"])
    print("\n--- Mock Chimera Signals Data ---")
    print(mock_chimera_signals.head())
