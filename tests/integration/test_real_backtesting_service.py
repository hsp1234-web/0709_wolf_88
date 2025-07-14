# 檔案: tests/integration/test_real_backtesting_service.py
import pytest
import pandas as pd
from unittest.mock import MagicMock

from src.core.services.backtesting_service import BacktestingService

@pytest.fixture
def mock_dependencies(app_context):
    """提供一個帶有模擬依賴的 BacktestingService 實例。"""
    # 從 app_context 獲取真實的 saver 和 logger
    results_saver = app_context.results_saver
    log_manager = app_context.log_manager

    # 創建服務實例
    service = BacktestingService(results_saver, log_manager)

    # === 核心戰術：模擬 (Mock) YFinanceClient ===
    # 創建一個假的 DataFrame 作為模擬數據
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=100))
    price_data = [100 + i + (5 * (i % 10)) for i in range(100)] # 模擬一些波動
    mock_price_df = pd.Series(price_data, index=dates, name="Close")

    # 用 MagicMock 替換掉真實的 yf_client
    service.yf_client = MagicMock()
    # 讓 get_daily_data 方法永遠返回我們的假數據
    service.yf_client.get_daily_data.return_value = mock_price_df

    return service, mock_price_df

def test_backtesting_service_with_real_logic(mock_dependencies):
    """
    驗證 BacktestingService 在使用 vectorbt 核心邏輯時，
    能否在模擬數據上計算出可預期的夏普比率。
    """
    service, _ = mock_dependencies

    # 1. 定義一個已知策略
    # 在我們的模擬數據上，(5, 20) 是一個能產生正向夏普比率的策略
    individual = (5, 20)
    backtest_id = "test_real_logic_001"

    # 2. 執行回測
    fitness = service.run_backtest(individual, backtest_id)

    # 3. 驗證結果
    # 我們預期夏普比率是一個正數浮點數。
    # 這裡不檢查精確值，因為它依賴於模擬數據的細微變化，
    # 但我們能確定它應該是一個有效的、大於零的數值。
    assert isinstance(fitness, float), "適應度應為浮點數"
    assert fitness > 0, f"對於一個有效策略，夏普比率應為正數，但得到 {fitness}"

    # 驗證無效策略
    invalid_individual = (20, 5)
    invalid_fitness = service.run_backtest(invalid_individual, "test_invalid_001")
    assert invalid_fitness == -1.0, "對於無效策略，適應度應為 -1.0"
